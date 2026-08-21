#!/usr/bin/env bash
set -euo pipefail

ROOTFS="${1:?Usage: $0 <rootfs> <package-list>}"
PACKAGE_LIST="${2:?Usage: $0 <rootfs> <package-list>}"

ROOTFS="$(readlink -f "$ROOTFS")"
[[ -d "$ROOTFS" && "$ROOTFS" != / ]] || {
    echo "ERROR: refusing unsafe root filesystem path: $ROOTFS" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || {
    echo "ERROR: install-kvm-userspace.sh must run as root" >&2
    exit 1
}
[[ -x "$ROOTFS/usr/bin/apt-get" && -x "$ROOTFS/usr/bin/dpkg-query" ]] || {
    echo "ERROR: VyOS root filesystem has no apt/dpkg tools" >&2
    exit 1
}
[[ -s "$PACKAGE_LIST" ]] || {
    echo "ERROR: KVM userspace package list missing: $PACKAGE_LIST" >&2
    exit 1
}
for mountpoint_path in dev proc sys run; do
    mountpoint -q "$ROOTFS/$mountpoint_path" || {
        echo "ERROR: chroot mount missing: $ROOTFS/$mountpoint_path" >&2
        exit 1
    }
done

mapfile -t PACKAGES < <(
    sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$PACKAGE_LIST"
)
(( ${#PACKAGES[@]} > 0 )) || {
    echo "ERROR: KVM userspace package list is empty" >&2
    exit 1
}

DNS_BACKUP=""
DNS_CREATED=no
restore_dns()
{
    if [[ -n "$DNS_BACKUP" ]]; then
        rm -f "$ROOTFS/etc/resolv.conf"
        cp -a "$DNS_BACKUP" "$ROOTFS/etc/resolv.conf"
        rm -rf "$(dirname "$DNS_BACKUP")"
    elif [[ "$DNS_CREATED" == yes ]]; then
        rm -f "$ROOTFS/etc/resolv.conf"
    fi
}
trap restore_dns EXIT

if [[ -L "$ROOTFS/etc/resolv.conf" ]]; then
    dns_link="$(readlink "$ROOTFS/etc/resolv.conf")"
    if [[ "$dns_link" == /* ]]; then
        dns_target="$ROOTFS$dns_link"
    else
        dns_target="$(dirname "$ROOTFS/etc/resolv.conf")/$dns_link"
    fi
    install -D -m 0644 /etc/resolv.conf "$dns_target"
else
    if [[ -e "$ROOTFS/etc/resolv.conf" ]]; then
        DNS_BACKUP="$(mktemp -d)/resolv.conf"
        cp -a "$ROOTFS/etc/resolv.conf" "$DNS_BACKUP"
    else
        DNS_CREATED=yes
    fi
    install -D -m 0644 /etc/resolv.conf "$ROOTFS/etc/resolv.conf"
fi

chroot "$ROOTFS" /usr/bin/env \
    DEBIAN_FRONTEND=noninteractive \
    PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    apt-get update

chroot "$ROOTFS" /usr/bin/env \
    DEBIAN_FRONTEND=noninteractive \
    PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    apt-get install -y --no-install-recommends "${PACKAGES[@]}"

PROFILE_DIR="$ROOTFS/usr/share/vyos-arm64-board-builder"
install -d -m 0755 "$PROFILE_DIR"
{
    printf '# KVM-over-IP userspace packages installed in the image\n'
    chroot "$ROOTFS" dpkg-query -W -f='${binary:Package}\t${Version}\n' \
        "${PACKAGES[@]}"
} > "$PROFILE_DIR/kvm-userspace-packages.txt"

chroot "$ROOTFS" apt-get clean
rm -rf "$ROOTFS/var/lib/apt/lists/"*

echo "Installed KVM-over-IP userspace packages: ${PACKAGES[*]}"
