// Which workflow TAB a run's result belongs to.
//
// A run keeps going when you switch to another workflow tab. When it ends, the
// server's `executed` message names only a node id, and ids repeat across
// workflows, so a node that looks itself up in the OPEN tab (app.graph /
// core's node.onExecuted) misses its own result AND paints it on another
// workflow's node that happens to have the same id (Discord 2026-10, Preview
// Image and Image Compare kept the old picture).
//
// Core already does it right for its own nodes: it files every result under
// the tab that queued the run (ChangeTracker: workflow.changeTracker
// .nodeOutputs[node id] = the SAME output object) and hands them back when that
// tab opens again, through the `onNodeOutputsUpdated` extension hook
// (ChangeTracker.restore -> restoreOutputs -> app.nodeOutputs). These helpers
// let a node follow the same rule:
//   runTab(output)            "active" | "other" | "unknown"; call it from a
//                             microtask queued in the executed handler, so
//                             core's own listener has filed the output first.
//   eachRestoredOutput(...)   for an onNodeOutputsUpdated hook: ONLY the results
//                             of runs that ended while their tab was not open,
//                             each handed out once.
// That hook also fires after every Ctrl+Z / Ctrl+Y, every reload of the open
// workflow and every load from the queue history, with outputs the node has
// already shown: re-applying those wrote state back and jammed undo (the next
// click recorded it and wiped redo). Results of ANOTHER tab that core's own
// store kept for the tab that was open when they ended are never handed out
// either: they are pending for their own tab, not this one.
// Anything this cannot place (a run queued from another browser or the API,
// an older frontend without these fields) answers "unknown" and the caller
// keeps its old behaviour.
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const MAX_PENDING = 1000;
// workflow -> keys of runs that ended while that workflow was not the open
// tab: file keys ("type/subfolder/filename"), or a content key for a result
// with no file (contentKey). Weak: a closed workflow takes its own.
const pending = new WeakMap();
// workflow -> (execution id -> that node's newest pending content key).
const lastContent = new WeakMap();

function filesOf(output) {
  const out = [];
  if (!output || typeof output !== "object") return out;
  for (const v of Object.values(output)) {
    if (!Array.isArray(v)) continue;
    for (const f of v) {
      if (f && typeof f === "object" && typeof f.filename === "string") {
        out.push(`${f.type || ""}/${f.subfolder || ""}/${f.filename}`);
      }
    }
  }
  return out;
}

// A result with no file (text, numbers: Show Text, AI Prompt, Image Resize's
// sizes...) is known by its node id and its CONTENT: core clones every output
// when it stores and restores a tab, so the object itself cannot be the key.
// The id keeps two nodes of one graph level with the same text apart (it is
// the INNER id, see keysOf).
function contentKey(id, output) {
  let s;
  try { s = JSON.stringify(output); } catch { return null; }
  if (typeof s !== "string") return null;
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return `#${id}:${s.length}:${(h2 >>> 0).toString(36)}${(h1 >>> 0).toString(36)}`;
}

// Only the node's OWN id goes into a content key: a run is recorded under its
// EXECUTION id ("12:5" inside a subgraph) and handed back re-keyed by LOCATOR
// id ("<subgraph uuid>:5", core's replaceOutputsFromLegacy), and the part after
// the last ":" is the same in both.
function keysOf(id, output) {
  const files = filesOf(output);
  if (files.length || id == null) return files;
  const k = contentKey(String(id).split(":").pop(), output);
  return k ? [k] : [];
}

function trackerHolds(workflow, output) {
  const outs = workflow?.changeTracker?.nodeOutputs;
  if (!outs || typeof outs !== "object") return false;
  for (const v of Object.values(outs)) {
    if (v === output) return true;
    // A merged result (detail.merge) is a new object holding the same items.
    for (const k in output) {
      const first = Array.isArray(output[k]) ? output[k][0] : undefined;
      if (first && typeof first === "object" && Array.isArray(v?.[k]) && v[k].includes(first)) return true;
    }
  }
  return false;
}

function ownerOf(output) {
  const ws = app.extensionManager?.workflow;
  if (!output || typeof output !== "object" || !ws) return null;
  // The open tab too: it can be missing from openWorkflows (seen after every
  // tab was closed).
  for (const w of new Set([ws.activeWorkflow, ...(ws.openWorkflows || [])])) {
    if (w && trackerHolds(w, output)) return w;
  }
  return null;
}

// Every run, not only the ones a Pixaroma node looks at: the open tab may have
// no node with that id at all, and then nothing of ours is called for it.
api.addEventListener("executed", ({ detail }) => {
  const output = detail?.output;
  if (!output || typeof output !== "object") return;
  queueMicrotask(() => {
    const owner = ownerOf(output);
    if (!owner || owner === app.extensionManager?.workflow?.activeWorkflow) return;
    let set = pending.get(owner);
    if (!set) pending.set(owner, (set = new Set()));
    const keys = keysOf(detail.node, output);
    if (keys.length === 1 && keys[0].startsWith("#")) {
      // Core keeps only a node's NEWEST output, so only its newest content key
      // can ever come back. An older one left pending matched a LATER run that
      // gave the same text and re-applied it on a plain tab switch (measured:
      // a Pause Text edit overwritten). Files never repeat, so file keys are
      // left alone.
      let last = lastContent.get(owner);
      if (!last) lastContent.set(owner, (last = new Map()));
      const old = last.get(String(detail.node));
      if (old && old !== keys[0]) set.delete(old);
      last.set(String(detail.node), keys[0]);
    }
    for (const f of keys) set.add(f);
    while (set.size > MAX_PENDING) set.delete(set.values().next().value);
  });
});

export function runTab(output) {
  const owner = ownerOf(output);
  if (!owner) return "unknown";
  return owner === app.extensionManager?.workflow?.activeWorkflow ? "active" : "other";
}

// The workflow (tab) a run's result belongs to, or null when it cannot be
// placed. Same timing rule as runTab. For a node that must act on its own tab's
// saved state while that tab is closed (Notify files the time under the node's
// own id, read from changeTracker.activeState).
export function runWorkflow(output) {
  return ownerOf(output);
}

// The node an onNodeOutputsUpdated key names: "id" on the root graph, or
// "<subgraph uuid>:<id>" inside a subgraph.
function nodeByLocator(locatorId) {
  const root = app.rootGraph || app.graph;
  const id = String(locatorId);
  const i = id.lastIndexOf(":");
  if (i < 0) return root?.getNodeById?.(id) ?? null;
  return root?.subgraphs?.get?.(id.slice(0, i))?.getNodeById?.(id.slice(i + 1)) ?? null;
}

export function eachRestoredOutput(nodeOutputs, comfyClass, fn) {
  if (!nodeOutputs || typeof nodeOutputs !== "object") return;
  const set = pending.get(app.extensionManager?.workflow?.activeWorkflow);
  if (!set?.size) return;
  for (const [locatorId, output] of Object.entries(nodeOutputs)) {
    if (!output || typeof output !== "object") continue;
    // The node's class first: every node type calls this from its own hook,
    // so hashing a text result before knowing it is ours is wasted work.
    const node = nodeByLocator(locatorId);
    if (!node || (node.comfyClass || node.type) !== comfyClass) continue;
    const keys = keysOf(locatorId, output);
    if (!keys.some((f) => set.has(f))) continue;
    fn(node, output);
    for (const f of keys) set.delete(f);
  }
}
