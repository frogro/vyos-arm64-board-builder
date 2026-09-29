# Base A hardware selection: independent of network and application profiles.
# Paths are repository-relative. Unknown boards retain DT/model derivation.
board_hardware_select() {
    local board="$1"
    BOARD_BASE_CONFIG=""
    BOARD_BASE_READY=""
    BOARD_BASE_MODULES=""
    BOARD_BASE_PATCHES=""
    BOARD_PERIPHERAL_PATCHES=""
    case "$board" in
        rock-5b|orangepi5-plus)
            BOARD_BASE_CONFIG="profiles/base-hardware/${board}.config"
            BOARD_BASE_READY="profiles/base-hardware/${board}-ready.config"
            BOARD_BASE_PATCHES="profiles/base-hardware/kernel-patches/rk3588-synopsys-hdmirx"
            ;;
    esac
    if [[ "$board" == orangepi5-plus ]]; then
        BOARD_BASE_MODULES="profiles/base-hardware/orangepi5-plus-modules.txt"
        BOARD_PERIPHERAL_PATCHES="profiles/base-hardware/kernel-patches/orangepi5-plus"
    fi
}
