#!/bin/bash
# Publish image-owned setup helpers without running them or replacing user files.
set -euo pipefail
STAGE="/usr/local/share/vyos-arm64-firstboot"
# vyos-router is Type=simple: After= only orders process startup, not the
# configuration commit that creates login users. Wait without running setup.
ENTRY=""
for ((attempt=0; attempt<120; attempt++)); do
    if ENTRY="$(getent passwd vyos)"; then
        IFS=: read -r _ _ _ _ _ pending_home _ <<<"$ENTRY"
        # useradd publishes passwd before it creates/seeds the home. Creating
        # it here can make useradd skip /etc/skel and break interactive CLI.
        if [[ "$pending_home" == /* && -f "$pending_home/.profile" && -f "$pending_home/.bashrc" ]]; then
            break
        fi
    fi
    ENTRY=""
    sleep 1
done
if [[ -z "$ENTRY" ]]; then
    echo "VyOS user home not initialized after 120 seconds; cannot publish setup helpers" >&2
    exit 1
fi
IFS=: read -r _ _ VYOS_UID VYOS_GID _ HOME_DIR _ <<<"$ENTRY"
[[ "$VYOS_UID" =~ ^[0-9]+$ && "$VYOS_GID" =~ ^[0-9]+$ && "$HOME_DIR" == /* ]]
test -d "$HOME_DIR"
# Remove only our own old convenience link, never a user file or custom link.
firstboot_link="$HOME_DIR/dhcp-wan-ssh-setup.sh"
if [[ -L "$firstboot_link" && "$(readlink "$firstboot_link")" == "$STAGE/dhcp-wan-ssh-setup.sh" ]]; then
    rm -- "$firstboot_link"
fi
for script in ap-dhcp-wan-setup.sh modem-connect.sh set-locales.sh; do
    test -x "$STAGE/$script"
    target="$HOME_DIR/$script"
    # Keep custom files and links, including intentionally dangling symlinks.
    if [[ ! -e "$target" && ! -L "$target" ]]; then
        ln -s "$STAGE/$script" "$target"
        chown -h "$VYOS_UID:$VYOS_GID" "$target"
    fi
done
