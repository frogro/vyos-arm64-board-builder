#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "$1 $2" == "run list" ]]; then
    printf '300\n200\n100\n'
    exit 0
fi

if [[ "$1" == "api" && "$2" =~ /actions/runs/([0-9]+)$ ]]; then
    case "${BASH_REMATCH[1]}" in
        100|200|300) printf 'success\n' ;;
        *) printf 'failure\n' ;;
    esac
    exit 0
fi

if [[ "$1" == "api" && "$2" =~ /actions/runs/([0-9]+)/artifacts$ ]]; then
    case "${BASH_REMATCH[1]}" in
        200) printf '9876\n' ;;
        100) printf '8765\n' ;;
        *) : ;;
    esac
    exit 0
fi

exit 1
EOF
chmod +x "$TMP/gh"

actual="$(
    GH_BIN="$TMP/gh" \
        "$ROOT/tools/resolve-raw-run.sh" \
        --repo frogro/test \
        --workflow raw.yml
)"
[[ "$actual" == "200" ]]

actual="$(
    GH_BIN="$TMP/gh" \
        "$ROOT/tools/resolve-raw-run.sh" \
        --repo frogro/test \
        --run-id 100
)"
[[ "$actual" == "100" ]]

if GH_BIN="$TMP/gh" \
    "$ROOT/tools/resolve-raw-run.sh" \
    --repo frogro/test \
    --run-id 300 >/dev/null 2>&1; then
    echo "FAIL: accepted a run without the required artifact" >&2
    exit 1
fi

echo "PASS: raw workflow run resolution"
