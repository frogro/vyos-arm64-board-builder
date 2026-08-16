#!/usr/bin/env bash

ARMBIAN_REPO="${ARMBIAN_REPO:-https://github.com/armbian/build.git}"
ARMBIAN_BRANCH="${ARMBIAN_BRANCH:-main}"

armbian_source_dir() {
    printf '%s\n' "${ROOT_DIR}/cache/armbian-build"
}

armbian_fetch() {
    local dir
    local ref

    dir="$(armbian_source_dir)"
    ref="${ARMBIAN_REF:-${ARMBIAN_BRANCH:-main}}"

    if [[ -d "${dir}/.git" ]]; then
        info "Updating Armbian build framework..."
    else
        info "Cloning Armbian build framework..."
        rm -rf "${dir}"

        git clone \
            --no-checkout \
            --filter=blob:none \
            "${ARMBIAN_REPO}" \
            "${dir}"
    fi

    info "Resolving Armbian reference: ${ref}"

    #
    # Works for branch names, tags and explicit commit IDs.
    #
    if git -C "${dir}" fetch \
        --depth=1 \
        origin "${ref}" 2>/dev/null; then

        git -C "${dir}" reset --hard FETCH_HEAD
    else
        #
        # Some servers do not allow a raw SHA as a normal refspec.
        # Fetch the normal branch history and resolve the requested
        # commit from there.
        #
        git -C "${dir}" fetch \
            --depth=100 \
            origin "${ARMBIAN_BRANCH:-main}"

        git -C "${dir}" cat-file -e "${ref}^{commit}" 2>/dev/null ||
            die "Unable to resolve Armbian reference: ${ref}"

        git -C "${dir}" reset --hard "${ref}"
    fi

    local resolved
    resolved="$(git -C "${dir}" rev-parse HEAD)"

    info "Armbian resolved commit: ${resolved}"
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
