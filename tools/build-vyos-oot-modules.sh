#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  build-vyos-oot-modules.sh \
      --vyos-tree PATH \
      --kernel-build PATH \
      --modules-root PATH \
      --kernel-release RELEASE \
      --localversion SUFFIX \
      [--cross-compile PREFIX] \
      [--work-dir PATH]

Build the stock VyOS out-of-tree ARM64 kernel modules against an already
built final VyOS/board kernel.

This tool is intentionally board-independent. It receives the final kernel
build and module tree as inputs and does not contain SBC-specific policy.
USAGE
}

VYOS_TREE=""
KBUILD=""
MODULES_ROOT=""
KREL=""
LOCALVERSION=""
CROSS_MODE="auto"
CROSS=""
WORK_DIR=""

while (($#)); do
    case "$1" in
        --vyos-tree)
            VYOS_TREE="$2"
            shift 2
            ;;
        --kernel-build)
            KBUILD="$2"
            shift 2
            ;;
        --modules-root)
            MODULES_ROOT="$2"
            shift 2
            ;;
        --kernel-release)
            KREL="$2"
            shift 2
            ;;
        --localversion)
            LOCALVERSION="$2"
            shift 2
            ;;
        --cross-compile)
            CROSS_MODE="explicit"
            CROSS="$2"
            shift 2
            ;;
        --work-dir)
            WORK_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

for value in \
    VYOS_TREE \
    KBUILD \
    MODULES_ROOT \
    KREL \
    LOCALVERSION
do
    if [[ -z "${!value}" ]]; then
        echo "ERROR: missing required argument: $value" >&2
        usage >&2
        exit 2
    fi
done

KD="${VYOS_TREE}/scripts/package-build/linux-kernel"
PACKAGE_TOML="${KD}/package.toml"

[[ -d "$VYOS_TREE" ]] ||
    { echo "ERROR: VyOS tree missing: $VYOS_TREE" >&2; exit 1; }

[[ -d "$KD" ]] ||
    { echo "ERROR: VyOS kernel package directory missing: $KD" >&2; exit 1; }

[[ -f "$PACKAGE_TOML" ]] ||
    { echo "ERROR: package.toml missing: $PACKAGE_TOML" >&2; exit 1; }

[[ -d "$KBUILD" ]] ||
    { echo "ERROR: kernel build directory missing: $KBUILD" >&2; exit 1; }

[[ -s "$KBUILD/.config" ]] ||
    { echo "ERROR: final kernel .config missing" >&2; exit 1; }

[[ -s "$KBUILD/Module.symvers" ]] ||
    { echo "ERROR: Module.symvers missing" >&2; exit 1; }

[[ -s "$KBUILD/System.map" ]] ||
    { echo "ERROR: System.map missing" >&2; exit 1; }

FINAL_MODULE_DIR="${MODULES_ROOT}/lib/modules/${KREL}"

[[ -d "$FINAL_MODULE_DIR" ]] ||
    {
        echo "ERROR: final in-tree module directory missing:" >&2
        echo "       $FINAL_MODULE_DIR" >&2
        exit 1
    }

if [[ "$CROSS_MODE" == "auto" ]]; then
    if [[ "$(uname -m)" == "aarch64" ]]; then
        CROSS=""
    else
        CROSS="${CROSS_COMPILE:-aarch64-linux-gnu-}"
    fi
fi

if [[ -n "$CROSS" ]]; then
    CC="${CROSS}gcc"

    command -v "$CC" >/dev/null 2>&1 ||
        {
            echo "ERROR: ARM64 compiler missing: $CC" >&2
            exit 1
        }
else
    CC="${CC:-gcc}"
fi

for cmd in \
    git \
    make \
    patch \
    curl \
    tar \
    python3 \
    modinfo \
    depmod
do
    command -v "$cmd" >/dev/null 2>&1 ||
        {
            echo "ERROR: required command missing: $cmd" >&2
            exit 1
        }
done

if grep -qx 'CONFIG_MODULE_COMPRESS_XZ=y' "$KBUILD/.config"; then
    MODULE_SUFFIX=".ko.xz"
elif grep -qx 'CONFIG_MODULE_COMPRESS_ZSTD=y' "$KBUILD/.config"; then
    MODULE_SUFFIX=".ko.zst"
else
    MODULE_SUFFIX=".ko"
fi

if grep -qx 'CONFIG_MODULE_SIG_FORCE=y' "$KBUILD/.config"; then
    [[ -s "$KBUILD/certs/signing_key.pem" ]] ||
        {
            echo "ERROR: CONFIG_MODULE_SIG_FORCE=y but signing key missing" >&2
            exit 1
        }

    [[ -s "$KBUILD/certs/signing_key.x509" ]] ||
        {
            echo "ERROR: CONFIG_MODULE_SIG_FORCE=y but signing cert missing" >&2
            exit 1
        }
fi

if [[ -z "$WORK_DIR" ]]; then
    WORK_DIR="$(dirname "$MODULES_ROOT")/vyos-oot-modules"
fi

SRC="${WORK_DIR}/src"
AUDIT="${WORK_DIR}/audit"

rm -rf "$WORK_DIR"
mkdir -p "$SRC" "$AUDIT" "$FINAL_MODULE_DIR/extra"


package_value() {
    local package="$1"
    local field="$2"

    python3 - "$PACKAGE_TOML" "$package" "$field" <<'PY'
import sys
import tomllib

path, wanted_name, field = sys.argv[1:]

with open(path, "rb") as f:
    data = tomllib.load(f)

for package in data.get("packages", []):
    if package.get("name") == wanted_name:
        value = package.get(field, "")
        if value is None:
            value = ""
        print(value)
        raise SystemExit(0)

raise SystemExit(
    f"Package {wanted_name!r} not found in {path}"
)
PY
}


clone_vyos_package() {
    local package="$1"
    local destination="$2"

    local url
    local commit

    url="$(package_value "$package" scm_url)"
    commit="$(package_value "$package" commit_id)"

    [[ -n "$url" ]] ||
        {
            echo "ERROR: no scm_url for VyOS package: $package" >&2
            exit 1
        }

    [[ -n "$commit" ]] ||
        {
            echo "ERROR: no commit_id for VyOS package: $package" >&2
            exit 1
        }

    echo
    echo "===== SOURCE: $package ====="
    echo "URL:    $url"
    echo "Commit: $commit"

    git clone "$url" "$destination"

    git -C "$destination" \
        checkout --detach "$commit"

    echo "Resolved:"
    git -C "$destination" rev-parse HEAD
}


apply_vyos_patches() {
    local source="$1"
    local patch_dir="$2"

    [[ -d "$patch_dir" ]] || return 0

    local patches=()

    while IFS= read -r -d '' patch_file; do
        patches+=("$patch_file")
    done < <(
        find "$patch_dir" \
            -maxdepth 1 \
            -type f \
            -name '*.patch' \
            -print0 |
        sort -z
    )

    local patch_file

    for patch_file in "${patches[@]}"; do
        echo "Apply VyOS patch: $(basename "$patch_file")"

        patch \
            -d "$source" \
            -p1 \
            < "$patch_file"
    done
}


kmake() {
    make \
        -C "$KBUILD" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS" \
        CC="$CC" \
        LOCALVERSION="$LOCALVERSION" \
        "$@"
}


install_external_dir() {
    local module_dir="$1"

    kmake \
        M="$module_dir" \
        INSTALL_MOD_PATH="$MODULES_ROOT" \
        INSTALL_MOD_DIR=extra \
        INSTALL_MOD_STRIP=1 \
        modules_install
}


echo "================================================================"
echo "===== VYOS OOT MODULE BUILDER ====="
echo "================================================================"
echo "VyOS tree:      $VYOS_TREE"
echo "Kernel build:   $KBUILD"
echo "Kernel release: $KREL"
echo "Localversion:   $LOCALVERSION"
echo "Modules root:   $MODULES_ROOT"
echo "Work dir:       $WORK_DIR"
echo "Cross prefix:   ${CROSS:-<native>}"
echo "Compiler:       $CC"
echo "Module suffix:  $MODULE_SUFFIX"


echo
echo "================================================================"
echo "===== 1. ACCEL-PPP-NG: IPOE + VLAN_MON ====="
echo "================================================================"

ACCEL="${SRC}/accel-ppp-ng"

clone_vyos_package \
    accel-ppp-ng \
    "$ACCEL"

apply_vyos_patches \
    "$ACCEL" \
    "${KD}/patches/accel-ppp-ng"

ACCEL_VERSION="$(
    git -C "$ACCEL" describe --tags --always
)"

printf '#define ACCEL_PPP_VERSION "%s"\n' \
    "$ACCEL_VERSION" \
    > "$ACCEL/drivers/ipoe/version.h"

printf '#define ACCEL_PPP_VERSION "%s"\n' \
    "$ACCEL_VERSION" \
    > "$ACCEL/drivers/vlan_mon/version.h"

for driver in \
    ipoe \
    vlan_mon
do
    DRIVER_DIR="$ACCEL/drivers/$driver"

    echo
    echo "--- Build accel driver: $driver ---"

    kmake \
        M="$DRIVER_DIR" \
        modules

    install_external_dir \
        "$DRIVER_DIR"
done


echo
echo "================================================================"
echo "===== 2. JOOL ====="
echo "================================================================"

JOOL_BUILD_SCRIPT="${KD}/build-jool.sh"

[[ -f "$JOOL_BUILD_SCRIPT" ]] ||
    {
        echo "ERROR: official VyOS Jool build script missing" >&2
        exit 1
    }

JOOL_VERSION="$(
    sed -n \
        's/^PACKAGE_VERSION=\([^[:space:]]*\).*$/\1/p' \
        "$JOOL_BUILD_SCRIPT" |
    head -1
)"

[[ -n "$JOOL_VERSION" ]] ||
    {
        echo "ERROR: unable to derive Jool version from VyOS build script" >&2
        exit 1
    }

echo "VyOS Jool version: $JOOL_VERSION"

JOOL_ARCHIVE="${SRC}/jool-${JOOL_VERSION}.tar.gz"

curl \
    --fail \
    --location \
    --retry 3 \
    --output "$JOOL_ARCHIVE" \
    "https://github.com/NICMx/Jool/archive/refs/tags/v${JOOL_VERSION}.tar.gz"

tar \
    -C "$SRC" \
    -xzf "$JOOL_ARCHIVE"

JOOL="${SRC}/Jool-${JOOL_VERSION}"

[[ -d "$JOOL" ]] ||
    {
        echo "ERROR: extracted Jool source missing: $JOOL" >&2
        exit 1
    }

for part in \
    common \
    nat64 \
    siit
do
    MODULE_DIR="$JOOL/src/mod/$part"

    echo
    echo "--- Build Jool: $part ---"

    kmake \
        M="$MODULE_DIR" \
        modules

    install_external_dir \
        "$MODULE_DIR"
done


echo
echo "================================================================"
echo "===== 3. NAT-RTSP ====="
echo "================================================================"

RTSP="${SRC}/nat-rtsp"

clone_vyos_package \
    nat-rtsp \
    "$RTSP"

apply_vyos_patches \
    "$RTSP" \
    "${KD}/patches/nat-rtsp"

kmake \
    M="$RTSP" \
    modules

install_external_dir \
    "$RTSP"


echo
echo "================================================================"
echo "===== 4. IPT-NETFLOW ====="
echo "================================================================"

IPT="${SRC}/ipt-netflow"

clone_vyos_package \
    ipt-netflow \
    "$IPT"

apply_vyos_patches \
    "$IPT" \
    "${KD}/patches/ipt-netflow"

(
    cd "$IPT"

    ./configure \
        --enable-direction \
        --enable-macaddress \
        --enable-vlan \
        --enable-sampler \
        --enable-aggregation \
        --kdir="$KBUILD"

    make \
        KDIR="$KBUILD" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS" \
        CC="$CC" \
        version.h \
        compat_def.h
)

kmake \
    M="$IPT" \
    modules

install_external_dir \
    "$IPT"


echo
echo "================================================================"
echo "===== 5. FINAL DEPMOD ====="
echo "================================================================"

depmod \
    -b "$MODULES_ROOT" \
    "$KREL"

DEPMOD_AUDIT="${AUDIT}/depmod-unresolved.txt"

depmod \
    -e \
    -F "$KBUILD/System.map" \
    -b "$MODULES_ROOT" \
    "$KREL" \
    > "$DEPMOD_AUDIT" \
    2>&1 || true

if grep -q \
    'needs unknown symbol' \
    "$DEPMOD_AUDIT"
then
    cat "$DEPMOD_AUDIT"

    echo
    echo "ERROR: unresolved kernel symbols remain" >&2
    exit 1
fi

echo "No unresolved kernel symbols."


echo
echo "================================================================"
echo "===== 6. VERIFY STOCK VYOS OOT MODULE SET ====="
echo "================================================================"

EXPECTED=(
    ipoe
    ipt_NETFLOW
    jool
    jool_common
    jool_siit
    nf_conntrack_rtsp
    nf_nat_rtsp
    vlan_mon
)

OK=0

for module in "${EXPECTED[@]}"; do
    file="${FINAL_MODULE_DIR}/extra/${module}${MODULE_SUFFIX}"

    [[ -f "$file" ]] ||
        {
            echo "ERROR: expected module missing: $file" >&2
            exit 1
        }

    name="$(modinfo -F name "$file")"
    vermagic="$(modinfo -F vermagic "$file")"
    signer="$(modinfo -F signer "$file")"

    [[ "$name" == "$module" ]] ||
        {
            echo "ERROR: module name mismatch for $file" >&2
            exit 1
        }

    case "$vermagic" in
        "$KREL "*)
            ;;
        *)
            echo "ERROR: vermagic mismatch for $file" >&2
            echo "       $vermagic" >&2
            exit 1
            ;;
    esac

    if grep -qx 'CONFIG_MODULE_SIG_FORCE=y' "$KBUILD/.config"; then
        [[ -n "$signer" ]] ||
            {
                echo "ERROR: unsigned module: $file" >&2
                exit 1
            }
    fi

    printf '%-22s %s\n' \
        "$module" \
        "OK"

    OK=$((OK + 1))
done


echo
echo "================================================================"
echo "===== 7. MODPROBE DEPENDENCY RESOLUTION ====="
echo "================================================================"

for module in "${EXPECTED[@]}"; do
    echo
    echo "--- $module ---"

    modprobe \
        -d "$MODULES_ROOT" \
        -S "$KREL" \
        --show-depends \
        "$module"
done


echo
echo "================================================================"
echo "===== SUCCESS ====="
echo "================================================================"
echo "Verified VyOS OOT modules: $OK / ${#EXPECTED[@]}"
echo "Kernel release:            $KREL"
echo "Module tree:               $FINAL_MODULE_DIR"
echo "Audit:                     $DEPMOD_AUDIT"
