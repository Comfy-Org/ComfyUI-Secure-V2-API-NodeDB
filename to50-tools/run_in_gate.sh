#!/usr/bin/env bash
# To-50% lane: run one Python test script in a bounded gate container (run from WSL bash).
#   run_in_gate.sh <pack_root> <tests_dir> <results_dir> <script relative to tests_dir> [args...]
# <pack_root> is the folder holding the PRISTINE upstream pack with the candidate v2/ tree inside it
# (the corpus layout <Pack>-HEAD/ + <Pack>-HEAD/v2/). It is mounted read-only at /pack.
# Optional: DEPS=<dir> mounts a read-only folder of unpacked, pinned wheels at /deps (add it to sys.path yourself).
#
# Rules (MERVYN, 2026-11-02):
#   * --network none, --read-only, non-root, --cap-drop ALL, --pids-limit 512, tmpfs /tmp 2g.
#   * Memory 4g (or GATE_MEM=8g when WSL MemAvailable >= 10 GiB at start). CPUs GATE_CPUS 1..4 (default 2).
#   * At most 2 lane containers at once (flock slots); refuses if WSL / has < 25 GiB free.
#   * No image is built or pulled; never pip install inside the container.
# Mounts (read-only): /core = ComfyUI 6257422b (clean), /overlay-live = JERRY's live overlay snapshot
# (also importable: sys.path.insert(0, "/overlay") then `from comfy_secure_nodes import packmanifest, packpatch`), /bases = guest comfy_api trees
# for SDK symbol checks (0cd9adec, 0b86765f), /pack, /tests, optional /deps; read-write: /results.
set -euo pipefail
PACK="$1"; TESTS="$2"; RESULTS="$3"; SCRIPT="$4"; shift 4
IMAGE_ID="sha256:e48accf76d58011cc86b1d88a6ff96d1c48597d13a2148bf931a6a9ce9e578e6"  # jerry-content-gate-base:e48accf76d58
LABEL="to50-lane=1"
CORE="${GATE_CORE:-/home/benjc/.popbot-host/workspaces/scratch/chat_a4240cc9e86c/lazytorch-r1/comfyui-base}"  # GATE_CORE=<clean ComfyUI checkout> to verify against a newer core (record its commit)
BASES="/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/jerry-rca-r2-20261029/sdk-surfaces-r1/runtime/worker/bases"
OVERLAY="/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/jerry-native-overlay-live-r1-20261029/vm-native-overlay-source/comfy_secure_nodes"
LOCKDIR="/tmp/to50-gate-locks"; mkdir -p "$LOCKDIR"
GIB_KB=$(( 1024 * 1024 ))
CPUS="${GATE_CPUS:-2}"; REQ_MEM="${GATE_MEM:-4g}"
case "$CPUS" in 1|2|3|4) ;; *) echo "gate: GATE_CPUS must be 1..4" >&2; exit 2;; esac
rootfree=$(df -Pk / | awk 'NR == 2 {print $4}')
if [ "${rootfree:-0}" -lt $(( 25 * GIB_KB )) ]; then echo "gate: refused (WSL / free ${rootfree} kB < 25 GiB)" >&2; exit 3; fi
# take one of two slots (waits up to GATE_WAIT_S, default 1800 s)
deadline=$(( $(date +%s) + ${GATE_WAIT_S:-1800} ))
slot=""
while [ -z "$slot" ]; do
  for s in 1 2; do
    exec {fd}>"$LOCKDIR/slot$s"
    if flock -n "$fd"; then slot=$s; break; fi
    exec {fd}>&-
  done
  if [ -z "$slot" ]; then
    [ "$(date +%s)" -ge "$deadline" ] && { echo "gate: refused (both slots busy for ${GATE_WAIT_S:-1800}s)" >&2; exit 3; }
    sleep 5
  fi
done
avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
MEM=4g
if [ "$REQ_MEM" = 8g ] && [ "${avail:-0}" -ge $(( 10 * GIB_KB )) ]; then MEM=8g; fi
if [ "${avail:-0}" -lt $(( 6 * GIB_KB )) ]; then echo "gate: refused (WSL MemAvailable ${avail} kB < 6 GiB)" >&2; exit 3; fi
echo "gate: core $CORE"  >&2
echo "gate: slot $slot, --cpus $CPUS --memory $MEM (MemAvailable ${avail} kB, / free ${rootfree} kB)" >&2
mkdir -p "$RESULTS"
EXTRA=()
[ -n "${DEPS:-}" ] && EXTRA+=(-v "$DEPS:/deps:ro")
NAME="to50-$(basename "$PACK" | tr -cd 'A-Za-z0-9_.-' | cut -c1-40)-$$"
set +e
docker run --rm --name "$NAME" --label "$LABEL" --network none --read-only \
  --memory "$MEM" --memory-swap "$MEM" --cpus "$CPUS" --pids-limit 512 \
  --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
  --tmpfs /tmp:rw,size=2g,mode=1777 -e HOME=/tmp -e OMP_NUM_THREADS="$CPUS" -e PYTHONDONTWRITEBYTECODE=1 \
  -e COMFY_CORE_ROOT=/core \
  -v "$CORE:/core:ro" -v "$PACK:/pack:ro" -v "$TESTS:/tests:ro" -v "$RESULTS:/results:rw" \
  -v "$BASES:/bases:ro" -v "$OVERLAY:/overlay-live:ro" -v "$OVERLAY:/overlay/comfy_secure_nodes:ro" "${EXTRA[@]}" \
  --entrypoint /usr/local/bin/python3 "$IMAGE_ID" -I -B "/tests/$SCRIPT" "$@"
rc=$?
set -e
docker rm -f "$NAME" >/dev/null 2>&1 || true
exit $rc
