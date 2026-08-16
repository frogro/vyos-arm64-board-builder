#!/usr/bin/env bash

VYOS_BUILD_REPO="${VYOS_BUILD_REPO:-https://github.com/vyos/vyos-build.git}"
VYOS_BRANCH="${VYOS_BRANCH:-rolling}"

vyos_source_dir() {
    printf '%s\n' "${ROOT_DIR}/cache/vyos-build"
}

vyos_fetch() {
    local dir
    dir="$(vyos_source_dir)"

    if [[ -d "${dir}/.git" ]]; then
        info "Updating VyOS build repository..."
        git -C "${dir}" fetch --depth=1 origin "${VYOS_BRANCH}"
        git -C "${dir}" reset --hard FETCH_HEAD
    else
        info "Cloning VyOS build repository..."
        rm -rf "${dir}"
        git clone \
            --depth=1 \
            --branch "${VYOS_BRANCH}" \
            "${VYOS_BUILD_REPO}" \
            "${dir}"
    fi
}

vyos_arm64_config() {
    local dir
    dir="$(vyos_source_dir)"

    local config="${dir}/scripts/package-build/linux-kernel/config/arm64/vyos_defconfig"

    [[ -f "${config}" ]] || die "VyOS ARM64 kernel config not found: ${config}"

    printf '%s\n' "${config}"
}

vyos_kernel_version() {
    local dir
    dir="$(vyos_source_dir)"

    local defaults="${dir}/data/defaults.toml"

    [[ -f "${defaults}" ]] || die "VyOS defaults.toml not found"

    grep -E 'kernel_version|linux_kernel_version' "${defaults}" | head -1
}
