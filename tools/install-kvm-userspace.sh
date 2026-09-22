#!/usr/bin/env bash
set -euo pipefail

ROOTFS="${1:?Usage: $0 <rootfs> <package-list>}"
PACKAGE_LIST="${2:?Usage: $0 <rootfs> <package-list>}"
# Historical filename; shared installation path for KVM and network packages.
PROFILE_NAME="${3:-kvm}"
case "$PROFILE_NAME" in kvm|network) ;; *) echo "Invalid userspace profile" >&2; exit 1 ;; esac

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

# Package installation in the offline rootfs must not start host-facing daemons.
POLICY="$ROOTFS/usr/sbin/policy-rc.d"
[[ ! -L "$POLICY" ]] || { echo "Unexpected policy-rc.d symlink" >&2; exit 1; }
POLICY_BACKUP=""
POLICY_CREATED=no
DNS_BACKUP=""
DNS_CREATED=no
APT_SOURCE=""
restore_dns()
{
    [[ -z "$APT_SOURCE" ]] || rm -f "$APT_SOURCE"
    if [[ -n "$POLICY_BACKUP" ]]; then
        cp -a "$POLICY_BACKUP" "$POLICY"
        rm -rf "$(dirname "$POLICY_BACKUP")"
    elif [[ "$POLICY_CREATED" == yes ]]; then
        rm -f "$POLICY"
    fi
    if [[ -n "$DNS_BACKUP" ]]; then
        rm -f "$ROOTFS/etc/resolv.conf"
        cp -a "$DNS_BACKUP" "$ROOTFS/etc/resolv.conf"
        rm -rf "$(dirname "$DNS_BACKUP")"
    elif [[ "$DNS_CREATED" == yes ]]; then
        rm -f "$ROOTFS/etc/resolv.conf"
    fi
}
trap restore_dns EXIT
if [[ -e "$POLICY" ]]; then
    POLICY_BACKUP="$(mktemp -d)/policy-rc.d"
    cp -a "$POLICY" "$POLICY_BACKUP"
else
    POLICY_CREATED=yes
fi
printf '#!/bin/sh\nexit 101\n' > "$POLICY"
chmod 0755 "$POLICY"

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

# Release images may intentionally contain no APT sources. Use only the
# matching Debian base during assembly and remove the temporary source again.
if ! grep -RhE '^[[:space:]]*(deb[[:space:]]|Types:.*deb)' \
    "$ROOTFS/etc/apt/sources.list" "$ROOTFS/etc/apt/sources.list.d" 2>/dev/null | grep -q .; then
    libc_version="$(chroot "$ROOTFS" dpkg-query -W -f='${Version}' libc6)"
    case "$libc_version" in 2.36-*) ;; *)
        echo "ERROR: no APT sources and unsupported Debian base: libc6 $libc_version" >&2
        exit 1 ;;
    esac
    [[ -f "$ROOTFS/usr/share/keyrings/debian-archive-keyring.gpg" ]] || exit 1
    install -d -m 0755 "$ROOTFS/etc/apt/sources.list.d"
    APT_SOURCE="$(mktemp "$ROOTFS/etc/apt/sources.list.d/builder-XXXXXX.list")"
    chmod 0644 "$APT_SOURCE"
    cat > "$APT_SOURCE" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian bookworm main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian-security bookworm-security main
SOURCES
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
    printf '# %s userspace packages installed in the image\n' "$PROFILE_NAME"
    chroot "$ROOTFS" dpkg-query -W -f='${binary:Package}\t${Version}\n' \
        "${PACKAGES[@]}"
} > "$PROFILE_DIR/$PROFILE_NAME-userspace-packages.txt"

chroot "$ROOTFS" apt-get clean
rm -rf "$ROOTFS/var/lib/apt/lists/"*

echo "Installed $PROFILE_NAME userspace packages: ${PACKAGES[*]}"
