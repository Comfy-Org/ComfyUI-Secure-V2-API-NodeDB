// Prompt Pixaroma - the tag library store.
//
// The library is { version, categories:[name...], tags:[{name, cat, text}...] },
// shared across every Prompt Pixaroma node on this machine. It is persisted as
// ONE JSON blob in an UNREGISTERED ComfyUI setting ("Pixaroma.Prompt.Library"),
// which:
//   * lives in ComfyUI's user settings, OUTSIDE our plugin folder, so it survives
//     updating / reinstalling the Pixaroma plugin (the user's #1 ask);
//   * is private to the user - it is NEVER written into a workflow, so a shared
//     workflow keeps the author's prompts to themselves;
//   * persists even though it is not declared in any extension's settings[]
//     (Vue Compat #20: comfy.settings.json is a plain JSON merge, no allow-list).
//     Same mechanism Seed history + Node Colors favorites use.
//
// tags are kept newest-first (new ones are unshifted on). categories are ordered
// and may be empty.
//
// A tag carries an OPTIONAL kind:"list" - one option per line, rolled to a single
// line by a #name token (see expand.mjs). The key is written ONLY when it is "list",
// so an existing library / an old export file needs no migration and is never
// rewritten just to add a default.
//
// EVERY CATEGORY BELONGS TO ONE SIDE: a Text category or a List category. `listCats`
// names the List ones (a subset of `categories`, which stays the full ordered list so
// an older Pixaroma reading a newer file still sees every category). A tag whose kind
// disagrees with its category's side is moved to its own bucket by normalize - the
// TAG's kind always wins, so a list can never be silently turned into plain text.
// "Text" and "List" are the two implicit buckets for a tag with no category (they
// replaced the single "Uncategorized" bucket); like it, they are reserved names and
// can never be real categories.

import { app } from "../../../scripts/app.js";
import { cleanMode, DEFAULT_MODE, resetCursor, listKey } from "./cursors.mjs";

const LIBRARY_SETTING = "Pixaroma.Prompt.Library";
export const NAME_RE = /[^a-zA-Z0-9_\-]/g;
// The two implicit buckets for a tag with no category, one per side.
export const TEXT_BUCKET = "Text";
export const LIST_BUCKET = "List";
// The single pre-2026-07-24 bucket. Still recognised on read so an existing library
// (or an old export file) folds into the new buckets; never written or shown again.
export const UNCATEGORIZED = "Uncategorized";
const RESERVED = new Set([TEXT_BUCKET, LIST_BUCKET, UNCATEGORIZED].map((s) => s.toLowerCase()));
const lc = (s) => String(s == null ? "" : s).toLowerCase();

// Seeded ONCE, the first time this browser opens a Prompt node (setting never
// written). Gives a new user a working template; every seed is editable/deletable.
const SEED = {
  version: 1,
  categories: ["Styles", "Lighting", "Camera", "Subjects"],
  listCats: ["Subjects"],   // so a new user sees what a List category is for
  tags: [
    { name: "animal", cat: "Subjects", kind: "list", text: "a red fox\na snow leopard\na barn owl\na koi carp" },
    { name: "oilpainting", cat: "Styles", text: "oil painting, thick impasto brush strokes, dramatic Rembrandt lighting, rich canvas texture, fine-art masterpiece" },
    { name: "watercolor", cat: "Styles", text: "loose watercolor wash, soft bleeding edges, paper texture, gentle pigment" },
    { name: "cyberpunk", cat: "Styles", text: "cyberpunk city, neon signs, rain-slick streets, volumetric fog, blade-runner mood" },
    { name: "goldenhour", cat: "Lighting", text: "golden hour, warm low sun, long soft shadows, cinematic rim light" },
    { name: "portrait", cat: "Camera", text: "head and shoulders portrait, shallow depth of field, 85mm lens, soft studio light" },
  ],
};

let _data = null;
let _persistTimer = null;
const _subs = new Set();

function settingsApi() {
  const s = app.ui?.settings;
  return s && typeof s.getSettingValue === "function" ? s : null;
}

// Only a real string (or a number, which hand-edited JSON produces) can NAME a thing.
// Blind String() coercion turned objects/arrays in an import file into categories
// literally called "[object Object]" and tags called "objectObject" - fabricated
// names the dropped-counter never saw. Guard the TYPE here, once, for every name.
function asName(v) {
  if (typeof v === "number" && Number.isFinite(v)) v = String(v);
  return typeof v === "string" ? v.trim() : "";
}
function cleanName(n) {
  return asName(n).replace(NAME_RE, "");
}

// Coerce any parsed blob into the canonical shape, deduping tag names.
function normalize(raw) {
  const out = { version: 1, categories: [], listCats: [], tags: [] };
  const src = raw && typeof raw === "object" ? raw : {};
  const seenCat = new Set();
  const addCat = (c) => {
    const name = asName(c);
    // Reserved names are case-INSENSITIVE: a user-typed "list" must not survive as a
    // separate category that then merges with the synthetic bucket of the same name.
    if (!name || RESERVED.has(lc(name)) || seenCat.has(lc(name))) return;
    seenCat.add(lc(name));
    out.categories.push(name);
  };
  for (const c of (Array.isArray(src.categories) ? src.categories : [])) addCat(c);
  // Declared List-side categories. A name here that the categories array forgot is
  // still a real category, so add it (an export of only the list side has no
  // `categories` overlap to rely on).
  const listKeys = new Set();
  for (const c of (Array.isArray(src.listCats) ? src.listCats : [])) {
    const name = asName(c);
    if (!name || RESERVED.has(lc(name))) continue;
    listKeys.add(lc(name));
    addCat(name);
  }
  const seenTag = new Set();
  for (const t of (Array.isArray(src.tags) ? src.tags : [])) {
    if (!t) continue;
    const name = cleanName(t.name);
    if (!name || seenTag.has(lc(name))) continue;
    seenTag.add(lc(name));
    let cat = asName(t.cat);
    let kind = t.kind === "list" ? "list" : "text";
    if (RESERVED.has(lc(cat))) {
      // A bucket name is not a category. "List" also TELLS us the tag is a list (an
      // import file may name the bucket instead of setting kind), and that only ever
      // ADDS information since an unset kind already means text.
      // "Text" must NOT do the mirror image: forcing kind="text" there would strip an
      // explicit kind:"list" and silently turn someone's list into a snippet, which is
      // exactly what "the tag's kind always wins" forbids. Legacy "Uncategorized"
      // likewise says nothing about the kind.
      if (lc(cat) === lc(LIST_BUCKET)) kind = "list";
      cat = "";
    }
    const rec = { name, cat, text: typeof t.text === "string" ? t.text : "" };
    // Only "list" is stored; anything else (missing, "text", junk) stays absent so a
    // plain text library round-trips byte-identical. Same for mode: the DEFAULT is
    // never written, so only a deliberate Random / In order is stored.
    if (kind === "list") rec.kind = "list";
    // Kept regardless of kind: the editor only offers it on a List, but `#texttag`
    // rolls a text tag's lines too, and gating on kind meant flipping a list to Text
    // and back silently lost the mode (the working copy kept it, the store did not).
    const mode = cleanMode(t.mode);
    if (mode !== DEFAULT_MODE) rec.mode = mode;
    out.tags.push(rec);
  }
  // Reconcile every tag's category to the canonical (case-matching) entry in the
  // list; a category a tag references but the list forgot is added - so the editor
  // sidebar (exact match) and the node's category list never disagree, and a
  // case-variant ("styles" vs "Styles") can't orphan a tag.
  const catByKey = new Map(out.categories.map((c) => [lc(c), c]));
  for (const t of out.tags) {
    if (!t.cat) continue;
    const canon = catByKey.get(lc(t.cat));
    if (canon) t.cat = canon;
    else { out.categories.push(t.cat); catByKey.set(lc(t.cat), t.cat); seenCat.add(lc(t.cat)); }
  }
  // Side repair (also the one-time migration for a library written before sides
  // existed): an UNDECLARED category holding nothing but lists is a List category.
  // Bucket the tags ONCE - re-filtering every tag per category made normalize
  // O(categories x tags), and normalize runs on every load AND every single edit.
  const tagsByCat = new Map();
  for (const t of out.tags) {
    if (!t.cat) continue;
    const k = lc(t.cat);
    const arr = tagsByCat.get(k);
    if (arr) arr.push(t); else tagsByCat.set(k, [t]);
  }
  // ONLY for a library/file written before sides existed. `listCats` being present at
  // all is the marker that sides are already declared - normalize always writes it, so
  // only a pre-sides blob lacks it. Running the heuristic every time meant a live Text
  // category could be silently PROMOTED to a List category: import a list over the one
  // text tag in `Styles` with "Replace mine", and `Styles` jumped to the List block
  // where text tags can no longer be filed. (With two tags in it the same action
  // evicted the tag instead, so one operation had two different outcomes.)
  const sidesDeclared = Array.isArray(src.listCats);
  if (!sidesDeclared) {
    for (const c of out.categories) {
      if (listKeys.has(lc(c))) continue;
      const inCat = tagsByCat.get(lc(c));
      if (inCat && inCat.length && inCat.every((t) => t.kind === "list")) listKeys.add(lc(c));
    }
  }
  // A category belongs to ONE side, so a tag whose kind disagrees with it moves to
  // its own bucket. The TAG's kind wins - never silently retype someone's list.
  for (const t of out.tags) {
    if (!t.cat) continue;
    const side = listKeys.has(lc(t.cat)) ? "list" : "text";
    if (side !== (t.kind === "list" ? "list" : "text")) t.cat = "";
  }
  out.listCats = out.categories.filter((c) => listKeys.has(lc(c)));
  // How each category picks (for its *wildcard). Keyed by the CANONICAL name so a
  // rename / case-variant can't orphan it; the DEFAULT mode is dropped, not stored.
  const srcModes = src.catModes && typeof src.catModes === "object" ? src.catModes : {};
  const byKey = new Map(out.categories.map((c) => [lc(c), c]));
  byKey.set(lc(TEXT_BUCKET), TEXT_BUCKET);
  byKey.set(lc(LIST_BUCKET), LIST_BUCKET);
  out.catModes = {};
  for (const [k, v] of Object.entries(srcModes)) {
    const canon = byKey.get(lc(k));
    const m = cleanMode(v);
    if (canon && m !== DEFAULT_MODE) out.catModes[canon] = m;
  }
  return out;
}

function persist(data) {
  const s = app.ui?.settings;
  if (!s) return;
  const json = JSON.stringify(data);
  try {
    if (typeof s.setSettingValueAsync === "function") s.setSettingValueAsync(LIBRARY_SETTING, json);
    else if (typeof s.setSettingValue === "function") s.setSettingValue(LIBRARY_SETTING, json);
  } catch { /* non-fatal: still applied in-memory this session */ }
}

// The live library { categories, tags }. Same cached instance between reads; go
// through setLibrary / commitLibrary to mutate so subscribers + storage stay synced.
export function getLibrary() {
  if (_data) return _data;
  const s = settingsApi();
  if (!s) return normalize(SEED); // settings not ready yet: don't cache the seed
  const raw = s.getSettingValue(LIBRARY_SETTING);
  if (raw == null) {
    _data = normalize(SEED);
    persist(_data); // lock the seed in so it's immediately editable
    return _data;
  }
  try {
    _data = normalize(typeof raw === "string" ? JSON.parse(raw) : raw);
  } catch {
    _data = normalize({});
  }
  return _data;
}

// Drop the cache so the next getLibrary() re-reads the setting from the server.
// The library is shared by every tab / window pointing at this ComfyUI, and each one
// caches it forever, so a second tab's edits are invisible here. Call this before
// taking a working copy (the editor does, on open) - otherwise the editor could open
// on a stale snapshot and write it straight back over the other tab's work.
export function reloadLibrary() { _data = null; return getLibrary(); }

// Would committing `data` actually change anything? Both sides are normalized first,
// so key order and dropped defaults cannot make an identical library look different
// (a raw JSON.stringify of a working copy always differs - `clone` and `normalize`
// order their keys differently).
export function isSameAsStored(data) {
  try { return JSON.stringify(normalize(data)) === JSON.stringify(getLibrary()); }
  catch { return false; }
}

export function getTags() { return getLibrary().tags; }

// Ordered category names. `side` ("text" | "list") filters to one side; omit for
// both. The side's bucket is appended when a tag actually sits in it. (normalize
// guarantees every referenced category is already in the list.)
export function getCategories(side) {
  const data = getLibrary();
  const out = data.categories.filter((c) => !side || sideOfCat(c, data) === side);
  if (side !== "list" && data.tags.some((t) => !t.cat && !isListTag(t))) out.push(TEXT_BUCKET);
  if (side !== "text" && data.tags.some((t) => !t.cat && isListTag(t))) out.push(LIST_BUCKET);
  return out;
}
// The tags that show under a category name (a real one or a bucket).
export function tagsInCat(name, data) {
  const d = data || getLibrary();
  return d.tags.filter((t) => lc(catOf(t)) === lc(name));
}

// Is this tag meant to be rolled one line at a time? (Cosmetic + convenience only:
// the SYMBOL decides what actually happens at expand time, so a mismatch can never
// error - see .claude/patterns/prompt.md #25.)
export function isListTag(t) { return !!t && t.kind === "list"; }

// THE splitter for a list tag's options: one per line, trimmed, blanks dropped.
// Shared by the run pick, the preview, the highlight and the autocomplete count so
// none of them can disagree about whether a #list is live.
export function tagLines(text) {
  if (typeof text !== "string") return [];
  const out = [];
  for (const raw of text.split(/\r?\n/)) { const s = raw.trim(); if (s) out.push(s); }
  return out;
}

// The category a tag shows under: its own, else the bucket for its side.
export function catOf(t) { return (t && t.cat) || (isListTag(t) ? LIST_BUCKET : TEXT_BUCKET); }

// Which side a category name sits on. The two buckets answer for themselves; an
// unknown name is a Text category (the default side).
export function sideOfCat(name, data) {
  if (lc(name) === lc(LIST_BUCKET)) return "list";
  if (lc(name) === lc(TEXT_BUCKET)) return "text";
  const d = data || getLibrary();
  return (d.listCats || []).some((c) => lc(c) === lc(name)) ? "list" : "text";
}
export function isListCat(name, data) { return sideOfCat(name, data) === "list"; }

// ── category ORDER ─────────────────────────────────────────────────────────
// `categories` is ONE flat ordered list holding both sides, but the editor draws a
// Text block and a List block, so the row ABOVE a category on screen is the previous
// SAME-SIDE entry - not necessarily the previous entry in the array. Every helper
// below therefore thinks in same-side terms and writes back into the flat list.
//
// Reorder touches `categories` and NOTHING ELSE, by design: normalize() re-derives
// `listCats` order from it, `catModes` is keyed by NAME, the cursors are keyed by
// NAME, and a tag points at its category by NAME. So moving a row can never orphan a
// tag, lose a Picks mode, or restart a sequence. Keep it that way - the moment a
// reorder has to touch a second structure, it can drift out of step with this one.

// Where a category sits in the flat list. Exact match first (what every other caller
// uses), then case-insensitive, so a hand-edited library whose tag says "styles"
// while the list says "Styles" still resolves to the same row.
function catIndex(list, name) {
  const i = list.indexOf(name);
  if (i > -1) return i;
  const k = lc(name);
  return list.findIndex((c) => lc(c) === k);
}

// The categories sharing `cat`'s side, in display order.
export function catsOnSameSide(data, cat) {
  const d = data || getLibrary();
  const side = sideOfCat(cat, d);
  return (d.categories || []).filter((c) => sideOfCat(c, d) === side);
}

// Move `cat` one row up (dir -1) or down (dir +1) inside its own side's block.
// Returns a NEW ordered categories array, or null when it cannot move (already at
// the end of its block, or the name is not a real category).
export function reorderCategoryStep(data, cat, dir) {
  const list = Array.isArray(data?.categories) ? data.categories : [];
  const from = catIndex(list, cat);
  if (from < 0 || (dir !== 1 && dir !== -1)) return null;
  const side = sideOfCat(list[from], data);
  // Walk the flat list for the nearest neighbour on the SAME side, stepping over the
  // other side's entries - on screen they are in a different block entirely.
  let to = -1;
  for (let i = from + dir; i >= 0 && i < list.length; i += dir) {
    if (sideOfCat(list[i], data) === side) { to = i; break; }
  }
  if (to < 0) return null;
  const next = list.slice();
  const tmp = next[from]; next[from] = next[to]; next[to] = tmp;
  return next;
}

// Is that step possible? Deliberately answered BY the move itself, so a dimmed
// "Move up" and a Move-up that does nothing can never disagree (the validator and
// its display share one implementation - see .claude/patterns/prompt.md #30).
export function canMoveCategory(data, cat, dir) {
  return reorderCategoryStep(data, cat, dir) !== null;
}

// Move `moved` so it sits directly above (`above` true) or below `target`. Both must
// be real categories on the SAME side - a category belongs to one block, and letting
// a drag carry it across would clear the category off every tag in it (normalize's
// "the tag's kind always wins"). Returns a NEW ordered categories array, or null when
// the move is refused or would change nothing.
export function reorderCategoryTo(data, moved, target, above) {
  const list = Array.isArray(data?.categories) ? data.categories : [];
  const from = catIndex(list, moved);
  const t0 = catIndex(list, target);
  if (from < 0 || t0 < 0 || from === t0) return null;
  if (sideOfCat(list[from], data) !== sideOfCat(list[t0], data)) return null;
  const side = sideOfCat(list[from], data);
  const next = list.slice();
  const [name] = next.splice(from, 1);
  // Re-find the target: removing an entry ABOVE it has shifted it down one.
  const t = catIndex(next, target);
  if (t < 0) return null;
  next.splice(above ? t : t + 1, 0, name);
  // A drop that lands exactly where it already was is not a change. Compare the
  // PER-SIDE sequence, never the flat array: the two sides are drawn as separate
  // blocks, so where a Text category sits relative to a List category in the flat
  // list is arbitrary and completely invisible. Dropping Styles just above Camera
  // when it is already the row above DOES shift it past a List category in the
  // array while changing nothing on screen - comparing the flat list called that a
  // move and committed + re-rendered the whole editor for it.
  const seq = (arr) => arr.filter((c) => sideOfCat(c, data) === side);
  const a = seq(next), b = seq(list);
  return a.every((c, i) => c === b[i]) ? null : next;
}

// How a list / a category picks: "random" | "shuffle" | "order" (see cursors.mjs).
export function tagMode(t) { return cleanMode(t && t.mode); }
export function catMode(name, data) {
  const d = data || getLibrary();
  const m = d.catModes || {};
  // OWN properties only: a category named "toString" / "constructor" would otherwise
  // read an inherited function off Object.prototype. cleanMode would fall back to the
  // default anyway, but reading inherited junk is the kind of thing that turns into a
  // real bug the moment this map grows a second use.
  const own = Object.prototype.hasOwnProperty;
  return cleanMode(own.call(m, name) ? m[name] : (own.call(m, String(name)) ? m[String(name)] : undefined));
}

export function findTag(name) {
  const k = String(name).toLowerCase();
  for (const t of getTags()) if (t.name.toLowerCase() === k) return t;
  return null;
}

// A name not already used by another tag (case-insensitive). Appends -2, -3, ...
export function uniqueTagName(base, ignore) {
  let n = cleanName(base) || "tag";
  const taken = (x) => {
    const k = x.toLowerCase();
    for (const t of getTags()) { if (t === ignore) continue; if (t.name.toLowerCase() === k) return true; }
    return false;
  };
  if (!taken(n)) return n;
  const stem = n; let i = 2;
  while (taken(stem + "-" + i)) i++;
  return stem + "-" + i;
}

function fanout() {
  for (const fn of _subs) { try { fn(_data); } catch { /* one bad listener can't break the rest */ } }
}

// Replace the whole library and persist immediately (add / delete / import / rename).
export function setLibrary(data) {
  _data = normalize(data);
  if (_persistTimer) { clearTimeout(_persistTimer); _persistTimer = null; }
  persist(_data);
  fanout();
  return _data;
}

// Live edit: update cache + notify subscribers now (nodes re-highlight/preview as
// you type), DEBOUNCE the settings write so we don't hammer comfy.settings.json.
export function commitLibrary(data) {
  _data = normalize(data);
  fanout();
  if (_persistTimer) clearTimeout(_persistTimer);
  _persistTimer = setTimeout(() => { persist(_data); _persistTimer = null; }, 350);
  return _data;
}

// Flush any pending debounced write now (call on blur / editor close).
// ONLY when a write is actually pending. Persisting unconditionally quietly cancelled
// the editor's own cross-tab guard: closeLibraryEditor deliberately skips
// commitLibrary when nothing changed (so tab A cannot stamp its open-time snapshot
// over tab B's edits), and then this wrote that snapshot out anyway two lines later.
// Gating on the pending TIMER is the right test and still cannot lose the last edit -
// an in-editor edit always leaves a timer set until it is written.
export function flushLibrary() {
  if (!_persistTimer) return;
  clearTimeout(_persistTimer); _persistTimer = null;
  if (_data) persist(_data);
}

export function subscribe(fn) { _subs.add(fn); return () => _subs.delete(fn); }

// Serialize the library for a file. `cat` omitted / null = everything; otherwise
// only that one bucket (pass TEXT_BUCKET / LIST_BUCKET for the tags with no category
// of their own). A scoped
// export still carries its category entry so the tags land back in the right place.
export function exportLibraryJSON(cat) {
  const lib = getLibrary();
  if (cat == null) return JSON.stringify(lib, null, 2);
  const tags = tagsInCat(cat, lib);
  // A bucket is not a real category, so it contributes no category entry - the tags'
  // own kind puts them back in the right bucket on import.
  const categories = lib.categories.filter((c) => lc(c) === lc(cat));
  const listCats = categories.filter((c) => isListCat(c, lib));
  // A BUCKET carries no category entry, but it CAN have its own Picks mode - look it
  // up by the scope name itself, not through `categories` (which is empty for a
  // bucket), or exporting just the Text/List bucket would silently drop its mode.
  const catModes = {};
  for (const [k, v] of Object.entries(lib.catModes || {})) if (lc(k) === lc(cat)) catModes[k] = v;
  return JSON.stringify({ version: 1, categories, listCats, catModes, tags }, null, 2);
}

// The buckets a parsed import file contains, in file order, with counts - what the
// import preview lists so the user can bring in only the categories they want.
export function importCategories(parsed) {
  const out = [];
  const seen = new Map();
  for (const t of (parsed?.data?.tags || [])) {
    const c = catOf(t);
    const k = c.toLowerCase();
    if (!seen.has(k)) { seen.set(k, { name: c, count: 0 }); out.push(seen.get(k)); }
    seen.get(k).count += 1;
  }
  // A category the FILE declares but that holds no tags still has to be offered, or an
  // export -> import round trip silently loses every empty category (its name, its
  // side, and its Picks mode). That matters most for the "Export a backup first" flow,
  // where the whole point is to get everything back.
  for (const c of (parsed?.data?.categories || [])) {
    const k = String(c || "").toLowerCase();
    if (!k || seen.has(k)) continue;
    seen.set(k, { name: c, count: 0 });
    out.push(seen.get(k));
  }
  return out;
}

// Narrow a parsed import to the chosen buckets and RECOMPUTE the clashes against the
// live library, so the keep-both / replace / skip step only ever sees tags that are
// actually coming in. Same { data, conflicts } shape parseImport returns.
export function subsetImport(parsed, names) {
  const keep = new Set((names || []).map((n) => lc(n)));
  const tags = (parsed?.data?.tags || []).filter((t) => keep.has(lc(catOf(t))));
  const categories = (parsed?.data?.categories || []).filter((c) => keep.has(lc(c)));
  const listCats = (parsed?.data?.listCats || []).filter((c) => keep.has(lc(c)));
  const catModes = {};
  for (const [k, v] of Object.entries(parsed?.data?.catModes || {})) if (keep.has(lc(k))) catModes[k] = v;
  const have = new Set(getTags().map((t) => lc(t.name)));
  const conflicts = tags.filter((t) => have.has(lc(t.name))).map((t) => t.name);
  return { data: { version: 1, categories, listCats, catModes, tags }, conflicts };
}

// Parse an imported blob into a normalized library WITHOUT applying it. Returns
// { data, conflicts:[name...] } so the caller can ask the user how to merge.
export function parseImport(jsonStr) {
  let raw;
  try { raw = JSON.parse(jsonStr); } catch { return { error: "That file is not valid JSON." }; }
  // Accept the full shape, a bare tags array, or { tags:[...] } / { library:[...] }.
  if (Array.isArray(raw)) raw = { tags: raw };
  else if (raw && !Array.isArray(raw.tags)) {
    raw = { categories: raw.categories, listCats: raw.listCats, catModes: raw.catModes, tags: raw.tags || raw.library || raw.snippets || raw.prompts };
  }
  // Two entries in the SAME FILE can collide only after name-cleaning / case-folding
  // ("Portrait" vs "portrait"; "ta+g" and "t a g" both clean to "tag"). normalize()
  // dedups by that key - correct for the live library, but here it would silently
  // DROP the second entry before conflicts are even computed, so its text is lost
  // with no warning and the import picker under-reports what the file holds. Make the
  // incoming names unique among themselves first, so every entry survives into the
  // picker and into the keep-both / replace / skip step.
  if (raw && Array.isArray(raw.tags)) {
    const seen = new Set();
    // Resume each base name from the suffix it reached last time. Restarting the
    // search at -2 for every entry is O(n^2): a file with 50k tags all named "foo"
    // walks ~1.25 BILLION iterations on the UI thread, freezing the tab before the
    // import dialog even appears. Resuming makes it amortised O(1) per tag.
    const nextSuffix = new Map();
    raw.tags = raw.tags.map((t) => {
      if (!t || typeof t !== "object") return t;
      const base = cleanName(t.name);
      if (!base) return t;
      const baseKey = base.toLowerCase();
      let name = base;
      if (seen.has(baseKey)) {
        let i = nextSuffix.get(baseKey) || 2;
        while (seen.has((base + "-" + i).toLowerCase())) i++;
        name = base + "-" + i;
        nextSuffix.set(baseKey, i + 1);
      }
      seen.add(name.toLowerCase());
      return name === t.name ? t : { ...t, name };
    });
  }
  // A tag name has to be typeable as an @token, so `normalize` drops anything that
  // cleans to nothing - which silently discards every Cyrillic / CJK / accented name in
  // the file. Worse, the import picker's counts are taken AFTER the drop, so a
  // collection could import as near-empty with nothing anywhere reporting the loss.
  // Count them here and say so. (Widening the name rule is NOT the fix: the token
  // grammar in expand.mjs is ASCII, so such a tag could never be referenced.)
  let dropped = 0;
  if (raw && Array.isArray(raw.tags)) {
    for (const t of raw.tags) {
      if (!t || typeof t !== "object" || !cleanName(t.name)) dropped++;
    }
  }
  const data = normalize(raw);
  // A file with categories but no usable tags is still a legitimate backup - exactly
  // what "Export a backup first" hands you for an empty category. Refuse ONLY when
  // there is nothing at all to bring in; the dropped count is reported by the picker.
  // (The category check used to sit on the no-tags branch only, so a file with three
  // categories plus two unusable tag names was refused while the same file with zero
  // tags imported fine - the same gate, applied twice with different rules.)
  // A tags-less file is only a library if its categories are real NAMES. This gate
  // once checked the RAW array because addCat coerced stray JSON into a category
  // literally called "[object Object]" - but the raw check accepted a file whose only
  // "category" was a reserved bucket name ("Uncategorized"), opening a dead-end picker
  // with nothing in it. asName now refuses non-names inside normalize itself, so the
  // normalized result is the single truth again: reserved-only and junk-only files
  // both normalize to zero categories and are refused with a clear error.
  if (!data.tags.length && !data.categories.length) {
    return {
      error: dropped
        ? `None of the ${dropped} tag${dropped === 1 ? "" : "s"} in that file can be used. A tag name can only contain letters a to z, numbers, - and _.`
        : "No tags found in that file.",
    };
  }
  const have = new Set(getTags().map((t) => t.name.toLowerCase()));
  const conflicts = data.tags.filter((t) => have.has(t.name.toLowerCase())).map((t) => t.name);
  return { data, conflicts, dropped };
}

// Apply a parsed import. mode: "both" (rename incoming clashes, keep everything),
// "replace" (overwrite my text on a clash), "skip" (only add non-clashing).
// Imported tags land on TOP (newest-first), categories are merged in.
export function applyImport(parsed, mode) {
  const cur = getLibrary();
  const tags = cur.tags.map((t) => ({ ...t }));
  const byKey = new Map(tags.map((t) => [t.name.toLowerCase(), t]));
  // Unique against the WORKING set (live + already-added), not just the live
  // library - else a "keep both" rename could collide with another incoming tag
  // (e.g. importing both `portrait` and `portrait-2`) and normalize would drop one.
  const uniqueIn = (base) => {
    let n = base, i = 2;
    while (byKey.has(n.toLowerCase())) { n = base + "-" + i; i++; }
    return n;
  };
  const toAdd = [];
  const replaced = [];
  for (const inc of parsed.data.tags) {
    const key = inc.name.toLowerCase();
    if (!byKey.has(key)) {
      const t = { ...inc };
      toAdd.push(t); byKey.set(key, t);
    } else if (mode === "replace") {
      // Replace the WHOLE tag, not just its text. Copying only `text` left a List
      // imported over a Text tag still marked Text, so `*Category` pasted all of its
      // lines at once instead of rolling one - a visibly wrong output, not a UI wart.
      const t = byKey.get(key);
      t.text = inc.text;
      if (inc.kind === "list") t.kind = "list"; else delete t.kind;
      if (inc.mode) t.mode = inc.mode; else delete t.mode;
      replaced.push(t.name);
    } else if (mode === "both") {
      const nn = uniqueIn(inc.name);
      const t = { ...inc, name: nn };
      toAdd.push(t); byKey.set(nn.toLowerCase(), t);
    }
    // "skip": do nothing
  }
  const next = {
    version: 1,
    categories: [...cur.categories],
    listCats: [...(cur.listCats || [])],
    catModes: { ...(cur.catModes || {}) },
    tags: toAdd.concat(tags), // newest (imported) on top
  };
  const catHave = new Set(next.categories.map((c) => lc(c)));
  for (const c of parsed.data.categories) {
    if (c && !catHave.has(lc(c))) { catHave.add(lc(c)); next.categories.push(c); }
  }
  // An incoming List category keeps its side. A name I ALREADY have keeps MY side -
  // my library wins on a clash, exactly as it does for a tag's text.
  const listHave = new Set(next.listCats.map((c) => lc(c)));
  for (const c of (parsed.data.listCats || [])) {
    if (c && !listHave.has(lc(c)) && !cur.categories.some((x) => lc(x) === lc(c))) {
      listHave.add(lc(c)); next.listCats.push(c);
    }
  }
  // Same rule for how a category picks: mine wins, theirs only fills a gap. Checking
  // `cur.categories` alone was not enough for the Text/List BUCKETS - they are never
  // in that list, so an imported bucket mode always overwrote the local one. Test the
  // mode map itself as well, which covers real categories and buckets alike.
  for (const [k, v] of Object.entries(parsed.data.catModes || {})) {
    if (!k) continue;
    const mine = cur.categories.some((x) => lc(x) === lc(k)) ||
      Object.keys(cur.catModes || {}).some((x) => lc(x) === lc(k));
    if (!mine) next.catModes[k] = v;
  }
  setLibrary(next);
  // A replaced tag's contents are wholly different now, so its old position means
  // nothing - carrying it over would resume someone else's deck.
  for (const name of replaced) { try { resetCursor(listKey(name)); } catch { /* ignore */ } }
  return { added: toAdd.length, replaced: replaced.length };
}
