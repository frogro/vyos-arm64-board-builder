#!/usr/bin/env bash

armbian_resolve_board() {
    local board="$1"
    local branch="${2:-current}"

    local armbian_dir
    local out
    local envfile
    local kernel_config

    armbian_dir="$(armbian_source_dir)"
    out="${ROOT_DIR}/work/build/${board}/armbian-effective"
    envfile="${out}/config.env"

    "${ROOT_DIR}/tools/resolve-armbian-effective-config.sh" \
        "${board}" \
        "${branch}" \
        "${out}"

    [[ -s "${envfile}" ]] || {
        die "Effective Armbian configuration missing: ${envfile}"
    }

    # shellcheck disable=SC1090
    source "${envfile}"

    kernel_config="${armbian_dir}/config/kernel/linux-${LINUXFAMILY}-${branch}.config"

    if [[ ! -f "${kernel_config}" ]]; then
        kernel_config=""
    fi

    printf 'BOARD=%s\n' "${BOARD}"
    printf 'BRANCH=%s\n' "${BRANCH}"
    printf 'BOARD_NAME=%s\n' "${BOARD_NAME}"
    printf 'BOARD_VENDOR=%s\n' "${BOARD_VENDOR}"
    printf 'BOARDFAMILY=%s\n' "${BOARDFAMILY}"
    printf 'LINUXFAMILY=%s\n' "${LINUXFAMILY}"
    printf 'BOARD_FILE=%s\n' "$(armbian_find_board_file "${board}")"
    printf 'DTB=%s\n' "${BOOT_FDT_FILE}"
    printf 'BOOTCONFIG=%s\n' "${BOOTCONFIG}"
    printf 'BOOTSOURCE=%s\n' "${BOOTSOURCE}"
    printf 'BOOTBRANCH=%s\n' "${BOOTBRANCH}"
    printf 'BOOTPATCHDIR=%s\n' "${BOOTPATCHDIR}"
    printf 'KERNEL_CONFIG=%s\n' "${kernel_config}"
    printf 'ARMBIAN_COMMIT=%s\n' "${ARMBIAN_COMMIT}"
}
