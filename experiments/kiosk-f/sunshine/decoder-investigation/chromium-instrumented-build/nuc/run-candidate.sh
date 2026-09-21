#!/bin/bash
set -euo pipefail
cd /home/photobooth/vyarm-chromium-build
export DOCKER_HOST=unix:///run/vyarm-nuc-docker.sock
test "$(docker info --format '{{.DockerRootDir}}')" = /home/photobooth/vyarm-chromium-build/docker-data
docker image inspect vyarm-chromium-builddeps:20260921 >/dev/null
# Single compile job is overridden only in this NUC-specific runner.
cat > source/vyarm-build-nuc.sh <<'BUILD'
#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee -a /src/vyarm-build-nuc.log) 2>&1
trap 'rc=$?; printf "VYARM_BUILD_EXIT=%s\n" "$rc"; exit "$rc"' EXIT
printf 'VYARM_NUC_BUILD_START '; date -u
export DEB_BUILD_OPTIONS=parallel=4
make -f debian/rules -f vyarm-regenerate.mk vyarm-regenerate
/src/vyarm-native-tools/ld-linux-x86-64.so.2 --library-path /src/vyarm-native-tools /src/vyarm-native-tools/ninja -j4 -C out/Release chrome chrome_sandbox
printf 'VYARM_BROWSER_BUILD_COMPLETE\n'
BUILD
chmod 755 source/vyarm-build-nuc.sh
docker run -d --name vyarm-chromium-nv15-build --platform linux/arm64 \
 --memory=20g --memory-swap=24g --cpus=8 --pids-limit=512 \
 --security-opt seccomp=unconfined \
 -v /home/photobooth/vyarm-chromium-build/source:/src -w /src \
 vyarm-chromium-builddeps:20260921 /bin/bash /src/vyarm-build-nuc.sh
