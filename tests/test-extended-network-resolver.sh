#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/kernel/scripts/kconfig" "$WORK/bin"

cat > "$WORK/kernel/Kconfig" <<'EOF'
mainmenu "Extended Network resolver fixture"

config GOOD_DRIVER
    tristate "Good module"

config FORCED_DRIVER
    bool "Forced built-in"
EOF

cat > "$WORK/kernel/scripts/kconfig/merge_config.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

shift
cat "$1" "$2" > "${KCONFIG_CONFIG:?}"
EOF
chmod +x "$WORK/kernel/scripts/kconfig/merge_config.sh"

cat > "$WORK/bin/make" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sed -i \
    's/^CONFIG_FORCED_DRIVER=m$/CONFIG_FORCED_DRIVER=y/' \
    "${KCONFIG_CONFIG:?}"
EOF
chmod +x "$WORK/bin/make"

cat > "$WORK/base.config" <<'EOF'
# CONFIG_GOOD_DRIVER is not set
# CONFIG_FORCED_DRIVER is not set
EOF

cat > "$WORK/profile.config" <<'EOF'
CONFIG_GOOD_DRIVER=m
CONFIG_FORCED_DRIVER=m
CONFIG_MISSING_DRIVER=m
EOF

PATH="$WORK/bin:$PATH" \
python3 "$ROOT/tools/resolve-extended-network-config.py" \
    --kernel "$WORK/kernel" \
    --base-config "$WORK/base.config" \
    --profile "$WORK/profile.config" \
    --output-dir "$WORK/enabled" \
    --enabled yes

grep -q '^CONFIG_GOOD_DRIVER=m$' \
    "$WORK/enabled/generated-final.config"
grep -q '^# CONFIG_FORCED_DRIVER is not set$' \
    "$WORK/enabled/generated-final.config"
grep -q 'ENABLED  CONFIG_GOOD_DRIVER' \
    "$WORK/enabled/extended-network-report.txt"
grep -q 'SKIPPED  CONFIG_FORCED_DRIVER' \
    "$WORK/enabled/extended-network-report.txt"
grep -q 'SKIPPED  CONFIG_MISSING_DRIVER' \
    "$WORK/enabled/extended-network-report.txt"

PATH="$WORK/bin:$PATH" \
python3 "$ROOT/tools/resolve-extended-network-config.py" \
    --kernel "$WORK/kernel" \
    --base-config "$WORK/base.config" \
    --profile "$WORK/profile.config" \
    --output-dir "$WORK/disabled" \
    --enabled no

cmp "$WORK/base.config" "$WORK/disabled/generated-final.config"

echo "PASS: Extended Network fail-soft Kconfig resolver"
