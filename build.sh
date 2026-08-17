#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "${ROOT_DIR}/lib/ui.sh"
source "${ROOT_DIR}/sources/armbian.sh"
source "${ROOT_DIR}/sources/armbian-resolver.sh"
source "${ROOT_DIR}/sources/vyos.sh"

extract_board_var() {
    local file="$1"
    local var="$2"

    grep -m1 -E \
        "(^|[[:space:]])(declare[[:space:]]+-g[[:space:]]+)?${var}=" \
        "$file" \
        2>/dev/null |
        sed -E \
            "s/.*${var}=[\"']?([^\"']+)[\"']?.*/\1/" ||
        true
}

find_reference_config() {
    local board_file="$1"
    local branch="$2"
    local armbian_dir
    local family
    local candidate

    armbian_dir="$(armbian_source_dir)"
    family="$(extract_board_var "$board_file" BOARDFAMILY)"

    [[ -n "$family" ]] || return 1

    candidate="${armbian_dir}/config/kernel/linux-${family}-${branch}.config"

    if [[ -f "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    #
    # Never guess a reference config.  Using an unrelated Armbian
    # kernel configuration would silently generate a bogus hardware
    # delta.  Boards whose BOARDFAMILY differs from their kernel
    # LINUXFAMILY will be resolved explicitly by the generic resolver.
    #
    return 1
}

find_vyos_kernel_source() {
    local version="$1"
    local dir="${ROOT_DIR}/cache/linux-vyos/linux-${version}"

    [[ -d "$dir" ]] || return 1

    printf '%s\n' "$dir"
}

main() {
    print_banner

    local board="${BOARD:-}"
    local branch="${HW_BRANCH:-${BRANCH:-current}}"
    local vyos_branch="${VYOS_BRANCH:-rolling}"

    local board_file
    local board_name
    local family
    local dtb
    local reference_config
    local vyos_config
    local kernel_version
    local kernel_source

    armbian_fetch
    vyos_fetch

    if [[ -z "$board" ]]; then
        board="$(select_board)"
    fi

    info "Validating board '${board}' against Armbian..."

    if ! board_file="$(armbian_validate_board "$board")"; then
        echo
        warn "Board '${board}' was not found in the current Armbian board database."
        echo
        echo "Some available boards:"
        armbian_list_boards | head -30
        echo
        die "Unknown Armbian board identifier: ${board}"
    fi

    board_name="$(extract_board_var "$board_file" BOARD_NAME)"
    family="$(extract_board_var "$board_file" BOARDFAMILY)"
    dtb="$(extract_board_var "$board_file" BOOT_FDT_FILE)"

    vyos_config="$(vyos_arm64_config)"

    kernel_version="$(
        vyos_kernel_version |
        grep -oE '[0-9]+\.[0-9]+\.[0-9]+' |
        head -1
    )"

    [[ -n "$kernel_version" ]] ||
        die "Unable to determine VyOS kernel version"

    #
    # Prepare the exact upstream kernel version used by VyOS and apply
    # the official VyOS kernel patch set before doing any board-specific
    # Kconfig derivation. VyOS patches may themselves introduce Kconfig
    # symbols, so this must happen first.
    #
    vyos_kernel_prepare "${kernel_version}"

    if ! kernel_source="$(find_vyos_kernel_source "$kernel_version")"; then
        die "Prepared VyOS kernel source not found: cache/linux-vyos/linux-${kernel_version}"
    fi

    reference_config="$(find_reference_config "$board_file" "$branch" || true)"

    echo
    info "Board:          ${board}"
    info "Board name:     ${board_name:-unknown}"
    info "Board family:   ${family:-unknown}"
    info "HW branch:      ${branch}"
    info "Board DTB:      ${dtb:-unknown}"
    info "VyOS branch:    ${vyos_branch}"
    info "VyOS kernel:    ${kernel_version}"
    info "VyOS config:    ${vyos_config}"
    info "Kernel source:  ${kernel_source}"

    if [[ -n "$reference_config" ]]; then
        info "Reference cfg:  ${reference_config}"
    else
        warn "No unique Armbian reference config resolved yet."
    fi

    echo

    [[ -n "$dtb" ]] ||
        die "BOOT_FDT_FILE not found in Armbian board definition"

    [[ -n "$reference_config" ]] ||
        die "Unable to resolve Armbian reference kernel config"

    info "Board metadata resolution successful."

    echo
    info "Building VyOS DTB..."

    local dtb_out="${ROOT_DIR}/work/build/${board}/dtb"
    local kbuild_out="${ROOT_DIR}/work/build/${board}/kernel"

    rm -rf "${dtb_out}" "${kbuild_out}"
    mkdir -p "${dtb_out}" "${kbuild_out}"

    info "Preparing official VyOS ARM64 kernel config..."

    cp "${vyos_config}" "${kbuild_out}/.config"

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        olddefconfig

    info "Building board DTB from VyOS kernel source..."

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        "${dtb}"

    local built_dtb="${kbuild_out}/arch/arm64/boot/dts/${dtb}"

    [[ -f "${built_dtb}" ]] ||
        die "VyOS DTB build failed: ${built_dtb}"

    cp "${built_dtb}" "${dtb_out}/"

    info "DTB built: ${built_dtb}"

    echo
    info "Extracting active DT nodes..."

    local nodes_json="${dtb_out}/active-nodes.json"

    python3 "${ROOT_DIR}/tools/dtb-active-nodes.py" \
        --dtb "${built_dtb}" \
        --output "${nodes_json}"

    [[ -s "${nodes_json}" ]] ||
        die "Active DT node extraction produced no output"

    info "Active nodes written: ${nodes_json}"

    echo
    info "Extracting active DT compatibles..."

    local compatibles="${dtb_out}/active-compatibles.txt"

    "${ROOT_DIR}/tools/dtb-active-compatibles.sh" \
        "${built_dtb}" \
        "${compatibles}"

    [[ -s "${compatibles}" ]] ||
        die "Active compatible extraction produced no output"

    info "Active compatibles written: ${compatibles}"

    echo
    info "Mapping DT compatibles to kernel drivers..."

    local map_out="${ROOT_DIR}/work/build/${board}/driver-map"

    rm -rf "${map_out}"
    mkdir -p "${map_out}"

    "${ROOT_DIR}/tools/map-dtb-of-drivers.sh" \
        "${kernel_source}" \
        "${compatibles}" \
        "${reference_config}" \
        "${map_out}"

    [[ -f "${map_out}/compatible-config-map.tsv" ]] ||
        die "Driver mapping did not produce compatible-config-map.tsv"

    echo
    echo "===== HARDWARE DERIVATION SUMMARY ====="
    echo "Board:          ${board}"
    echo "DTB:            ${built_dtb}"
    echo "Active nodes:   ${nodes_json}"
    echo "Driver map:     ${map_out}/compatible-config-map.tsv"
    echo "Reference cfg:  ${reference_config}"

    echo
    info "Generating board-specific VyOS kernel configuration..."

    local config_out="${ROOT_DIR}/work/build/${board}/config"

    rm -rf "${config_out}"
    mkdir -p "${config_out}"

    python3 "${ROOT_DIR}/tools/generate-board-config.py" \
        --kernel "${kernel_source}" \
        --vyos-config "${vyos_config}" \
        --reference-config "${reference_config}" \
        --driver-map "${map_out}/compatible-config-map.tsv" \
        --boot-profile "${ROOT_DIR}/profiles/boot-media.conf" \
        --policy "${ROOT_DIR}/profiles/kernel-policy.conf" \
        --boot-media sd,emmc,nvme,usb \
        --output-dir "${config_out}"

    [[ -f "${config_out}/generated-board.config" ]] ||
        die "Board config generation failed"

    [[ -f "${config_out}/generated-final.config" ]] ||
        die "Final kernel config was not generated"

    [[ -f "${config_out}/validation.txt" ]] ||
        die "Kernel config validation output missing"

    if grep -q '^FAIL' "${config_out}/validation.txt"; then
        echo
        echo "===== VALIDATION FAILURES ====="
        grep '^FAIL' "${config_out}/validation.txt"
        die "Board kernel configuration validation failed"
    fi

    if [[ -s "${config_out}/kconfig-closure/unresolved.txt" ]]; then
        echo
        echo "===== UNRESOLVED KCONFIG DEPENDENCIES ====="
        cat "${config_out}/kconfig-closure/unresolved.txt"
        die "Unresolved Kconfig dependencies remain"
    fi

    echo
    echo "===== BOARD CONFIG SUMMARY ====="
    echo "Board fragment: ${config_out}/generated-board.config"
    echo "Final config:    ${config_out}/generated-final.config"
    echo "Validation:      ${config_out}/validation.txt"
    echo
    echo "Validation FAIL: 0"
    echo "Kconfig unresolved: 0"

    echo
    info "Hardware/config derivation completed successfully."

    echo
    info "Preparing final VyOS ARM64 kernel build..."

    local final_config="${config_out}/generated-final.config"
    local artifacts="${ROOT_DIR}/work/build/${board}/artifacts"
    local modules_out="${ROOT_DIR}/work/build/${board}/modules"

    rm -rf "${artifacts}" "${modules_out}"
    mkdir -p "${artifacts}" "${modules_out}"

    #
    # The earlier Kbuild tree was only used to compile the stock-VyOS
    # DTB for hardware discovery. Replace its config now with the fully
    # resolved board-specific VyOS config.
    #
    #
    # Native ARM64 runners need no cross prefix. x86_64 builders use
    # the standard Debian/Ubuntu AArch64 GNU toolchain.
    #
    # IMPORTANT: Kconfig must use the exact same toolchain as the
    # subsequent kernel build. Compiler capability tests influence
    # ARM64 Kconfig symbols (MTE, BTI, etc.).
    #
    local cross=""

    if [[ "$(uname -m)" != "aarch64" ]]; then
        cross="${CROSS_COMPILE:-aarch64-linux-gnu-}"

        command -v "${cross}gcc" >/dev/null 2>&1 ||
            die "ARM64 cross compiler not found: ${cross}gcc"
    fi

    cp "${final_config}" "${kbuild_out}/.config"

    #
    # Match the kernel release/ABI name used by official VyOS images.
    # The upstream VyOS defconfig leaves LOCALVERSION empty because the
    # package build adds the VyOS suffix externally. Our direct kernel
    # build must do that explicitly.
    #
    "${kernel_source}/scripts/config" \
        --file "${kbuild_out}/.config" \
        --set-str LOCALVERSION "-vyos"

    "${kernel_source}/scripts/config" \
        --file "${kbuild_out}/.config" \
        --disable LOCALVERSION_AUTO

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        CROSS_COMPILE="${cross}" \
        olddefconfig

    local jobs="${JOBS:-$(nproc)}"

    echo
    info "Building VyOS ARM64 kernel (${jobs} jobs)..."

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        CROSS_COMPILE="${cross}" \
        -j"${jobs}" \
        Image \
        modules \
        "${dtb}"

    local image="${kbuild_out}/arch/arm64/boot/Image"
    local final_dtb="${kbuild_out}/arch/arm64/boot/dts/${dtb}"

    [[ -s "${image}" ]] ||
        die "Kernel Image was not generated"

    [[ -s "${final_dtb}" ]] ||
        die "Final board DTB was not generated"

    echo
    info "Installing kernel modules..."

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        CROSS_COMPILE="${cross}" \
        INSTALL_MOD_PATH="${modules_out}" \
        modules_install

    cp "${image}" \
        "${artifacts}/Image"

    mkdir -p \
        "${artifacts}/dtb/$(dirname "${dtb}")"

    cp "${final_dtb}" \
        "${artifacts}/dtb/${dtb}"

    cp "${kbuild_out}/.config" \
        "${artifacts}/kernel.config"

    local kernel_release
    kernel_release="$(
        make -s \
            -C "${kernel_source}" \
            O="${kbuild_out}" \
            ARCH=arm64 \
            CROSS_COMPILE="${cross}" \
            kernelrelease
    )"

    [[ -n "${kernel_release}" ]] ||
        die "Unable to determine final kernel release"

    printf '%s\n' "${kernel_release}" > "${artifacts}/kernel.release"

    if [[ -f "${kbuild_out}/System.map" ]]; then
        cp "${kbuild_out}/System.map" \
            "${artifacts}/System.map"
    fi

    echo
    echo "===== KERNEL BUILD SUMMARY ====="
    echo "Board:          ${board}"
    echo "Kernel:         ${kernel_version}"
    echo "Image:          ${artifacts}/Image"
    echo "DTB:            ${artifacts}/dtb/${dtb}"
    echo "Modules:        ${modules_out}/lib/modules"
    echo "Kernel config:  ${artifacts}/kernel.config"
    echo "Kernel release: ${kernel_release}"
    echo
    info "VyOS ARM64 board kernel build completed successfully."
}

main "$@"
