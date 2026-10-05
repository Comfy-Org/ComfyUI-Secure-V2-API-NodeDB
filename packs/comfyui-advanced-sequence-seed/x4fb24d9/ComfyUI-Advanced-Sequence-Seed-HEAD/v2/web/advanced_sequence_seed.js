import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "AdvancedSequenceSeedNode";
const states = new WeakMap();

function dispose(node) {
  const state = states.get(node);
  if (!state) return;
  states.delete(node);
  state.unsubscribe?.();
}

function install(node) {
  dispose(node);
  const force = node.widgets.get("force_recalculation");
  const current = node.widgets.get("current_seed");
  if (!force || !current) throw new Error("Advanced Sequence Seed widgets are unavailable");
  const syncDisabled = () => current.setDisabled(Boolean(force.getValue()));
  const unsubscribe = force.on("change", syncDisabled);
  states.set(node, { current, unsubscribe });
  syncDisabled();
}

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => install(node));
  builder.onConfigured((node) => {
    const state = states.get(node);
    if (!state) return install(node);
    state.current.setDisabled(Boolean(node.widgets.get("force_recalculation")?.getValue()));
  });
  builder.onExecuted((node, result) => {
    const state = states.get(node);
    const value = result?.raw?.seed;
    const seed = Array.isArray(value) ? value[0] : value;
    if (!state || typeof seed !== "number" || !Number.isFinite(seed)) return;
    state.current.setValue(Math.trunc(seed));
  });
  builder.onRemoved((node) => dispose(node));
});
