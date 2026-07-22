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

# Production Native bootstrap trust is deliberately embedded, never accepted from the
# environment or an unsigned network response. Empty long-lived roots keep this path
# unavailable until the release owner provisions the publisher key and Developer ID team.
NATIVE_BOOTSTRAP_ALLOWED_SIGNER=""
NATIVE_BOOTSTRAP_TEAM_ID=""
NATIVE_BOOTSTRAP_MANIFEST_URL="https://github.com/ProjectViventium/viventium/releases/latest/download/viventium-native-bootstrap-manifest.json"
NATIVE_BOOTSTRAP_SIGNATURE_URL="https://github.com/ProjectViventium/viventium/releases/latest/download/viventium-native-bootstrap-manifest.json.sig"
NATIVE_BOOTSTRAP_RELEASE_BASE="https://github.com/ProjectViventium/viventium/releases/download"
NATIVE_BOOTSTRAP_MINIMUM_MACOS="14.0"
# Release owners advance this signed-source floor for every Native publication. The
# protected release workflow requires it to equal that release's sequence.
NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE="1"
NATIVE_BOOTSTRAP_FREE_RESERVE_BYTES="2147483648"
NATIVE_BOOTSTRAP_TEMPORARY_ROOT=""

INSTALL_DISTRIBUTION="${VIVENTIUM_INSTALL_DISTRIBUTION:-}"
if [[ -z "$INSTALL_DISTRIBUTION" ]]; then
  if [[ -n "$NATIVE_BOOTSTRAP_ALLOWED_SIGNER" && -n "$NATIVE_BOOTSTRAP_TEAM_ID" ]]; then
    INSTALL_DISTRIBUTION="native"
  else
    # Do not make a network Native path the novice default until long-lived trust is provisioned.
    INSTALL_DISTRIBUTION="source"
  fi
fi

cleanup_native_bootstrap() {
  local temporary_name=""
  if [[ -z "${NATIVE_BOOTSTRAP_TEMPORARY_ROOT:-}" ]]; then
    return 0
  fi
  temporary_name="$(/usr/bin/basename "$NATIVE_BOOTSTRAP_TEMPORARY_ROOT")"
  if [[ "$temporary_name" == viventium-native-bootstrap.* && -d "$NATIVE_BOOTSTRAP_TEMPORARY_ROOT" ]]; then
    /bin/rm -rf -- "$NATIVE_BOOTSTRAP_TEMPORARY_ROOT"
  fi
}

run_native_bootstrap() {
  local architecture=""
  local expected_sha256=""
  local expected_size=""
  local expected_uncompressed_size=""
  local release_tag=""
  local release_id=""
  local sequence=""
  local artifact_name=""
  local artifact_url=""
  local temporary_root=""
  local archive_path=""
  local app_path=""
  local executable_path=""
  local actual_sha256=""
  local signing_details=""
  local actual_team_id=""
  local current_macos=""
  local manifest_path=""
  local signature_path=""
  local allowed_signers_path=""
  local schema_version=""
  local embedded_policy_path=""
  local embedded_schema_version=""
  local embedded_release_base=""
  local embedded_release_tag=""
  local embedded_release_id=""
  local embedded_sequence=""
  local available_kib=""
  local available_bytes=""
  local required_bytes=""

  if [[ -z "$NATIVE_BOOTSTRAP_ALLOWED_SIGNER" || -z "$NATIVE_BOOTSTRAP_TEAM_ID" ]]; then
    echo "Native release trust policy is not provisioned; refusing source fallback." >&2
    echo "Use the source checkout only for an explicit developer or local-QA install." >&2
    return 1
  fi
  if [[ ! "$NATIVE_BOOTSTRAP_TEAM_ID" =~ ^[A-Z0-9]{10}$ || \
        "$NATIVE_BOOTSTRAP_ALLOWED_SIGNER" == *$'\n'* || \
        "$NATIVE_BOOTSTRAP_ALLOWED_SIGNER" != bootstrap@viventium.example\ ssh-* ]]; then
    echo "Native release trust policy is invalid; refusing source fallback." >&2
    return 1
  fi
  if [[ "$(/usr/bin/uname -s)" != "Darwin" ]]; then
    echo "Easy Install Native supports macOS only." >&2
    return 1
  fi
  current_macos="$(/usr/bin/sw_vers -productVersion)"
  if ! /usr/bin/awk -v current="$current_macos" -v required="$NATIVE_BOOTSTRAP_MINIMUM_MACOS" 'BEGIN {
    split(current, a, "."); split(required, b, ".");
    for (i = 1; i <= 3; i++) {
      av = (a[i] == "" ? 0 : a[i]) + 0; bv = (b[i] == "" ? 0 : b[i]) + 0;
      if (av > bv) exit 0; if (av < bv) exit 1;
    }
    exit 0;
  }'; then
    echo "Easy Install Native requires macOS ${NATIVE_BOOTSTRAP_MINIMUM_MACOS} or newer; this Mac is ${current_macos}." >&2
    return 1
  fi
  architecture="$(/usr/bin/uname -m)"
  case "$architecture" in
    arm64|x86_64) ;;
    *)
      echo "Unsupported Mac architecture: $architecture" >&2
      return 1
      ;;
  esac

  temporary_root="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/viventium-native-bootstrap.XXXXXX")"
  NATIVE_BOOTSTRAP_TEMPORARY_ROOT="$temporary_root"
  manifest_path="$temporary_root/viventium-native-bootstrap-manifest.json"
  signature_path="${manifest_path}.sig"
  allowed_signers_path="$temporary_root/allowed_signers"
  printf '%s\n' "$NATIVE_BOOTSTRAP_ALLOWED_SIGNER" > "$allowed_signers_path"
  /bin/chmod 600 "$allowed_signers_path"
  archive_path="$temporary_root/$artifact_name"
  trap cleanup_native_bootstrap EXIT
  /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 --silent --show-error \
    --max-filesize 1048576 --output "$manifest_path" "$NATIVE_BOOTSTRAP_MANIFEST_URL"
  /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 --silent --show-error \
    --max-filesize 65536 --output "$signature_path" "$NATIVE_BOOTSTRAP_SIGNATURE_URL"
  /usr/bin/ssh-keygen -Y verify -f "$allowed_signers_path" -I bootstrap@viventium.example -n viventium-bootstrap -s "$signature_path" < "$manifest_path" >/dev/null

  schema_version="$(/usr/bin/plutil -extract schema_version raw -o - "$manifest_path")"
  release_tag="$(/usr/bin/plutil -extract release_tag raw -o - "$manifest_path")"
  release_id="$(/usr/bin/plutil -extract release_id raw -o - "$manifest_path")"
  sequence="$(/usr/bin/plutil -extract sequence raw -o - "$manifest_path")"
  artifact_name="$(/usr/bin/plutil -extract "artifacts.${architecture}.filename" raw -o - "$manifest_path")"
  expected_sha256="$(/usr/bin/plutil -extract "artifacts.${architecture}.sha256" raw -o - "$manifest_path")"
  expected_size="$(/usr/bin/plutil -extract "artifacts.${architecture}.size" raw -o - "$manifest_path")"
  expected_uncompressed_size="$(/usr/bin/plutil -extract "artifacts.${architecture}.uncompressed_size" raw -o - "$manifest_path")"
  if [[ "$schema_version" != 1 || ! "$release_tag" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ || \
        ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ || \
        ! "$sequence" =~ ^[1-9][0-9]{0,8}$ || "$sequence" -lt "$NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE" || \
        "$artifact_name" != "ViventiumBootstrap-${architecture}.zip" || \
        ! "$expected_sha256" =~ ^[0-9a-f]{64}$ || \
        ! "$expected_size" =~ ^[1-9][0-9]{0,8}$ || "$expected_size" -gt 268435456 || \
        ! "$expected_uncompressed_size" =~ ^[1-9][0-9]{0,9}$ || \
        "$expected_uncompressed_size" -gt 2147483648 ]]; then
    echo "Signed Native bootstrap manifest is invalid." >&2
    return 1
  fi
  artifact_url="${NATIVE_BOOTSTRAP_RELEASE_BASE}/${release_tag}/${artifact_name}"
  archive_path="$temporary_root/$artifact_name"
  available_kib="$(/bin/df -Pk "$temporary_root" | /usr/bin/awk 'NR == 2 {print $4}')"
  if [[ ! "$available_kib" =~ ^[1-9][0-9]*$ ]]; then
    echo "Native bootstrap free disk space could not be verified." >&2
    return 1
  fi
  available_bytes="$((available_kib * 1024))"
  required_bytes="$((expected_size + expected_uncompressed_size + NATIVE_BOOTSTRAP_FREE_RESERVE_BYTES))"
  if (( available_bytes < required_bytes )); then
    echo "Native bootstrap needs more free disk space before download and expansion." >&2
    return 1
  fi
  /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 --silent --show-error \
    --max-filesize 268435456 --output "$archive_path" "$artifact_url"
  if [[ "$(/usr/bin/stat -f %z "$archive_path")" != "$expected_size" ]]; then
    echo "Native bootstrap size verification failed." >&2
    return 1
  fi
  actual_sha256="$(/usr/bin/shasum -a 256 "$archive_path" | /usr/bin/awk '{print $1}')"
  if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    echo "Native bootstrap digest verification failed." >&2
    return 1
  fi

  /usr/bin/ditto -x -k "$archive_path" "$temporary_root/unpacked"
  app_path="$temporary_root/unpacked/ViventiumBootstrap.app"
  executable_path="$app_path/Contents/MacOS/ViventiumBootstrap"
  if [[ -L "$app_path" || ! -d "$app_path" || -L "$executable_path" || ! -x "$executable_path" ]]; then
    echo "Native bootstrap bundle structure is invalid." >&2
    return 1
  fi
  /usr/bin/codesign --verify --deep --strict --verbose=2 "$app_path"
  signing_details="$(/usr/bin/codesign -dv --verbose=4 "$app_path" 2>&1)"
  actual_team_id="$(printf '%s\n' "$signing_details" | /usr/bin/sed -n 's/^TeamIdentifier=//p' | /usr/bin/head -n 1)"
  if [[ "$actual_team_id" != "$NATIVE_BOOTSTRAP_TEAM_ID" ]]; then
    echo "Native bootstrap publisher identity verification failed." >&2
    return 1
  fi
  /usr/sbin/spctl --assess --type execute --verbose=2 "$app_path"
  embedded_policy_path="$app_path/Contents/Resources/release.json"
  if [[ -L "$embedded_policy_path" || ! -f "$embedded_policy_path" ]]; then
    echo "Native bootstrap embedded release policy is unavailable." >&2
    return 1
  fi
  embedded_schema_version="$(/usr/bin/plutil -extract schema_version raw -o - "$embedded_policy_path")"
  embedded_release_base="$(/usr/bin/plutil -extract release_base raw -o - "$embedded_policy_path")"
  embedded_release_tag="$(/usr/bin/plutil -extract release_tag raw -o - "$embedded_policy_path")"
  embedded_release_id="$(/usr/bin/plutil -extract release_id raw -o - "$embedded_policy_path")"
  embedded_sequence="$(/usr/bin/plutil -extract sequence raw -o - "$embedded_policy_path")"
  if [[ "$embedded_schema_version" != 1 || \
        "$embedded_release_base" != "$NATIVE_BOOTSTRAP_RELEASE_BASE" || \
        "$embedded_release_tag" != "$release_tag" || \
        "$embedded_release_id" != "$release_id" || \
        "$embedded_sequence" != "$sequence" ]]; then
    echo "Native bootstrap release policy does not match the signed bootstrap manifest." >&2
    return 1
  fi
  "$executable_path" "$@"
}

case "$INSTALL_DISTRIBUTION" in
  native)
    run_native_bootstrap "$@"
    exit $?
    ;;
  source)
    ;;
  *)
    echo "Unsupported VIVENTIUM_INSTALL_DISTRIBUTION: $INSTALL_DISTRIBUTION" >&2
    exit 1
    ;;
esac

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
