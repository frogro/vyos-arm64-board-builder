#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="${BUILD_REPO:-${GITHUB_REPOSITORY:-}}"
WORKFLOW="${RAW_WORKFLOW:-test-vyos-arm64-raw.yml}"
REQUESTED_RUN="${RAW_RUN_ID:-}"
ARTIFACT_NAME="${RAW_ARTIFACT_NAME:-vyos-arm64-raw}"
GH_BIN="${GH_BIN:-gh}"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: resolve-raw-run.sh --repo OWNER/REPO [options]

Options:
  --workflow FILE       Raw-image workflow (default: test-vyos-arm64-raw.yml)
  --run-id ID           Require this successful run instead of auto-discovery
  --artifact NAME       Required artifact name (default: vyos-arm64-raw)
EOF
}

while (($#)); do
    case "$1" in
        --repo) REPOSITORY="${2:-}"; shift 2 ;;
        --workflow) WORKFLOW="${2:-}"; shift 2 ;;
        --run-id) REQUESTED_RUN="${2:-}"; shift 2 ;;
        --artifact) ARTIFACT_NAME="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
done

[[ "$REPOSITORY" =~ ^[^/]+/[^/]+$ ]] ||
    die "repository must use OWNER/REPO form"
[[ "$ARTIFACT_NAME" =~ ^[A-Za-z0-9._-]+$ ]] ||
    die "invalid artifact name: $ARTIFACT_NAME"

command -v "$GH_BIN" >/dev/null 2>&1 ||
    die "GitHub CLI not found: $GH_BIN"

artifact_id_for_run() {
    local run_id="$1"
    local artifacts

    artifacts="$(
        "$GH_BIN" api \
            "repos/${REPOSITORY}/actions/runs/${run_id}/artifacts" \
            --paginate \
            --jq ".artifacts[] | select(.name == \"${ARTIFACT_NAME}\" and (.expired | not)) | .id"
    )"

    printf '%s\n' "$artifacts" | sed -n '1p'
}

validate_run() {
    local run_id="$1"
    local conclusion
    local artifact_id

    [[ "$run_id" =~ ^[0-9]+$ ]] ||
        die "invalid raw workflow run ID: $run_id"

    conclusion="$(
        "$GH_BIN" api \
            "repos/${REPOSITORY}/actions/runs/${run_id}" \
            --jq '.conclusion'
    )" || return 1

    [[ "$conclusion" == "success" ]] || return 1

    artifact_id="$(artifact_id_for_run "$run_id")" || return 1
    [[ -n "$artifact_id" ]]
}

if [[ -n "$REQUESTED_RUN" && "$REQUESTED_RUN" != "auto" ]]; then
    if ! validate_run "$REQUESTED_RUN"; then
        die "run ${REQUESTED_RUN} is not successful or has no unexpired ${ARTIFACT_NAME} artifact"
    fi

    printf '%s\n' "$REQUESTED_RUN"
    exit 0
fi

mapfile -t candidates < <(
    "$GH_BIN" run list \
        --repo "$REPOSITORY" \
        --workflow "$WORKFLOW" \
        --status success \
        --limit 50 \
        --json databaseId \
        --jq '.[].databaseId'
)

for run_id in "${candidates[@]}"; do
    [[ "$run_id" =~ ^[0-9]+$ ]] || continue

    if validate_run "$run_id"; then
        printf '%s\n' "$run_id"
        exit 0
    fi
done

die "no successful ${WORKFLOW} run with an unexpired ${ARTIFACT_NAME} artifact was found"
