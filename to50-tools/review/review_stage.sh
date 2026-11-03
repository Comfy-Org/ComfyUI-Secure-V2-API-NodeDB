#!/usr/bin/env bash
# MERVYN's one-command publication review for a to-50% stage (run in WSL bash; never pushes or commits).
#   review_stage.sh <slug> [stage_dir]
# env: REPAIR=1   pristine comes from corpus main (packs/<slug>/<key> minus v2) instead of the upstream clone
#      DEPS=<dir> unpacked pinned wheels for the gate (default: <pack folder>/deps if it exists)
#      PARITY="<script> [<script>...]" parity scripts relative to v2/tests (default: v2/tests/test_*parity*.py)
#      SKIP_GATE=1 static checks only
# Writes <lane>/review/<slug>/<UTC>/ : review.log, FAILS.txt, WARNS.txt, *.json evidence, REVIEW.json.
set -uo pipefail
slug="$1"
L=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/to50-20261102
C=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/corpus
BASES=/mnt/c/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/coordination/jerry-rca-r2-20261029/sdk-surfaces-r1/runtime/worker/bases
B0=$BASES/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages
B1=$BASES/0b86765f07a7e81a1ef731161472c4af3ceba43b506238eed7fd548dd3bc3727/common-site-packages
T=$L/tools; RV=$T/review
PK=$L/packs/$slug
ST="${2:-$PK/stage}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT=$L/review/$slug/$TS; mkdir -p "$OUT"
W=$(mktemp -d ~/to50-review."$slug".XXXX)
PY="python3 -I"
log(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$OUT/review.log"; }
fail(){ log "FAIL: $*"; echo "$*" >> "$OUT/FAILS.txt"; }
warn(){ log "WARN: $*"; echo "$*" >> "$OUT/WARNS.txt"; }
: > "$OUT/FAILS.txt"; : > "$OUT/WARNS.txt"
log "review $slug stage=$ST work=$W out=$OUT tools=$(sha256sum "$RV"/*.py "$RV"/*.sh "$T/packpair.py" "$T/run_in_gate.sh" | awk '{printf "%s:%s ", substr($2, length($2)-20), substr($1,1,12)}')"

# ---- 0. layout --------------------------------------------------------------------------------------------------------
[ -d "$ST/packs/$slug" ] || { fail "no $ST/packs/$slug"; exit 1; }
mapfile -t keys < <(ls "$ST/packs/$slug")
[ "${#keys[@]}" -eq 1 ] || { fail "expected one key under stage/packs/$slug, found: ${keys[*]}"; exit 1; }
key=${keys[0]}
mapfile -t pfs < <(ls "$ST/packs/$slug/$key")
[ "${#pfs[@]}" -eq 1 ] || { fail "expected one pack folder, found: ${pfs[*]}"; exit 1; }
pack=${pfs[0]}
SP="$ST/packs/$slug/$key/$pack"
PAIR="$ST/patches/$slug/$key/$slug-$key"
[ -f "$PAIR.json" ] && [ -f "$PAIR.diff" ] || fail "pair missing: $PAIR.{json,diff}"
[ -d "$SP/v2" ] || fail "no v2/ in staged pack"
log "key=$key pack=$pack"
# Snapshot what is being reviewed: publication uses THIS pair and refuses if the live stage changed afterwards.
mkdir -p "$W/stage-snapshot"
cp "$PAIR.json" "$PAIR.diff" "$W/stage-snapshot/" 2>/dev/null
for f in SHA256SUMS packs-json-entry.json; do [ -f "$ST/$f" ] && cp "$ST/$f" "$W/stage-snapshot/"; done
[ -f "$W/stage-snapshot/SHA256SUMS" ] && log "stage snapshot: SHA256SUMS $(sha256sum "$W/stage-snapshot/SHA256SUMS" | cut -c1-16)"

# ---- 1. SHA256SUMS ------------------------------------------------------------------------------------------------------
if [ -f "$ST/SHA256SUMS" ]; then
  (cd "$ST" && sed 's/\r$//' SHA256SUMS | sha256sum -c --quiet - ) > "$OUT/sha256sums-check.txt" 2>&1 \
    && log "SHA256SUMS ok ($(wc -l < "$ST/SHA256SUMS") lines)" || fail "SHA256SUMS check failed (see sha256sums-check.txt)"
else
  fail "stage/SHA256SUMS missing"
fi

# ---- 2. packs.json entry ------------------------------------------------------------------------------------------------
ENTRY=""; for f in "$ST/packs-json-entry.json" "$PK/packs-json-entry.json"; do [ -f "$f" ] && { ENTRY=$f; break; }; done
if [ -z "$ENTRY" ]; then fail "packs-json-entry.json missing"; else
  $PY - "$ENTRY" "$C/packs/packs.json" "$slug" "$key" "$pack" "${REPAIR:-0}" > "$OUT/entry-check.json" <<'EOF' || fail "packs.json entry check failed (entry-check.json)"
import json, sys
entry_path, corpus_json, slug, key, pack, repair = sys.argv[1:]
e = json.load(open(entry_path)); corpus = json.load(open(corpus_json))
if slug in e and isinstance(e[slug], dict): e = e[slug]
fails = []
for k in ("commit", "key", "pack", "upstream"):
    if k not in e: fails.append(f"missing {k}")
if e.get("key") != key: fails.append(f"key {e.get('key')} != staged {key}")
if e.get("pack") != pack: fails.append(f"pack {e.get('pack')} != staged {pack}")
if e.get("commit", "")[:7] != key[1:8]: fails.append(f"key {key} is not x+commit[:7] ({e.get('commit')})")
if repair == "1":
    if corpus.get(slug) != e: fails.append(f"repair entry differs from corpus main: {corpus.get(slug)}")
elif slug in corpus:
    fails.append(f"slug already in corpus packs.json: {corpus[slug]}")
print(json.dumps({"entry": e, "fail": fails}, indent=1)); sys.exit(1 if fails else 0)
EOF
  log "entry: $(tr -d '\n' < "$OUT/entry-check.json" | cut -c1-300)"
fi
COMMIT=$($PY -c 'import json,sys; e=json.load(open(sys.argv[1])); s=sys.argv[2]; e=e.get(s,e) if isinstance(e.get(s),dict) else e; print(e.get("commit",""))' "$ENTRY" "$slug" 2>/dev/null)
UPSTREAM=$($PY -c 'import json,sys; e=json.load(open(sys.argv[1])); s=sys.argv[2]; e=e.get(s,e) if isinstance(e.get(s),dict) else e; print(e.get("upstream",""))' "$ENTRY" "$slug" 2>/dev/null)

# ---- 3. fresh pristine (ext4) -------------------------------------------------------------------------------------------
mkdir -p "$W/pristine/$slug/$key"
if [ "${REPAIR:-0}" = 1 ]; then
  (cd "$C" && git -c core.autocrlf=false -c core.eol=lf archive HEAD "packs/$slug/$key") | tar -x -C "$W" || fail "corpus archive failed"
  mkdir -p "$W/main/$slug/$key"; cp -a "$W/packs/$slug/$key/$pack" "$W/main/$slug/$key/"
  cp -a "$W/packs/$slug/$key/$pack" "$W/pristine/$slug/$key/"; rm -rf "$W/pristine/$slug/$key/$pack/v2"
  log "pristine from corpus main $(git -C "$C" rev-parse --short HEAD)"
else
  if git -c core.autocrlf=false clone --quiet --no-checkout "$UPSTREAM" "$W/up" 2>"$OUT/clone.err" \
     && git -C "$W/up" -c core.autocrlf=false -c advice.detachedHead=false checkout --quiet "$COMMIT" 2>>"$OUT/clone.err"; then
    rm -rf "$W/up/.git"; mv "$W/up" "$W/pristine/$slug/$key/$pack"
    log "pristine = fresh clone $UPSTREAM @ $COMMIT"
  else
    fail "upstream clone/checkout failed ($UPSTREAM @ $COMMIT): $(head -c 300 "$OUT/clone.err")"
  fi
fi
FP="$W/pristine/$slug/$key/$pack"
# PRE_OMITTED=1 (new packs): the worker staged with the Comfy omission policy already applied. Apply the same plan to the
# fresh pristine before comparing; the generic OMITTED.md goes to $W for publish_stage.sh, the list stays outside git.
if [ "${PRE_OMITTED:-0}" = 1 ] && [ "${REPAIR:-0}" != 1 ]; then
  mkdir -p /home/benjc/ab-expand/archive/omitted
  OLIST="/home/benjc/ab-expand/archive/omitted/$slug-$key-$(date -u +%Y%m%dT%H%M%SZ)-pre.json"
  if $PY "$RV/omit_media.py" plan "$FP" "$OLIST" > "$OUT/pre-omit.txt" 2>&1 \
     && $PY "$RV/omit_media.py" apply "$FP" "$OLIST" >> "$OUT/pre-omit.txt" 2>&1; then
    if $PY -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))['entries'] else 1)" "$OLIST"; then
      $PY "$RV/omit_media.py" note "$OLIST" "$W/OMITTED.md" >> "$OUT/pre-omit.txt" 2>&1
    fi
    log "PRE_OMITTED: omission plan applied to the fresh pristine (list $OLIST)"
  else
    fail "PRE_OMITTED: omission plan failed (pre-omit.txt)"
  fi
fi
$PY "$RV/treecmp.py" bytes "$SP" "$FP" --skip-v2 > "$OUT/pristine-cmp.json" \
  && log "staged pristine == fresh pristine (bytes)" || fail "staged pristine differs from fresh pristine (pristine-cmp.json)"

# ---- 4. replay the pair onto the fresh pristine, compare with staged v2 ------------------------------------------------
mkdir -p "$W/replay/$slug"; cp -a "$W/pristine/$slug/$key" "$W/replay/$slug/"
RP="$W/replay/$slug/$key/$pack"
if $PY "$T/packpair.py" apply "$W/replay/$slug/$key" "$PAIR" > "$OUT/apply.txt" 2>&1; then
  log "pair applies to fresh pristine"
  $PY "$RV/treecmp.py" bytes "$RP/v2" "$SP/v2" > "$OUT/replay-cmp.json" \
    && log "replayed v2 == staged v2 (bytes)" || fail "replayed v2 differs from staged v2 (replay-cmp.json)"
else
  fail "pair does not apply: $(tail -c 400 "$OUT/apply.txt")"
fi
$PY "$RV/treecmp.py" modes "$PAIR.json" "$FP" > "$OUT/pair-modes.json" \
  && log "pair modes ok" || fail "pair modes (pair-modes.json)"
grep -q '"warn": \[\]' "$OUT/pair-modes.json" || warn "pair modes differ from pristine for some files (pair-modes.json)"

# ---- 5. regenerate the pair from (fresh pristine + replayed v2) --------------------------------------------------------
if [ -d "$RP/v2" ]; then
  mkdir -p "$W/regen"
  if $PY "$T/packpair.py" generate "$W/replay/$slug/$key" "$W/regen" > "$OUT/regen.txt" 2>&1; then
    for ext in json diff; do
      cmp -s "$W/regen/$slug-$key.$ext" "$PAIR.$ext" && log "regenerated .$ext == staged" || fail "regenerated .$ext differs from staged pair"
    done
    log "pair counts $(cat "$OUT/regen.txt")"
  else
    fail "pair regeneration failed: $(tail -c 300 "$OUT/regen.txt")"
  fi
fi

# ---- 6. review diffs for MERVYN's reading -------------------------------------------------------------------------------
cp "$PAIR.diff" "$OUT/conversion.diff" 2>/dev/null
if [ "${REPAIR:-0}" = 1 ] && [ -d "$W/main/$slug/$key/$pack/v2" ] && [ -d "$RP/v2" ]; then
  (cd "$W" && diff -ruN "main/$slug/$key/$pack/v2" "replay/$slug/$key/$pack/v2") > "$OUT/repair-vs-main.diff"
  log "repair delta vs main: $(grep -c '^+++ ' "$OUT/repair-vs-main.diff") files, $(wc -l < "$OUT/repair-vs-main.diff") lines"
fi

# ---- 6b. Policy: committed text must not mention outside workflow collections or outside weights' provenance ----------
# Lines ADDED by the conversion (pair diff "+" lines) are scanned. The term list lives OUTSIDE git (MENTION_PATTERNS file,
# one extended regex); the built-in fallback is generic. Upstream pristine text is not scanned here.
PATTERNS_FILE="${MENTION_PATTERNS:-/home/benjc/ab-expand/archive/mention-patterns.txt}"
if [ -f "$PATTERNS_FILE" ]; then PATTERN=$(tr -d '\n' < "$PATTERNS_FILE"); else
  PATTERN='scraped|unlock|[0-9][0-9,]* (workflows|saved nodes|stored workflows)|/releases/download/|https?://[^ ]*\.(pth|pt|ckpt|safetensors|onnx|bin)\b'
fi
if [ -f "$OUT/conversion.diff" ]; then
  grep -n '^+' "$OUT/conversion.diff" | grep -v '^[0-9]*:+++ ' \
    | grep -iE "$PATTERN" \
    > "$OUT/external-mentions.txt" || true
  n=$(grep -c . "$OUT/external-mentions.txt")
  if [ "$n" -gt 0 ]; then
    fail "mention policy: $n added lines match the outside-source mention patterns (external-mentions.txt); scrub or justify"
  else
    log "external-mention rule: clean"
  fi
fi

# ---- 7. static SDK / hard-rule check ------------------------------------------------------------------------------------
if [ -d "$RP/v2" ]; then
  $PY "$RV/sdk_check.py" "$RP/v2" "0cd9adec=$B0" "0b86765f=$B1" > "$OUT/sdk-check.json" 2> "$OUT/sdk-check.err" \
    && log "sdk check PASS" || fail "sdk check FAIL (sdk-check.json)"
  $PY - "$OUT/sdk-check.json" <<'EOF' | tee -a "$OUT/review.log"
import json, sys, collections
d = json.load(open(sys.argv[1]))
print(f"  sdk: verdict={d['verdict']} min_base={d['min_base']} chains={len(d['chains'])} fails={len(d['fail'])} warns={dict(collections.Counter(w['rule'] for w in d['warn']))}")
for f in d["fail"][:20]: print(f"  sdk FAIL {f['rule']} {f['where']} {f['detail']}")
EOF
fi

# ---- 8. gate: real-encoder manifest recompute + V1/V2 interface diff; then parity re-run -------------------------------
if [ "${SKIP_GATE:-0}" != 1 ] && [ -d "$RP/v2" ]; then
  DEPSDIR="${DEPS:-}"; [ -z "$DEPSDIR" ] && [ -d "$PK/deps" ] && DEPSDIR="$PK/deps"
  export DEPS="$DEPSDIR"
  GATE_WAIT_S=3600 bash "$T/run_in_gate.sh" "$RP" "$RV" "$OUT/gate" gate_review.py > "$OUT/gate-review.out" 2> "$OUT/gate-review.err"
  rc=$?
  [ $rc -eq 0 ] && log "gate review PASS" || fail "gate review rc=$rc (gate/gate-review.json, gate-review.out)"
  head -c 1500 "$OUT/gate-review.out" | tee -a "$OUT/review.log"; echo | tee -a "$OUT/review.log"
  if [ -n "${PARITY:-}" ]; then read -r -a scripts <<< "$PARITY"; else
    mapfile -t scripts < <(cd "$RP/v2/tests" 2>/dev/null && ls test_*parity*.py 2>/dev/null)
  fi
  [ "${#scripts[@]}" -gt 0 ] || fail "no parity script found in v2/tests"
  for s in "${scripts[@]}"; do
    po="$OUT/parity/${s%.py}"; mkdir -p "$po"
    # LANE-SPEC mounts the pack root at /pack; some harnesses (packdb.load_pack) expect the snapshot dir (<slug>/<key>).
    # PARITY_MOUNT=pack|snapshot forces one; default: pack, then snapshot if the first run wrote no parity.json.
    mounts=("${PARITY_MOUNT:-pack}"); [ -z "${PARITY_MOUNT:-}" ] && mounts=(pack snapshot)
    rc=1
    for mnt in "${mounts[@]}"; do
      src="$RP"; [ "$mnt" = snapshot ] && src="$W/replay/$slug/$key"
      rm -f "$po/parity.json"
      GATE_WAIT_S=3600 bash "$T/run_in_gate.sh" "$src" "$RP/v2/tests" "$po" "$s" > "$po/stdout.txt" 2> "$po/stderr.txt"
      rc=$?
      log "parity $s mount=$mnt rc=$rc"
      [ -f "$po/parity.json" ] && break
      [ $rc -eq 0 ] && break   # a passing run on the first mount is final (some harnesses support only one mount)
    done
    [ $rc -eq 0 ] && log "parity $s rc=0" || fail "parity $s rc=$rc (parity/${s%.py}/stderr.txt)"
    if [ -f "$po/parity.json" ]; then
      $PY - "$po/parity.json" <<'EOF' | tee -a "$OUT/review.log"
import json, sys, collections
d = json.load(open(sys.argv[1]))
nodes = d.get("nodes", d) if isinstance(d, dict) else {}
c = collections.Counter(); cases = 0
for k, v in (nodes.items() if isinstance(nodes, dict) else []):
    if isinstance(v, dict) and "verdict" in v:
        c[v["verdict"]] += 1; cases += int(v.get("cases", v.get("case_count", 0)) or 0)
print(f"  parity verdicts {dict(c)} cases={cases} negative_control={d.get('negative_control') if isinstance(d, dict) else None}")
EOF
    elif [ $rc -eq 0 ] && grep -Eq '"(verdict|status)": "PASS"|"ok": true' "$po/stdout.txt"; then
      log "parity $s wrote no parity.json; its stdout reports PASS: $(grep -Eo '"(verdict|status)": "PASS"|"ok": true' "$po/stdout.txt" | tail -1)"
    else
      fail "parity $s wrote no parity.json"
    fi
  done
fi

# ---- 9. summary ---------------------------------------------------------------------------------------------------------
nf=$(grep -c . "$OUT/FAILS.txt"); nw=$(grep -c . "$OUT/WARNS.txt")
$PY - "$OUT" "$slug" "$key" "$pack" "$nf" "$nw" "$W" <<'EOF'
import json, sys, hashlib, os
out, slug, key, pack, nf, nw, work = sys.argv[1:]
ev = {}
for root, _, files in os.walk(out):
    for f in sorted(files):
        p = os.path.join(root, f)
        if f != "REVIEW.json":
            ev[os.path.relpath(p, out)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
r = {"slug": slug, "key": key, "pack": pack, "fails": open(os.path.join(out, "FAILS.txt")).read().splitlines(),
     "warns": open(os.path.join(out, "WARNS.txt")).read().splitlines(), "verdict": "FAIL" if int(nf) else "PASS (pending MERVYN diff read + claim spot-checks)",
     "work_dir": work, "evidence_sha256": ev}
json.dump(r, open(os.path.join(out, "REVIEW.json"), "w"), indent=1)
print(json.dumps({k: r[k] for k in ("slug", "key", "verdict", "fails", "warns")}, indent=1))
EOF
log "done: $nf fails, $nw warns -> $OUT (work dir $W kept for publication)"
