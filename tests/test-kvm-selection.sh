#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/ui.sh
source "$ROOT/lib/ui.sh"

[[ "$(KVM_OVER_IP=yes select_kvm_over_ip)" == "yes" ]]
[[ "$(KVM_OVER_IP=true select_kvm_over_ip)" == "yes" ]]
[[ "$(KVM_OVER_IP=no select_kvm_over_ip)" == "no" ]]
[[ "$(KVM_OVER_IP=0 select_kvm_over_ip)" == "no" ]]

unset KVM_OVER_IP
[[ "$(select_kvm_over_ip </dev/null)" == "no" ]]

if (KVM_OVER_IP=invalid select_kvm_over_ip) >/dev/null 2>&1; then
    echo "ERROR: invalid KVM-over-IP selection was accepted" >&2
    exit 1
fi

echo "PASS: KVM-over-IP profile selection"
