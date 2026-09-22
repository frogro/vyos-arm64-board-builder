#!/usr/bin/env bash
set -euo pipefail

BUILD_REPO="${BUILD_REPO:-frogro/vyos-arm64-board-builder}"
WORKFLOW="${WORKFLOW:-build-board-candidate.yml}"
RAW_WORKFLOW="${RAW_WORKFLOW:-test-vyos-arm64-raw.yml}"

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/ui.sh
source "${SCRIPT_ROOT}/lib/ui.sh"

DEFAULT_WORKFLOW_REF="$(
    git -C "$SCRIPT_ROOT"         symbolic-ref --quiet --short HEAD         2>/dev/null ||
    printf '%s\n' main
)"

WORKFLOW_REF="${WORKFLOW_REF:-$DEFAULT_WORKFLOW_REF}"

ARMBIAN_REF="${ARMBIAN_REF:-main}"
ARMBIAN_REMOTE="${ARMBIAN_REMOTE:-https://github.com/armbian/build.git}"

VYOS_BRANCH="${VYOS_BRANCH:-rolling}"

RAW_RUN_ID="${RAW_RUN_ID:-auto}"
PUBLISH_RELEASE="${PUBLISH_RELEASE:-}"
BOOT_BRANCH="${BOOT_BRANCH:-auto}"
DRY_RUN="no"
ASSUME_YES="no"

CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/vyos-arm64-board-builder"
ARMBIAN_CACHE="${CACHE_ROOT}/armbian-build"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

need() {
    command -v "$1" >/dev/null 2>&1 ||
        die "required command not found: $1"
}

usage() {
    cat <<'EOF'
Usage: ./trigger-release.sh [options]

Interactively select a board and optional feature profiles, verify a usable
VyOS ARM64 raw-image workflow artifact, and dispatch the board-image workflow.

Options:
  --dry-run             Validate and print the request; do not dispatch
  --yes                 Dispatch without the final confirmation
  --raw-run-id ID       Pin a raw run (default: newest usable run)
  --publish-release     Publish a successful build as a GitHub release
  --no-publish-release  Build an Actions artifact only (safe default)
  -h, --help            Show this help

Environment overrides: BUILD_REPO, WORKFLOW, WORKFLOW_REF, ARMBIAN_REF,
RAW_WORKFLOW, RAW_RUN_ID, HW_REFERENCE, EXTENDED_NETWORK,
TAILSCALE_SUBNET_ROUTER, KVM_OVER_IP and PUBLISH_RELEASE.
EOF
}

while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN="yes"; shift ;;
        --yes) ASSUME_YES="yes"; shift ;;
        --raw-run-id)
            [[ $# -ge 2 ]] || die "--raw-run-id requires a value"
            RAW_RUN_ID="$2"
            shift 2
            ;;
        --publish-release) PUBLISH_RELEASE="yes"; shift ;;
        --no-publish-release) PUBLISH_RELEASE="no"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
done

normalize_boolean() {
    case "${1,,}" in
        1|true|yes|y|j|ja|on|enabled) printf 'yes\n' ;;
        0|false|no|n|nein|off|disabled) printf 'no\n' ;;
        *) return 1 ;;
    esac
}

workflow_boolean() {
    case "${1,,}" in
        1|true|yes|y|j|ja|on|enabled) printf 'true\n' ;;
        0|false|no|n|nein|off|disabled) printf 'false\n' ;;
        *) return 1 ;;
    esac
}

select_publish_release() {
    local requested="$PUBLISH_RELEASE"

    if [[ -n "$requested" ]]; then
        normalize_boolean "$requested" ||
            die "invalid PUBLISH_RELEASE value: $requested"
        return
    fi

    if [[ ! -t 0 ]]; then
        printf 'no\n'
        return
    fi

    read -r -p \
        'Publish a successful build as GitHub Latest Release? [y/N] ' \
        requested

    normalize_boolean "${requested:-no}" 2>/dev/null || printf 'no\n'
}

for cmd in git gh grep sed sort awk mktemp python3; do
    need "$cmd"
done

sync_armbian_metadata() {
    mkdir -p "$CACHE_ROOT"

    if [[ ! -d "$ARMBIAN_CACHE/.git" ]]; then
        echo "==> Creating local Armbian metadata cache"

        git clone \
            --filter=blob:none \
            --no-checkout \
            "$ARMBIAN_REMOTE" \
            "$ARMBIAN_CACHE"
    fi

    echo "==> Loading Armbian board definitions from: $ARMBIAN_REF"

    git -C "$ARMBIAN_CACHE" fetch \
        --quiet \
        --depth=1 \
        origin \
        "$ARMBIAN_REF"

    git -C "$ARMBIAN_CACHE" checkout \
        --quiet \
        --detach \
        FETCH_HEAD

    ARMBIAN_COMMIT="$(
        git -C "$ARMBIAN_CACHE" rev-parse HEAD
    )"

    export ARMBIAN_COMMIT
}

extract_var() {
    local file="$1"
    local var="$2"
    local line
    local value

    line="$(
        grep -m1 -E \
            "(^|[[:space:]])(declare[[:space:]]+-g[[:space:]]+)?${var}=" \
            "$file" \
            2>/dev/null ||
            true
    )"

    [[ -n "$line" ]] || return 1

    value="$(
        printf '%s\n' "$line" |
            sed -nE \
                "s/.*${var}=\"([^\"]*)\".*/\1/p"
    )"

    if [[ -z "$value" ]]; then
        value="$(
            printf '%s\n' "$line" |
                sed -nE \
                    "s/.*${var}=([^[:space:]]+).*/\1/p" |
                tr -d "'\""
        )"
    fi

    [[ -n "$value" ]] || return 1

    printf '%s' "$value"
}

board_status() {
    case "$1" in
        *.conf) printf 'supported' ;;
        *.csc)  printf 'community' ;;
        *.wip)  printf 'wip' ;;
        *.eos)  printf 'eos' ;;
        *.tvb)  printf 'tvbox' ;;
        *)      printf 'other' ;;
    esac
}

discover_boards() {
    local out="$1"
    local file
    local board
    local name
    local targets
    local status

    : > "$out"

    shopt -s nullglob

    for file in \
        "$ARMBIAN_CACHE"/config/boards/*.{conf,csc,wip,eos,tvb}
    do
        targets="$(
            extract_var "$file" KERNEL_TARGET \
                2>/dev/null ||
                true
        )"

        #
        # No known kernel target -> not useful for this
        # automatic builder.
        #
        [[ -n "$targets" ]] || continue

        board="$(basename "$file")"
        board="${board%.*}"

        name="$(
            extract_var "$file" BOARD_NAME \
                2>/dev/null ||
                true
        )"

        [[ -n "$name" ]] || name="$board"

        status="$(board_status "$file")"

        printf '%s\t%s\t%s\t%s\n' \
            "$board" \
            "$name" \
            "$status" \
            "$targets" \
            >> "$out"
    done

    shopt -u nullglob

    sort -u -o "$out" "$out"

    python3 - "$SCRIPT_ROOT/profiles/board-models" >> "$out" <<'PY_MODELS'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
if root.is_dir():
    for path in sorted(root.glob("*.json")):
        model = json.loads(path.read_text(encoding="utf-8"))
        print(
            "\t".join(
                (
                    model["model"],
                    model["name"],
                    "model",
                    "auto",
                )
            )
        )
PY_MODELS

    sort -u -o "$out" "$out"

    [[ -s "$out" ]] ||
        die "no usable Armbian boards found"
}

pick_board() {
    local file="$1"
    local query
    local tmp
    local count
    local choice

    if command -v fzf >/dev/null 2>&1; then
        awk -F '\t' '
            {
                printf "%-30s | %-42s | %-10s | %s\n",
                    $1, $2, $3, $4
            }
        ' "$file" |
            fzf \
                --height=80% \
                --border \
                --prompt='Armbian BOARD > ' \
                --header='BOARD | board name | status | kernel targets' |
            awk -F ' *\\| *' '
                {
                    gsub(/[[:space:]]+$/, "", $1)
                    print $1
                }
            '

        return
    fi

    echo >&2

    read -r -p \
        "Board search (e.g. rock, radxa, orange, banana, rpi; blank = all): " \
        query

    tmp="$(mktemp)"

    if [[ -n "$query" ]]; then
        grep -i -- "$query" "$file" > "$tmp" ||
            true
    else
        cp "$file" "$tmp"
    fi

    count="$(
        wc -l < "$tmp" |
            tr -d ' '
    )"

    [[ "$count" -gt 0 ]] || {
        rm -f "$tmp"
        die "no matching boards"
    }

    awk -F '\t' '
        {
            printf "%3d) %-28s %-40s [%s] {%s}\n",
                NR, $1, $2, $3, $4
        }
    ' "$tmp" >&2

    while true; do
        read -r -p \
            "Select board [1-$count]: " \
            choice

        [[ "$choice" =~ ^[0-9]+$ ]] ||
            continue

        (( choice >= 1 && choice <= count )) ||
            continue

        awk -F '\t' \
            -v n="$choice" \
            'NR == n { print $1 }' \
            "$tmp"

        rm -f "$tmp"

        return
    done
}

main() {
    gh auth status >/dev/null 2>&1 ||
        die "GitHub CLI is not authenticated; run: gh auth login"

    gh workflow view "$WORKFLOW" \
        --repo "$BUILD_REPO" \
        --ref "$WORKFLOW_REF" \
        --yaml >/dev/null ||
        die "workflow ${WORKFLOW} is unavailable at ref ${WORKFLOW_REF}"

    sync_armbian_metadata

    local board_list
    local board
    local line
    local board_name
    local status
    local hardware_reference="${HW_REFERENCE:-auto}"
    local extended_network
    local tailscale_subnet_router
    local kvm_over_ip
    local publish_release
    local resolved_raw_run_id
    local ans

    board_list="$(mktemp)"

    trap 'rm -f "${board_list:-}"' EXIT

    discover_boards "$board_list"

    echo
    echo "VyOS ARM64 Release Builder"
    echo "=========================="
    echo
    echo "VyOS base       : official ARM64 / ${VYOS_BRANCH}"
    echo "Armbian use     : hardware reference only"
    echo "Armbian ref     : ${ARMBIAN_REF}"
    echo "Armbian commit  : ${ARMBIAN_COMMIT}"
    echo "Workflow ref    : ${WORKFLOW_REF}"
    echo

    board="$(pick_board "$board_list")"

    [[ -n "$board" ]] ||
        die "no board selected"

    line="$(
        awk -F '\t' \
            -v b="$board" \
            '$1 == b { print; exit }' \
            "$board_list"
    )"

    board_name="$(
        printf '%s\n' "$line" |
            awk -F '\t' '{print $2}'
    )"

    status="$(
        printf '%s\n' "$line" |
            awk -F '\t' '{print $3}'
    )"

    extended_network="$(select_extended_network)"
    tailscale_subnet_router="$(select_tailscale_subnet_router)"
    kvm_over_ip="$(select_kvm_over_ip)"
    publish_release="$(select_publish_release)"

    echo
    echo "Verifying VyOS ARM64 raw-image input..."
    resolved_raw_run_id="$(
        "$SCRIPT_ROOT/tools/resolve-raw-run.sh" \
            --repo "$BUILD_REPO" \
            --workflow "$RAW_WORKFLOW" \
            --run-id "$RAW_RUN_ID"
    )"

    echo
    echo "Selected VyOS ARM64 build"
    echo "-------------------------"
    echo "Board           : $board"
    echo "Board name      : $board_name"
    echo "Armbian status  : $status"
    echo "HW reference    : automatic from VyOS kernel"
    if [[ "$hardware_reference" != "auto" ]]; then
        echo "Developer mode  : forced $hardware_reference"
    fi
    echo "Armbian commit  : $ARMBIAN_COMMIT"
    echo "VyOS branch     : $VYOS_BRANCH"
    echo "Extended net    : $extended_network"
    echo "Tailscale       : $tailscale_subnet_router"
    echo "KVM-over-IP     : $kvm_over_ip"
    echo "Raw workflow    : $RAW_WORKFLOW"
    echo "Raw run ID      : $resolved_raw_run_id (verified artifact)"
    echo "Publish release : $publish_release"
    echo "Dispatch mode   : $([[ "$DRY_RUN" == yes ]] && echo dry-run || echo live)"
    echo
    echo "Armbian supplies hardware metadata only."
    echo "Kernel and userspace are built from the VyOS ARM64 sources."
    echo

    if [[ "$DRY_RUN" == "yes" ]]; then
        echo "Dry-run complete. No workflow was dispatched."
        exit 0
    fi

    if [[ "$ASSUME_YES" != "yes" ]]; then
        read -r -p \
            "Trigger this GitHub Actions build now? [y/N]: " \
            ans

        [[ "${ans,,}" == "y" ||
           "${ans,,}" == "yes" ||
           "${ans,,}" == "j" ||
           "${ans,,}" == "ja" ]] || {
            echo "Cancelled."
            exit 0
        }
    fi

    gh workflow run "$WORKFLOW" \
        --repo "$BUILD_REPO" \
        --ref "$WORKFLOW_REF" \
        -f board="$board" \
        -f hardware_reference="$hardware_reference" \
        -f extended_network="$(workflow_boolean "$extended_network")" \
        -f tailscale_subnet_router="$(workflow_boolean "$tailscale_subnet_router")" \
        -f kvm_over_ip="$(workflow_boolean "$kvm_over_ip")" \
        -f armbian_ref="$ARMBIAN_COMMIT" \
        -f raw_run_id="$resolved_raw_run_id" \
        -f publish_release="$(workflow_boolean "$publish_release")"

    echo
    echo "Build dispatched."
    echo
    echo "Follow with:"
    echo \
        "gh run list --repo $BUILD_REPO --workflow $WORKFLOW --limit 5"
}

main "$@"
