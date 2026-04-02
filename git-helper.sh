#!/bin/bash
# Public workspace git helper for the ProjectViventium repo family.

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
MANIFEST_PATH="$PROJECT_ROOT/devops/git/repos.json"
MAIN_STAGE_EXCLUDES_JSON='["apps/macos/ViventiumHelper/.build","viventium_v0_4/docker/skyvern/postgres-data","viventium_v0_4/docker/skyvern/artifacts/local"]'

usage() {
    cat <<'USAGE'
Usage:
  ./git-helper.sh list
  ./git-helper.sh status [--repo <name>]... [--repos a,b,c] [--all] [--dry-run]
  ./git-helper.sh pull -b <branch> [--repo <name>]... [--repos a,b,c] [--all] [--dry-run]
  ./git-helper.sh push -b <branch> -m <message> [--force] [--repo <name>]... [--repos a,b,c] [--all] [--include-public-components] [--dry-run]

Commands:
  list    Show the public repo catalog managed by this workspace.
  status  Show git status for the selected repos. Defaults to main + all components.
  pull    Fetch origin and checkout the selected branch. Defaults to main only.
  push    Commit and push the selected repos. Defaults to main only.

Selectors:
  --repo <name>                Repeatable. Use 'main' for the root repo.
  --repos a,b,c                Comma-separated repo names.
  --all                        Select main plus every configured component repo.
  --include-public-components  Legacy alias for --all.
  --dry-run                    Print the selected repos/actions without changing git state.

Examples:
  ./git-helper.sh list
  ./git-helper.sh status
  ./git-helper.sh status --repo LibreChat
  ./git-helper.sh pull -b main --all
  ./git-helper.sh push -b main -m "Update release docs"
  ./git-helper.sh push -b main -m "Sync public repos" --repo LibreChat --repo google_workspace_mcp
  ./git-helper.sh push -b feature/public-polish -m "Workspace sweep" --include-public-components
USAGE
}

die() {
    echo "Error: $1" >&2
    exit 1
}

ensure_manifest_exists() {
    [ -f "$MANIFEST_PATH" ] || die "repo manifest not found at $MANIFEST_PATH"
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

workspace_repo_path() {
    local repo_path="$1"
    if [[ "$repo_path" = /* ]]; then
        echo "$repo_path"
    else
        echo "$PROJECT_ROOT/$repo_path"
    fi
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

ensure_git_repo() {
    local path="$1"
    local name="$2"
    if [ ! -d "$path/.git" ]; then
        echo "  - $name: not a git repo at $path" >&2
        return 1
    fi
    return 0
}

ensure_main_origin() {
    local path="$1"
    local origin_url
    origin_url="$(git -C "$path" remote get-url origin 2>/dev/null || echo "")"
    if [ -z "$origin_url" ]; then
        echo "  - main: origin remote missing" >&2
        return 1
    fi

    local slug owner
    slug="$(extract_repo_slug "$origin_url" || true)"
    if [ -z "$slug" ]; then
        echo "  - main: origin is not a GitHub URL: $origin_url" >&2
        return 1
    fi
    owner="${slug%%/*}"
    if [ "$owner" != "ProjectViventium" ]; then
        echo "  - main: origin owner is $owner (expected ProjectViventium)" >&2
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

emit_repo_lines() {
    python3 - "$MANIFEST_PATH" "$@" <<'PY'
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
include_all = sys.argv[3].lower() == "true"
default_all = sys.argv[4].lower() == "true"
selectors = sys.argv[5:]

payload = json.loads(manifest_path.read_text(encoding="utf-8"))
repos = payload.get("repos", [])

seen_names = set()
catalog = [{"name": "main", "path": ".", "origin": "", "upstream": "", "upstream_branch": "main"}]
catalog.extend(repos)

alias_map = {}
ordered_names = []
for repo in catalog:
    name = str(repo.get("name", "")).strip()
    path = str(repo.get("path", "")).strip()
    origin = str(repo.get("origin", "")).strip()
    upstream = str(repo.get("upstream", "")).strip()
    upstream_branch = str(repo.get("upstream_branch", "main")).strip() or "main"

    if not name or not path:
        raise SystemExit(f"Manifest entry is missing required fields: {repo!r}")
    lower_name = name.lower()
    if lower_name in seen_names:
        raise SystemExit(f"Duplicate repo name in manifest: {name}")
    seen_names.add(lower_name)

    normalized = {
        "name": name,
        "path": path,
        "origin": origin,
        "upstream": upstream,
        "upstream_branch": upstream_branch,
    }
    ordered_names.append(name)

    aliases = {lower_name, pathlib.PurePosixPath(path).name.lower()}
    if name == "main":
        aliases.update({"root", "."})
    if origin:
        slug = origin.rstrip("/").split("/")[-1]
        if slug.endswith(".git"):
            slug = slug[:-4]
        aliases.add(slug.lower())
    for alias in aliases:
        alias_map.setdefault(alias, []).append(normalized)

requested = []
unknown = []
seen_selected = set()

def add_repo(repo: dict[str, str]) -> None:
    key = repo["name"].lower()
    if key in seen_selected:
        return
    seen_selected.add(key)
    requested.append(repo)

for raw in selectors:
    for token in raw.split(","):
        name = token.strip()
        if not name:
            continue
        matches = alias_map.get(name.lower(), [])
        if not matches:
            unknown.append(name)
            continue
        if len(matches) > 1:
            match_names = ", ".join(sorted({repo["name"] for repo in matches}))
            raise SystemExit(f"Ambiguous repo selector '{name}': {match_names}")
        add_repo(matches[0])

if unknown:
    available = ", ".join(ordered_names)
    raise SystemExit(
        "Unknown repo selector(s): " + ", ".join(unknown) + ". Available repos: " + available
    )

if mode == "list":
    selected = catalog
elif requested:
    selected = requested
elif include_all or default_all:
    selected = catalog
else:
    selected = [catalog[0]]

for repo in selected:
    print(
        "|".join(
            [
                repo["name"],
                repo["path"],
                repo["origin"],
                repo["upstream"],
                repo["upstream_branch"],
            ]
        )
    )
PY
}

print_repo_catalog() {
    local repo_lines
    repo_lines="$(emit_repo_lines "list" false false)" || return 1

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch; do
        if [ "$repo_name" = "main" ]; then
            echo "main|.|$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null || echo "<missing-origin>")"
        else
            echo "$repo_name|$repo_path|$origin_url"
        fi
    done <<< "$repo_lines"
}

stage_repo_changes() {
    local name="$1"
    local path="$2"

    if [ "$name" = "main" ]; then
        # Runtime container data and Swift helper build output are noisy/volatile.
        local add_exit=0
        while IFS= read -r -d '' relpath; do
            git -C "$path" add -A -- "$relpath" || add_exit=$?
        done < <(
            VIVENTIUM_MAIN_STAGE_EXCLUDES_JSON="$MAIN_STAGE_EXCLUDES_JSON" python3 - "$path" <<'PY'
import pathlib
import json
import os
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
exclude_prefixes = json.loads(os.environ["VIVENTIUM_MAIN_STAGE_EXCLUDES_JSON"])

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
            VIVENTIUM_MAIN_STAGE_EXCLUDES_JSON="$MAIN_STAGE_EXCLUDES_JSON" python3 - "$path" <<'PY'
import pathlib
import json
import os
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])
exclude_prefixes = json.loads(os.environ["VIVENTIUM_MAIN_STAGE_EXCLUDES_JSON"])

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
        while IFS= read -r -d '' relpath; do
            git -C "$path" add -- "$relpath" || add_exit=$?
        done < <(
            python3 - "$path" <<'PY'
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1])

raw = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    cwd=repo,
)
for entry in raw.decode("utf-8", "replace").split("\0"):
    if not entry:
        continue
    path = pathlib.PurePosixPath(entry)
    first = path.parts[0] if path.parts else ""
    if first == ".next" or first.startswith(".next."):
        continue
    sys.stdout.write(entry)
    sys.stdout.write("\0")
PY
        )
        return $add_exit
    fi

    git -C "$path" add -A
    return $?
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

ensure_repo_checkout() {
    local name="$1"
    local path="$2"
    local expected_origin="$3"

    if [ -d "$path/.git" ]; then
        return 0
    fi

    if [ "$name" = "main" ]; then
        echo "  - main: root repo checkout missing at $path" >&2
        return 1
    fi

    if [ -e "$path" ] && [ ! -d "$path/.git" ]; then
        echo "  - $name: path exists but is not a git repo: $path" >&2
        return 1
    fi

    mkdir -p "$(dirname "$path")" || {
        echo "  - $name: failed to create parent directory for $path" >&2
        return 1
    }

    echo "  - $name: cloning missing checkout from $expected_origin"
    git clone "$expected_origin" "$path" >/dev/null 2>&1 || {
        echo "  - $name: clone failed" >&2
        return 1
    }
    return 0
}

commit_and_push_repo() {
    local name="$1"
    local path="$2"
    local expected_origin="$3"
    local branch="$4"
    local message="$5"
    local force_push="$6"
    local dry_run="$7"

    echo "[$name] $path"

    if [ "$dry_run" = true ]; then
        echo "  - would checkout/create branch $branch"
        echo "  - would stage repo-safe changes"
        echo "  - would commit with message: $message"
        echo "  - would push to origin/$branch$([ "$force_push" = true ] && echo ' (force)')"
        return 0
    fi

    ensure_git_repo "$path" "$name" || return 1

    if [ -n "$expected_origin" ]; then
        ensure_nested_origin "$path" "$name" "$expected_origin" || return 1
    else
        ensure_main_origin "$path" || return 1
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
    local dry_run="$5"

    echo "[$name] $path"

    if [ "$dry_run" = true ]; then
        echo "  - would fetch origin"
        echo "  - would checkout origin/$branch"
        return 0
    fi

    if [ -n "$expected_origin" ]; then
        ensure_repo_checkout "$name" "$path" "$expected_origin" || return 1
    fi

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

    git -C "$path" fetch origin --prune || {
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

show_repo_status() {
    local name="$1"
    local path="$2"
    local expected_origin="$3"
    local dry_run="$4"

    echo "[$name] $path"

    if [ "$dry_run" = true ]; then
        echo "  - would inspect git status"
        return 0
    fi

    if [ ! -d "$path/.git" ]; then
        echo "  - missing checkout" >&2
        return 1
    fi

    if [ -n "$expected_origin" ]; then
        ensure_nested_origin "$path" "$name" "$expected_origin" || return 1
    else
        ensure_main_origin "$path" || return 1
    fi

    git -C "$path" status --short --branch
    return $?
}

run_status() {
    local include_all="$1"
    local dry_run="$2"
    shift 2
    local failures=()
    local repo_lines

    repo_lines="$(emit_repo_lines "status" "$include_all" true "$@")" || return 1

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch; do
        [ -n "$repo_name" ] || continue
        local abs_repo_path
        abs_repo_path="$(workspace_repo_path "$repo_path")"
        if ! show_repo_status "$repo_name" "$abs_repo_path" "$origin_url" "$dry_run"; then
            failures+=("$repo_name")
        fi
    done <<< "$repo_lines"

    if [ "${#failures[@]}" -ne 0 ]; then
        echo ""
        echo "Status completed with issues:"
        printf '  - %s\n' "${failures[@]}"
        return 1
    fi
    return 0
}

run_push() {
    local branch="$1"
    local message="$2"
    local force_push="$3"
    local include_all="$4"
    local dry_run="$5"
    shift 5
    local failures=()
    local repo_lines

    echo "Pushing selected repos"
    echo "  branch : $branch"
    echo "  message: $message"
    echo "  force  : $force_push"
    echo "  dry-run: $dry_run"
    echo ""

    repo_lines="$(emit_repo_lines "push" "$include_all" false "$@")" || return 1

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch; do
        [ -n "$repo_name" ] || continue
        local abs_repo_path
        abs_repo_path="$(workspace_repo_path "$repo_path")"
        if ! commit_and_push_repo "$repo_name" "$abs_repo_path" "$origin_url" "$branch" "$message" "$force_push" "$dry_run"; then
            failures+=("$repo_name")
        fi
    done <<< "$repo_lines"

    if [ "${#failures[@]}" -ne 0 ]; then
        echo ""
        echo "Push completed with failures:"
        printf '  - %s\n' "${failures[@]}"
        return 1
    fi

    echo ""
    echo "$([ "$dry_run" = true ] && echo "Dry run completed successfully." || echo "Push completed successfully.")"
    return 0
}

run_pull() {
    local branch="$1"
    local include_all="$2"
    local dry_run="$3"
    shift 3
    local failures=()
    local repo_lines

    echo "Checking out branch across selected repos"
    echo "  branch : $branch"
    echo "  dry-run: $dry_run"
    echo ""

    repo_lines="$(emit_repo_lines "pull" "$include_all" false "$@")" || return 1

    while IFS='|' read -r repo_name repo_path origin_url upstream_url upstream_branch; do
        [ -n "$repo_name" ] || continue
        local abs_repo_path
        abs_repo_path="$(workspace_repo_path "$repo_path")"
        if ! checkout_branch_from_origin "$repo_name" "$abs_repo_path" "$origin_url" "$branch" "$dry_run"; then
            failures+=("$repo_name")
        fi
    done <<< "$repo_lines"

    if [ "${#failures[@]}" -ne 0 ]; then
        echo ""
        echo "Pull completed with failures:"
        printf '  - %s\n' "${failures[@]}"
        return 1
    fi

    echo ""
    echo "$([ "$dry_run" = true ] && echo "Dry run completed successfully." || echo "Pull completed successfully.")"
    return 0
}

parse_repo_selectors() {
    local selectors=()
    local include_all=false
    local dry_run=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --repo)
                [ $# -ge 2 ] || die "Missing value for --repo"
                selectors+=("${2:-}")
                shift 2
                ;;
            --repos)
                [ $# -ge 2 ] || die "Missing value for --repos"
                selectors+=("${2:-}")
                shift 2
                ;;
            --all|--all-components|--include-public-components)
                include_all=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                break
                ;;
        esac
    done

    PARSED_INCLUDE_ALL="$include_all"
    PARSED_DRY_RUN="$dry_run"
    PARSED_SELECTOR_COUNT="${#selectors[@]}"
    if [ "${#selectors[@]}" -gt 0 ]; then
        PARSED_SELECTORS=("${selectors[@]}")
    else
        PARSED_SELECTORS=()
    fi
    PARSED_REMAINING=("$@")
}

if [ $# -lt 1 ]; then
    usage
    exit 1
fi

ensure_manifest_exists

command="$1"
shift

case "$command" in
    list)
        if [ $# -gt 0 ]; then
            die "list does not take extra arguments"
        fi
        print_repo_catalog
        ;;
    status)
        parse_repo_selectors "$@"
        if [ "${#PARSED_REMAINING[@]}" -gt 0 ]; then
            die "Unknown option: ${PARSED_REMAINING[0]}"
        fi
        if [ "${#PARSED_SELECTORS[@]}" -gt 0 ]; then
            run_status "$PARSED_INCLUDE_ALL" "$PARSED_DRY_RUN" "${PARSED_SELECTORS[@]}"
        else
            run_status "$PARSED_INCLUDE_ALL" "$PARSED_DRY_RUN"
        fi
        ;;
    push)
        branch=""
        message=""
        force_push=false
        selectors=()
        include_all=false
        dry_run=false
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
                --repo)
                    [ $# -ge 2 ] || die "Missing value for --repo"
                    selectors+=("${2:-}")
                    shift 2
                    ;;
                --repos)
                    [ $# -ge 2 ] || die "Missing value for --repos"
                    selectors+=("${2:-}")
                    shift 2
                    ;;
                --all|--all-components|--include-public-components)
                    include_all=true
                    shift
                    ;;
                --dry-run)
                    dry_run=true
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
        [ -n "$branch" ] || die "Missing branch (-b <branch>)"
        [ -n "$message" ] || die "Missing commit message (-m <message>)"
        branch="$(normalize_branch "$branch")" || die "Invalid branch"
        if [ "${#selectors[@]}" -gt 0 ]; then
            run_push "$branch" "$message" "$force_push" "$include_all" "$dry_run" "${selectors[@]}"
        else
            run_push "$branch" "$message" "$force_push" "$include_all" "$dry_run"
        fi
        ;;
    pull)
        branch=""
        selectors=()
        include_all=false
        dry_run=false
        while [ $# -gt 0 ]; do
            case "$1" in
                -b|--branch)
                    branch="${2:-}"
                    shift 2
                    ;;
                --repo)
                    [ $# -ge 2 ] || die "Missing value for --repo"
                    selectors+=("${2:-}")
                    shift 2
                    ;;
                --repos)
                    [ $# -ge 2 ] || die "Missing value for --repos"
                    selectors+=("${2:-}")
                    shift 2
                    ;;
                --all|--all-components|--include-public-components)
                    include_all=true
                    shift
                    ;;
                --dry-run)
                    dry_run=true
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
        [ -n "$branch" ] || die "Missing branch (-b <branch>)"
        branch="$(normalize_branch "$branch")" || die "Invalid branch"
        if [ "${#selectors[@]}" -gt 0 ]; then
            run_pull "$branch" "$include_all" "$dry_run" "${selectors[@]}"
        else
            run_pull "$branch" "$include_all" "$dry_run"
        fi
        ;;
    -h|--help)
        usage
        ;;
    *)
        die "Unknown command: $command"
        ;;
esac
