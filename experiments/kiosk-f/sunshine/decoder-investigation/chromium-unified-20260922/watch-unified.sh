#!/bin/bash
set -euo pipefail
export DOCKER_HOST=unix:///run/vyarm-nuc-docker.sock
base=/home/photobooth/vyarm-chromium-build
src=$base/source-cross
name=vyarm-chromium-unified-build
log=$base/unified-watch.log
status=$base/unified-watch.status
exec >>"$log" 2>&1
attempt=0
max_oom=0
while :; do
  now=$(date -u +%FT%TZ)
  state=$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}' "$name")
  read -r phase code oom <<<"$state"
  free_k=$(df --output=avail "$base" | tail -1 | tr -d ' ')
  printf '%s state=%s free_KiB=%s\n' "$now" "$state" "$free_k"
  if [[ "$phase" == running ]]; then
    events=$(docker exec "$name" cat /sys/fs/cgroup/memory.events 2>/dev/null || true)
    n=$(awk '$1=="oom_kill" {print $2}' <<<"$events")
    [[ ${n:-0} -le $max_oom ]] || max_oom=$n
    docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' "$name" || true
    tail -n 2 "$src/vyarm-cross-build.log" || true
    if (( free_k < 5242880 )); then
      docker stop -t 30 "$name"
      echo "$now stopped: less than 5 GiB free; no files deleted" | tee "$status"
      exit 2
    fi
    echo "$now running; retry=$attempt oom_kills=$max_oom" >"$status"
  elif [[ "$phase" == exited ]]; then
    if [[ "$code" == 0 ]] && grep -q '^VYARM_BROWSER_BUILD_COMPLETE$' "$src/vyarm-cross-build.log"; then
      file "$src/out/Release/chrome" "$src/out/Release/chrome_sandbox"
      sha256sum "$src/out/Release/chrome" "$src/out/Release/chrome_sandbox" > "$base/unified-artifacts.sha256"
      echo "$now build complete; browser runtime tests still required" | tee "$status"
      exit 0
    elif { [[ "$oom" == true ]] || (( max_oom > 0 )); } && (( attempt < 2 )); then
      attempt=$((attempt+1))
      jobs=$((8 / (2 ** attempt)))
      echo "$jobs" > "$src/vyarm-jobs"
      echo "$now memory failure: retry incremental build with $jobs jobs"
      max_oom=0
      docker start "$name"
    else
      docker logs --tail 80 "$name"
      echo "$now stopped with exit $code: needs analysis; no blind restart" | tee "$status"
      exit 1
    fi
  else
    echo "$now unexpected state: $phase; needs analysis" | tee "$status"
    exit 1
  fi
  sleep 60
done
