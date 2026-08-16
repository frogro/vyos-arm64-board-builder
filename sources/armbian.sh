#!/usr/bin/env bash

ARMBIAN_REPO="${ARMBIAN_REPO:-https://github.com/armbian/build.git}"
ARMBIAN_BRANCH="${ARMBIAN_BRANCH:-main}"

armbian_source_dir() {
    printf '%s\n' "${ROOT_DIR}/cache/armbian-build"
}

armbian_fetch() {
    local dir
    dir="$(armbian_source_dir)"

    if [[ -d "${dir}/.git" ]]; then
        info "Updating Armbian build framework..."
        git -C "${dir}" fetch --depth=1 origin "${ARMBIAN_BRANCH}"
        git -C "${dir}" reset --hard FETCH_HEAD
    else
        info "Cloning Armbian build framework..."
        rm -rf "${dir}"
        git clone \
            --depth=1 \
            --branch "${ARMBIAN_BRANCH}" \
            "${ARMBIAN_REPO}" \
            "${dir}"
    fi
}

armbian_find_board_file() {
    local board="$1"
    local dir
    dir="$(armbian_source_dir)"

    find "${dir}/config/boards" \
        -maxdepth 1 \
        -type f \
        -name "${board}.*" \
        -print -quit
}

armbian_validate_board() {
    local board="$1"
    local file

    file="$(armbian_find_board_file "${board}")"

    if [[ -z "${file}" ]]; then
        return 1
    fi

    printf '%s\n' "${file}"
}

armbian_list_boards() {
    local dir
    dir="$(armbian_source_dir)"

    find "${dir}/config/boards" \
        -maxdepth 1 \
        -type f \
        -printf '%f\n' |
        sed -E 's/\.(conf|csc|eos|tvb|wip)$//' |
        sort -u
}
