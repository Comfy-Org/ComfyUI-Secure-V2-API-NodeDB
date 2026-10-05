import { comfy } from "/comfy/api/v2.js";


const MAX_REFERENCES = 16;
const IMAGE = /^image(\d+)$/;
const MASK = /^mask(\d+)$/;
const reconciling = new Set();

function pairNumbers(node, bounded = true) {
  const found = new Set();
  for (const input of node.inputs.all()) {
    const match = IMAGE.exec(input.name) || MASK.exec(input.name);
    if (match) found.add(Number(match[1]));
  }
  return [...found]
    .filter((value) => Number.isInteger(value) && value >= 1 && (!bounded || value <= MAX_REFERENCES))
    .sort((left, right) => left - right);
}

function slot(node, name) {
  return node.inputs.byName(name);
}

function addPair(node, index) {
  if (!slot(node, `image${index}`)) node.inputs.add(`image${index}`, "IMAGE", { shape: "optional" });
  if (!slot(node, `mask${index}`)) node.inputs.add(`mask${index}`, "MASK", { shape: "optional" });
}

function removePair(node, index) {
  const mask = slot(node, `mask${index}`);
  if (mask) node.inputs.remove(mask.id);
  const image = slot(node, `image${index}`);
  if (image) node.inputs.remove(image.id);
}

function pairEmpty(node, index) {
  return !slot(node, `image${index}`)?.isConnected && !slot(node, `mask${index}`)?.isConnected;
}

export function reconcileReferencePairs(node) {
  const key = String(node.id);
  if (reconciling.has(key)) return;
  reconciling.add(key);
  try {
    for (const index of pairNumbers(node, false)) {
      if (index > MAX_REFERENCES) removePair(node, index);
    }
    let numbers = pairNumbers(node);
    if (numbers.length === 0) {
      addPair(node, 1);
      numbers = [1];
    }
    for (const index of numbers) addPair(node, index);

    for (;;) {
      numbers = pairNumbers(node);
      if (numbers.length <= 1) break;
      const last = numbers.at(-1);
      const previous = numbers.at(-2);
      if (!pairEmpty(node, last) || !pairEmpty(node, previous)) break;
      removePair(node, last);
    }

    numbers = pairNumbers(node);
    const last = numbers.at(-1);
    if (last < MAX_REFERENCES && !pairEmpty(node, last)) addPair(node, last + 1);
  } finally {
    reconciling.delete(key);
  }
}

comfy.defs.extend("TextEncodeKrea2", (builder) => {
  builder.onCreated((node) => reconcileReferencePairs(node));
  builder.onConfigured((node) => reconcileReferencePairs(node));
  builder.onConnectionsChanged((node) => reconcileReferencePairs(node));
});
