import { comfy } from "/comfy/api/v2.js";


function audioSlots(node) {
  return node.inputs.all().filter((input) => input.type === "AUDIO");
}


function ensureMixWidgets(node, index) {
  const volume = `volume${index}`;
  const start = `start_secs${index}`;
  if (!node.widgets.get(volume)) {
    node.widgets.add({
      type: "number",
      name: volume,
      value: 1,
      options: { default: 1, step: 0.05 },
    });
  }
  if (!node.widgets.get(start)) {
    node.widgets.add({
      type: "number",
      name: start,
      value: 0,
      options: { default: 0, step: 1, min: 0 },
    });
  }
}


function reconcile(node, withWidgets) {
  const slots = audioSlots(node);
  const names = new Set(slots.map((slot) => slot.name));
  let index = 1;
  if (withWidgets) {
    while (names.has(`audio${index}`)) {
      ensureMixWidgets(node, index);
      index += 1;
    }
  } else {
    while (names.has(`audio${index}`)) index += 1;
  }

  // Pinned getHasSpareAudios ignores its reduce accumulator: its answer is
  // solely whether the final AUDIO socket is free. Preserve that edge case.
  const finalSlotIsSpare = slots.length > 0 && !slots.at(-1).isConnected;
  if (!finalSlotIsSpare) {
    node.inputs.add(`audio${index}`, "AUDIO", {});
    if (withWidgets) ensureMixWidgets(node, index);
  }
}


const restoringConcat = new Set();
comfy.defs.extend("AudioConcat", (builder) => {
  builder.onCreated((node, event) => {
    if (event.restored || event.loading) {
      restoringConcat.add(node.id);
    } else {
      reconcile(node, false);
    }
  });
  builder.onConfigured((node) => {
    restoringConcat.delete(node.id);
    reconcile(node, false);
  });
  builder.onConnectionsChanged((node) => {
    if (!restoringConcat.has(node.id)) reconcile(node, false);
  });
  builder.onRemoved((node) => restoringConcat.delete(node.id));
});


const restoringMix = new Set();
comfy.defs.extend("AudioMix", (builder) => {
  builder.onCreated((node, event) => {
    if (event.restored || event.loading) {
      restoringMix.add(node.id);
    } else {
      reconcile(node, true);
    }
  });
  builder.onConfigured((node) => {
    restoringMix.delete(node.id);
    reconcile(node, true);
  });
  builder.onConnectionsChanged((node) => {
    if (!restoringMix.has(node.id)) reconcile(node, true);
  });
  builder.onRemoved((node) => restoringMix.delete(node.id));
});
