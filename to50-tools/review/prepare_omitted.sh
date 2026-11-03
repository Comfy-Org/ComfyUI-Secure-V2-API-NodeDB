#!/usr/bin/env bash
# Apply the Comfy omission policy (no upstream media, example/demo workflows or bundled model files in git) to a REVIEWED
# work dir before publication (WSL bash):  prepare_omitted.sh <slug> <review work dir>
# Rewrites <work>/replay/<slug>/<key>/<pack> (pristine + v2), regenerates the pair into <work>/publish-pair/, re-proves the
# replay, writes <work>/OMITTED.md (git-safe: count, size, one digest) and archives the per-file list OUTSIDE git.
set -euo pipefail
slug="$1"; WORK="$2"
LL=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/to50-20261102
T=$LL/tools; RV=$T/review
ARCH=/home/benjc/ab-expand/archive/omitted; mkdir -p "$ARCH"
key=$(ls "$WORK/replay/$slug"); pack=$(ls "$WORK/replay/$slug/$key")
P="$WORK/replay/$slug/$key/$pack"
LIST="$ARCH/$slug-$key-$(date -u +%Y%m%dT%H%M%SZ).json"
python3 -I "$RV/omit_media.py" plan "$P" "$LIST"
python3 -I "$RV/omit_media.py" apply "$P" "$LIST"
if python3 -I -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))[\"entries\"] else 1)" "$LIST"; then python3 -I "$RV/omit_media.py" note "$LIST" "$WORK/OMITTED.md"; else rm -f "$WORK/OMITTED.md"; echo "nothing to omit: no OMITTED.md"; fi
rm -rf "$WORK/publish-pair"; mkdir -p "$WORK/publish-pair"
python3 -I "$T/packpair.py" generate "$WORK/replay/$slug/$key" "$WORK/publish-pair" > /dev/null
# replay proof on the reduced trees
R=$(mktemp -d ~/omit-replay.XXXX); mkdir -p "$R/$slug/$key"; cp -a "$P" "$R/$slug/$key/"; rm -rf "$R/$slug/$key/$pack/v2"
python3 -I "$T/packpair.py" apply "$R/$slug/$key" "$WORK/publish-pair/$slug-$key" > /dev/null
python3 -I "$T/packpair.py" cmptree "$R/$slug/$key/$pack/v2" "$P/v2" > "$WORK/omit-replay.json" \
  || { echo "omission replay FAILED"; cat "$WORK/omit-replay.json"; exit 1; }
echo "omission applied: list $LIST (outside git); pair regenerated; replay exact ($(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["files_compared"])' "$WORK/omit-replay.json") v2 files)"
[ -f "$WORK/OMITTED.md" ] && cat "$WORK/OMITTED.md" || true
