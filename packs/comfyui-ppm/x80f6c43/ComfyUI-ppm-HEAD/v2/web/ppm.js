import { comfy } from "/comfy/api/v2.js";


export const FRONTEND_INTENTS = Object.freeze([
  "grow paired conditioning and mask sockets for AttentionCouplePPM",
  "trim trailing unused AttentionCouplePPM socket pairs",
  "grow MaskCompositePPM mask sockets",
  "trim trailing unused MaskCompositePPM sockets while retaining mask_1",
]);

const reconciling = new Set();

function numbered(slots, prefix) {
  return slots
    .all()
    .filter((slot) => slot.name.startsWith(prefix))
    .sort((left, right) => {
      const a = Number(left.name.slice(prefix.length));
      const b = Number(right.name.slice(prefix.length));
      return a - b;
    });
}

function reconcileAttention(node) {
  if (reconciling.has(node.id)) return;
  reconciling.add(node.id);
  try {
    const baseCond = node.inputs.byName("base_cond");
    const baseMask = node.inputs.byName("base_mask");
    if (!baseCond || !baseMask) return;

    const conds = numbered(node.inputs, "cond_");
    const masks = numbered(node.inputs, "mask_");

    while (
      conds.length > 0 &&
      masks.length > 0 &&
      !conds.at(-1).isConnected &&
      !masks.at(-1).isConnected
    ) {
      const mask = masks.pop();
      const cond = conds.pop();
      node.inputs.remove(mask.id);
      node.inputs.remove(cond.id);
    }

    const lastCond = conds.at(-1);
    const lastMask = masks.at(-1);
    const onlyBase =
      conds.length === 0 &&
      masks.length === 0 &&
      baseCond.isConnected &&
      baseMask.isConnected;
    const lastPairFull =
      Boolean(lastCond?.isConnected) && Boolean(lastMask?.isConnected);
    if (onlyBase || lastPairFull) {
      const index = Math.min(conds.length, masks.length) + 1;
      node.inputs.add(`cond_${index}`, "CONDITIONING", { shape: "optional" });
      node.inputs.add(`mask_${index}`, "MASK", { shape: "optional" });
    }
  } finally {
    reconciling.delete(node.id);
  }
}

function reconcileMasks(node) {
  if (reconciling.has(node.id)) return;
  reconciling.add(node.id);
  try {
    const masks = numbered(node.inputs, "mask_");
    while (masks.length > 1 && !masks.at(-1).isConnected) {
      node.inputs.remove(masks.pop().id);
    }
    if (masks.at(-1)?.isConnected) {
      node.inputs.add(`mask_${masks.length + 1}`, "MASK", {
        shape: "optional",
      });
    }
  } finally {
    reconciling.delete(node.id);
  }
}

comfy.defs.extend("AttentionCouplePPM", (builder) => {
  builder.onConnectionsChanged((node) => reconcileAttention(node));
});

comfy.defs.extend("MaskCompositePPM", (builder) => {
  builder.onConnectionsChanged((node) => reconcileMasks(node));
});
