#!/usr/bin/env bash

print_banner() {
    cat <<'BANNER'
============================================================
 VyOS ARM64 Board Builder
============================================================

Build board-specific VyOS ARM64 images using:

  - official VyOS ARM64 userspace
  - official VyOS Linux kernel source/configuration
  - hardware information derived from Armbian/Core
  - minimal board-specific kernel config additions
  - minimal required board patches
  - board-specific DTB / firmware / bootloader

Armbian is used as a hardware reference only.
The resulting image does NOT use an Armbian kernel.

BANNER
}

info() {
    printf '[INFO] %s\n' "$*"
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

die() {
    printf '[ERROR] %s\n' "$*" >&2
    exit 1
}

select_board() {
    local board

    printf 'Enter Armbian BOARD identifier\n' >&2
    printf 'Examples: rock-5b, orangepi5, nanopi-r6s\n\n' >&2
    read -r -p 'BOARD: ' board

    [[ -n "${board}" ]] || die "No board selected"

    printf '%s\n' "${board}"
}
