// Dropdown Pixaroma - the XY Plot sweep provider.
//
// This node keeps its list in node.properties.dropdownState and injects the
// chosen value into a hidden input at queue time (Vue Compat #9), so it has NO
// widget for XY Plot to enumerate and would never appear in the picker at all.
// Here we advertise one axis - which entry is picked - and patch the injected
// value per cell. Registered through js/shared/sweep_targets.mjs so neither side
// imports the other's internals.
//
// The axis VALUE is the entry's NAME, not its position. That is what makes the
// grid readable: the squares come out labelled "top left" and "full body", which
// is the whole reason for naming things in this node. The cost is that two
// entries sharing a name are ambiguous - see note().

import { registerSweepProvider } from "../shared/sweep_targets.mjs";
import { HIDDEN_INPUT, readState, injectedState, valuesOf } from "./core.mjs";
import { coerceValue, previewText } from "./coerce.mjs";

const CLASS = "PixaromaDropdown";
// Namespaced so it can never collide with a real widget name on any node.
// There is exactly ONE axis per Dropdown node, so no row id is needed - but the
// prefix still matters, because `owns` is what stops this provider claiming an
// unrelated axis that happens to sit on the same node.
const AXIS = "pixdd:entry";

function owns(axis) {
  return !!(axis && typeof axis.widgetName === "string" && axis.widgetName === AXIS);
}

// A display name for an entry. An unnamed entry still has to be pickable and
// still has to label its square, so fall back to its position.
function labelOf(opt, i) {
  const n = String(opt?.name || "").trim();
  return n || `(entry ${i + 1})`;
}

// The names XY Plot offers as the checklist. Duplicates are NOT collapsed: the
// user can see both in the list, and note() warns that they cannot be told
// apart. Silently dropping one would make an entry unsweepable for a reason
// nothing on screen explains.
function optionNames(node) {
  return readState(node).options.map(labelOf);
}

function enumerate(node) {
  const st = readState(node);
  // No entries means nothing to vary. Offering the axis anyway would let someone
  // run a whole grid of identical squares, so say why instead.
  const names = optionNames(node);
  const cur = st.options[st.index];
  return [{
    name: AXIS,
    subField: "entry",
    label: "Entry",
    type: "combo",
    options: names,
    cur: names.length ? labelOf(cur, st.index) : "(no entries yet - add some in the node's settings)",
  }];
}

function lookup(node, axis) {
  if (!owns(axis)) return null;
  return enumerate(node).find((e) => e.name === axis.widgetName) || null;
}

// The "now:" line under the picker. Shows the value as well as the name, since
// the name alone does not tell you what the square will actually run with.
function preview(node) {
  const st = readState(node);
  const opt = st.options[st.index];
  if (!opt) return "(no entries yet)";
  const vals = valuesOf(opt, st.outs.length);
  const shown = st.outs.map((o, k) => (st.outs.length > 1 ? `${o.name}: ` : "")
    + previewText(vals[k], o.type)).join(", ");
  return `${labelOf(opt, st.index)} - ${shown}`;
}

// The axis title drawn on the grid. The node's own title when the user has given
// it one, because a canvas with three Dropdowns on it otherwise produces three
// grids all labelled "Entry".
function displayName(node) {
  const t = String(node?.title || "").trim();
  return t && t !== "Dropdown Pixaroma" ? t : "Entry";
}

// Heads-up lines. Both of these are things the grid cannot show you.
function note(node) {
  const st = readState(node);
  if (!st.options.length) {
    return "This Dropdown has no entries yet, so every square would come out the same. "
      + "Add some in the node's settings first.";
  }
  const names = optionNames(node);
  const dupes = names.filter((n, i) => names.indexOf(n) !== i);
  if (dupes.length) {
    const first = [...new Set(dupes)][0];
    return `Two entries are both called "${first}", so a square asking for it always gets the `
      + `first one. Rename one of them to tell them apart.`;
  }
  return "";
}

// Write this cell's value into the node's prompt entry.
function inject(entry, axis, value, node) {
  if (!entry || !owns(axis)) return;
  const names = optionNames(node);
  const want = String(value);

  const idx = names.indexOf(want);
  if (idx < 0) {
    // The entry was renamed or deleted after the axis was picked. Every square
    // would silently run the node's current selection instead, which looks like
    // the sweep is being ignored - so say so and leave the entry alone.
    console.warn(
      `[Dropdown Pixaroma] XY Plot asked for the entry "${want}", which is not on this node `
      + `any more - it was renamed or deleted after the axis was picked. This square ran with `
      + `whatever the node is currently set to. Re-pick the axis.`,
    );
    return;
  }

  entry.inputs = entry.inputs || {};
  // Build from the node's own lean shape so the types travel with the values and
  // Python needs no special case for a swept run. The index is passed IN rather
  // than the value patched on afterwards: above one output the lean shape holds
  // a `values` array, and writing `.value` onto it would be silently ignored -
  // every square would then run the node's current pick instead of the swept
  // one, which looks exactly like a sweep that is being ignored.
  const base = injectedState(node, idx);
  entry.inputs[HIDDEN_INPUT] = JSON.stringify(base);

  // Sanity: a value that does not read as the node's type still runs (Python
  // falls back), but in a GRID that produces a square silently identical to
  // every other broken one, which reads as a plot that did not work.
  // Works on BOTH lean shapes: the single-output one carries value/type, the
  // multi-output one carries values/types. Reading only the first pair would
  // miss a broken second value entirely.
  const sent = Array.isArray(base.values) ? base.values : [base.value];
  const kinds = Array.isArray(base.types) ? base.types : [base.type];
  sent.forEach((v, k) => {
    const kind = kinds[k] || "text";
    const resolved = coerceValue(v, kind);
    if (kind !== "text" && (resolved === 0 || resolved === false) && String(v || "").trim()) {
      console.warn(
        `[Dropdown Pixaroma] the entry "${want}" does not read as ${kind}, so this square `
        + `ran with the fallback value. Fix it in the node's settings, or the grid will have `
        + `identical squares in it.`,
      );
    }
  });
}

registerSweepProvider(CLASS, { owns, enumerate, lookup, preview, displayName, note, inject });
