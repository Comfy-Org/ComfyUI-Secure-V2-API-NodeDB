import { comfy } from "/comfy/api/v2.js";


const states = new Set();
const stateByNode = new WeakMap();


function integerValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : fallback;
}


function removeState(node) {
  const state = stateByNode.get(node);
  if (!state) return;
  state.unsubscribeSerialize();
  states.delete(state);
  stateByNode.delete(node);
}


function installCounter(node) {
  removeState(node);
  const start = node.widgets.get("start");
  const count = node.widgets.get("count");
  if (!start || !count) throw new Error("Simple Counter is missing its widgets");

  const state = {
    node,
    start,
    count,
    next: integerValue(start.getValue()),
    unsubscribeSerialize: () => {},
  };
  state.unsubscribeSerialize = count.on("beforeSerialize", (event) => {
    if (event.context !== "prompt") return;
    event.setSerializedValue(state.next);
    state.next += 1;
  });
  states.add(state);
  stateByNode.set(node, state);
}


comfy.defs.extend("Simple Counter", (builder) => {
  builder.hideWidget("count");
  builder.onCreated((node) => installCounter(node));
  builder.onConfigured((node) => installCounter(node));
  builder.onRemoved((node) => removeState(node));
});


comfy.queue.onAfterRun((event) => {
  if (!Array.isArray(event.promptIds) || event.promptIds.length === 0) return;
  for (const state of states) {
    state.next = integerValue(state.start.getValue());
  }
});


export { installCounter, integerValue };
