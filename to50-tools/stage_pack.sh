#!/usr/bin/env bash
# Stage a converted pack in corpus layout (WSL bash):
#   stage_pack.sh <slug> <snapshot dir on ext4 (<...>/<slug>/<key>, holding <Pack>/ with v2/)> <upstream url> <commit>
# Writes <lane>/packs/<slug>/stage/: packs/<slug>/<key>/<Pack>, patches/<slug>/<key>/<slug>-<key>.{json,diff},
# packs-json-entry.json, REPLAY-CMPTREE.json (pair applied to the pristine == v2) and SHA256SUMS (over everything).
set -euo pipefail
slug="$1"; S="$2"; UP="$3"; COMMIT="$4"
L=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/to50-20261102
T=$L/tools
key=$(basename "$S"); pack=$(ls "$S")
[ "$(echo "$pack" | wc -l)" = 1 ] || { echo "expected one pack folder in $S"; exit 1; }
[ "x${COMMIT:0:7}" = "$key" ] || { echo "key $key != x+commit[:7]"; exit 1; }
ST=$(mktemp -d ~/stage."$slug".XXXX)
mkdir -p "$ST/packs/$slug" "$ST/patches/$slug/$key"
cp -a "$S" "$ST/packs/$slug/"
find "$ST" -name __pycache__ -prune -exec rm -rf {} +
python3 -I "$T/packpair.py" generate "$ST/packs/$slug/$key" "$ST/patches/$slug/$key"
python3 -I - "$ST/packs-json-entry.json" "$COMMIT" "$key" "$pack" "$UP" <<'EOF'
import json, sys
out, commit, key, pack, up = sys.argv[1:]
open(out, "w").write(json.dumps({"commit": commit, "key": key, "pack": pack, "upstream": up}, indent=2) + "\n")
EOF
R=$(mktemp -d); mkdir -p "$R/$slug/$key"; cp -a "$S/$pack" "$R/$slug/$key/"; rm -rf "$R/$slug/$key/$pack/v2"
python3 -I "$T/packpair.py" apply "$R/$slug/$key" "$ST/patches/$slug/$key/$slug-$key" > /dev/null
python3 -I "$T/packpair.py" cmptree "$R/$slug/$key/$pack/v2" "$S/$pack/v2" > "$ST/REPLAY-CMPTREE.json"
(cd "$ST" && find packs patches packs-json-entry.json REPLAY-CMPTREE.json -type f | sort | xargs sha256sum > SHA256SUMS)
D="$L/packs/$slug/stage"; rm -rf "$D"; cp -r "$ST" "$D"
echo "staged $slug $key ($pack): $(cat "$ST/REPLAY-CMPTREE.json")"
