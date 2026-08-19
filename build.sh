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

    #
    # Match the official VyOS kernel build. The VyOS defconfig keeps
    # CONFIG_LOCALVERSION empty; the kernel flavor suffix is supplied
    # to Kbuild through LOCALVERSION.
    #
    local kernel_flavor="${KERNEL_FLAVOR:-vyos}"
    local kernel_localversion="${KERNEL_LOCALVERSION:-}"

    if [[ -z "${kernel_localversion}" ]]; then
        kernel_localversion="-${kernel_flavor}"
    fi

    #
    # Requested boot-media capabilities are a build input, not
    # board-specific generator logic. A board/profile/provider may
    # override this later without changing the Kconfig engine.
    #
    local boot_media="${BOOT_MEDIA:-sd,emmc,nvme,usb}"

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

    #
    # Reproduce the complete official VyOS ARM64 kernel configuration:
    #
    #   arm64/vyos_defconfig
    #       +
    #   all common config/*.config fragments
    #
    # This is architecture-wide and intentionally contains no
    # board-specific policy. The hardware delta is derived afterwards
    # from DTB + reference kernel metadata.
    #
    local vyos_baseline_dir="${ROOT_DIR}/work/build/${board}/vyos-baseline"
    local vyos_complete_config="${vyos_baseline_dir}/vyos-complete.config"

    mkdir -p "${vyos_baseline_dir}"

    vyos_arm64_complete_config \
        "${kernel_source}" \
        "${vyos_complete_config}"

    vyos_config="${vyos_complete_config}"

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

    #
    # Resolve the ARM64 toolchain once and use it for every Kconfig and
    # Kbuild phase. Compiler capability tests are part of Kconfig and
    # must not depend on the architecture of the build host.
    #
    local cross=""

    if [[ "$(uname -m)" != "aarch64" ]]; then
        cross="${CROSS_COMPILE:-aarch64-linux-gnu-}"

        command -v "${cross}gcc" >/dev/null 2>&1 ||
            die "ARM64 cross compiler not found: ${cross}gcc"
    fi

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
        CROSS_COMPILE="${cross}" \
        olddefconfig

    info "Building board DTB from VyOS kernel source..."

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        CROSS_COMPILE="${cross}" \
        "${dtb}"

    local built_dtb="${kbuild_out}/arch/arm64/boot/dts/${dtb}"

    [[ -f "${built_dtb}" ]] ||
        die "VyOS DTB build failed: ${built_dtb}"

    cp "${built_dtb}" "${dtb_out}/"

    info "DTB built: ${built_dtb}"

    echo
    info "Extracting active DT nodes..."

    local nodes_json="${dtb_out}/active-nodes.json"
    local supplier_graph="${dtb_out}/supplier-graph.json"

    python3 "${ROOT_DIR}/tools/dtb-active-nodes.py" \
        --dtb "${built_dtb}" \
        --output "${nodes_json}" \
        --graph-output "${supplier_graph}"

    [[ -s "${nodes_json}" ]] ||
        die "Active DT node extraction produced no output"

    [[ -s "${supplier_graph}" ]] ||
        die "DT supplier graph extraction produced no output"

    info "Active nodes written: ${nodes_json}"
    info "Supplier graph written: ${supplier_graph}"

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

    #
    # Device Tree compatibles describe devices instantiated directly
    # from DT. MFD parents can additionally create platform children
    # which have no independent DT compatible.
    #
    # Resolve those children from the active parent driver's variant
    # path and Linux MFD/Kbuild metadata. This is generic and contains
    # no board-specific or RK806-specific policy.
    #
    local mfd_map="${map_out}/mfd-child-config-map.tsv"
    local hardware_map="${map_out}/hardware-config-map.tsv"

    python3 "${ROOT_DIR}/tools/mfd-child-drivers.py" \
        --kernel "${kernel_source}" \
        --driver-map "${map_out}/compatible-config-map.tsv" \
        --output "${mfd_map}"

    cat \
        "${map_out}/compatible-config-map.tsv" \
        "${mfd_map}" |
        sort -u > "${hardware_map}"

    #
    # Resolve the concrete DT controller nodes which can reach the
    # requested boot media.  The discovery uses DT properties and
    # Linux driver metadata rather than board-specific addresses.
    #
    local boot_dep_out="${ROOT_DIR}/work/build/${board}/boot-deps"
    local boot_roots_out="${boot_dep_out}/roots"
    local boot_closure_out="${boot_dep_out}/closure"
    local mfd_services_out="${boot_dep_out}/mfd-services"
    local boot_symbols_out="${boot_dep_out}/symbols"

    rm -rf "${boot_dep_out}"

    python3 "${ROOT_DIR}/tools/dtb-boot-roots.py" \
        --dtb "${built_dtb}" \
        --graph "${supplier_graph}" \
        --driver-map "${map_out}/compatible-config-map.tsv" \
        --boot-media "${boot_media}" \
        --output-dir "${boot_roots_out}"

    local boot_roots_file="${boot_roots_out}/boot-roots.txt"

    [[ -s "${boot_roots_file}" ]] ||
        die "No DT boot roots discovered for requested media: ${boot_media}"

    local boot_root_args=()
    local boot_root

    while IFS= read -r boot_root; do
        [[ -n "${boot_root}" ]] || continue
        boot_root_args+=(--root-node "${boot_root}")
    done < "${boot_roots_file}"

    (( ${#boot_root_args[@]} > 0 )) ||
        die "Boot root argument list is empty"

    python3 "${ROOT_DIR}/tools/dtb-boot-closure.py" \
        --kernel "${kernel_source}" \
        --graph "${supplier_graph}" \
        --driver-map "${map_out}/compatible-config-map.tsv" \
        "${boot_root_args[@]}" \
        --output-dir "${boot_closure_out}"

    local boot_final="${boot_closure_out}/final"

    [[ -s "${boot_final}/supplier-closure.json" ]] ||
        die "Boot supplier closure missing"

    [[ -s "${boot_final}/driver-context.json" ]] ||
        die "Boot driver context missing"

    python3 "${ROOT_DIR}/tools/dtb-mfd-services.py" \
        --closure "${boot_final}/supplier-closure.json" \
        --driver-context "${boot_final}/driver-context.json" \
        --mfd-map "${mfd_map}" \
        --output-dir "${mfd_services_out}"

    [[ -s "${mfd_services_out}/mfd-service-context.json" ]] ||
        die "MFD boot service context missing"

    python3 "${ROOT_DIR}/tools/dtb-boot-symbols.py" \
        --driver-context "${boot_final}/driver-context.json" \
        --mfd-services "${mfd_services_out}/mfd-service-context.json" \
        --output-dir "${boot_symbols_out}"

    local boot_symbols="${boot_symbols_out}/boot-critical-symbols.txt"

    [[ -s "${boot_symbols}" ]] ||
        die "Boot-critical symbol derivation produced no symbols"

    echo
    echo "===== HARDWARE DERIVATION SUMMARY ====="
    echo "Board:          ${board}"
    echo "DTB:            ${built_dtb}"
    echo "Active nodes:   ${nodes_json}"
    echo "Supplier graph: ${supplier_graph}"
    echo "DT driver map:  ${map_out}/compatible-config-map.tsv"
    echo "MFD child map:  ${mfd_map}"
    echo "Hardware map:   ${hardware_map}"
    echo "Boot roots:     ${boot_roots_file}"
    echo "Boot closure:   ${boot_final}"
    echo "MFD services:   ${mfd_services_out}"
    echo "Boot symbols:   ${boot_symbols}"
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
        --driver-map "${hardware_map}" \
        --boot-critical-symbols "${boot_symbols}" \
        --boot-profile "${ROOT_DIR}/profiles/boot-media.conf" \
        --policy "${ROOT_DIR}/profiles/kernel-policy.conf" \
        --boot-media "${boot_media}" \
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
    cp "${final_config}" "${kbuild_out}/.config"

    #
    # Match the kernel release/ABI name used by official VyOS images.
    # The upstream VyOS defconfig leaves LOCALVERSION empty because the
    # package build adds the VyOS suffix externally. Our direct kernel
    # build must do that explicitly.
    #
    "${kernel_source}/scripts/config" \
        --file "${kbuild_out}/.config" \
        --set-str LOCALVERSION ""

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
        LOCALVERSION="${kernel_localversion}" \
        -j"${jobs}" \
        Image \
        Image.gz \
        modules \
        "${dtb}"

    local image="${kbuild_out}/arch/arm64/boot/Image"
    local image_gz="${kbuild_out}/arch/arm64/boot/Image.gz"
    local final_dtb="${kbuild_out}/arch/arm64/boot/dts/${dtb}"

    [[ -s "${image}" ]] ||
        die "Kernel Image was not generated"

    [[ -s "${image_gz}" ]] ||
        die "Compressed kernel Image.gz was not generated"

    [[ -s "${final_dtb}" ]] ||
        die "Final board DTB was not generated"

    local kernel_release
    kernel_release="$(
        make -s \
            -C "${kernel_source}" \
            O="${kbuild_out}" \
            ARCH=arm64 \
            CROSS_COMPILE="${cross}" \
            LOCALVERSION="${kernel_localversion}" \
            kernelrelease
    )"

    [[ -n "${kernel_release}" ]] ||
        die "Unable to determine final kernel release"

    local expected_kernel_release
    expected_kernel_release="${kernel_version}${kernel_localversion}"

    [[ "${kernel_release}" == "${expected_kernel_release}" ]] ||
        die "Kernel release mismatch: generated=${kernel_release}, expected=${expected_kernel_release}"

    echo
    info "Installing stripped kernel modules..."

    make \
        -C "${kernel_source}" \
        O="${kbuild_out}" \
        ARCH=arm64 \
        CROSS_COMPILE="${cross}" \
        LOCALVERSION="${kernel_localversion}" \
        INSTALL_MOD_PATH="${modules_out}" \
        INSTALL_MOD_STRIP=1 \
        modules_install

    local installed_modules="${modules_out}/lib/modules/${kernel_release}"

    [[ -d "${installed_modules}" ]] ||
        die "Installed kernel module tree missing: ${installed_modules}"

    #
    # modules_install creates development-only source/build links.
    # They do not belong in the VyOS runtime filesystem.
    #
    rm -f \
        "${installed_modules}/build" \
        "${installed_modules}/source"

    #
    # Restore the complete stock VyOS ARM64 module baseline.
    #
    # These are VyOS out-of-tree modules, not board-specific hardware
    # drivers. Build them against the final board kernel so MODVERSIONS,
    # signing and compression exactly match this kernel.
    #
    info "Building stock VyOS out-of-tree kernel modules..."

    "${ROOT_DIR}/tools/build-vyos-oot-modules.sh" \
        --vyos-tree "${ROOT_DIR}/cache/vyos-build" \
        --kernel-build "${kbuild_out}" \
        --modules-root "${modules_out}" \
        --kernel-release "${kernel_release}" \
        --localversion "${kernel_localversion}" \
        --cross-compile "${cross}" \
        --work-dir "${ROOT_DIR}/work/build/${board}/vyos-oot-modules"

    cp "${image}" \
        "${artifacts}/Image"

    cp "${image_gz}" \
        "${artifacts}/Image.gz"

    mkdir -p \
        "${artifacts}/dtb/$(dirname "${dtb}")"

    cp "${final_dtb}" \
        "${artifacts}/dtb/${dtb}"

    cp "${kbuild_out}/.config" \
        "${artifacts}/kernel.config"

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
    echo "Image.gz:       ${artifacts}/Image.gz"
    echo "DTB:            ${artifacts}/dtb/${dtb}"
    echo "Modules:        ${modules_out}/lib/modules"
    echo "Kernel config:  ${artifacts}/kernel.config"
    echo "Kernel release: ${kernel_release}"
    echo
    info "VyOS ARM64 board kernel build completed successfully."
}

main "$@"
