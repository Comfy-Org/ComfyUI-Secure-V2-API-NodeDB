// Dropdown Pixaroma - state, defaults, and the output slot.
//
// The list and the type belong to the NODE, not to whatever it is wired to.
// That is the whole difference from Control Panel, whose rows adopt the type of
// their target, and it is why this node never reads its own connections to
// decide anything.

import { isGraphLoading } from "../shared/graph_loading.mjs";
import { accentOf } from "../shared/node_settings.mjs";
import { slotAccepts } from "../shared/slot_types.mjs";
import { SOCKET_TYPES, WIRE_TYPES, normalizeType } from "./coerce.mjs";

export const CLASS = "PixaromaDropdown";

// node.properties key (camelCase) and the Python INPUT_TYPES key (PascalCase).
// They differ in case on purpose, matching every other Pixaroma node - and a
// silent typo in the second one means Python always sees its default and the
// node appears to ignore every change you make, so it is stated twice.
export const STATE_PROP = "dropdownState";
export const HIDDEN_INPUT = "DropdownState";   // matches the Python INPUT_TYPES key

// Geometry. Legacy and Nodes 2.0 both derive from these, so they are the one
// place to tune the row.
export const ROW_H = 26;
export const MIN_W = 210;
export const DEFAULT_W = 250;
export const BODY_PAD = 7;

// A zero-width space. Truthy, so neither renderer falls back to painting the raw
// slot name ("value") on top of our row, but nothing is actually drawn.
// An empty string would fall through litegraph's `||` chain back to slot.name.
// Written as an escape, NOT as a literal U+200B byte: an invisible character in
// source is unreviewable and undiffable (it once cost this project a whole
// debugging session in a regex).
export const ZW = "\u200B";

export const OUT_NAME = "value";

// How many values one entry can carry. Python declares exactly this many ANY
// outputs and always returns this many; the browser shows only the first
// `outs.length` of them. Four covers sampler+scheduler, width+height,
// steps+cfg and model+clip; raising it means changing RETURN_NAMES too.
export const MAX_OUTS = 4;

/** Default name for output i (0-based). Output 1 keeps the historic "value". */
export function defaultOutName(i) {
  return i === 0 ? OUT_NAME : `${OUT_NAME}_${i + 1}`;
}

// How the node picks an entry when the workflow RUNS.
//   fixed     - always the one you chose. The default, and the only mode that
//               leaves the node completely predictable.
//   increment - the next one down the list each run, wrapping at the end.
//   random    - any one, never the same twice in a row when there are 2+.
export const MODES = ["fixed", "increment", "random"];
export const MODE_LETTERS = { fixed: "F", increment: "I", random: "R" };
export const MODE_LABELS = {
  fixed: "Fixed - always the entry you picked",
  increment: "In order - the next entry each run, wrapping at the end",
  random: "Random - any entry each run",
};

export function defaultState() {
  // `outs` is part of the IN-MEMORY shape and every reader may rely on it being
  // present - readState returns this object verbatim when a node has no state
  // yet, which is every freshly created node. writeState deletes it again when
  // it is trivial, so nothing extra is ever written to a saved workflow.
  return {
    version: 1, type: "text", index: 0, mode: "fixed", options: [],
    outs: [{ name: OUT_NAME, type: "text" }],
  };
}

function normalizeMode(m) {
  return MODES.includes(m) ? m : "fixed";
}

/** node -> its state, always a valid object. Never trusts what it finds. */
export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = defaultState();
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return st;

  st.type = normalizeType(raw.type);
  st.mode = normalizeMode(raw.mode);

  if (Array.isArray(raw.options)) {
    for (const o of raw.options) {
      // Drop a non-object row rather than letting it crash the list later.
      // Control Panel learned this one the hard way: a single null row aborted
      // value injection for every OTHER node of its type on the canvas.
      if (!o || typeof o !== "object" || Array.isArray(o)) continue;
      st.options.push({
        name: typeof o.name === "string" ? o.name : "",
        value: typeof o.value === "string" ? o.value : (o.value == null ? "" : String(o.value)),
        // Outputs 2..N. An entry saved before multi-output has no `v` at all,
        // which is exactly why there is nothing to migrate: it reads as an
        // empty list here and writeState drops it again on the way out.
        v: Array.isArray(o.v)
          ? o.v.map((x) => (typeof x === "string" ? x : (x == null ? "" : String(x))))
          : [],
      });
    }
  }

  st.outs = normalizeOuts(raw.outs, st.type);

  const n = Number(raw.index);
  st.index = Number.isFinite(n) ? Math.max(0, Math.min(st.options.length - 1, Math.trunc(n))) : 0;
  if (!st.options.length) st.index = 0;
  return st;
}

/**
 * raw.outs -> a valid array of {name, type}, always at least one entry long.
 *
 * Synthesised from `type` when absent, which is what makes an old single-output
 * state a valid multi-output state with no rewrite: the default IS the old
 * shape. Output 1's type mirrors `state.type` so the two can never disagree,
 * and Python keeps reading `type` exactly as it always has.
 */
function normalizeOuts(raw, type) {
  const outs = [];
  if (Array.isArray(raw)) {
    for (const o of raw.slice(0, MAX_OUTS)) {
      if (!o || typeof o !== "object" || Array.isArray(o)) continue;
      outs.push({ name: typeof o.name === "string" ? o.name : "", type: normalizeType(o.type) });
    }
  }
  if (!outs.length) outs.push({ name: OUT_NAME, type });
  outs[0].type = type;
  for (let i = 0; i < outs.length; i++) if (!outs[i].name) outs[i].name = defaultOutName(i);
  return outs;
}

/** How many outputs this node currently shows. Always 1..MAX_OUTS. */
export function outCount(node) {
  return readState(node).outs.length;
}

/** One entry -> exactly `n` value strings, padded with "". */
export function valuesOf(opt, n) {
  const out = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) out.push(opt && typeof opt.value === "string" ? opt.value : "");
    else out.push(opt && Array.isArray(opt.v) && typeof opt.v[i - 1] === "string" ? opt.v[i - 1] : "");
  }
  return out;
}

/** Write value `i` (0-based) onto an entry, growing `v` only as far as needed. */
export function setValueAt(opt, i, text) {
  const str = typeof text === "string" ? text : String(text == null ? "" : text);
  if (i === 0) { opt.value = str; return opt; }
  if (!Array.isArray(opt.v)) opt.v = [];
  while (opt.v.length < i) opt.v.push("");
  opt.v[i - 1] = str;
  return opt;
}

/**
 * The single write path. Everything that changes the list goes through here so
 * the stored index can never point at a row that is not there.
 *
 * Deliberately NOT diff-gated against the stored object: callers pass a patch
 * and we always re-normalize. It IS safe on the load path only because nothing
 * on the load path calls it - see the note in index.js.
 */
export function writeState(node, patch) {
  if (!node) return defaultState();
  if (!node.properties) node.properties = {};
  const cur = readState(node);
  const next = { ...cur, ...(patch || {}) };

  next.version = 1;
  next.type = normalizeType(next.type);
  next.mode = normalizeMode(next.mode);
  next.outs = normalizeOuts(next.outs, next.type);
  next.options = Array.isArray(next.options) ? next.options.map((o) => {
    const row = {
      name: typeof o?.name === "string" ? o.name : "",
      value: typeof o?.value === "string" ? o.value : (o?.value == null ? "" : String(o.value)),
    };
    // Keep `v` only when it actually holds something. An entry that has never
    // had a second value stays byte-identical to how it was saved, so opening
    // an existing workflow cannot flag it modified (Vue Compat #18). Trailing
    // blanks are trimmed for the same reason.
    const v = Array.isArray(o?.v)
      ? o.v.map((x) => (typeof x === "string" ? x : (x == null ? "" : String(x))))
      : [];
    while (v.length && v[v.length - 1] === "") v.pop();
    if (v.length) row.v = v;
    return row;
  }) : [];
  const n = Number(next.index);
  next.index = Number.isFinite(n) ? Math.max(0, Math.min(next.options.length - 1, Math.trunc(n))) : 0;
  if (!next.options.length) next.index = 0;

  // A plain one-output Dropdown never grows an `outs` key, so its stored shape
  // is exactly what it was before this feature existed.
  if (next.outs.length <= 1 && next.outs[0].name === OUT_NAME) delete next.outs;

  node.properties[STATE_PROP] = next;
  return next;
}

/** The currently selected option, or null when the list is empty. */
export function selectedOption(node) {
  const st = readState(node);
  return st.options[st.index] || null;
}

/**
 * What the browser sends Python. ONLY what changes the result.
 *
 * The injected string becomes part of the node's inputs, so ComfyUI hashes it:
 * anything in here that is really display-only would re-run the graph when it
 * changed. Renaming a row, recolouring the node, reordering, or editing a row
 * you have NOT selected must all be free. So the names, the rest of the list and
 * the accent stay out, and Python accepts this lean shape directly.
 */
/**
 * The index this BUILD should send.
 *
 * In Fixed mode that is simply the entry you chose. The other two modes derive
 * from a RUNTIME cursor (`node._pixDdCursor`) and NEVER touch node.properties:
 * a run that wrote the new position into the workflow would flag it modified
 * every single time you pressed Run, which is the trap Seed Pixaroma documents.
 * The cost is that the sequence restarts from your chosen entry after a page
 * reload, which is predictable and visible.
 *
 * The pick is HELD in `node._pixDdPending` until it is actually spent, so
 * calling this twice for one queue (graphToPrompt runs for Export, for Save and
 * for a queue that then fails validation) hands back the SAME entry.
 */
export function pendingIndex(node) {
  const st = readState(node);
  const n = st.options.length;
  if (!n) return 0;
  const clamp = (i) => Math.max(0, Math.min(i, n - 1));
  if (st.mode === "fixed") return clamp(st.index);

  // A held pick stays valid only while it still points at a real row.
  if (Number.isInteger(node._pixDdPending) && node._pixDdPending < n) return node._pixDdPending;

  let next;
  if (st.mode === "random") {
    // ALWAYS random, including the very first run after switching to R. The
    // first-run branch below is for In-order only: it exists so a sequence
    // starts where the user is looking, but applying it to Random made the
    // first Run send the entry already on the face while the panel promised
    // "a different entry at random each run".
    const avoid = Number.isInteger(node._pixDdCursor) ? clamp(node._pixDdCursor) : clamp(st.index);
    next = Math.floor(Math.random() * n);
    // Never the same entry twice running - with a two-entry list a repeat reads
    // as the mode not working at all.
    if (n > 1 && next === avoid) next = (next + 1 + Math.floor(Math.random() * (n - 1))) % n;
  } else if (!Number.isInteger(node._pixDdCursor)) {
    // First run after a load: send what the node is showing, THEN start moving.
    next = clamp(st.index);
  } else {
    next = (clamp(node._pixDdCursor) + 1) % n;
  }
  node._pixDdPending = next;
  return next;
}

/**
 * Spend the held pick. Called ONLY when a queue is actually accepted, so an
 * Export or a rejected queue does not move an "In order" list on.
 */
export function commitPick(node) {
  if (Number.isInteger(node._pixDdPending)) {
    node._pixDdCursor = node._pixDdPending;
    node._pixDdPending = null;
  } else if (readState(node).mode === "fixed") {
    node._pixDdCursor = null;   // Fixed does not accumulate a position
  }
}

/** What the node face should show: the pick that is queued or last ran. */
export function shownIndex(node) {
  const st = readState(node);
  const n = st.options.length;
  if (!n) return 0;
  const clamp = (i) => Math.max(0, Math.min(i, n - 1));
  if (st.mode === "fixed") return clamp(st.index);
  if (Number.isInteger(node._pixDdPending) && node._pixDdPending < n) return node._pixDdPending;
  if (Number.isInteger(node._pixDdCursor)) return clamp(node._pixDdCursor);
  return clamp(st.index);
}

/**
 * What the browser sends Python. ONLY what changes the result.
 *
 * The injected string becomes part of the node's inputs, so ComfyUI hashes it:
 * anything in here that is really display-only would re-run the graph when it
 * changed. Renaming a row, recolouring the node, reordering, or editing a row
 * you have NOT selected must all be free. So the names, the rest of the list,
 * the mode and the accent stay out, and Python accepts this lean shape directly.
 */
export function injectedState(node, indexOverride) {
  const st = readState(node);
  // XY Plot names the entry for the square being rendered; everything else
  // takes whatever this build is due to send.
  const idx = Number.isInteger(indexOverride) ? indexOverride : pendingIndex(node);
  const opt = st.options[idx];

  // ONE output: emit the historic shape, byte for byte. The injected string is
  // the node's cache key, so any change here would re-run every existing
  // workflow the first time it was opened after an update. Multi-output is
  // strictly additive precisely so this line can stay as it was.
  if (st.outs.length <= 1) {
    return { version: 1, type: st.type, value: opt ? opt.value : null };
  }
  return {
    version: 1,
    types: st.outs.map((o) => o.type),
    values: valuesOf(opt, st.outs.length),
  };
}

/**
 * Put the chosen type on the output slot so the CANVAS refuses an incompatible
 * drag. Python declares ANY; this is the frontend half of that, and there is no
 * second server-side check behind it.
 *
 * Every write is diff-gated. Slots are serialized, and re-writing an identical
 * value still counts as a change on some builds, which would flag a clean
 * workflow "modified" the moment it was opened (Vue Compat #18).
 */
export function syncOutputs(node) {
  if (!node?.outputs) return;
  const outs = readState(node).outs;
  const n = outs.length;

  // Grow/shrink to match.
  //
  // ⚠ The trim is NOT a no-op on load, and an earlier version of this comment
  // wrongly said it was. Python always declares MAX_OUTS, so the ComfyNode
  // CONSTRUCTOR (`addOutputs(this, nodeData.outputs)`) has already built FOUR
  // slots before `configure` runs, and nothing on the load path shrinks them
  // back: `configure` zips the def slots onto the saved ones, and that zip pads
  // to the LONGER array. Either mechanism alone yields four, so a saved
  // ONE-output Dropdown arrives here carrying four regardless.
  // Trimming is what makes serialize() match the file again; delete it and every
  // workflow containing this node opens flagged "modified" (Vue Compat #18).
  // (Verified by executing the frontend's own configure, 1.49.6.)
  //
  // The three phantom slots carry `links: null`, which is why the gate below
  // never trips on them and only a genuinely damaged file reaches it.
  while (node.outputs.length > n) {
    const last = node.outputs[node.outputs.length - 1];
    // NEVER destroy a wire because a file was merely OPENED. removeOutput calls
    // disconnectOutput whenever node.graph is set, and by onConfigure time the
    // graph, its links and every target node all exist - so without this gate a
    // state that disagreed with the saved slot count silently cut those wires
    // on load. That happens for real on a version skew: a 4-output Dropdown
    // saved by a newer build, re-saved by an older one (which drops `outs`
    // while keeping the 4 slots and links), then reopened here.
    //
    // A state that disagrees with the saved slots is a DAMAGED FILE, not an
    // instruction to cut. Leave the extra slots in place - they are recoverable
    // by setting the output count back up, and the values are still stored - and
    // say so rather than doing it invisibly.
    if (isGraphLoading() && Array.isArray(last?.links) && last.links.length) {
      console.warn(
        `[Pixaroma.Dropdown] node ${node.id}: the saved workflow has `
        + `${node.outputs.length} outputs with wires attached but its settings say `
        + `${n}. Keeping the wires. Set the output count back to `
        + `${node.outputs.length} in the node's settings to use them.`,
      );
      break;
    }
    node.removeOutput?.(node.outputs.length - 1);
  }
  while (node.outputs.length < n && node.addOutput) node.addOutput(defaultOutName(node.outputs.length), "*");

  for (let i = 0; i < n && i < node.outputs.length; i++) {
    const out = node.outputs[i];
    // WIRE_TYPES, not SOCKET_TYPES: a plain "STRING" cannot be DRAGGED onto a
    // COMBO widget input (sampler_name, ckpt_name, ...). Stripped back to the
    // plain name on serialize, so the saved file is unchanged. See coerce.mjs.
    const want = WIRE_TYPES[outs[i].type] || "*";
    const nm = outs[i].name || defaultOutName(i);
    // Every write diff-gated: slots are serialized, and rewriting an identical
    // value still counts as a change on some builds (Vue Compat #18).
    if (out.name !== nm) out.name = nm;
    if (out.label !== ZW) out.label = ZW;
    if (out.type !== want) out.type = want;
  }
}

/** Kept so older call sites keep working; the node has had N outputs since. */
export const syncOutput = syncOutputs;

/**
 * Drop a wire the new type can no longer feed. A real user action ONLY.
 *
 * Returns the number of links cut so the caller can say so - silently severing
 * a connection the user cannot see them lose is how a workflow quietly stops
 * working. Never runs during a load: the saved graph is by definition already
 * consistent, and cutting there would damage a file just by opening it.
 */
export function dropIncompatibleLinks(node) {
  if (!node?.outputs?.length || isGraphLoading()) return 0;
  const graph = node.graph;
  if (!graph) return 0;
  let cut = 0;
  for (const out of node.outputs) cut += dropOnOutput(graph, out);
  return cut;
}

function dropOnOutput(graph, out) {
  const links = Array.isArray(out?.links) ? out.links.slice() : [];
  if (!links.length) return 0;
  const want = out.type;
  let cut = 0;

  for (const id of links) {
    let link = graph.links?.[id];
    // graph.links can be a Map on newer frontends (Vue Compat #3).
    if (!link && typeof graph.links?.get === "function") link = graph.links.get(id);
    if (!link) continue;
    const target = graph.getNodeById?.(link.target_id);
    const slot = target?.inputs?.[link.target_slot];
    if (!slot) continue;
    const accepts = slot.type;
    // slotAccepts, not "===": it covers the "*" wildcard on either side (Reroute,
    // Set/Get, Preview Any) AND a ComfyUI multi-type input, which arrives as the
    // comma-joined "FLOAT,INT,BOOLEAN" (core's Math Expression). An equality test
    // read that as one unknown name and cut a wire the user had just drawn.
    if (slotAccepts(accepts, want)) continue;
    target.disconnectInput?.(link.target_slot);
    cut++;
  }
  return cut;
}

export { accentOf };
