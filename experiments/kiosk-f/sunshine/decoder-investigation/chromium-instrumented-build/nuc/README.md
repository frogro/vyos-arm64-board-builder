# NUC build handoff, 2026-09-21

Ubuntu NUC12WSKi5, i5-1240P, 32 GB nominal RAM. SSH user photobooth,
LAN 192.168.178.136. Build root /home/photobooth/vyarm-chromium-build.
No chat/session migration. ThinkPad remains the working repository host.

Dedicated Docker socket unix:///run/vyarm-nuc-docker.sock, systemd unit
vyarm-nuc-docker, overlay2 data under build root/docker-data. Default Docker
unmodified. User installed Docker and ARM64 binfmt and started the dedicated
service using sudo. ARM64 uname smoke test passed. Compiler still ARM64 QEMU;
GN/Ninja are native x86 orchestration, not a native cross compiler.

Transferred complete source excluding out and log files, then stopped ThinkPad
compiler and transferred out separately. Three root-owned Ninja files initially
failed read permission; ownership corrected and final rsync passed. All 37 critical
patched/build source SHA256 values match. Image archive SHA256:
d9a53a23557817a0aba5d40c0b688a6ccc70acf52aadf94426112c7bd80be914
Image vyarm-chromium-builddeps:20260921 ID:
e18d1a90e1a1eeab3fd927a917394ed9d2fcd9c95798a21f7490332c89608b36

Build container vyarm-chromium-nv15-build started at 20:05:30 UTC:
70b32ece2d4fd4cb55fc04ceb38614257d1d4ca99a74f4ae17990d9d0b7308a9
4 compile jobs, single linker per GN settings, 8 CPU quota, 20 GiB RAM,
24 GiB RAM+swap, 512 process limit. /home had 65 GiB free at start; monitor
space while compiling. Script run-candidate.sh records log/exit/completion marker.
No browser build success or live NV15 playback proof yet.

ThinkPad build container and dedicated Docker service stopped after NUC launch.
ThinkPad source/cache and external development drive retained. Copy completed
browser artifacts, build logs and new source changes back to development drive;
do not copy whole Docker storage. Do not disconnect development drive while
repository operations are active. NUC data is independent of that drive.

Transfer stalled when ThinkPad changed Wi-Fi/IP; resumed with compression,
SSH keepalives and rsync timeout over direct 192.168.178.x network. No MTU change
was made; stale TCP sessions were the immediate transfer problem.

Status: docker -H unix:///run/vyarm-nuc-docker.sock ps -a
Log: source/vyarm-build-nuc.log
The daemon is transient and will need starting again after a NUC reboot.
