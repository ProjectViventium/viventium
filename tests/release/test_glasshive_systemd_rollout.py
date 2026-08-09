from __future__ import annotations

import ast
import importlib.util
import io
import json
import shlex
import sqlite3
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deploy" / "glasshive" / "systemd" / "glasshive_rollout.py"
SPEC = importlib.util.spec_from_file_location("glasshive_rollout", MODULE_PATH)
assert SPEC and SPEC.loader
rollout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rollout)

ROOTLESS_MODULE_PATH = (
    ROOT / "deploy" / "glasshive" / "systemd" / "glasshive_rootless_docker_probe.py"
)
ROOTLESS_SPEC = importlib.util.spec_from_file_location("glasshive_rootless_docker_probe", ROOTLESS_MODULE_PATH)
assert ROOTLESS_SPEC and ROOTLESS_SPEC.loader
rootless_probe = importlib.util.module_from_spec(ROOTLESS_SPEC)
ROOTLESS_SPEC.loader.exec_module(rootless_probe)

UI_PROBE_MODULE_PATH = (
    ROOT / "deploy" / "glasshive" / "systemd" / "glasshive_ui_readiness_probe.py"
)
UI_PROBE_SPEC = importlib.util.spec_from_file_location("glasshive_ui_readiness_probe", UI_PROBE_MODULE_PATH)
assert UI_PROBE_SPEC and UI_PROBE_SPEC.loader
ui_probe = importlib.util.module_from_spec(UI_PROBE_SPEC)
UI_PROBE_SPEC.loader.exec_module(ui_probe)


def _database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE owners (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            owner_id TEXT NOT NULL
        );
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            owner_ref TEXT REFERENCES owners(id)
        );
        INSERT INTO owners VALUES ('owner-row', 'tenant-synthetic', 'user-synthetic');
        INSERT INTO workspaces VALUES ('workspace-row', 'tenant-synthetic', 'user-synthetic', 'owner-row');
        """
    )
    conn.commit()
    conn.close()


def _invariants() -> list[dict[str, object]]:
    return [
        {"table": "owners", "identity_columns": ["tenant_id", "owner_id"]},
        {"table": "workspaces", "identity_columns": ["tenant_id", "owner_id"]},
    ]


def test_sqlite_backup_includes_committed_wal_and_redacts_identity_samples(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite3"
    _database(source)
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"

    receipt = rollout.backup_and_restore_test(
        source=source,
        backup=backup,
        restore_test=restored,
        invariants=_invariants(),
    )

    assert receipt["quick_check"] == "ok"
    assert receipt["integrity_check"] == "ok"
    assert receipt["foreign_key_violations"] == 0
    assert receipt["tables"]["workspaces"]["row_count"] == 1
    rendered = json.dumps(receipt, sort_keys=True)
    assert "tenant-synthetic" not in rendered
    assert "user-synthetic" not in rendered
    with sqlite3.connect(restored) as conn:
        assert conn.execute("SELECT count(*) FROM workspaces").fetchone()[0] == 1


def test_migration_comparison_fails_on_existing_row_or_owner_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.sqlite3"
    after = tmp_path / "after.sqlite3"
    _database(before)
    _database(after)
    with sqlite3.connect(after) as conn:
        conn.execute("DELETE FROM workspaces")
        conn.commit()

    before_receipt = rollout.inspect_database(before, _invariants())
    after_receipt = rollout.inspect_database(after, _invariants())

    with pytest.raises(rollout.RolloutError, match="invariant drift"):
        rollout.compare_migration_invariants(before_receipt, after_receipt)


def test_database_inspection_fails_on_foreign_key_violation(tmp_path: Path) -> None:
    database = tmp_path / "bad.sqlite3"
    _database(database)
    with sqlite3.connect(database) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO workspaces VALUES ('orphan', 'tenant-synthetic', 'user-synthetic', 'missing')"
        )
        conn.commit()

    with pytest.raises(rollout.RolloutError, match="foreign key"):
        rollout.inspect_database(database, _invariants())


def test_release_manifest_detects_mutation_and_unlisted_files(tmp_path: Path) -> None:
    release = tmp_path / "release"
    (release / "viventium_v0_4" / "GlassHive").mkdir(parents=True)
    tracked = release / "viventium_v0_4" / "GlassHive" / "artifact.txt"
    tracked.write_text("candidate\n", encoding="utf-8")
    rollout.write_release_manifest(
        release,
        release_id="release-20260806",
        parent_revision="a" * 40,
        glasshive_revision="b" * 40,
    )
    rollout.verify_release_manifest(release, expected_release_id="release-20260806")

    tracked.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(rollout.RolloutError, match="manifest"):
        rollout.verify_release_manifest(release, expected_release_id="release-20260806")

    tracked.write_text("candidate\n", encoding="utf-8")
    (release / "unlisted.txt").write_text("residue\n", encoding="utf-8")
    with pytest.raises(rollout.RolloutError, match="manifest"):
        rollout.verify_release_manifest(release, expected_release_id="release-20260806")


@pytest.mark.parametrize(
    "contents",
    [b"not json", b"{}", b'{"schema_version": 1, "release_id": 7, "entries": []}'],
)
def test_previous_release_identity_rejects_malformed_manifest(
    tmp_path: Path, contents: bytes
) -> None:
    (tmp_path / rollout.MANIFEST_NAME).write_bytes(contents)

    with pytest.raises(rollout.RolloutError, match="manifest"):
        rollout.read_release_identity(tmp_path)


def test_release_manifest_binds_external_symlink_target_content(tmp_path: Path) -> None:
    release = tmp_path / "release"
    release.mkdir()
    interpreter = tmp_path / "toolchain" / "python3"
    interpreter.parent.mkdir()
    interpreter.write_text("immutable interpreter\n", encoding="utf-8")
    (release / "python").symlink_to(interpreter)
    rollout.write_release_manifest(
        release,
        release_id="release-20260806",
        parent_revision="a" * 40,
        glasshive_revision="b" * 40,
    )
    rollout.verify_release_manifest(release, expected_release_id="release-20260806")

    interpreter.write_text("mutated interpreter\n", encoding="utf-8")
    with pytest.raises(rollout.RolloutError, match="manifest"):
        rollout.verify_release_manifest(release, expected_release_id="release-20260806")


def test_archive_extraction_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.tar"
    payload = b"must not escape\n"
    with tarfile.open(archive, "w:") as bundle:
        member = tarfile.TarInfo("../escaped.txt")
        member.size = len(payload)
        bundle.addfile(member, io.BytesIO(payload))

    with (
        tarfile.open(archive, "r:") as bundle,
        pytest.raises(rollout.RolloutError, match="unsafe path"),
    ):
        rollout._extract_validated_archive(bundle, tmp_path / "destination")
    assert not (tmp_path / "escaped.txt").exists()


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def test_stage_release_uses_clean_exact_pin_and_two_frozen_environments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    glasshive = source / "viventium_v0_4" / "GlassHive"
    runtime = glasshive / "runtime_phase1"
    ui = glasshive / "frontends" / "glass-drive-ui"
    for project, package_name in (
        (runtime, "workers_projects_runtime"),
        (ui, "glass_drive_ui"),
    ):
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname='synthetic'\nversion='1.0.0'\n")
        (project / "uv.lock").write_text("version = 1\nrevision = 3\nrequires-python = '>=3.12'\n")
        package = project / "src" / package_name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("RELOCATED = True\n", encoding="utf-8")
    _git(glasshive, "init")
    _git(glasshive, "config", "user.name", "Synthetic Release")
    _git(glasshive, "config", "user.email", "release@example.com")
    _git(glasshive, "add", ".")
    _git(glasshive, "commit", "-m", "synthetic GlassHive")
    glasshive_revision = _git(glasshive, "rev-parse", "HEAD")

    deploy = source / "deploy" / "glasshive" / "systemd"
    deploy.mkdir(parents=True)
    for name in (
        "glasshive_rollout.py",
        "glasshive_rootless_docker_probe.py",
        "glasshive_ui_readiness_probe.py",
    ):
        path = deploy / name
        path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        path.chmod(0o755)
    (source / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "GlassHive",
                        "path": "viventium_v0_4/GlassHive",
                        "ref": glasshive_revision,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _git(source, "init")
    _git(source, "config", "user.name", "Synthetic Release")
    _git(source, "config", "user.email", "release@example.com")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "synthetic parent")

    python_root = tmp_path / "python-runtime" / "bin"
    python_root.mkdir(parents=True)
    python = python_root / "python3"
    python.write_text(
        "#!/bin/sh\n"
        'venv_root="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"\n'
        'site_root="$(find "${venv_root}/lib" -type d -name site-packages -print -quit)"\n'
        'test -n "${site_root}"\n'
        'test "$1" = "-B"\n'
        'test "$2" = "-c"\n'
        f"exec {shlex.quote(str(Path(sys.executable).resolve()))} -B -S -c "
        "'import site,sys; site.addsitedir(sys.argv[1]); exec(sys.argv[2])' "
        '"${site_root}" "$3"\n',
        encoding="utf-8",
    )
    python.chmod(0o700)

    uv_log = tmp_path / "uv.log"
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "import sys\n"
        f"with Path({str(uv_log)!r}).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'venv':\n"
        "    Path('.venv/bin').mkdir(parents=True)\n"
        "    Path('.venv/lib/python3.12/site-packages').mkdir(parents=True)\n"
        "    allowed_python = Path(sys.argv[sys.argv.index('--python') + 1]).resolve()\n"
        "    Path('.venv/bin/python').symlink_to(allowed_python)\n"
        "elif sys.argv[1] == 'sync':\n"
        "    site_roots = list(Path('.venv/lib').glob('python*/site-packages'))\n"
        "    if len(site_roots) != 1:\n"
        "        raise SystemExit('synthetic venv has no unique site-packages')\n"
        "    source = (Path.cwd() / 'src').resolve()\n"
        "    (site_roots[0] / '__editable__.synthetic.pth').write_text(str(source) + '\\n')\n"
        "    (site_roots[0] / '_virtualenv.pth').write_text('# synthetic bootstrap\\n')\n"
        "    uvicorn = Path('.venv/bin/uvicorn')\n"
        "    uvicorn.write_text('#!/bin/sh\\nexit 0\\n')\n"
        "    uvicorn.chmod(0o755)\n"
        "else:\n"
        "    raise SystemExit('unexpected synthetic uv command')\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o700)
    releases = tmp_path / "releases"

    staging_commands: list[tuple[tuple[str, ...], Path | None]] = []
    real_run_checked = rollout._run_checked

    def record_checked_command(
        command: list[str] | tuple[str, ...], *, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        staging_commands.append((tuple(command), Path(cwd) if cwd is not None else None))
        return real_run_checked(command, cwd=cwd)

    monkeypatch.setattr(rollout, "_run_checked", record_checked_command)

    real_replace = rollout.os.replace

    def replace_requiring_owner_writable_source(source: Path, destination: Path) -> None:
        source_path = Path(source)
        if (
            source_path.is_dir()
            and source_path.name.startswith(".staging-")
            and not stat.S_IMODE(source_path.stat().st_mode) & stat.S_IWUSR
        ):
            raise PermissionError("source directory must remain owner-writable for atomic rename")
        real_replace(source, destination)

    monkeypatch.setattr(rollout.os, "replace", replace_requiring_owner_writable_source)

    manifest = rollout.stage_release(
        source=source,
        releases_root=releases,
        release_id="release-20260806",
        uv=fake_uv,
        python=python,
    )

    release = releases / "release-20260806"
    assert manifest["glasshive_revision"] == glasshive_revision
    rollout.verify_release_manifest(release, expected_release_id="release-20260806")
    commands = uv_log.read_text(encoding="utf-8").splitlines()
    assert len(commands) == 4
    assert all(
        "venv --relocatable --python" in command and command.endswith(" .venv")
        for command in commands[::2]
    )
    assert all(
        "sync --frozen --no-dev --link-mode copy --python" in command
        and "--no-editable" not in command
        and command.endswith("/.venv/bin/python")
        for command in commands[1::2]
    )
    relocated_imports = [
        (command, cwd)
        for command, cwd in staging_commands
        if len(command) == 4
        and command[1:3] == ("-B", "-c")
        and command[3] in {"import workers_projects_runtime", "import glass_drive_ui"}
    ]
    assert {command[3] for command, _cwd in relocated_imports} == {
        "import workers_projects_runtime",
        "import glass_drive_ui",
    }
    assert all(
        cwd is not None and ".relocation-probe-" in str(cwd)
        for _command, cwd in relocated_imports
    )
    for project in (
        release / "viventium_v0_4" / "GlassHive" / "runtime_phase1",
        release / "viventium_v0_4" / "GlassHive" / "frontends" / "glass-drive-ui",
    ):
        site_roots = list((project / ".venv" / "lib").glob("python*/site-packages"))
        assert len(site_roots) == 1
        assert (project / ".venv" / "bin" / "python").resolve() == python.resolve()
        editable_paths = list(site_roots[0].glob("__editable__*.pth"))
        assert len(editable_paths) == 1
        editable_value = editable_paths[0].read_text(encoding="utf-8").strip()
        assert editable_value and not Path(editable_value).is_absolute()
        assert (site_roots[0] / editable_value).resolve() == (project / "src").resolve()
        assert (site_roots[0] / "_virtualenv.pth").read_text(encoding="utf-8") == (
            "# synthetic bootstrap\n"
        )
        assert not list((project / "src").rglob("__pycache__"))
        assert not list((project / "src").rglob("*.pyc"))
    assert not list(releases.glob(".relocation-probe-*"))
    assert stat.S_IMODE(release.stat().st_mode) == 0o555
    assert not (release / ".git").exists()


def test_editable_path_rewrite_fails_closed_when_layout_is_ambiguous(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source = project / "src"
    site_root = project / ".venv" / "lib" / "python3.12" / "site-packages"
    source.mkdir(parents=True)
    site_root.mkdir(parents=True)

    with pytest.raises(rollout.RolloutError, match="exactly one editable source path"):
        rollout._relativize_editable_project_path(project)

    for name in ("first.pth", "second.pth"):
        (site_root / name).write_text(str(source.resolve()) + "\n", encoding="utf-8")
    with pytest.raises(rollout.RolloutError, match="exactly one editable source path"):
        rollout._relativize_editable_project_path(project)


def test_relocation_import_failure_restores_staging_without_probe_residue(tmp_path: Path) -> None:
    releases = tmp_path / "releases"
    staging = releases / ".staging-release-synthetic"
    glasshive = staging / "viventium_v0_4" / "GlassHive"
    for project, exit_code in (
        (glasshive / "runtime_phase1", 0),
        (glasshive / "frontends" / "glass-drive-ui", 1),
    ):
        executable = project / ".venv" / "bin" / "python"
        executable.parent.mkdir(parents=True)
        executable.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
        executable.chmod(0o700)

    with pytest.raises(rollout.RolloutError, match="release staging command failed"):
        rollout._probe_relocated_project_imports(
            staging=staging,
            releases_root=releases,
            release_id="release-synthetic",
        )

    assert staging.is_dir()
    assert not list(releases.glob(".relocation-probe-*"))


def test_relocation_fsync_failure_restores_staging_without_probe_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    releases = tmp_path / "releases"
    staging = releases / ".staging-release-synthetic"
    staging.mkdir(parents=True)
    real_fsync_directory = rollout._fsync_directory
    calls = 0

    def fail_first_fsync(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("synthetic fsync failure")
        real_fsync_directory(path)

    monkeypatch.setattr(rollout, "_fsync_directory", fail_first_fsync)

    with pytest.raises(OSError, match="synthetic fsync failure"):
        rollout._probe_relocated_project_imports(
            staging=staging,
            releases_root=releases,
            release_id="release-synthetic",
        )

    assert calls == 2
    assert staging.is_dir()
    assert not list(releases.glob(".relocation-probe-*"))


def test_adapter_contract_requires_all_named_acceptance_checks(tmp_path: Path) -> None:
    adapter = tmp_path / "acceptance-adapter"
    adapter.write_text(
        "#!/bin/sh\nprintf '%s\\n' '{\"ok\":true,\"checks\":{\"designed_root\":true}}'\n",
        encoding="utf-8",
    )
    adapter.chmod(0o700)

    with pytest.raises(rollout.RolloutError, match="authenticated_mcp_initialize"):
        rollout.run_acceptance_adapter(
            adapter,
            action="candidate",
            payload={"release_id": "release-20260806"},
        )


def test_live_edge_contract_names_every_public_route_and_header_family() -> None:
    contract = rollout.ingress_route_contract({"runtime": 18766, "mcp": 18767, "ui": 18780})

    assert contract["browser"] == {
        "exact_paths": [
            "/",
            "/auth",
            "/login",
            "/confirm-change",
            "/favicon.ico",
            "/health",
            "/static",
            "/ui",
            "/v1",
        ],
        "path_prefixes": [
            "/auth/",
            "/static/",
            "/api/",
            "/r/",
            "/watch/",
            "/desktop/",
            "/novnc/",
            "/ui/",
            "/v1/",
        ],
        "service": "glasshive-ui",
        "upstream": "http://127.0.0.1:18780",
        "preserve_client_headers": ["X-GlassHive-CSRF"],
        "websocket_path_prefixes": ["/novnc/"],
    }
    assert contract["mcp"]["exact_paths"] == [
        "/mcp",
        "/.well-known/oauth-protected-resource/mcp",
    ]
    assert contract["mcp"]["upstream"] == "http://127.0.0.1:18767"
    assert contract["mcp"]["forbid_oauth2_proxy_html_redirect"] is True
    assert contract["jwks"]["exact_paths"] == ["/.well-known/jwks.json"]
    assert contract["jwks"]["upstream"] == "http://127.0.0.1:18780"
    assert contract["private_upstreams"] == ["http://127.0.0.1:18766"]
    assert contract["scrub_client_header_prefixes"] == [
        "X-Viventium-",
        "X-GlassHive-",
        "X-LibreChat-",
    ]
    assert {
        "root_to_glass_drive_bff",
        "auth_to_glass_drive_bff",
        "login_to_glass_drive_bff",
        "static_to_glass_drive_bff",
        "api_to_glass_drive_bff",
        "confirm_change_to_glass_drive_bff",
        "short_links_to_glass_drive_bff",
        "watch_to_glass_drive_bff",
        "desktop_to_glass_drive_bff",
        "novnc_websocket_to_glass_drive_bff",
        "runtime_ui_proxy_to_glass_drive_bff",
        "runtime_v1_proxy_to_glass_drive_bff",
        "favicon_to_glass_drive_bff",
        "health_to_glass_drive_bff",
        "all_browser_routes_same_release",
        "mcp_to_mcp_service",
        "mcp_metadata_to_mcp_service",
        "mcp_no_oauth2_proxy_html_redirect",
        "jwks_to_glass_drive_bff",
        "identity_header_families_scrubbed",
        "browser_csrf_header_preserved",
        "runtime_not_public",
        "runtime_release_provenance",
        "ui_release_provenance",
        "mcp_release_provenance",
    }.issubset(rollout.ACCEPTANCE_CHECKS["live"])


def test_ingress_contract_covers_every_decorated_bff_route_family() -> None:
    source_path = (
        ROOT
        / "viventium_v0_4"
        / "GlassHive"
        / "frontends"
        / "glass-drive-ui"
        / "src"
        / "glass_drive_ui"
        / "server.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    public_paths: set[str] = set()
    route_methods = {"get", "post", "put", "patch", "delete", "api_route", "websocket"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = node.decorator_list
        else:
            decorators = []
        for decorator in decorators:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in route_methods
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                public_paths.add(decorator.args[0].value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "mount"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            public_paths.add(node.args[0].value)

    contract = rollout.ingress_route_contract({"runtime": 18766, "mcp": 18767, "ui": 18780})
    browser = contract["browser"]
    assert isinstance(browser, dict)
    exact = set(browser["exact_paths"])
    prefixes = tuple(browser["path_prefixes"])
    jwks = contract["jwks"]
    assert isinstance(jwks, dict)
    explicitly_owned = exact | set(jwks["exact_paths"])
    missing = sorted(
        path for path in public_paths if path not in explicitly_owned and not path.startswith(prefixes)
    )
    assert missing == []


def test_operator_doc_has_complete_entra_registration_contract() -> None:
    guide = (ROOT / "deploy" / "glasshive" / "systemd" / "README.md").read_text(encoding="utf-8")
    for required in (
        '"requestedAccessTokenVersion": 2',
        '"preAuthorizedApplications"',
        '"signInAudience": "AzureADMyOrg"',
        "`isFallbackPublicClient: true`",
        "http://localhost:<fixed-registered-claude-loopback-port>/callback",
        "http://127.0.0.1:<fixed-registered-codex-loopback-port>/callback/<server-hash>",
        "api://<glasshive-api-app-client-id-guid>/user_impersonation",
        "GLASSHIVE_MCP_OAUTH_REQUIRED_SCOPES",
        "GLASSHIVE_MCP_OAUTH_TOKEN_SCOPES",
        "access-token `scp` claim must equal `user_impersonation`",
        "group-overage",
        "exact tenant id and issuer",
    ):
        assert required in guide


def test_candidate_health_requires_exact_manifest_provenance_on_all_three_surfaces() -> None:
    expected = {
        "release_id": "release-20260806",
        "parent_revision": "a" * 40,
        "glasshive_revision": "b" * 40,
    }
    runtime = {"status": "ok", "release": dict(expected)}
    ui = {"status": "ok", "release": dict(expected), "runtime": {"release": dict(expected)}}
    mcp = {"status": "ok", "release": dict(expected)}

    rollout.validate_release_health_provenance(
        runtime=runtime,
        ui=ui,
        mcp=mcp,
        expected=expected,
    )
    mcp["release"] = {**expected, "release_id": "wrong-release"}
    with pytest.raises(rollout.RolloutError, match="MCP release provenance"):
        rollout.validate_release_health_provenance(
            runtime=runtime,
            ui=ui,
            mcp=mcp,
            expected=expected,
        )


def test_adapter_path_rejects_symlink_and_group_writable_executable(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    adapter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    adapter.chmod(0o720)
    with pytest.raises(rollout.RolloutError, match="writable"):
        rollout.validate_adapter_path(adapter)

    adapter.chmod(0o700)
    link = tmp_path / "adapter-link"
    link.symlink_to(adapter)
    with pytest.raises(rollout.RolloutError, match="symlink"):
        rollout.validate_adapter_path(link)


def test_slot_configuration_rejects_mixed_or_reused_ports() -> None:
    with pytest.raises(rollout.RolloutError, match="distinct"):
        rollout.validate_ports({"runtime": 18766, "mcp": 18766, "ui": 18780})
    with pytest.raises(rollout.RolloutError, match="active slot"):
        rollout.validate_candidate_ports(
            {"runtime": 8766, "mcp": 18767, "ui": 18780},
            {"runtime": 8766, "mcp": 8767, "ui": 8780},
        )


def test_active_environment_is_non_secret_and_written_atomically(tmp_path: Path) -> None:
    target = tmp_path / "runtime-active.env"
    rollout.write_active_environment(
        target,
        {
            "GLASSHIVE_RUNTIME_PORT": "18766",
            "WPR_DB_PATH": "/var/lib/glasshive/runtime.sqlite3",
        },
    )
    assert target.read_text(encoding="utf-8") == (
        "GLASSHIVE_RUNTIME_PORT=18766\nWPR_DB_PATH=/var/lib/glasshive/runtime.sqlite3\n"
    )
    assert stat.S_IMODE(target.stat().st_mode) == 0o640

    with pytest.raises(rollout.RolloutError, match="secret"):
        rollout.write_active_environment(target, {"OIDC_CLIENT_SECRET": "not-allowed"})

    with pytest.raises(rollout.RolloutError, match="invalid active environment value"):
        rollout.write_active_environment(target, {"GLASSHIVE_RUNTIME_PORT": " 18766"})


def test_systemd_units_use_slot_env_and_explicit_release_group_restart_contract() -> None:
    unit_dir = ROOT / "deploy" / "glasshive" / "systemd"
    runtime = (unit_dir / "glasshive-runtime.service").read_text(encoding="utf-8")
    mcp = (unit_dir / "glasshive-mcp.service").read_text(encoding="utf-8")
    ui = (unit_dir / "glasshive-ui.service").read_text(encoding="utf-8")
    target = (unit_dir / "glasshive.target").read_text(encoding="utf-8")

    assert "PartOf=glasshive.target" in runtime
    assert "PartOf=glasshive.target" in mcp
    assert "PartOf=glasshive.target" in ui
    assert "runtime-active.env" in runtime
    assert "gateway-active.env" in mcp
    assert "gateway-active.env" in ui
    assert "--port ${GLASSHIVE_RUNTIME_PORT}" in runtime
    assert "--port ${GLASSHIVE_MCP_PORT}" in mcp
    assert "--port ${GLASSHIVE_UI_PORT}" in ui
    assert "uv run" not in runtime + mcp + ui
    assert "After=network-online.target glasshive-runtime.service glasshive-ui.service" in mcp
    assert "Requires=glasshive-runtime.service glasshive-ui.service" in mcp
    assert "GLASSHIVE_AUTH_STATE_PATH" not in runtime
    assert "ExecStartPost=" in ui
    assert "--no-access-log" in ui
    assert "glasshive_ui_readiness_probe.py" in ui
    assert "--auth-state ${GLASSHIVE_AUTH_STATE_PATH}" in ui
    assert "glasshive_rootless_docker_probe.py" in runtime
    assert "SupplementaryGroups=glasshive-state" in runtime
    assert " docker" not in next(
        line for line in runtime.splitlines() if line.startswith("SupplementaryGroups=")
    )
    assert "Requires=glasshive-runtime.service glasshive-mcp.service glasshive-ui.service" in target


def test_rootless_probe_accepts_only_explicit_rootless_security_option() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, '["name=seccomp","name=rootless"]\n', "")

    options = rootless_probe.probe(
        docker_host="unix:///run/user/1234/docker.sock",
        expected_uid=1234,
        runner=runner,
    )

    assert "name=rootless" in options
    assert calls == [["/usr/bin/docker", "info", "--format", "{{json .SecurityOptions}}"]]


@pytest.mark.parametrize(
    ("returncode", "stdout", "message"),
    [
        (0, '["name=seccomp"]', "does not advertise rootless"),
        (1, "", "unavailable"),
        (0, "not-json", "valid JSON"),
    ],
)
def test_rootless_probe_rejects_rootful_unavailable_and_malformed_daemons(
    returncode: int,
    stdout: str,
    message: str,
) -> None:
    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, returncode, stdout, "synthetic failure")

    with pytest.raises(rootless_probe.RootlessDockerError, match=message):
        rootless_probe.probe(
            docker_host="unix:///run/user/1234/docker.sock",
            expected_uid=1234,
            runner=runner,
        )


def test_rootless_probe_rejects_rootful_or_ambiguous_socket_paths() -> None:
    with pytest.raises(rootless_probe.RootlessDockerError, match="rootless socket"):
        rootless_probe.probe(docker_host="unix:///var/run/docker.sock")


def test_ui_readiness_requires_initialized_auth_registry(tmp_path: Path) -> None:
    database = tmp_path / "auth.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE auth_principals (user_id TEXT PRIMARY KEY)")
        connection.commit()
    with pytest.raises(ui_probe.UiReadinessError, match="schema is not initialized"):
        ui_probe.verify_auth_registry(database)

    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE auth_sessions (session_hash TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE auth_oidc_flows (state_hash TEXT PRIMARY KEY)")
        connection.commit()
    ui_probe.verify_auth_registry(database)


class FakeSystem:
    def __init__(self, *, fail_start: str = "") -> None:
        self.events: list[str] = []
        self.fail_start = fail_start

    def rootless_probe(self) -> None:
        self.events.append("rootless-probe")

    def stop_group(self) -> None:
        self.events.append("stop-group")

    def assert_stopped(self, database_paths: list[Path]) -> None:
        self.events.append("assert-stopped")

    def start_group(self, *, phase: str) -> None:
        self.events.append(f"start-group:{phase}")
        if phase == self.fail_start:
            raise rollout.RolloutError(f"injected {phase} start failure")

    def probe_group(self, *, phase: str, ports: dict[str, int], expected: dict[str, object]) -> None:
        self.events.append(f"probe-group:{phase}")


class FakeAdapters:
    def __init__(self, *, fail_action: str = "") -> None:
        self.events: list[str] = []
        self.fail_action = fail_action

    def call_state(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        self.events.append(f"state:{action}")
        if action == self.fail_action:
            raise rollout.RolloutError(f"injected state {action} failure")
        if action == "clone":
            candidate = Path(str(payload["candidate_state_dir"]))
            candidate.mkdir(parents=True)
            for database in payload.get("candidate_databases", []):
                if isinstance(database, dict):
                    (candidate / str(database["relative"])).parent.mkdir(parents=True, exist_ok=True)
        return {"ok": True, f"{action}_id": f"synthetic-{action}"}

    def call_ingress(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        self.events.append(f"ingress:{action}")
        if action == self.fail_action:
            raise rollout.RolloutError(f"injected ingress {action} failure")
        release_id = str(payload.get("release_id") or payload.get("previous_release_id") or "previous")
        return {"ok": True, "active_release_id": release_id, "snapshot_id": "ingress-before"}

    def call_acceptance(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        self.events.append(f"acceptance:{action}")
        if action == self.fail_action:
            raise rollout.RolloutError(f"injected acceptance {action} failure")
        required = rollout.ACCEPTANCE_CHECKS[action]
        return {"ok": True, "checks": {name: True for name in required}}


def _release(path: Path, release_id: str, marker: str) -> None:
    runtime_bin = path / "viventium_v0_4" / "GlassHive" / "runtime_phase1" / ".venv" / "bin"
    ui_bin = path / "viventium_v0_4" / "GlassHive" / "frontends" / "glass-drive-ui" / ".venv" / "bin"
    runtime_bin.mkdir(parents=True)
    ui_bin.mkdir(parents=True)
    (runtime_bin / "python").write_text(marker, encoding="utf-8")
    (runtime_bin / "uvicorn").write_text(marker, encoding="utf-8")
    (ui_bin / "uvicorn").write_text(marker, encoding="utf-8")
    rollout.write_release_manifest(
        path,
        release_id=release_id,
        parent_revision="a" * 40,
        glasshive_revision="b" * 40,
    )


def _deployment_fixture(tmp_path: Path) -> tuple[rollout.RolloutConfig, Path, Path]:
    releases = tmp_path / "releases"
    previous = releases / "previous"
    candidate = releases / "candidate"
    _release(previous, "previous", "old")
    _release(candidate, "candidate", "new")
    current = tmp_path / "current"
    current.symlink_to(previous)

    state = tmp_path / "state"
    state.mkdir()
    candidate_state_root = state / ".rollout-candidates"
    candidate_state_root.mkdir()
    runtime_db = state / "runtime.sqlite3"
    auth_db = state / "auth.sqlite3"
    _database(runtime_db)
    _database(auth_db)
    runtime_env = tmp_path / "runtime-active.env"
    gateway_env = tmp_path / "gateway-active.env"
    rollout.write_active_environment(
        runtime_env,
        {
            "DOCKER_HOST": "unix:///run/user/1234/docker.sock",
            "GLASSHIVE_RUNTIME_PORT": "8766",
            "GLASSHIVE_STATE_DIR": str(state),
            "WPR_DB_PATH": str(runtime_db),
        },
    )
    rollout.write_active_environment(
        gateway_env,
        {
            "GLASSHIVE_AUTH_STATE_PATH": str(auth_db),
            "GLASSHIVE_MCP_PORT": "8767",
            "GLASSHIVE_RUNTIME_BASE_URL": "http://127.0.0.1:8766",
            "GLASSHIVE_UI_PORT": "8780",
            "WPR_MCP_BASE_URL": "http://127.0.0.1:8766",
        },
    )
    config = rollout.RolloutConfig(
        release_id="candidate",
        release_dir=candidate,
        releases_root=releases,
        current_symlink=current,
        runtime_active_env=runtime_env,
        gateway_active_env=gateway_env,
        state_dir=state,
        transactions_dir=tmp_path / "transactions",
        candidate_ports={"runtime": 18766, "mcp": 18767, "ui": 18780},
        expected={
            "mcp_resource": "https://glasshive.example.com/mcp",
            "mcp_resource_metadata_url": (
                "https://glasshive.example.com/.well-known/oauth-protected-resource/mcp"
            ),
            "mcp_issuer": "https://id.example.com/tenant/v2.0",
            "mcp_scopes": ["api://api-app-id/user_impersonation"],
            "mcp_token_audiences": ["api-app-id"],
            "mcp_token_scopes": ["user_impersonation"],
            "mcp_allowed_client_ids": ["claude-client-id", "codex-client-id"],
            "mcp_tenant_id": "tenant-id",
            "mcp_principal_claim": "oid",
        },
        databases=[
            rollout.DatabaseConfig(
                name="runtime",
                path=runtime_db,
                env_name="WPR_DB_PATH",
                candidate_relative=Path("runtime.sqlite3"),
                invariants=_invariants(),
            ),
            rollout.DatabaseConfig(
                name="auth",
                path=auth_db,
                env_name="GLASSHIVE_AUTH_STATE_PATH",
                candidate_relative=Path("auth.sqlite3"),
                invariants=_invariants(),
            ),
        ],
        ingress_adapter=tmp_path / "ingress-adapter",
        state_adapter=tmp_path / "state-adapter",
        acceptance_adapter=tmp_path / "acceptance-adapter",
        runtime_user="glasshive-runtime",
        candidate_state_root=candidate_state_root,
    )
    return config, runtime_db, previous


def test_active_gateway_places_watch_state_beside_auth_database_in_writable_state(
    tmp_path: Path,
) -> None:
    config, runtime_db, _ = _deployment_fixture(tmp_path)
    auth_db = next(database.path for database in config.databases if database.name == "auth")

    runtime, gateway = rollout._active_values(
        config,
        ports=config.candidate_ports,
        state_dir=config.state_dir,
        database_paths={"WPR_DB_PATH": runtime_db, "GLASSHIVE_AUTH_STATE_PATH": auth_db},
        background_consumers_enabled=False,
        reconcile_on_startup=False,
    )

    assert gateway["GLASSHIVE_WATCH_SESSION_STATE_PATH"] == str(
        auth_db.parent / "watch_sessions.sqlite3"
    )
    assert runtime["GLASSHIVE_BACKGROUND_CONSUMERS_ENABLED"] == "false"


def test_rollout_rejects_candidate_state_outside_systemd_writable_state_root(
    tmp_path: Path,
) -> None:
    config, _, _ = _deployment_fixture(tmp_path)
    outside_state = tmp_path / "candidate-state-outside-service-write-path"
    outside_state.mkdir()
    config.candidate_state_root = outside_state

    with pytest.raises(rollout.RolloutError, match="candidate state root escapes"):
        rollout.execute_rollout(config, system=FakeSystem(), adapters=FakeAdapters())


def test_shipped_candidate_state_is_beneath_every_service_writable_state_root() -> None:
    systemd_dir = ROOT / "deploy" / "glasshive" / "systemd"
    example = json.loads((systemd_dir / "rollout.example.json").read_text(encoding="utf-8"))
    state_dir = Path(example["state_dir"])
    candidate_state_root = Path(example["candidate_state_root"])

    assert candidate_state_root != state_dir
    assert candidate_state_root.is_relative_to(state_dir)
    for unit_name in (
        "glasshive-runtime.service",
        "glasshive-ui.service",
        "glasshive-mcp.service",
    ):
        unit = (systemd_dir / unit_name).read_text(encoding="utf-8")
        assert f"ReadWritePaths={state_dir}" in unit


def test_successful_rollout_rehearses_clone_then_switches_ingress(tmp_path: Path) -> None:
    config, _, _ = _deployment_fixture(tmp_path)
    class ReconcilePolicySystem(FakeSystem):
        def __init__(self) -> None:
            super().__init__()
            self.consumer_policy_by_phase: list[tuple[str, str, str]] = []

        def start_group(self, *, phase: str) -> None:
            values = rollout.read_active_environment(config.runtime_active_env)
            self.consumer_policy_by_phase.append(
                (
                    phase,
                    values["GLASSHIVE_RECONCILE_ON_STARTUP"],
                    values["GLASSHIVE_BACKGROUND_CONSUMERS_ENABLED"],
                )
            )
            super().start_group(phase=phase)

    system = ReconcilePolicySystem()
    adapters = FakeAdapters()

    receipt = rollout.execute_rollout(config, system=system, adapters=adapters)

    assert receipt["status"] == "committed"
    assert config.current_symlink.resolve() == config.release_dir.resolve()
    expected_provenance = {
        "GLASSHIVE_COMPONENT_REVISION": "b" * 40,
        "GLASSHIVE_PARENT_REVISION": "a" * 40,
        "GLASSHIVE_RELEASE_ID": config.release_id,
    }
    for environment in (config.runtime_active_env, config.gateway_active_env):
        values = rollout.read_active_environment(environment)
        assert {key: values[key] for key in expected_provenance} == expected_provenance
    assert system.events == [
        "rootless-probe",
        "probe-group:preflight",
        "stop-group",
        "assert-stopped",
        "start-group:rehearsal",
        "probe-group:rehearsal",
        "stop-group",
        "assert-stopped",
        "start-group:candidate-live",
        "probe-group:candidate-live",
    ]
    assert system.consumer_policy_by_phase == [
        ("rehearsal", "false", "false"),
        ("candidate-live", "true", "true"),
    ]
    assert adapters.events == [
        "ingress:inspect",
        "acceptance:preflight",
        "state:snapshot",
        "state:clone",
        "state:seal_clone",
        "acceptance:candidate",
        "ingress:switch",
        "acceptance:live",
        "ingress:status",
        "state:commit",
        "state:cleanup_clone",
    ]


def test_production_ingress_requires_exact_route_contract_attestation(tmp_path: Path) -> None:
    config, _, _ = _deployment_fixture(tmp_path)
    contract = rollout.ingress_route_contract(config.candidate_ports)
    payload = {"release_id": config.release_id, "route_contract": contract}
    response = {"ok": True, "active_release_id": config.release_id}
    config.ingress_adapter.write_text(
        "#!/bin/sh\nprintf '%s\\n' '" + json.dumps(response) + "'\n",
        encoding="utf-8",
    )
    config.ingress_adapter.chmod(0o700)

    adapters = rollout.ProductionAdapters(config)
    with pytest.raises(rollout.RolloutError, match="exact route contract"):
        adapters.call_ingress("switch", payload)

    response["route_contract_sha256"] = rollout._canonical_json_sha256(contract)
    config.ingress_adapter.write_text(
        "#!/bin/sh\nprintf '%s\\n' '" + json.dumps(response) + "'\n",
        encoding="utf-8",
    )
    assert adapters.call_ingress("switch", payload)["active_release_id"] == config.release_id


@pytest.mark.parametrize(
    ("failure", "where"),
    [
        ("rehearsal", "system"),
        ("candidate-live", "system"),
        ("candidate", "adapter"),
        ("switch", "adapter"),
        ("live", "adapter"),
    ],
)
def test_any_candidate_or_cutover_failure_restores_database_release_and_ingress(
    tmp_path: Path,
    failure: str,
    where: str,
) -> None:
    config, runtime_db, previous = _deployment_fixture(tmp_path)
    system = FakeSystem(fail_start=failure if where == "system" else "")
    adapters = FakeAdapters(fail_action=failure if where == "adapter" else "")

    with pytest.raises(rollout.RolloutError):
        rollout.execute_rollout(config, system=system, adapters=adapters)

    assert config.current_symlink.resolve() == previous.resolve()
    with sqlite3.connect(runtime_db) as conn:
        assert conn.execute("SELECT count(*) FROM workspaces").fetchone()[0] == 1
    assert "state:restore" in adapters.events
    assert "state:cleanup_clone" in adapters.events
    assert "start-group:rollback" in system.events
    assert "acceptance:rollback" in adapters.events
    assert "ingress:status" in adapters.events


def test_live_migration_damage_is_restored_from_verified_backup(tmp_path: Path) -> None:
    config, runtime_db, previous = _deployment_fixture(tmp_path)

    class DamagingSystem(FakeSystem):
        def start_group(self, *, phase: str) -> None:
            super().start_group(phase=phase)
            if phase == "candidate-live":
                with sqlite3.connect(runtime_db) as conn:
                    conn.execute("DELETE FROM workspaces")
                    conn.commit()
                raise rollout.RolloutError("injected incompatible live migration")

    with pytest.raises(rollout.RolloutError):
        rollout.execute_rollout(config, system=DamagingSystem(), adapters=FakeAdapters())

    assert config.current_symlink.resolve() == previous.resolve()
    with sqlite3.connect(runtime_db) as conn:
        assert conn.execute("SELECT count(*) FROM workspaces").fetchone()[0] == 1


def test_first_control_plane_auth_database_is_rehearsed_and_removed_on_failed_cutover(
    tmp_path: Path,
) -> None:
    config, _, previous = _deployment_fixture(tmp_path)
    auth = next(database for database in config.databases if database.name == "auth")
    auth.allow_create_if_missing = True
    auth.path.unlink()

    class InitializingSystem(FakeSystem):
        def start_group(self, *, phase: str) -> None:
            super().start_group(phase=phase)
            if phase in {"rehearsal", "candidate-live"}:
                active = rollout.read_active_environment(config.gateway_active_env)
                auth_path = Path(active["GLASSHIVE_AUTH_STATE_PATH"])
                if not auth_path.exists():
                    _database(auth_path)
            if phase == "candidate-live":
                raise rollout.RolloutError("injected post-initialization failure")

    with pytest.raises(rollout.RolloutError):
        rollout.execute_rollout(config, system=InitializingSystem(), adapters=FakeAdapters())

    assert not auth.path.exists()
    assert config.current_symlink.resolve() == previous.resolve()


def test_existing_incomplete_journal_blocks_a_second_rollout(tmp_path: Path) -> None:
    config, _, _ = _deployment_fixture(tmp_path)
    config.transactions_dir.mkdir()
    unfinished = config.transactions_dir / "rollout-unfinished"
    unfinished.mkdir()
    (unfinished / "journal.json").write_text(
        json.dumps({"schema_version": 1, "status": "live_stopped"}),
        encoding="utf-8",
    )

    with pytest.raises(rollout.RolloutError, match="recover"):
        rollout.execute_rollout(config, system=FakeSystem(), adapters=FakeAdapters())


def test_recover_retries_a_journaled_incomplete_rollback(tmp_path: Path) -> None:
    config, _, previous = _deployment_fixture(tmp_path)
    with pytest.raises(rollout.RolloutError, match="rollback is incomplete"):
        rollout.execute_rollout(
            config,
            system=FakeSystem(fail_start="candidate-live"),
            adapters=FakeAdapters(fail_action="restore"),
        )
    transactions = sorted(config.transactions_dir.glob("rollout-*"))
    assert len(transactions) == 1

    receipt = rollout.recover_rollout(
        config,
        transaction_id=transactions[0].name,
        system=FakeSystem(),
        adapters=FakeAdapters(),
    )

    assert receipt["status"] == "rolled_back"
    assert config.current_symlink.resolve() == previous.resolve()
