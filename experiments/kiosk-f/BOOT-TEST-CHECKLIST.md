# Known boot-test trap: unmanaged panic=30

This is a recurring, already diagnosed test-setup error, not a new decoder
finding. It occurred on 2026-09-22 at11:36:52 and again at16:42:41. The second
occurrence should have been prevented using the earlier test record.

## Cause and misleading symptoms

VyOS system_option.py manages the panic kernel argument from persisted system
options. Adding panic=30 only to an experimental GRUB entry makes startup detect
a mismatch. In the observed configuration it removes that argument, loads
/boot/vmlinuz with /boot/initrd.img and requests systemctl kexec. Consequently,
the intended testkernel can be replaced by the normal kernel shortly after boot.
This can resemble a boot loop or power fault. BOOT_IMAGE in /proc/cmdline may
still name the test image after kexec and is not sufficient proof of the kernel.

## Mandatory preflight for subsequent test boots

1. Read this checklist before creating or reusing an experimental boot entry.
2. Do not add panic=30 (or another VyOS-managed argument) independently of the
   persisted VyOS configuration. Check the installed system_option.py managed
   arguments and resulting command line before boot. Do not change production
   configuration merely to bypass the mismatch during an isolated test.
3. If a temporary panic timeout is needed, wait for completed VyOS configuration
   loading, record the current kernel.panic value, then set it at runtime with
   sysctl. Restore it after a non-rebooting test. This is not an early-boot guard
   and a later config apply may change it again.
4. Retain the separate one-shot boot entry, known-good default and conditional
   confirmation timer. Document that a userspace timer cannot recover an early
   hang before systemd starts; do not claim otherwise.
5. After startup verify uname -r, a candidate-specific capability/parameter or
   build identity, boot ID, router startup completion and kiosk services. Never
   accept only BOOT_IMAGE or an initially reachable SSH service as confirmation.
6. If another boot occurs, inspect system_option/kexec logs before attributing it
   to decoder code, kernel crash, watchdog or power supply.

## Existing evidence

- [First occurrence, test4 at11:36](sunshine/decoder-investigation/vp9-av1/test4-live-20260922/README.md): installed parser/generate_cmdline comparison already verified the corrected entry.
- [Repeated occurrence, candidate tests at16:42](av1-reset-candidates-20260922/README.md): captured system_option source and kexec journal; successful retry without the unmanaged argument.

This note changes no live system, production defaults or release workflow.
