#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR=""
case "$SCRIPT_PATH" in
  ""|-|bash|sh|stdin|/dev/fd/*|/proc/self/fd/*)
    ;;
  *)
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" 2>/dev/null && pwd || true)"
    ;;
esac

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/bin/viventium" && -x "$SCRIPT_DIR/bin/viventium" ]]; then
  exec "$SCRIPT_DIR/bin/viventium" install "$@"
fi

REPO_URL="${VIVENTIUM_REPO_URL:-https://github.com/ProjectViventium/viventium.git}"
INSTALL_DIR="${VIVENTIUM_INSTALL_DIR:-${VIVENTIUM_INSTALL_ROOT:-$HOME/viventium}}"
BRANCH="${VIVENTIUM_REPO_BRANCH:-main}"

canonical_repo_identity() {
  local repo_url="${1%/}"
  case "$repo_url" in
    git@github.com:*)
      repo_url="https://github.com/${repo_url#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      repo_url="https://github.com/${repo_url#ssh://git@github.com/}"
      ;;
  esac
  printf '%s\n' "${repo_url%.git}"
}

validate_existing_checkout_origin() {
  local actual_origin=""
  local actual_identity=""
  local expected_identity=""

  actual_origin="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
  expected_identity="$(canonical_repo_identity "$REPO_URL")"
  actual_identity="$(canonical_repo_identity "$actual_origin")"
  if [[ -z "$actual_origin" || "$actual_identity" != "$expected_identity" ]]; then
    echo "Refusing to update an existing checkout with an unexpected origin." >&2
    echo "Expected: $REPO_URL" >&2
    echo "Found: ${actual_origin:-<missing origin>}" >&2
    echo "Choose an empty VIVENTIUM_INSTALL_DIR or correct the checkout origin explicitly." >&2
    return 1
  fi
}

validate_existing_checkout_clean() {
  local tracked_changes=""
  if ! tracked_changes="$(git -C "$INSTALL_DIR" status --porcelain --untracked-files=no)"; then
    echo "Refusing to update an existing checkout whose tracked state cannot be inspected." >&2
    echo "Choose an empty VIVENTIUM_INSTALL_DIR or repair the checkout explicitly." >&2
    return 1
  fi
  if [[ -n "$tracked_changes" ]]; then
    echo "Refusing to update an existing checkout with tracked changes." >&2
    echo "Preserve or discard those changes explicitly, or choose an empty VIVENTIUM_INSTALL_DIR." >&2
    return 1
  fi
}

validate_existing_checkout_matches_remote() {
  local local_head=""
  local remote_head=""
  local_head="$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true)"
  remote_head="$(git -C "$INSTALL_DIR" rev-parse "refs/remotes/origin/$BRANCH" 2>/dev/null || true)"
  if [[ -z "$local_head" || -z "$remote_head" || "$local_head" != "$remote_head" ]]; then
    echo "Refusing to execute an existing checkout that does not exactly match the requested origin branch." >&2
    echo "Choose an empty VIVENTIUM_INSTALL_DIR or reconcile the checkout explicitly." >&2
    return 1
  fi
}

mkdir -p "$(dirname "$INSTALL_DIR")"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  validate_existing_checkout_origin
  validate_existing_checkout_clean
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  validate_existing_checkout_clean
  validate_existing_checkout_matches_remote
else
  git clone --depth 1 --single-branch --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

exec "$INSTALL_DIR/bin/viventium" install "$@"
