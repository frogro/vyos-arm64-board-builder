# Shared capability predicate; not a board-name switch.
native_extlinux_enabled() {
    [[ "${FIRMWARE_PROVIDER:-}" == armbian-uboot &&
       "${HW_BRANCH:-}" == current && "${BOOT_BRANCH:-}" == vendor &&
       "${UBOOT_BOOTSCRIPT:-}" == boot-rk35xx.cmd* ]]
}
