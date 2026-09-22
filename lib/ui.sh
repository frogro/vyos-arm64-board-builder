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

select_extended_network() {
    local requested="${EXTENDED_NETWORK:-}"

    if [[ -n "$requested" ]]; then
        case "${requested,,}" in
            1|true|yes|y|on|enabled)
                printf 'yes\n'
                return 0
                ;;
            0|false|no|n|off|disabled)
                printf 'no\n'
                return 0
                ;;
            *)
                die "Invalid EXTENDED_NETWORK value: $requested"
                ;;
        esac
    fi

    # Non-interactive builds must be deterministic and must never block.
    if [[ ! -t 0 ]]; then
        printf 'no\n'
        return 0
    fi

    cat >&2 <<'NOTICE'

Optional Extended Network Support
---------------------------------
This option adds a broad, curated set of WWAN, Wi-Fi and Ethernet
drivers and firmware that are not enabled by stock VyOS. Most of these
components will not be relevant to any single system. Enabling the bundle
increases image size; drivers loaded for detected hardware use additional
memory, and every additional driver or firmware component increases the
system's attack surface.

This is a convenience-oriented profile. Industrial and security-sensitive
deployments should instead use a selective driver and firmware set.

Review the maintained list before enabling it:
https://github.com/frogro/vyos-arm64-board-builder/blob/generic-board-image-pipeline/docs/extended-network-drivers.md
NOTICE

    read -r -p \
        'Include common additional network drivers and firmware? [y/N] ' \
        requested

    case "${requested,,}" in
        y|yes)
            printf 'yes\n'
            ;;
        *)
            printf 'no\n'
            ;;
    esac
}

select_tailscale_subnet_router() {
    local requested="${TAILSCALE_SUBNET_ROUTER:-}"

    if [[ -n "$requested" ]]; then
        case "${requested,,}" in
            1|true|yes|y|on|enabled)
                printf 'yes\n'
                return 0
                ;;
            0|false|no|n|off|disabled)
                printf 'no\n'
                return 0
                ;;
            *)
                die "Invalid TAILSCALE_SUBNET_ROUTER value: $requested"
                ;;
        esac
    fi

    if [[ ! -t 0 ]]; then
        printf 'no\n'
        return 0
    fi

    cat >&2 <<'NOTICE'

Optional Tailscale Subnet Router Support
----------------------------------------
This profile adds only the kernel validation, persistent service wrapper and
runtime readiness tooling for a later local Tailscale installation. It does
not install Tailscale, authenticate a node or advertise any routes.
NOTICE

    read -r -p 'Prepare this image as a Tailscale subnet router? [y/N] ' requested

    case "${requested,,}" in
        y|yes) printf 'yes\n' ;;
        *) printf 'no\n' ;;
    esac
}

select_kvm_over_ip() {
    local requested="${KVM_OVER_IP:-}"

    if [[ -n "$requested" ]]; then
        case "${requested,,}" in
            1|true|yes|y|on|enabled) printf 'yes\n'; return 0 ;;
            0|false|no|n|off|disabled) printf 'no\n'; return 0 ;;
            *) die "Invalid KVM_OVER_IP value: $requested" ;;
        esac
    fi

    if [[ ! -t 0 ]]; then
        printf 'no\n'
        return 0
    fi

    cat >&2 <<'NOTICE'

Optional KVM-over-IP Preparation
--------------------------------
This profile enables generic V4L2/UVC capture, USB capture audio and HID gadget
kernel capabilities, installs v4l-utils and GStreamer, adds persistent
readiness tooling and includes a pinned, source-built ARM64 µStreamer binary.
Exact-board providers may add an internal HDMI receiver and OTG settings.
It does not automatically start the streamer or open a network port.
NOTICE

    read -r -p 'Prepare this image for KVM-over-IP? [y/N] ' requested
    case "${requested,,}" in
        y|yes) printf 'yes\n' ;;
        *) printf 'no\n' ;;
    esac
}
