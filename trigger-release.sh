#!/usr/bin/env bash
set -euo pipefail

BUILD_REPO="${BUILD_REPO:-frogro/vyos-arm64-board-builder}"
WORKFLOW="${WORKFLOW:-build-board-candidate.yml}"
WORKFLOW_REF="${WORKFLOW_REF:-main}"

ARMBIAN_REF="${ARMBIAN_REF:-main}"
ARMBIAN_REMOTE="${ARMBIAN_REMOTE:-https://github.com/armbian/build.git}"

VYOS_BRANCH="${VYOS_BRANCH:-rolling}"

RAW_RUN_ID="${RAW_RUN_ID:-32008814114}"
PUBLISH_RELEASE="${PUBLISH_RELEASE:-true}"
BOOT_BRANCH="${BOOT_BRANCH:-auto}"

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

for cmd in git gh grep sed sort awk mktemp; do
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

pick_branch() {
    local targets="$1"
    local default=""
    local -a branches=()
    local item
    local i
    local choice

    IFS=',' read -r -a branches <<< "$targets"

    for item in "${branches[@]}"; do
        if [[ "$item" == "current" ]]; then
            default="current"
            break
        fi
    done

    if [[ -z "$default" ]]; then
        default="${branches[0]}"
    fi

    if [[ "${#branches[@]}" -eq 1 ]]; then
        printf '%s\n' "${branches[0]}"
        return
    fi

    echo >&2
    echo "Available Armbian hardware reference branches:" >&2

    i=1

    for item in "${branches[@]}"; do
        printf '  %d) %s' "$i" "$item" >&2

        if [[ "$item" == "$default" ]]; then
            printf ' [default]' >&2
        fi

        printf '\n' >&2

        ((i++))
    done

    while true; do
        read -r -p \
            "Select branch [$default]: " \
            choice

        if [[ -z "$choice" ]]; then
            printf '%s\n' "$default"
            return
        fi

        if [[ "$choice" =~ ^[0-9]+$ ]] &&
           (( choice >= 1 && choice <= ${#branches[@]} ))
        then
            printf '%s\n' \
                "${branches[$((choice - 1))]}"

            return
        fi

        for item in "${branches[@]}"; do
            if [[ "$choice" == "$item" ]]; then
                printf '%s\n' "$item"
                return
            fi
        done
    done
}

main() {
    sync_armbian_metadata

    local board_list
    local board
    local line
    local board_name
    local status
    local targets
    local branch
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

    targets="$(
        printf '%s\n' "$line" |
            awk -F '\t' '{print $4}'
    )"

    branch="$(pick_branch "$targets")"

    echo
    echo "Selected VyOS ARM64 build"
    echo "-------------------------"
    echo "Board           : $board"
    echo "Board name      : $board_name"
    echo "Armbian status  : $status"
    echo "HW reference    : $branch"
    echo "Armbian commit  : $ARMBIAN_COMMIT"
    echo "VyOS branch     : $VYOS_BRANCH"
    echo
    echo "Armbian supplies hardware metadata only."
    echo "Kernel and userspace are built from the VyOS ARM64 sources."
    echo

    read -r -p \
        "Trigger GitHub Actions release build now? [y/N]: " \
        ans

    [[ "${ans,,}" == "y" ||
       "${ans,,}" == "yes" ||
       "${ans,,}" == "j" ||
       "${ans,,}" == "ja" ]] || {
        echo "Cancelled."
        exit 0
    }

    gh workflow run "$WORKFLOW" \
        --repo "$BUILD_REPO" \
        --ref "$WORKFLOW_REF" \
        -f board="$board" \
        -f branch="$branch" \
        -f boot_branch="$BOOT_BRANCH" \
        -f raw_run_id="$RAW_RUN_ID" \
        -f publish_release="$PUBLISH_RELEASE"

    echo
    echo "Build dispatched."
    echo
    echo "Follow with:"
    echo \
        "gh run list --repo $BUILD_REPO --workflow $WORKFLOW --limit 5"
}

main "$@"
