#!/usr/bin/env bash

armbian_resolve_board() {
    local board="$1"
    local branch="${2:-edge}"

    local armbian_dir
    local board_file
    local family
    local dtb
    local kernel_config

    armbian_dir="$(armbian_source_dir)"

    board_file="$(armbian_find_board_file "${board}")"

    [[ -n "${board_file}" ]] || {
        die "Unable to resolve Armbian board: ${board}"
    }

    family="$(
        grep -E '^[[:space:]]*(declare -g )?BOARDFAMILY=' "${board_file}" |
        head -1 |
        sed -E 's/.*BOARDFAMILY=["'"'"']?([^"'"'"']+)["'"'"']?.*/\1/'
    )"

    dtb="$(
        grep -E '^[[:space:]]*BOOT_FDT_FILE=' "${board_file}" |
        head -1 |
        sed -E 's/.*BOOT_FDT_FILE=["'"'"']?([^"'"'"']+)["'"'"']?.*/\1/'
    )"

    case "${family}:${branch}" in
        rockchip-rk3588:edge)
            kernel_config="${armbian_dir}/config/kernel/linux-rockchip64-edge.config"
            ;;
        *)
            kernel_config=""
            ;;
    esac

    echo "BOARD=${board}"
    echo "BRANCH=${branch}"
    echo "BOARDFAMILY=${family}"
    echo "BOARD_FILE=${board_file}"
    echo "DTB=${dtb}"
    echo "KERNEL_CONFIG=${kernel_config}"
}
