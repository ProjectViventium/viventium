#!/bin/bash
# Single-command helper for pushing/pulling all repos listed in the manifest.

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
WORKSPACE_MANIFEST_SCRIPT="$PROJECT_ROOT/devops/git/scripts/_workspace_repo_manifest.sh"
BOOTSTRAP_SCRIPT="$PROJECT_ROOT/devops/git/scripts/bootstrap-workspace.sh"
LOCAL_STATE_SNAPSHOT_SCRIPT="$PROJECT_ROOT/viventium_v0_4/viventium-local-state-snapshot.sh"
GH_READY=false

if [ ! -f "$WORKSPACE_MANIFEST_SCRIPT" ]; then
    echo "Error: workspace manifest helper not found at $WORKSPACE_MANIFEST_SCRIPT" >&2
    exit 1
fi

# shellcheck source=devops/git/scripts/_workspace_repo_manifest.sh
source "$WORKSPACE_MANIFEST_SCRIPT"
set +e

usage() {
    cat <<'USAGE'
Usage:
  ./git-helper.sh push -b <branch> -m <message> [--force] [--skip-local-state-snapshot] [--include-public-components]
  ./git-helper.sh pull -b <branch>
  ./git-helper.sh status

Commands:
  push    Commit and push the tracked workspace repos by default. Manual component
          repos can be backed up into a separate local companion repo when one is
          configured, and are only pushed when --include-public-components is passed.
  pull    Bootstrap nested repos (if needed) and checkout a branch everywhere.
  status  Show git status across all repos.

Examples:
  ./git-helper.sh push -b feature/viventium_alpha_1 -m "my commit msg"
  ./git-helper.sh push -b feature/viventium_alpha_1 -m "my commit msg" --include-public-components
  ./git-helper.sh push -b feature/viventium_alpha_1 -m "my commit msg" --force
  ./git-helper.sh push -b feature/viventium_alpha_1 -m "my commit msg" --skip-local-state-snapshot
  ./git-helper.sh pull -b feature/viventium_alpha_1
USAGE
}

die() {
    echo "Error: $1" >&2
    exit 1
}

normalize_branch() {
    local branch="$1"
    if [ -z "$branch" ]; then
        echo ""
        return 1
    fi
    echo "$branch"
    return 0
}

extract_repo_slug() {
    local url="$1"
    local slug
    slug=$(echo "$url" | sed -E 's#.*github.com[:/]+([^/]+/[^/]+).*#\1#')
    slug="${slug%.git}"
    if [ -z "$slug" ] || [ "$slug" = "$url" ]; then
        echo ""
        return 1
    fi
    echo "$slug"
}

init_gh() {
    if ! command -v gh >/dev/null 2>&1; then
        echo "Note: gh not found; skipping remote creation."
        return 0
    fi
    if ! gh auth status -h github.com >/dev/null 2>&1; then
        echo "Note: gh not authenticated; skipping remote creation."
        return 0
    fi
    GH_READY=true
    return 0
}

ensure_remote_repo_exists() {
    local name="$1"
    local origin_url="$2"
    local upstream_url="$3"
    local expected_visibility="${4:-private}"

    if [ "$GH_READY" != true ]; then
        return 0
    fi

    local private_slug
    private_slug="$(extract_repo_slug "$origin_url" || true)"
    if [ -z "$private_slug" ]; then
        echo "  - $name: unable to parse origin slug for repo creation" >&2
        return 1
    fi

    if gh repo view "$private_slug" >/dev/null 2>&1; then
        return 0
    fi

    echo "  - $name: creating $expected_visibility repo $private_slug"
    if [ "$expected_visibility" = "public" ]; then
        gh repo create "$private_slug" --public --description "Workspace-managed repository" >/dev/null 2>&1 || true
    elif [ -n "$upstream_url" ]; then
        local upstream_slug
        upstream_slug="$(extract_repo_slug "$upstream_url" || true)"
        # Never fork public upstreams; forks cannot be made private on GitHub.
        gh repo create "$private_slug" --private --description "Private mirror of $upstream_slug" >/dev/null 2>&1 || true
    else
        gh repo create "$private_slug" --private --description "Private repository" >/dev/null 2>&1 || true
    fi

    if ! gh repo view "$private_slug" >/dev/null 2>&1; then
        echo "  - $name: failed to create $private_slug" >&2
        return 1
    fi

    gh repo edit "$private_slug" --visibility "$expected_visibility" >/dev/null 2>&1 || true
    return 0
}

ensure_repo_visibility() {
    local name="$1"
    local origin_url="$2"
    local expected_visibility="${3:-private}"

    if [ "$GH_READY" != true ]; then
        return 0
    fi

    local private_slug
    private_slug="$(extract_repo_slug "$origin_url" || true)"
    if [ -z "$private_slug" ]; then
        return 0
    fi

    local info visibility is_fork
    info=$(gh repo view "$private_slug" --json visibility,isFork -q '.visibility + "|" + (.isFork|tostring)' 2>/dev/null || echo "")
    if [ -z "$info" ]; then
        return 0
    fi

    visibility="$(echo "${info%%|*}" | tr '[:upper:]' '[:lower:]')"
    is_fork="$(echo "${info##*|}" | tr '[:upper:]' '[:lower:]')"

    if [ "$visibility" != "$expected_visibility" ]; then
        if [ "$expected_visibility" = "private" ] && [ "$is_fork" = "true" ]; then
            echo "  - $name: $private_slug is a public fork; GitHub forbids private forks. Delete and recreate as a private mirror." >&2
        else
            echo "  - $name: $private_slug visibility is $visibility (expected $expected_visibility)." >&2
        fi
        return 1
    fi

    return 0
}

ensure_git_repo() {
    local path="$1"
    local name="$2"
    if [ ! -d "$path/.git" ]; then
        echo "  - $name: not a git repo at $path" >&2
        return 1
    fi
    return 0
}

workspace_repo_path() {
    local repo_path="$1"
    if [[ "$repo_path" = /* ]]; then
        echo "$repo_path"
    else
        echo "$PROJECT_ROOT/$repo_path"
    fi
}

find_private_repo_path() {
    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch visibility push_policy backup_to_private; do
        if [ "$repo_name" = "private-companion-repo" ] || [ "$repo_name" = "private-companion-repo" ] || [ "$repo_name" = ".private-companion-repo" ]; then
            workspace_repo_path "$repo_path"
            return 0
        fi
    done < <(read_workspace_repo_manifest)
    return 1
}

component_backup_excludes() {
    cat <<'EOF'
.env
.env.*
.next
.next.*
node_modules
dist
coverage
__pycache__
*.pyc
EOF
}

backup_public_component_state() {
    local branch="$1"
    local message="$2"
    local private_repo_path="$3"

    if [ -z "$private_repo_path" ] || [ ! -d "$private_repo_path/.git" ]; then
        echo "Skipping public-component backup: companion backup repo not available."
        return 0
    fi

    local safe_branch timestamp backup_root
    safe_branch="$(echo "$branch" | tr '/[:space:]' '-' | tr -cd '[:alnum:]_.-')"
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup_root="$private_repo_path/curated/component-patches/$safe_branch/$timestamp"
    mkdir -p "$backup_root"

    local backed_up=false

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch visibility push_policy backup_to_private; do
        if [ "$push_policy" != "manual" ] || [ "$backup_to_private" != "true" ]; then
            continue
        fi

        local abs_repo_path
        abs_repo_path="$(workspace_repo_path "$repo_path")"
        if [ ! -d "$abs_repo_path/.git" ]; then
            continue
        fi

        if [ -z "$(git -C "$abs_repo_path" status --porcelain)" ]; then
            continue
        fi

        local repo_slug repo_backup_path
        repo_slug="$(echo "$repo_name" | tr '[:upper:] ' '[:lower:]-' | tr -cd '[:alnum:]-_')"
        repo_backup_path="$backup_root/$repo_slug"
        mkdir -p "$repo_backup_path/untracked"

        printf '%s\n' "$message" > "$repo_backup_path/message.txt"
        printf '%s\n' "$branch" > "$repo_backup_path/branch.txt"
        printf '%s\n' "$origin_url" > "$repo_backup_path/origin.txt"
        printf '%s\n' "$upstream_url" > "$repo_backup_path/upstream.txt"
        git -C "$abs_repo_path" rev-parse HEAD > "$repo_backup_path/base_commit.txt" 2>/dev/null || true
        git -C "$abs_repo_path" status --short > "$repo_backup_path/status.txt"
        git -C "$abs_repo_path" diff --binary HEAD | gzip -9 > "$repo_backup_path/tracked.patch.gz"

        python3 - "$abs_repo_path" "$repo_backup_path/untracked" <<'PY'
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
exclude_names = {
    ".env",
    ".next",
    "node_modules",
    "dist",
    "coverage",
    "__pycache__",
}
exclude_prefixes = (".env.", ".next.")

raw = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    cwd=repo,
)
for entry in raw.decode("utf-8", "replace").split("\0"):
    if not entry:
        continue
    path = pathlib.Path(entry)
    parts = path.parts
    if any(part in exclude_names for part in parts):
        continue
    if any(part.startswith(exclude_prefixes) for part in parts):
        continue
    src = repo / path
    if not src.exists():
        continue
    dest = out / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        continue
    dest.write_bytes(src.read_bytes())
PY

        backed_up=true
        echo "  - backed up private copy of $repo_name to $repo_backup_path"
    done < <(read_workspace_repo_manifest)

    if [ "$backed_up" = false ]; then
        rm -rf "$backup_root"
    fi
    return 0
}

ensure_main_origin() {
    local path="$1"
    local origin_url
    origin_url="$(git -C "$path" remote get-url origin 2>/dev/null || echo "")"
    if [ -z "$origin_url" ]; then
        echo "  - Main repo: origin remote missing" >&2
        return 1
    fi

    local slug owner
    slug="$(extract_repo_slug "$origin_url" || true)"
    if [ -z "$slug" ]; then
        echo "  - Main repo: origin is not a GitHub URL: $origin_url" >&2
        return 1
    fi
    owner="${slug%%/*}"
    if [ "$owner" != "ProjectViventium" ]; then
        echo "  - Main repo: origin owner is $owner (expected ProjectViventium)" >&2
        return 1
    fi
    return 0
}

ensure_nested_origin() {
    local path="$1"
    local name="$2"
    local expected_origin="$3"

    local expected_slug
    expected_slug="$(extract_repo_slug "$expected_origin" || true)"
    if [ -z "$expected_slug" ]; then
        echo "  - $name: invalid expected origin $expected_origin" >&2
        return 1
    fi

    local current_origin
    current_origin="$(git -C "$path" remote get-url origin 2>/dev/null || echo "")"
    if [ -z "$current_origin" ]; then
        git -C "$path" remote add origin "$expected_origin" || {
            echo "  - $name: failed to add origin $expected_origin" >&2
            return 1
        }
        current_origin="$expected_origin"
    fi

    local current_slug
    current_slug="$(extract_repo_slug "$current_origin" || true)"
    if [ "$current_slug" != "$expected_slug" ]; then
        echo "  - $name: origin mismatch (expected $expected_slug, got $current_slug)"
        echo "  - $name: updating origin to $expected_origin"
        git -C "$path" remote set-url origin "$expected_origin" || {
            echo "  - $name: failed to update origin" >&2
            return 1
        }
    fi
    return 0
}

stage_repo_changes() {
    local name="$1"
    local path="$2"

    if [ "$name" = "main" ]; then
        # Runtime container data and Swift helper build output are noisy/volatile.
        # Stage tracked edits/deletions surgically so tracked-but-ignored helper
        # build artifacts cannot make the whole add step fail.
        local add_exit=0
        while IFS= read -r -d '' relpath; do
            git -C "$path" add -A -- "$relpath" || add_exit=$?
        done < <(
            python3 - "$path" <<'PY'
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
exclude_prefixes = [
    "apps/macos/ViventiumHelper/.build",
    "viventium_v0_4/docker/skyvern/postgres-data",
    "viventium_v0_4/docker/skyvern/artifacts/local",
]

raw = subprocess.check_output(
    ["git", "ls-files", "-m", "-d", "-z"],
    cwd=repo,
)
seen = set()
for entry in raw.decode("utf-8", "replace").split("\0"):
    if not entry or entry in seen:
        continue
    if any(entry == prefix or entry.startswith(prefix + "/") for prefix in exclude_prefixes):
        continue
    seen.add(entry)
    sys.stdout.write(entry)
    sys.stdout.write("\0")
PY
        )
        while IFS= read -r -d '' relpath; do
            git -C "$path" add -- "$relpath" || add_exit=$?
        done < <(
            python3 - "$path" <<'PY'
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
exclude_prefixes = [
    "apps/macos/ViventiumHelper/.build",
    "viventium_v0_4/docker/skyvern/postgres-data",
    "viventium_v0_4/docker/skyvern/artifacts/local",
]

raw = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    cwd=repo,
)
for entry in raw.decode("utf-8", "replace").split("\0"):
    if not entry:
        continue
    path = pathlib.PurePosixPath(entry)
    posix = path.as_posix()
    if any(posix == prefix or posix.startswith(prefix + "/") for prefix in exclude_prefixes):
        continue
    sys.stdout.write(entry)
    sys.stdout.write("\0")
PY
        )
        return $add_exit
    fi

    if [ "$name" = "LibreChat" ]; then
        git -C "$path" add -A -- . \
            ':!.env' \
            ':!.env.*'
        return $?
    fi

    if [ "$name" = "google_workspace_mcp" ]; then
        git -C "$path" add -A -- . \
            ':!mcp_server_debug.log'
        return $?
    fi

    if [ "$name" = "agent-starter-react" ]; then
        git -C "$path" add -u -- .
        local add_exit=0
        python3 - "$path" <<'PY' | while IFS= read -r -d '' relpath; do
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
exclude_prefixes = [
    ".next",
    ".next.",
]

raw = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    cwd=repo,
)
for entry in raw.decode("utf-8", "replace").split("\0"):
    if not entry:
        continue
    path = pathlib.PurePosixPath(entry)
    first = path.parts[0] if path.parts else ""
    if any(first == prefix.rstrip(".") or first.startswith(prefix) for prefix in exclude_prefixes):
        continue
    sys.stdout.write(entry)
    sys.stdout.write("\0")
PY
            git -C "$path" add -- "$relpath" || add_exit=$?
        done
        return $add_exit
    fi

    if [ "$name" = "private-companion-repo" ] || [ "$name" = "private-companion-repo" ] || [ "$name" = ".private-companion-repo" ]; then
        git -C "$path" add -u -- . \
            ':!video_editor' \
            ':!video_editor/**' \
            ':!to-be-deleted' \
            ':!to-be-deleted/**' \
            ':!curated/misc' \
            ':!curated/misc/**' \
            ':!curated/runtime_workspace_cache' \
            ':!curated/runtime_workspace_cache/**' \
            ':!curated/archive_from_root_cleanup_20260312' \
            ':!curated/archive_from_root_cleanup_20260312/**' \
            ':!curated/runtime-state/.viventium/runtime/isolated/mongo-data' \
            ':!curated/runtime-state/.viventium/runtime/isolated/mongo-data/**' \
            ':!curated/runtime-state/.viventium/runtime/isolated/meili-data' \
            ':!curated/runtime-state/.viventium/runtime/isolated/meili-data/**' \
            ':!curated/runtime-state/librechat/.local_artifacts/data-node-dual.local' \
            ':!curated/runtime-state/librechat/.local_artifacts/data-node-dual.local/**' \
            ':!curated/runtime-state/output' \
            ':!curated/runtime-state/output/**' \
            ':!curated/runtime-state/tmp' \
            ':!curated/runtime-state/tmp/**' \
            ':!curated/runtime-state/skyvern' \
            ':!curated/runtime-state/skyvern/**'
        local add_exit=0
        python3 - "$path" <<'PY' | while IFS= read -r -d '' relpath; do
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
exclude_prefixes = [
    "video_editor",
    "to-be-deleted",
    "curated/misc",
    "curated/runtime_workspace_cache",
    "curated/archive_from_root_cleanup_20260312",
    "curated/runtime-state/.viventium/runtime/isolated/mongo-data",
    "curated/runtime-state/.viventium/runtime/isolated/meili-data",
    "curated/runtime-state/librechat/.local_artifacts/data-node-dual.local",
    "curated/runtime-state/output",
    "curated/runtime-state/tmp",
    "curated/runtime-state/skyvern",
]

raw = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    cwd=repo,
)
for entry in raw.decode("utf-8", "replace").split("\0"):
    if not entry:
        continue
    if any(entry == prefix or entry.startswith(prefix + "/") for prefix in exclude_prefixes):
        continue
    path = pathlib.PurePosixPath(entry)
    parts = path.parts
    if ".venv" in parts or ".pytest_cache" in parts or "__pycache__" in parts or ".git" in parts:
        continue
    if any(part == ".next" or part.startswith(".next.") for part in parts):
        continue
    if any(part in {"node_modules", "dist", "coverage"} for part in parts):
        continue
    if path.suffix in {".pyc", ".pyo"}:
        continue
    full_path = repo / path
    candidate = full_path if full_path.is_dir() else full_path.parent
    skip_for_nested_git = False
    while candidate != repo and candidate != candidate.parent:
        if (candidate / ".git").exists():
            skip_for_nested_git = True
            break
        candidate = candidate.parent
    if skip_for_nested_git:
        continue
    sys.stdout.write(entry)
    sys.stdout.write("\0")
PY
            git -C "$path" add -- "$relpath" || add_exit=$?
        done
        return $add_exit
    fi

    git -C "$path" add -A
    return $?
}

private_repo_list_tracked_oversized_paths() {
    local path="$1"
    local limit_bytes="${VIVENTIUM_GIT_HELPER_PRIVATE_MAX_FILE_BYTES:-100000000}"
    python3 - "$path" "$limit_bytes" <<'PY'
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
limit = int(sys.argv[2])

result = subprocess.run(
    ["git", "-C", str(repo), "ls-files", "-z", "--", "video_editor", "to-be-deleted"],
    check=True,
    capture_output=True,
)

matches = []
for raw_entry in result.stdout.split(b"\0"):
    if not raw_entry:
        continue
    relpath = raw_entry.decode("utf-8", errors="replace")
    full_path = repo / relpath
    try:
        if not full_path.is_file():
            continue
        size_bytes = full_path.stat().st_size
    except FileNotFoundError:
        continue
    if size_bytes >= limit:
        matches.append((size_bytes, relpath))

for size_bytes, relpath in sorted(matches, reverse=True)[:20]:
    size_mb = size_bytes / 1_000_000
    print(f"{size_mb:8.2f} MB  {relpath}")
PY
}

cleanup_temp_dir() {
    local temp_dir="${1:-}"
    if [ -n "$temp_dir" ] && [ -d "$temp_dir" ]; then
        rm -rf "$temp_dir"
    fi
}

push_branch_via_temp_clone() {
    local name="$1"
    local path="$2"
    local branch="$3"
    local force_push="$4"

    local origin_url temp_dir push_exit=0
    origin_url="$(git -C "$path" remote get-url origin 2>/dev/null || echo "")"
    if [ -z "$origin_url" ]; then
        echo "  - $name: origin remote missing for temp-clone push recovery" >&2
        return 1
    fi

    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/git-helper-push.XXXXXX")" || {
        echo "  - $name: failed to create temp dir for push recovery" >&2
        return 1
    }

    if ! git -C "$temp_dir" init >/dev/null 2>&1; then
        cleanup_temp_dir "$temp_dir"
        echo "  - $name: failed to initialize temp repo for push recovery" >&2
        return 1
    fi

    if ! git -C "$temp_dir" remote add origin "$origin_url"; then
        cleanup_temp_dir "$temp_dir"
        echo "  - $name: failed to configure origin in temp repo" >&2
        return 1
    fi

    if ! git -C "$temp_dir" remote add localsrc "$path"; then
        cleanup_temp_dir "$temp_dir"
        echo "  - $name: failed to attach local repo for push recovery" >&2
        return 1
    fi

    git -C "$temp_dir" fetch --no-tags origin >/dev/null 2>&1 || true

    if ! git -C "$temp_dir" fetch --no-tags localsrc "refs/heads/$branch:refs/heads/$branch"; then
        cleanup_temp_dir "$temp_dir"
        echo "  - $name: failed to import local branch into temp repo" >&2
        return 1
    fi

    if ! git -C "$temp_dir" checkout -B "$branch" "refs/heads/$branch" >/dev/null 2>&1; then
        cleanup_temp_dir "$temp_dir"
        echo "  - $name: failed to checkout $branch in temp repo" >&2
        return 1
    fi

    if [ "$force_push" = true ]; then
        git -C "$temp_dir" push --force -u origin "$branch"
        push_exit=$?
    else
        git -C "$temp_dir" push -u origin "$branch"
        push_exit=$?
    fi

    if [ $push_exit -eq 0 ]; then
        git -C "$path" fetch origin "refs/heads/$branch:refs/remotes/origin/$branch" >/dev/null 2>&1 || true
    fi

    cleanup_temp_dir "$temp_dir"
    return $push_exit
}

run_local_state_snapshot() {
    local branch="$1"
    local skip_snapshot="$2"

    if [ "$skip_snapshot" = true ]; then
        echo "Skipping local state snapshot (requested)."
        return 0
    fi

    if [ "${VIVENTIUM_GIT_HELPER_SNAPSHOT_BEFORE_PUSH:-true}" != "true" ]; then
        echo "Skipping local state snapshot (VIVENTIUM_GIT_HELPER_SNAPSHOT_BEFORE_PUSH=false)."
        return 0
    fi

    if [ ! -x "$LOCAL_STATE_SNAPSHOT_SCRIPT" ]; then
        if [ "${VIVENTIUM_GIT_HELPER_ALLOW_PUSH_WITHOUT_SNAPSHOT:-false}" = "true" ]; then
            echo "Warning: snapshot script missing; continuing without snapshot."
            return 0
        fi
        echo "Error: local state snapshot script not found/executable: $LOCAL_STATE_SNAPSHOT_SCRIPT" >&2
        return 1
    fi

    local safe_label
    safe_label="$(echo "$branch" | tr '/[:space:]' '-' | tr -cd '[:alnum:]_.-')"
    echo "Creating local state snapshot (branch=$branch)..."
    if ! bash "$LOCAL_STATE_SNAPSHOT_SCRIPT" --label "$safe_label"; then
        if [ "${VIVENTIUM_GIT_HELPER_ALLOW_PUSH_WITHOUT_SNAPSHOT:-false}" = "true" ]; then
            echo "Warning: local state snapshot failed; continuing because VIVENTIUM_GIT_HELPER_ALLOW_PUSH_WITHOUT_SNAPSHOT=true"
            return 0
        fi
        echo "Error: local state snapshot failed; aborting push." >&2
        return 1
    fi
    return 0
}

commit_and_push_repo() {
    local name="$1"
    local path="$2"
    local expected_origin="$3"
    local expected_visibility="$4"
    local branch="$5"
    local message="$6"
    local force_push="$7"

    echo "[$name] $path"
    ensure_git_repo "$path" "$name" || return 1

    if [ -n "$expected_origin" ]; then
        ensure_nested_origin "$path" "$name" "$expected_origin" || return 1
    else
        ensure_main_origin "$path" || return 1
    fi

    local origin_url
    origin_url="$(git -C "$path" remote get-url origin 2>/dev/null || echo "")"
    if [ -n "$origin_url" ]; then
        ensure_repo_visibility "$name" "$origin_url" "$expected_visibility" || return 1
    fi

    if [ "$name" = "private-companion-repo" ] || [ "$name" = "private-companion-repo" ] || [ "$name" = ".private-companion-repo" ]; then
        local tracked_oversized
        tracked_oversized="$(private_repo_list_tracked_oversized_paths "$path")"
        if [ -n "$tracked_oversized" ]; then
            echo "  - $name: push blocked because tracked files at or above GitHub's 100 MB hard limit still exist under excluded private paths." >&2
            echo "    Keep video_editor/ and to-be-deleted/ excluded from staging, but rebuild the branch from a clean base before pushing this repo." >&2
            echo "    First oversized tracked examples:" >&2
            while IFS= read -r line; do
                [ -n "$line" ] && echo "      $line" >&2
            done <<< "$tracked_oversized"
            return 3
        fi
    fi

    git -C "$path" checkout -B "$branch" >/dev/null 2>&1 || {
        echo "  - $name: failed to checkout branch $branch" >&2
        return 1
    }

    local status
    status="$(git -C "$path" status --porcelain)"
    if [ -n "$status" ]; then
        stage_repo_changes "$name" "$path" || {
            echo "  - $name: failed to add changes" >&2
            return 1
        }
        if ! git -C "$path" diff --cached --quiet; then
            git -C "$path" commit -m "$message" || {
                echo "  - $name: commit failed" >&2
                return 1
            }
            echo "  - committed"
        else
            echo "  - no staged changes after add"
        fi
    else
        echo "  - no changes to commit"
    fi

    if [ "$force_push" = true ]; then
        if ! git -C "$path" push --force -u origin "$branch"; then
            echo "  - $name: direct push failed, retrying via temp clone"
            push_branch_via_temp_clone "$name" "$path" "$branch" "$force_push" || {
                echo "  - $name: push failed" >&2
                return 1
            }
            echo "  - recovered push via temp clone"
        fi
    else
        if ! git -C "$path" push -u origin "$branch"; then
            echo "  - $name: direct push failed, retrying via temp clone"
            push_branch_via_temp_clone "$name" "$path" "$branch" "$force_push" || {
                echo "  - $name: push failed" >&2
                return 1
            }
            echo "  - recovered push via temp clone"
        fi
    fi
    echo "  - pushed to origin/$branch"
    return 0
}

checkout_branch_from_origin() {
    local name="$1"
    local path="$2"
    local expected_origin="$3"
    local branch="$4"

    echo "[$name] $path"
    ensure_git_repo "$path" "$name" || return 1

    if [ -n "$expected_origin" ]; then
        ensure_nested_origin "$path" "$name" "$expected_origin" || return 1
    else
        ensure_main_origin "$path" || return 1
    fi

    if [ -n "$(git -C "$path" status --porcelain)" ]; then
        echo "  - $name: working tree dirty, aborting checkout" >&2
        return 1
    fi

    git -C "$path" fetch origin || {
        echo "  - $name: failed to fetch origin" >&2
        return 1
    }

    if ! git -C "$path" show-ref --quiet "refs/remotes/origin/$branch"; then
        echo "  - $name: origin/$branch not found" >&2
        return 1
    fi

    git -C "$path" checkout -B "$branch" "origin/$branch" >/dev/null 2>&1 || {
        echo "  - $name: failed to checkout origin/$branch" >&2
        return 1
    }
    echo "  - checked out $branch"
    return 0
}

run_status() {
    local status_script="$PROJECT_ROOT/devops/git/scripts/git-status-all.sh"
    if [ -f "$status_script" ]; then
        bash "$status_script"
        return $?
    fi
    echo "git-status-all.sh not found; showing main repo status only"
    git -C "$PROJECT_ROOT" status --short
}

run_push() {
    local branch="$1"
    local message="$2"
    local force_push="$3"
    local skip_snapshot="$4"
    local include_public_components="$5"
    local failures=()
    local blockers=()
    local private_repo_path=""

    private_repo_path="$(find_private_repo_path || true)"

    echo "Pushing workspace repos"
    echo "  branch : $branch"
    echo "  message: $message"
    echo "  force  : $force_push"
    echo "  manual component pushes: $([ "$include_public_components" = true ] && echo "enabled" || echo "disabled (backed up to companion repo)")"
    echo "  snapshot before push: $([ "$skip_snapshot" = true ] && echo "disabled" || echo "enabled")"
    echo ""

    run_local_state_snapshot "$branch" "$skip_snapshot" || return 1

    init_gh

    local repo_exit=0
    commit_and_push_repo "main" "$PROJECT_ROOT" "" "private" "$branch" "$message" "$force_push" || repo_exit=$?
    if [ "$repo_exit" -ne 0 ]; then
        failures+=("main")
    fi

    backup_public_component_state "$branch" "$message" "$private_repo_path" || failures+=("component-private-backup")

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch visibility push_policy backup_to_private; do
        if [ -z "$repo_name" ] || [ -z "$repo_path" ]; then
            continue
        fi

        if [ "$push_policy" = "manual" ] && [ "$include_public_components" != true ]; then
            echo "[$repo_name] skipped public push (push_policy=manual)"
            continue
        fi

        if ! ensure_remote_repo_exists "$repo_name" "$origin_url" "$upstream_url" "$visibility"; then
            failures+=("$repo_name (remote create)")
            continue
        fi
        repo_exit=0
        commit_and_push_repo "$repo_name" "$(workspace_repo_path "$repo_path")" "$origin_url" "$visibility" "$branch" "$message" "$force_push" || repo_exit=$?
        if [ "$repo_exit" -eq 3 ]; then
            blockers+=("$repo_name (oversized tracked files in excluded private paths)")
        elif [ "$repo_exit" -ne 0 ]; then
            failures+=("$repo_name")
        fi
    done < <(read_workspace_repo_manifest)

    if [ "${#blockers[@]}" -ne 0 ] || [ "${#failures[@]}" -ne 0 ]; then
        echo ""
        echo "Push completed with issues:"
        if [ "${#blockers[@]}" -ne 0 ]; then
            echo "Blocked:"
            printf '  - %s\n' "${blockers[@]}"
        fi
        if [ "${#failures[@]}" -ne 0 ]; then
            echo "Failures:"
            printf '  - %s\n' "${failures[@]}"
        fi
        return 1
    fi

    echo ""
    echo "Push completed successfully."
    return 0
}

run_pull() {
    local branch="$1"
    local failures=()

    if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
        die "bootstrap script not found at $BOOTSTRAP_SCRIPT"
    fi

    local bootstrap_args=()
    if ! command -v gh >/dev/null 2>&1; then
        echo "Note: gh not found; skipping repo creation."
        bootstrap_args+=(--no-create)
    elif ! gh auth status -h github.com >/dev/null 2>&1; then
        echo "Note: gh not authenticated; skipping repo creation."
        bootstrap_args+=(--no-create)
    fi

    if [ "${#bootstrap_args[@]}" -gt 0 ]; then
        bash "$BOOTSTRAP_SCRIPT" "${bootstrap_args[@]}" || die "bootstrap failed"
    else
        bash "$BOOTSTRAP_SCRIPT" || die "bootstrap failed"
    fi

    echo ""
    echo "Checking out branch across all repos"
    echo "  branch: $branch"
    echo ""

    if ! checkout_branch_from_origin "main" "$PROJECT_ROOT" "" "$branch"; then
        failures+=("main")
    fi

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch visibility push_policy backup_to_private; do
        if [ -z "$repo_name" ] || [ -z "$repo_path" ]; then
            continue
        fi
        if ! checkout_branch_from_origin "$repo_name" "$(workspace_repo_path "$repo_path")" "$origin_url" "$branch"; then
            failures+=("$repo_name")
        fi
    done < <(read_workspace_repo_manifest)

    if [ "${#failures[@]}" -ne 0 ]; then
        echo ""
        echo "Pull completed with failures:"
        printf '  - %s\n' "${failures[@]}"
        return 1
    fi

    echo ""
    echo "Pull completed successfully."
    return 0
}

if [ $# -lt 1 ]; then
    usage
    exit 1
fi

command="$1"
shift

case "$command" in
    push)
        branch=""
        message=""
        force_push=false
        skip_snapshot=false
        include_public_components=false
        while [ $# -gt 0 ]; do
            case "$1" in
                -b|--branch)
                    branch="${2:-}"
                    shift 2
                    ;;
                -m|--message)
                    message="${2:-}"
                    shift 2
                    ;;
                --force)
                    force_push=true
                    shift
                    ;;
                --skip-local-state-snapshot)
                    skip_snapshot=true
                    shift
                    ;;
                --include-public-components)
                    include_public_components=true
                    shift
                    ;;
                -h|--help)
                    usage
                    exit 0
                    ;;
                *)
                    die "Unknown option: $1"
                    ;;
            esac
        done
        if [ -z "$branch" ]; then
            die "Missing branch (-b <branch>)"
        fi
        if [ -z "$message" ]; then
            die "Missing commit message (-m <message>)"
        fi
        branch="$(normalize_branch "$branch")" || die "Invalid branch"
        run_push "$branch" "$message" "$force_push" "$skip_snapshot" "$include_public_components"
        ;;
    pull)
        branch=""
        while [ $# -gt 0 ]; do
            case "$1" in
                -b|--branch)
                    branch="${2:-}"
                    shift 2
                    ;;
                -h|--help)
                    usage
                    exit 0
                    ;;
                *)
                    die "Unknown option: $1"
                    ;;
            esac
        done
        if [ -z "$branch" ]; then
            die "Missing branch (-b <branch>)"
        fi
        branch="$(normalize_branch "$branch")" || die "Invalid branch"
        run_pull "$branch"
        ;;
    status)
        run_status
        ;;
    -h|--help)
        usage
        ;;
    *)
        die "Unknown command: $command"
        ;;
esac
