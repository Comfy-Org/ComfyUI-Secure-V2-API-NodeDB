"use strict";

// Global Seed (Inspire), Secure Nodes V2.
//
// The original controls seeds on the server: js/prompt.js wraps api.queuePrompt to send a map of the root
// graph's seed widgets with the workflow, inspire/inspire_server.py's on-prompt handler rewrites the queued
// prompt (prompt_seed_update) and the embedded workflow (workflow_seed_update), and js/seed.js applies the
// "inspire-global-seed" event back to the widgets. V2 does not let a pack rewrite the queued prompt, so the
// same rules run here, on the graph, just before the prompt is built (comfy.queue.onBeforeRun), and the
// prompt then carries them. control_seed, SeedGenerator and the per-node rules are the original's, line for
// line in meaning. Differences are listed in SECURE_CONVERSION.md.

import { comfy } from "/comfy/api/v2.js";

export const GLOBAL_SEED = "GlobalSeed //Inspire";
export const MAX_SEED = 2 ** 32 - 1; // inspire_server.max_seed
const PLACEHOLDER = "$GlobalSeed.value$";
const SEED_INPUTS = ["seed", "noise_seed"];
const ACTIONS = ["fixed", "increment", "decrement", "randomize",
  "increment for each node", "decrement for each node", "randomize for each node"];

/** random.randint(0, max_seed), inclusive. */
export function randomSeed() {
  return Math.floor(Math.random() * (MAX_SEED + 1));
}

/** inspire_server.control_seed: the GlobalSeed value after one control step. */
export function controlSeed(action, value) {
  if (action === "increment" || action === "increment for each node") {
    value += 1;
    if (value > MAX_SEED) value = 0;
  } else if (action === "decrement" || action === "decrement for each node") {
    value -= 1;
    if (value < 0) value = MAX_SEED;
  } else if (action === "randomize" || action === "randomize for each node") {
    value = randomSeed();
  }
  return value;
}

/** inspire_server.SeedGenerator: the seed for each controlled widget, in prompt order. */
export class SeedGenerator {
  constructor(baseValue, action) {
    this.baseValue = baseValue;
    if (action === "increment for each node") this.mode = "incr";
    else if (action === "decrement for each node") this.mode = "decr";
    else if (action === "randomize for each node") this.mode = "rand";
    else this.mode = "fix";
  }

  next() {
    const seed = this.baseValue;
    if (this.mode === "incr") {
      this.baseValue += 1;
      if (this.baseValue > MAX_SEED) this.baseValue = 0;
    } else if (this.mode === "decr") {
      this.baseValue -= 1;
      if (this.baseValue < 0) this.baseValue = MAX_SEED;
    } else if (this.mode === "rand") {
      this.baseValue = randomSeed();
    }
    return seed;
  }
}

/** Muted and bypassed nodes are left out of the prompt, so the original never sees them. */
function inPrompt(node) {
  const mode = node.getMode();
  return mode !== "never" && mode !== "bypass";
}

/** The prompt's key order: the browser serializes integer-like node ids in ascending order. */
function promptOrder(nodes) {
  const numeric = [];
  const other = [];
  for (const node of nodes) (/^\d+$/.test(String(node.id)) ? numeric : other).push(node);
  numeric.sort((a, b) => Number(a.id) - Number(b.id));
  return [...numeric, ...other];
}

/**
 * The widgets the original would reseed on this node: a `seed` / `noise_seed` widget that is still a widget
 * (js/prompt.js skips converted widgets), whose value reaches the prompt as a number (a connected socket
 * sends a link instead), on a node whose backend definition declares that input (frontend-only nodes, such
 * as a Primitive, never reach the prompt).
 */
function seedWidgets(node) {
  const definition = comfy.defs.get(node.type);
  if (!definition || !inPrompt(node)) return [];
  const widgets = [];
  for (const name of SEED_INPUTS) {
    const widget = node.widgets.get(name);
    if (!widget || widget.isHidden()) continue;
    const socket = node.inputs.byName(name);
    if (socket && socket.isConnected) continue;
    if (!definition.inputs.some((input) => input.name === name)) continue;
    if (typeof widget.getValue() !== "number") continue;
    widgets.push(widget);
  }
  return widgets;
}

function widgetOf(node, name) {
  return node.widgets.get(name);
}

let pendingAfterRun = null;

/**
 * prompt_seed_update + workflow_seed_update, applied to the graph before the prompt is built.
 * Returns the restore step for the values the original changed only in the prompt or only in the
 * embedded workflow.
 */
export function beforeRun() {
  pendingAfterRun = null;
  const root = comfy.graph.root();
  if (!root) return undefined;
  const nodes = promptOrder(root.nodes());
  // The original keeps the last GlobalSeed it meets in the prompt.
  let controller;
  for (const node of nodes) if (node.type === GLOBAL_SEED && inPrompt(node)) controller = node;
  if (!controller) return undefined;
  const valueWidget = widgetOf(controller, "value");
  const modeWidget = widgetOf(controller, "mode");
  const actionWidget = widgetOf(controller, "action");
  if (!valueWidget || !modeWidget || !actionWidget) return undefined;
  const action = String(actionWidget.getValue());
  if (!ACTIONS.includes(action)) return undefined;
  const before = Boolean(modeWidget.getValue());
  let value = Number(valueWidget.getValue());
  const restore = [];

  if (before) {
    // control before generate: the prompt and the widgets get the controlled value; js/seed.js keeps the
    // previous one in last_seed; the embedded workflow records action "fixed" (workflow_seed_update), so the
    // saved workflow reproduces this run while the graph keeps the user's action.
    value = controlSeed(action, value);
    for (const node of nodes) {
      if (node.type !== GLOBAL_SEED) continue;
      const own = widgetOf(node, "value");
      const last = widgetOf(node, "last_seed");
      if (last && own) last.setValue(own.getValue());
      if (own) own.setValue(value);
      const ownAction = widgetOf(node, "action");
      if (ownAction && inPrompt(node) && ownAction.getValue() !== "fixed") {
        const kept = ownAction.getValue();
        ownAction.setValue("fixed");
        restore.push(() => ownAction.setValue(kept));
      }
    }
  }

  // "$GlobalSeed.value$" in any text the prompt carries becomes the value, for this prompt only.
  const replaced = String(value);
  for (const node of comfy.graph.queryNodes({ scope: "root-and-subgraphs" })) {
    for (const widget of node.widgets.all()) {
      const text = widget.getValue();
      if (typeof text === "string" && text.includes(PLACEHOLDER)) {
        widget.setValue(text.split(PLACEHOLDER).join(replaced));
        restore.push(() => widget.setValue(text));
      }
    }
  }

  const generator = new SeedGenerator(value, action);
  for (const node of nodes) {
    for (const widget of seedWidgets(node)) widget.setValue(generator.next());
  }

  if (!before) pendingAfterRun = { action, value };
  return restore.length ? () => { for (const undo of restore.reverse()) undo(); } : undefined;
}

/** control after generate: the next value, applied once the prompt was submitted (as js/seed.js did). */
export function afterRun() {
  const pending = pendingAfterRun;
  pendingAfterRun = null;
  if (!pending) return;
  const root = comfy.graph.root();
  if (!root) return;
  const next = controlSeed(pending.action, pending.value);
  for (const node of root.nodes()) {
    if (node.type !== GLOBAL_SEED) continue;
    const own = widgetOf(node, "value");
    const last = widgetOf(node, "last_seed");
    if (last && own) last.setValue(own.getValue());
    if (own) own.setValue(next);
  }
}

comfy.queue.onBeforeRun(beforeRun);
comfy.queue.onAfterRun(afterRun);
