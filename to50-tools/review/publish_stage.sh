#!/usr/bin/env bash
# MERVYN: publish one REVIEWED to-50% stage to corpus main (run from Git Bash; uses WSL for copies and verification).
#   publish_stage.sh <slug> <review work dir (WSL path, from review_stage.sh)> <commit message file (Windows path)>
# env: REPAIR=1 replaces only packs/<slug>/<key>/<pack>/v2 and the pair; the packs.json entry must already exist.
#      FULL_REPLACE=1 replaces the whole pack folder (pristine + v2) and the pair (e.g. an omission fix-forward).
# If <work>/publish-pair exists (prepare_omitted.sh), that pair is published; <work>/OMITTED.md is placed next to the pack.
# Commits locally, then proves the COMMITTED bytes (git archive HEAD) replay to the reviewed v2. It never pushes;
# push by hand after reading the verification: git push origin HEAD:main
set -euo pipefail
slug="$1"; WORK="$2"; MSG="$3"
CW=/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/corpus
CL=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/corpus
LL=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/to50-20261102
ST="${STAGE:-$LL/packs/$slug/stage}"
die(){ echo "publish: $*" >&2; exit 1; }
export MSYS_NO_PATHCONV=1
cd "$CW"
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "corpus HEAD $(git rev-parse --short HEAD) != origin/main $(git rev-parse --short origin/main)"
[ -z "$(git status --porcelain)" ] || die "corpus working tree is dirty"
key=$(wsl.exe -e bash -c "ls '$WORK/replay/$slug'" | tr -d '\r')
pack=$(wsl.exe -e bash -c "ls '$WORK/replay/$slug/$key'" | tr -d '\r')
[ -n "$key" ] && [ -n "$pack" ] || die "cannot read key/pack from $WORK/replay/$slug"
# The stage must be exactly what was reviewed (workers sometimes re-stage after a review started).
wsl.exe -e bash -c "cmp -s '$WORK/stage-snapshot/SHA256SUMS' '$ST/SHA256SUMS' && cmp -s '$WORK/stage-snapshot/$slug-$key.json' '$ST/patches/$slug/$key/$slug-$key.json' && cmp -s '$WORK/stage-snapshot/$slug-$key.diff' '$ST/patches/$slug/$key/$slug-$key.diff'" \
  || die "the stage changed after the review (or the review has no snapshot): re-run review_stage.sh"
PUBPAIR="$WORK/stage-snapshot"; wsl.exe -e test -d "$WORK/publish-pair" && PUBPAIR="$WORK/publish-pair"
echo "publish $slug $key $pack (REPAIR=${REPAIR:-0} FULL_REPLACE=${FULL_REPLACE:-0}) pair=$PUBPAIR onto $(git rev-parse --short HEAD)"
# The corpus is a cone-mode sparse checkout: bring the pack's paths into the working tree first (a repair's files must be
# on disk to be replaced; new paths must be in the sparse set before `git add` accepts them).
git sparse-checkout add "packs/$slug" "patches/$slug"
wsl.exe -e bash -c "set -euo pipefail
  if [ '${FULL_REPLACE:-0}' = 1 ]; then
    [ -d '$CL/packs/$slug/$key/$pack' ] || { echo 'replace target missing'; exit 1; }
    rm -rf '$CL/packs/$slug/$key/$pack'
    cp -r '$WORK/replay/$slug/$key/$pack' '$CL/packs/$slug/$key/'
  elif [ '${REPAIR:-0}' = 1 ]; then
    [ -d '$CL/packs/$slug/$key/$pack/v2' ] || { echo 'repair target missing'; exit 1; }
    rm -rf '$CL/packs/$slug/$key/$pack/v2'
    cp -r '$WORK/replay/$slug/$key/$pack/v2' '$CL/packs/$slug/$key/$pack/'
  else
    [ ! -e '$CL/packs/$slug' ] || { echo 'packs/$slug already exists on main'; exit 1; }
    mkdir -p '$CL/packs/$slug/$key'
    cp -r '$WORK/replay/$slug/$key/$pack' '$CL/packs/$slug/$key/'
    python3 -I - '$CL/packs/packs.json' '$ST/packs-json-entry.json' '$slug' <<'EOF'
import json, sys
p, e, slug = sys.argv[1:]
raw = open(p, 'rb').read(); d = json.loads(raw)
assert (json.dumps(d, indent=2) + '\n').encode() == raw, 'packs.json does not round-trip'
entry = json.load(open(e)); entry = entry.get(slug, entry) if isinstance(entry.get(slug), dict) else entry
assert slug not in d, 'slug already present'
d[slug] = {k: entry[k] for k in ('commit', 'key', 'pack', 'upstream')}
open(p, 'wb').write((json.dumps(d, indent=2) + '\n').encode())
print('packs.json +', slug)
EOF
  fi
  mkdir -p '$CL/patches/$slug/$key'
  cp '$PUBPAIR/$slug-$key.json' '$PUBPAIR/$slug-$key.diff' '$CL/patches/$slug/$key/'
  if [ -f '$WORK/OMITTED.md' ]; then cp '$WORK/OMITTED.md' '$CL/packs/$slug/$key/OMITTED.md'; fi
"
# -f: the reviewed tree is committed as-is, even where a nested upstream .gitignore (e.g. `tests/`, `test_*.py`)
# would hide our added v2 files. The post-commit tree comparison below proves nothing extra or missing went in.
git add -A -f "packs/$slug" "patches/$slug" packs/packs.json
git -c core.autocrlf=false commit -q -F "$MSG"
echo "committed $(git rev-parse --short HEAD): $(git show --stat --format= HEAD | tail -1)"
TAR="$(cygpath -w "/tmp/publish-$slug-$$.tar")"
git -c core.autocrlf=false -c core.eol=lf archive -o "$TAR" HEAD "packs/$slug/$key" "patches/$slug/$key"
TARL=$(wsl.exe -e wslpath -a "$TAR" | tr -d '\r')
wsl.exe -e bash -c "set -euo pipefail
  V=\$(mktemp -d ~/publish-verify.XXXX); tar -x -C \$V -f '$TARL'
  python3 -I '$LL/tools/review/treecmp.py' bytes \$V/packs/$slug/$key/$pack '$WORK/replay/$slug/$key/$pack' > \$V/committed-vs-reviewed.json \
    && echo 'committed tree == reviewed tree (bytes)' || { echo 'COMMITTED TREE DIFFERS'; cat \$V/committed-vs-reviewed.json; exit 1; }
  for ext in json diff; do
    cmp \$V/patches/$slug/$key/$slug-$key.\$ext '$PUBPAIR/$slug-$key.'\$ext || { echo \"COMMITTED .\$ext DIFFERS FROM THE REVIEWED PAIR\"; exit 1; }
    echo \"committed .\$ext == reviewed pair\"
  done
  mkdir -p \$V/pr/$slug/$key; cp -a \$V/packs/$slug/$key/$pack \$V/pr/$slug/$key/; rm -rf \$V/pr/$slug/$key/$pack/v2
  python3 -I '$LL/tools/packpair.py' apply \$V/pr/$slug/$key \$V/patches/$slug/$key/$slug-$key >/dev/null
  if python3 -I '$LL/tools/packpair.py' cmptree \$V/pr/$slug/$key/$pack/v2 \$V/packs/$slug/$key/$pack/v2; then
    echo 'committed pair replays onto committed pristine == committed v2 (bytes+modes)'
  else
    echo 'COMMITTED PAIR DOES NOT REPLAY TO THE COMMITTED v2'; exit 1
  fi
  echo verify dir \$V" || die "post-commit verification FAILED: the commit is local only; reset it with: git reset --hard origin/main"
echo "VERIFIED. To publish: cd $CW && git push origin HEAD:main"
