#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "${ROOT_DIR}/lib/ui.sh"
source "${ROOT_DIR}/sources/armbian.sh"
source "${ROOT_DIR}/sources/armbian-resolver.sh"
source "${ROOT_DIR}/sources/vyos.sh"

main() {
    print_banner

    local board="${BOARD:-}"
    local hw_source="${HW_SOURCE:-armbian-edge}"
    local vyos_branch="${VYOS_BRANCH:-rolling}"
    local board_file

    armbian_fetch

    if [[ -z "${board}" ]]; then
        board="$(select_board)"
    fi

    info "Validating board '${board}' against Armbian..."

    if ! board_file="$(armbian_validate_board "${board}")"; then
        echo
        warn "Board '${board}' was not found in the current Armbian board database."
        echo
        echo "Some available boards:"
        armbian_list_boards | head -30
        echo
        die "Unknown Armbian board identifier: ${board}"
    fi

    echo
    info "Board:       ${board}"
    info "Board file:  ${board_file}"
    info "HW source:   ${hw_source}"
    info "VyOS branch: ${vyos_branch}"
    echo

    info "Board validation successful."

    echo
    echo "----- Armbian board definition -----"
    sed -n '1,120p' "${board_file}"
    echo "------------------------------------"
    echo

    warn "Hardware derivation is not implemented yet."
}

main "$@"
