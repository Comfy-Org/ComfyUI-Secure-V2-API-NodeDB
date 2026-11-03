// Prompt Pack Pixaroma - state + parsing module.
//
// State lives on node.properties.promptPackState.
// Shape: {
//   version: 1,
//   mode: "paragraph" | "line" | "rule",
//   text: "...",          // raw textarea content
//   activePrompt: ""      // transient, set per queue iteration
// }
//
// LiteGraph serializes node.properties natively into workflow JSON, so save
// and reload are automatic. The graphToPrompt hook in index.js packs
// activePrompt into the hidden PromptPackState input at workflow-submit time.
// The queuePrompt patch in index.js mutates activePrompt right before each
// per-prompt enqueue.
//
// activePrompt is transient. The saved value on disk is whatever the last
// loop iteration left behind and is not relied on at workflow load - the
// next Run overwrites it before any prompt is captured.

import { feedsOnlyInactiveSwitch } from "../shared/queue_drivers.mjs";

export const STATE_PROP = "promptPackState";
export const MODE_PARAGRAPH = "paragraph";
export const MODE_LINE = "line";
export const MODE_RULE = "rule";

// THE THREE SPLIT MODES MIRROR Save Text Pixaroma's three separators, one for
// one - js/save_text/state.mjs::SEPARATORS + nodes/_save_text_helpers.py.
// That is the whole point of the pairing: whatever separator you collected
// with, pick the pill of the same name here and the .txt drops straight in.
// Our mode id and its separator id differ only for the two that predate the
// pairing (paragraph = "blank", line = "newline"); renaming those would
// rewrite every saved workflow, so only the LABELS were brought into line.
//
// ADDING A FOURTH: add it to Save Text's SEPARATORS (both sides, JS + Python)
// and to this table. Nothing else needs to know - the pills, the counter and
// the queue loop are all driven from here.
//
// There is deliberately NO comma option, and Save Text dropped its own on the
// same day (2026-08-18, one day after it shipped, so nobody could be relying
// on it). Both nodes exist to carry PROMPTS, and an ordinary prompt is full of
// commas, so splitting on one shreds a single prompt into fragments: the count
// lies, the duplicate guard stops matching and the rollover fires early
// (save-text.md #7). An option that is broken for the node's own subject
// matter is worse than no option.
//
//   mode id      Save Text id   joins entries with
//   -----------  -------------  ---------------------
//   paragraph    blank          "\n\n"
//   line         newline        "\n"
//   rule         rule           "\n---\n"
//
// Each splitter is deliberately more permissive than the exact string Save
// Text writes, so a file the user has since hand-edited (or opened in
// Notepad, which rewrites the line endings to \r\n) still parses.
const SPLITTERS = Object.assign(Object.create(null), {
  // A "blank line" is any \n + optional whitespace + \n.
  [MODE_PARAGRAPH]: /\n\s*\n+/,
  [MODE_LINE]: /\r?\n/,
  // A line that is ONLY dashes (3 or more), so a prompt that happens to
  // contain "--- something ---" is left alone. The (?:\r?\n|$) tail also
  // matches a rule sitting at the very end of the text.
  [MODE_RULE]: /\r?\n[ \t]*-{3,}[ \t]*(?:\r?\n|$)/,
});

// Ordered for display. The pills render in this order in both nodes, so the
// two settings read the same way top to bottom.
export const MODES = [
  {
    id: MODE_PARAGRAPH,
    label: "Blank line",
    title: "Blank line: prompts are separated by an empty line. Best for long, multi-line prompts. Matches Save Text's \"Blank line\".",
  },
  {
    id: MODE_LINE,
    label: "New line",
    title: "New line: every single line is its own prompt. Best for short one-liners. Matches Save Text's \"New line\".",
  },
  {
    id: MODE_RULE,
    label: "--- line",
    title: "--- line: prompts are separated by a line containing only dashes. Use this when your prompts have blank lines inside them. Matches Save Text's \"--- line\".",
  },
];

// Is this a mode we know how to split on? Used by readState + setMode so a
// hand-edited workflow can never leave the node in an unsplittable state.
export function isMode(mode) {
  return typeof mode === "string" && SPLITTERS[mode] instanceof RegExp;
}

// Resolve a mode id to its splitter, falling back to the default.
//
// SPLITTERS has a NULL prototype and the result is type-checked, both
// deliberately: a plain-object lookup walks the prototype chain and every
// Object.prototype member is truthy, so a mode id of "constructor" or
// "toString" would hand back a FUNCTION. Save Text hit exactly that and
// wrote a stringified function into the user's .txt (save-text.md #8).
function splitterFor(mode) {
  const s = SPLITTERS[mode];
  return s instanceof RegExp ? s : SPLITTERS[MODE_PARAGRAPH];
}

export function defaultState() {
  return {
    version: 1,
    mode: MODE_PARAGRAPH,
    text: "",
    activePrompt: "",
  };
}

export function readState(node) {
  const s = node.properties?.[STATE_PROP];
  if (!s || typeof s !== "object") return defaultState();
  // Defensive normalisation against hand-edited workflow JSON. An unknown
  // mode (including one from a NEWER build that has a fifth separator) falls
  // back to the default rather than leaving the node unable to split.
  if (!isMode(s.mode)) s.mode = MODE_PARAGRAPH;
  if (typeof s.text !== "string") s.text = "";
  if (typeof s.activePrompt !== "string") s.activePrompt = "";
  s.version = 1;
  return s;
}

export function writeState(node, state) {
  node.properties = node.properties || {};
  node.properties[STATE_PROP] = state;
}

export function setMode(node, mode) {
  if (!isMode(mode)) return;
  const state = readState(node);
  state.mode = mode;
  writeState(node, state);
}

export function setText(node, text) {
  const state = readState(node);
  state.text = String(text || "");
  writeState(node, state);
}

// Parse a text block into individual prompts. THE one splitter in the node -
// the pills, the counter pill and the queue loop all come through here, so a
// new mode cannot be half-supported (the counter used to carry its own
// private copy of this and would have quietly reported the wrong number).
//
// Every mode .trim()s each piece and drops empties, so a trailing separator
// or a stray blank line never inflates the count past what will queue.
export function parsePrompts(text, mode) {
  if (typeof text !== "string" || !text) return [];
  return text
    .split(splitterFor(mode))
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

// Convenience: count of parsed prompts from current node state.
export function countPrompts(node) {
  const state = readState(node);
  return parsePrompts(state.text, state.mode).length;
}

// restoreFromProperties: ensures node.properties.promptPackState exists with
// defaults and applies readState normalization.
export function restoreFromProperties(node) {
  writeState(node, readState(node));
}

// A node only "drives the queue" if it is actually part of the workflow
// being run. A Prompt Pack node that is muted/bypassed OR not wired to
// anything must NOT intercept the Run - otherwise an empty leftover node
// sitting on the canvas blocks every unrelated workflow with the "Paste at
// least one prompt to run" toast (GitHub issue #39).
//
// mode 2 = muted (LiteGraph NEVER), mode 4 = bypass (ComfyUI). Anything
// else (0 / undefined) counts as active.
function isPackNodeActive(node) {
  return node.mode !== 2 && node.mode !== 4;
}

// Connected = at least one output slot has a live link. Prompt Pack's only
// output is `text`; if it isn't wired, the node feeds nothing and should be
// ignored by the queue loop.
function isPackNodeConnected(node) {
  const outs = node.outputs || [];
  for (const o of outs) {
    if (o && Array.isArray(o.links) && o.links.length > 0) return true;
  }
  return false;
}

function isPackNodeDriving(node) {
  if (!node) return false;
  const isClass = node.comfyClass === "PixaromaPromptPack" || node.type === "PixaromaPromptPack";
  // feedsOnlyInactiveSwitch: when this node is wired ONLY into a Switch
  // Pixaroma input that the Switch isn't currently routing, its prompts can't
  // reach any output this run, so it must NOT drive the queue (otherwise
  // every driver wired into one Switch loops and the counts multiply).
  return isClass && isPackNodeActive(node) && isPackNodeConnected(node)
    && !feedsOnlyInactiveSwitch(node);
}

// Find the first PixaromaPromptPack node that actually drives the queue
// (active + connected), top-level pass first, then subgraph recursion. Used
// by the queuePrompt patch in index.js. Returns null when no participating
// node exists, so the patch falls through to a normal single run.
export function findFirstPromptPackNode(app) {
  const graph = app.graph;
  if (!graph) return null;
  const top = graph._nodes || graph.nodes || [];
  for (const n of top) {
    if (isPackNodeDriving(n)) return n;
  }
  function walk(nodes) {
    for (const n of nodes || []) {
      if (isPackNodeDriving(n)) return n;
      const sub = n?.subgraph?._nodes || n?.subgraph?.nodes;
      if (sub) {
        const hit = walk(sub);
        if (hit) return hit;
      }
    }
    return null;
  }
  return walk(top);
}
