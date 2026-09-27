#!/bin/bash
set -euo pipefail
loaders=(/work/native-pack/ld-linux-*)
[[ ${#loaders[@]} == 1 && -x ${loaders[0]} ]]
for tool in mksquashfs unsquashfs; do
  cat > "/usr/local/bin/$tool" <<WRAP
#!/bin/sh
exec ${loaders[0]} --library-path /work/native-pack /work/native-pack/$tool "\$@"
WRAP
  chmod 755 "/usr/local/bin/$tool"
done
mksquashfs -version
unsquashfs -version || [[ $? == 1 ]]
