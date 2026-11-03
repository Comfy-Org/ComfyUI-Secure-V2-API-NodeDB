// Prompt Pixaroma - where a list / category is UP TO when it is not on Random.
//
// Pure random repeats (1,1,3,2,1 is normal), so a #list or *category can also run:
//   * shuffle - a deck: every option comes up once before any repeat, then it
//     reshuffles (and the new deck never opens with the card the old one ended on)
//   * order   - 1,2,3,... looping
// Both need to remember a POSITION between runs. That position lives here, in its own
// unregistered setting - NEVER in the workflow (a run must not dirty it, Vue Compat
// #18) and NEVER in the library blob (so an export carries your tags, not how far
// through them you happen to be).
//
// A cursor is keyed "list:<tag>" / "cat:<category>" (lower-cased), so it belongs to
// the list itself: two Prompt nodes using #poses walk the same sequence, which is
// what "this list is in order" means. Editing the list to a different length starts
// its deck over.

import { app } from "../../../scripts/app.js";

const CURSOR_SETTING = "Pixaroma.Prompt.Cursors";
// Shuffle leads because it is what people mean by "random": a surprise every time
// WITHOUT the same option landing twice in a row. It is also the DEFAULT, so a list
// with no mode of its own shuffles - true Random has to be asked for.
export const MODES = ["shuffle", "random", "order"];
export const DEFAULT_MODE = "shuffle";
export const MODE_LABEL = { random: "Random", shuffle: "Shuffle", order: "In order" };
export function isMode(m) { return MODES.includes(m); }
export function cleanMode(m) { return isMode(m) ? m : DEFAULT_MODE; }
// Does this mode keep a place between runs? (Random picks fresh every time, so it has
// no position to show and nothing to start over.) Distinct from "is the default".
export function hasPosition(m) { return cleanMode(m) !== "random"; }

export const listKey = (name) => "list:" + String(name).toLowerCase();
export const catKey = (name) => "cat:" + String(name).toLowerCase();

let _data = null;
let _loaded = false;
let _timer = null;

function settingsApi() {
  const s = app.ui?.settings;
  return s && typeof s.getSettingValue === "function" ? s : null;
}
// The cursor map, or NULL when settings are not ready yet. Null rather than an empty
// object on purpose: caching {} would hide the saved positions forever once settings
// DID arrive, and handing back a throwaway object would let a pick "advance" a
// sequence that is then silently dropped. Callers degrade instead (see nextIndex).
function all() {
  if (_loaded) return _data;
  const s = settingsApi();
  if (!s) return null;
  const raw = s.getSettingValue(CURSOR_SETTING);
  try { _data = (raw && typeof raw === "string" ? JSON.parse(raw) : raw) || {}; }
  catch { _data = {}; }
  if (!_data || typeof _data !== "object" || Array.isArray(_data)) _data = {};
  _loaded = true;
  return _data;
}
function persist() {
  const s = app.ui?.settings;
  if (!s || !_loaded || !_data) return;
  const json = JSON.stringify(_data);
  try {
    if (typeof s.setSettingValueAsync === "function") s.setSettingValueAsync(CURSOR_SETTING, json);
    else if (typeof s.setSettingValue === "function") s.setSettingValue(CURSOR_SETTING, json);
  } catch { /* non-fatal: still correct in memory for this session */ }
}
// Runs happen in bursts (a queue of 10 fires ten picks), so coalesce the writes.
function touch() {
  if (_timer) clearTimeout(_timer);
  _timer = setTimeout(() => { persist(); _timer = null; }, 300);
}
export function flushCursors() {
  if (_timer) { clearTimeout(_timer); _timer = null; }
  persist();
}
// Queue a run and close the tab inside the 300ms debounce and that run's advance
// would be lost. Best-effort flush on the way out (the write may still be cut short
// by the browser, but it costs nothing to try).
if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
  window.addEventListener("pagehide", () => { try { flushCursors(); } catch { /* ignore */ } });
}

// A stored deck must be DISTINCT in-range indices. Filtering the bad entries out
// would happily deal a corrupt deck like [0,0,1] - a repeat inside ONE deck, the one
// thing this mode promises never to do - so a deck that fails is thrown away whole.
// Shared with cursorInfo so the count it SHOWS can never describe a deck that
// nextIndex is about to discard and reshuffle.
function validBag(bag, n) {
  if (!Array.isArray(bag)) return false;
  const seen = new Set();
  for (const x of bag) {
    if (!Number.isInteger(x) || x < 0 || x >= n || seen.has(x)) return false;
    seen.add(x);
  }
  return true;
}

function shuffled(n) {
  const a = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Picks made but not yet spent on a run. `app.graphToPrompt` is NOT a queue: ComfyUI
// calls it for Workflow > Export, for workflow sharing, and several Pixaroma Save
// buttons call it too. Advancing on every call meant pressing Save silently ate the
// next entry, so an "In order" list skipped it forever - and a run that failed
// validation burned one as well.
// Holding the pick here also makes EVERY node in one prompt build agree: two Prompt
// nodes using the same #list get the same line (which is what "they move through it
// together" means), and a parked, unwired node can no longer steal picks from the one
// you are actually using.
// Cleared by commitPicks() once a queue has genuinely been accepted.
// The ADVANCE rides along in `state` and is applied to the stored map only here, when
// a queue has genuinely been accepted. It used to be written at roll time with only
// the in-memory `_pending` acting as the hold - which meant the hold protected nothing
// durable: pressing Export, or a run rejected by validation, permanently advanced an
// "In order" list on disk, the card immediately reported a position no run had reached,
// and after a tab reload that option was skipped for good. That is the exact symptom
// the hold was introduced to fix; it only papered over it while the tab stayed alive.
// If the tab dies between an accepted queue and this call the advance is lost, so a
// run REPEATS an option rather than SKIPPING one - the safe direction of the two.
const _pending = new Map();   // key -> { i, n, mode, state, build }
// Which prompt BUILD each held pick belongs to. Without this, commitPicks spent every
// pick it was holding, including ones rolled by a build that was never queued - so an
// Export (or a rejected run) still burned an option, just one accepted run later
// instead of immediately. A pick from an older build stays HELD (clearing it would
// destroy the hold that this whole mechanism exists for) until a build that actually
// uses that key is accepted.
let _build = 0;
// The build id MUST ride on the PROMPT OBJECT, not on a module global. commitPicks runs
// when the POST resolves, and ANY other graphToPrompt in that window (a Pixaroma Save
// button, Workflow > Export, another extension) moves a global on - so the commit spent
// the un-queued build's picks and dropped the accepted run's own. Measured inversion of
// both halves at once: the run's list repeated while the export's list skipped.
const _buildOf = new WeakMap();
// IDEMPOTENT PER PROMPT OBJECT, and that is load-bearing now that TWO nodes roll
// picks. Prompt Pixaroma and AI Prompt each wrap app.graphToPrompt, so both hooks run
// for one build - and extension load order is not stable, so neither can assume it
// goes first. If this incremented twice, the hook that ran FIRST would stamp its picks
// with build N while the prompt object ended up carrying N+1, and commitPicks would
// skip those picks forever: that node's "In order" list would never advance.
// One graphToPrompt call creates one fresh output object, so object identity IS the
// build. Whichever hook sees it first opens the build; the second reuses it, and both
// nodes' picks are spent together by the one commit.
// Callers MUST call this BEFORE rolling anything, or they roll under the previous
// build's number.
export function beginPickBuild(promptObj) {
  if (promptObj && typeof promptObj === "object") {
    const already = _buildOf.get(promptObj);
    if (already != null) return already;
  }
  _build++;
  if (promptObj && typeof promptObj === "object") {
    try { _buildOf.set(promptObj, _build); } catch { /* not weak-mappable, fall back */ }
  }
  return _build;
}
// `queued` is the prompt object that was actually POSTed, so the picks spent are
// exactly the ones that produced it. Without it we can only assume the newest build.
export function commitPicks(queued) {
  if (!_pending.size) return;
  let build = _build;
  if (queued && typeof queued === "object") {
    const b = _buildOf.get(queued);
    if (b != null) build = b;
  }
  const map = all();
  let wrote = false;
  for (const [key, p] of _pending) {
    if (p.build !== build) continue;           // rolled by a build that was not queued
    if (map && p.state) { map[key] = p.state; wrote = true; }
    _pending.delete(key);
  }
  // Only when something durable actually changed: a run whose lists are all on Random
  // (state null) has nothing to save, and flushing anyway wrote the settings blob on
  // every queue of a batch and created the key on installs that never had one.
  if (wrote) flushCursors();
}

// The index to use NOW, advancing the cursor. `len` is the current pool size, so a
// list that was edited to a different length starts its sequence over. A pick already
// made and not yet spent on a run is REUSED (see _pending above) - the mode and pool
// size must still match, or the pick no longer means anything.
// `occ` is WHICH USE of this key we are answering within one prompt build: the first
// `#fruit` in a box is 0, the second 1, the third 2. Repeats used to all collide on
// the single held pick, so `#fruit #fruit #fruit` printed one word three times (users
// asked for three different ones; this was invariant #39's documented "LEFT" item).
// The hold is therefore an ARRAY of picks per key rather than one, which keeps BOTH
// things the hold exists for: an un-queued build (Export, a Save button, a rejected
// queue) still hands the same cards back to the real run, and a second Prompt node
// starts its own count at 0 so it agrees with the first node's first use - which is
// also what stops a parked, unwired node stealing a card off the deck.
// IN ORDER is deliberately exempt: it advances once per RUN, so every use in one
// build reports the same entry (the user's call - "only in order will be the same").
export function nextIndex(key, len, mode, occ = 0) {
  const n = Math.floor(len);
  if (!(n > 0)) return -1;
  const m = cleanMode(mode);
  const want = m === "order" ? 0 : Math.max(0, Math.floor(occ) || 0);
  const held = _pending.get(key);
  if (held && held.n === n && held.mode === m) {
    // RE-STAMP: this build is using the held pick, so it is this build's to spend.
    // Without this, a pick first rolled by an un-queued build (an Export) would keep
    // that build's stamp forever and never commit, so a real run using it would not
    // advance the sequence at all.
    held.build = _build;
    // Deal as many further cards as this build has asked for, each continuing from the
    // previous one's state so a shuffle keeps dealing down the SAME deck.
    while (held.picks.length <= want) {
      const more = rollIndex(key, n, m, held.state);
      if (more.i < 0) break;
      held.picks.push(more.i);
      held.state = more.state;
    }
    return held.picks[Math.min(want, held.picks.length - 1)];
  }
  const r = rollIndex(key, n, m);
  if (r.i < 0) return r.i;
  const rec = { picks: [r.i], n, mode: m, state: r.state, build: _build };
  _pending.set(key, rec);
  while (rec.picks.length <= want) {
    const more = rollIndex(key, n, m, rec.state);
    if (more.i < 0) break;
    rec.picks.push(more.i);
    rec.state = more.state;
  }
  return rec.picks[Math.min(want, rec.picks.length - 1)];
}

// The actual draw. Called by nextIndex - once per key for the first use in a build,
// then again per extra use (a repeated #list in one box), each time continuing from
// the previous draw's `from` state so a shuffle deals down the SAME deck instead of
// re-reading the stored one and handing back the card it just dealt.
// Returns { i, state }: `state` is what the stored cursor SHOULD become if this pick is
// spent on a real run. It is deliberately NOT written here - commitPicks applies it.
function rollIndex(key, n, m, from) {
  if (m === "random" || n === 1) return { i: Math.floor(Math.random() * n), state: from ?? null };
  const map = all();
  // Nowhere to remember a position (settings not ready). Fall back to a plain random
  // pick rather than pretending to sequence and dropping the result.
  if (!map) return { i: Math.floor(Math.random() * n), state: null };
  let st = from !== undefined ? from : map[key];
  if (!st || typeof st !== "object" || st.n !== n) st = null;   // pool changed -> restart

  if (m === "order") {
    const i = st && Number.isInteger(st.i) ? ((st.i % n) + n) % n : 0;
    return { i, state: { n, i: (i + 1) % n, last: i } };
  }
  // shuffle: deal from a deck, reshuffle when it runs out.
  // A stored deck must be DISTINCT in-range indices. Filtering out the bad entries
  // (the old behaviour) would happily deal a corrupt deck like [0,0,1] - a repeat
  // inside one deck, which is the one thing this mode promises never to do - so a
  // deck that fails the check is thrown away and reshuffled instead.
  let bag = validBag(st && st.bag, n) ? st.bag.slice() : null;
  const last = st && Number.isInteger(st.last) ? st.last : -1;
  if (!bag || !bag.length) {
    bag = shuffled(n);
    // Don't open a new deck with the card the old one closed on - that is exactly the
    // back-to-back repeat this mode exists to avoid. Cards are dealt from the END, so
    // the offender is the last element. SWAP it with a random other position rather
    // than rotating it to the front: rotating maps every blocked deck onto ONE
    // specific allowed deck, which leaves that deck twice as likely as the others
    // (measured: consecutive decks came out identical 33% of the time instead of 25%,
    // so a 3-option list visibly looked like it was cycling). A random swap spreads
    // the blocked decks evenly, giving a uniform draw over the allowed ones.
    if (n > 1 && bag[bag.length - 1] === last) {
      const j = Math.floor(Math.random() * (n - 1));   // any slot except the last
      [bag[n - 1], bag[j]] = [bag[j], bag[n - 1]];
    }
  }
  const i = bag.pop();
  return { i, state: { n, bag, last: i } };
}

// What to show in the library: how far through the sequence this cursor is.
// Returns null for random (nothing to show) or when nothing has run yet.
export function cursorInfo(key, len, mode) {
  const n = Math.floor(len);
  const m = cleanMode(mode);
  if (m === "random" || !(n > 0)) return null;
  const map = all();
  const st = map && map[key];
  if (!st || typeof st !== "object" || st.n !== n) return m === "order" ? `next 1 of ${n}` : `${n} left`;
  if (m === "order") {
    const i = Number.isInteger(st.i) ? ((st.i % n) + n) % n : 0;
    return `next ${i + 1} of ${n}`;
  }
  // A deck nextIndex would reject must not be reported as if it were live.
  const left = validBag(st.bag, n) ? st.bag.length : 0;
  return `${left || n} left in the deck`;
}

// Start this list / category over (the deck reshuffles, the counter returns to 1).
export function resetCursor(key) {
  _pending.delete(key);          // a held pick belongs to the old sequence
  const map = all();
  if (map && map[key]) { delete map[key]; touch(); }
}

// Carry a position to a new name. Renaming a list / category is not a change of
// CONTENT, so "next 4 of 12" must not silently become "next 1 of 12" (and the old key
// must not linger in storage forever).
export function renameCursor(fromKey, toKey) {
  if (fromKey === toKey) return;
  const held = _pending.get(fromKey);
  if (held) { _pending.set(toKey, held); _pending.delete(fromKey); }
  const map = all();
  if (!map || !map[fromKey]) return;
  map[toKey] = map[fromKey];
  delete map[fromKey];
  touch();
}
