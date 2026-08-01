from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "first_upgrade_bridge.py"


def load_module():
    specification = importlib.util.spec_from_file_location(
        "first_upgrade_bridge_docker_qa",
        MODULE_PATH,
    )
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    os.environ.get("VIVENTIUM_RUN_DISPOSABLE_DOCKER_BRIDGE") != "1",
    reason="requires an explicitly enabled local disposable Docker volume",
)
def test_real_disposable_volume_and_bind_bridges_readiness_and_cleanup(
    tmp_path: Path,
) -> None:
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker CLI is unavailable")
    image = os.environ.get("VIVENTIUM_DOCKER_BRIDGE_TEST_IMAGE", "mongo:8.0.20")
    if subprocess.run(
        [docker, "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode:
        pytest.skip("Docker daemon is unavailable")
    if subprocess.run(
        [docker, "image", "inspect", image],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode:
        pytest.skip(f"Disposable test image is not cached: {image}")
    image_id = subprocess.run(
        [docker, "image", "inspect", "--format", "{{.Id}}", image],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert image_id.startswith("sha256:")

    module = load_module()
    support = tmp_path / "support"
    transaction = support / "upgrade-backups" / f"qa-{uuid.uuid4().hex}"
    checkpoint_runtime = transaction / "checkpoint" / "runtime"
    checkpoint_runtime.mkdir(parents=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    runtime_env = checkpoint_runtime / "runtime.env"
    runtime_env.write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=compat",
                "VIVENTIUM_INSTALL_MODE=docker",
                f"VIVENTIUM_LOCAL_MONGO_PORT={port}",
                "VIVENTIUM_LOCAL_MONGO_DB=BridgeDockerQA",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o400)
    checkpoint_runtime.chmod(0o500)
    transaction.chmod(0o700)
    manifest = {
        "kind": "directory",
        "files": [
            {
                "path": "runtime.env",
                "size": runtime_env.stat().st_size,
                "sha256": hashlib.sha256(runtime_env.read_bytes()).hexdigest(),
            }
        ],
    }
    volume = f"viventium-first-upgrade-qa-{uuid.uuid4().hex}"
    subprocess.run(
        [
            docker,
            "volume",
            "create",
            "--label",
            "com.viventium.qa=first-upgrade-bridge",
            volume,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    context = module.UpgradeContext(
        repo_root=REPO_ROOT,
        app_support_dir=support,
        transaction=transaction,
        ledger={
            "storage_inventory": {
                "mongodb": {
                    "backend": "docker_named_volume",
                    "runtime_engine": "docker",
                    "profile": "compat",
                    "volume_name": volume,
                    "image": image,
                    "image_id": image_id,
                    "checkpoint_status": "complete",
                    "existed_before": True,
                }
            },
            "surfaces": [
                {
                    "label": "runtime",
                    "backup": str(checkpoint_runtime),
                    "manifest": manifest,
                }
            ],
        },
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=True,
    )
    session = None
    try:
        session = module._start_checkpoint_mongo(context, checkpoint_runtime)
        container_id = session.identity["container_id"]
        inserted = module._docker_call(
            [
                "container",
                "exec",
                container_id,
                "mongosh",
                "--host",
                "127.0.0.1",
                "--port",
                "27017",
                "--quiet",
                "--eval",
                (
                    "const c=db.getSiblingDB('BridgeDockerQA').proof;"
                    "c.insertOne({_id:'synthetic',ok:true});"
                    "quit(c.countDocuments({_id:'synthetic',ok:true})===1?0:3)"
                ),
            ]
        )
        assert inserted.returncode == 0
        module._stop_checkpoint_mongo(context, session)
        session = None
        assert module._docker_inspect(container_id, allow_missing=True) is None

        bind_data = support / "data" / "mongodb"
        bind_data.mkdir(parents=True)
        bind_context = module.UpgradeContext(
            repo_root=REPO_ROOT,
            app_support_dir=support,
            transaction=transaction,
            ledger={
                "storage_inventory": {
                    "mongodb": {
                        "backend": "app_support_bind",
                        "runtime_engine": "docker",
                        "profile": "compat",
                        "path": str(bind_data),
                        "image": image,
                        "image_id": image_id,
                        "observed_from": "container_inspect",
                        "checkpoint_status": "complete",
                        "existed_before": True,
                    }
                },
                "surfaces": context.ledger["surfaces"],
            },
            predecessor=context.predecessor,
            successor=context.successor,
            was_running=True,
        )
        session = module._start_checkpoint_mongo(bind_context, checkpoint_runtime)
        bind_container_id = session.identity["container_id"]
        inserted = module._docker_call(
            [
                "container",
                "exec",
                bind_container_id,
                "mongosh",
                "--host",
                "127.0.0.1",
                "--port",
                "27017",
                "--quiet",
                "--eval",
                (
                    "const c=db.getSiblingDB('BridgeDockerQA').proof;"
                    "c.insertOne({_id:'synthetic-bind',ok:true});"
                    "quit(c.countDocuments({_id:'synthetic-bind',ok:true})===1?0:3)"
                ),
            ]
        )
        assert inserted.returncode == 0
        module._stop_checkpoint_mongo(bind_context, session)
        session = None
        assert module._docker_inspect(bind_container_id, allow_missing=True) is None
    finally:
        if session is not None:
            active_context = (
                bind_context if "bind_context" in locals() else context
            )
            module._stop_checkpoint_mongo(active_context, session)
        removed = subprocess.run(
            [docker, "volume", "rm", volume],
            check=False,
            capture_output=True,
            text=True,
        )
        assert removed.returncode == 0, removed.stderr
