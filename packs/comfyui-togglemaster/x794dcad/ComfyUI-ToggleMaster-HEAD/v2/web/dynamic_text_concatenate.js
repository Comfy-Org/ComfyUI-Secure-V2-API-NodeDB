import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "DynamicTextConcatenate";
const MIN_INPUTS = 2;
const MAX_INPUTS = 10;
const TEXT_INPUT = /^text_(\d+)$/;

function textInputs(node) {
  return node.inputs.all()
    .filter((slot) => TEXT_INPUT.test(slot.name))
    .sort((left, right) => Number(left.name.slice(5)) - Number(right.name.slice(5)));
}

function synchronizeInputs(node) {
  let inputs = textInputs(node);

  while (inputs.length > MIN_INPUTS) {
    const last = inputs.at(-1);
    const previous = inputs.at(-2);
    if (last.isConnected || previous.isConnected) break;
    node.inputs.remove(last.id);
    inputs = textInputs(node);
  }

  if (inputs.length > 0 && inputs.every((slot) => slot.isConnected)
      && inputs.length < MAX_INPUTS) {
    const used = new Set(inputs.map((slot) => Number(slot.name.slice(5))));
    let index = 1;
    while (used.has(index)) index += 1;
    if (index <= MAX_INPUTS) node.inputs.add(`text_${index}`, "STRING", { shape: "optional" });
  }
}

function deferSynchronization(node) {
  queueMicrotask(() => synchronizeInputs(node));
}

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => deferSynchronization(node));
  builder.onConfigured((node) => deferSynchronization(node));
  builder.onConnectionsChanged((node, event) => {
    const slot = event.side === "input" ? node.inputs.at(event.index) : undefined;
    if (slot && TEXT_INPUT.test(slot.name)) {
      deferSynchronization(node);
    }
  });
});
