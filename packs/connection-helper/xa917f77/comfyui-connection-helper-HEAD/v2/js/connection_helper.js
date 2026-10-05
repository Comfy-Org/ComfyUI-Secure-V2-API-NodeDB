import { comfy } from "/comfy/api/v2.js";

/** @typedef {import("../comfy-api").Comfy} Comfy */
/** @typedef {import("../comfy-api").GraphHandle} GraphHandle */
/** @typedef {import("../comfy-api").NodeHandle} NodeHandle */
/** @typedef {import("../comfy-api").InputSlotHandle} InputSlotHandle */
/** @typedef {import("../comfy-api").OutputSlotHandle} OutputSlotHandle */
/** @typedef {{ distance: number, input: InputSlotHandle, output: OutputSlotHandle | undefined }} InputMatch */

const MAX_DISTANCE = 1000;
/** @type {WeakMap<Comfy, { dispose(): void }>} */
const installations = new WeakMap();

/** @param {NodeHandle} a @param {NodeHandle} b */
function sameNode(a, b) {
  return a.id === b.id && a.graphId === b.graphId;
}

/** @param {NodeHandle} node */
function center(node) {
  const position = node.getPosition();
  const size = node.getSize();
  return {
    x: position.x + size.width / 2,
    y: position.y + size.height / 2,
  };
}

/** @param {NodeHandle} a @param {NodeHandle} b */
function distance(a, b) {
  const ac = center(a);
  const bc = center(b);
  return Math.hypot(ac.x - bc.x, ac.y - bc.y);
}

/** @param {GraphHandle} graph @param {NodeHandle} node @param {number} [maxDistance] */
export function nearestNode(graph, node, maxDistance = MAX_DISTANCE) {
  /** @type {NodeHandle | undefined} */
  let nearest;
  let nearestDistance = maxDistance;
  for (const candidate of graph.nodes()) {
    if (sameNode(candidate, node)) continue;
    const candidateDistance = distance(node, candidate);
    if (candidateDistance < nearestDistance) {
      nearest = candidate;
      nearestDistance = candidateDistance;
    }
  }
  return nearest;
}

/** @param {NodeHandle} target @param {InputSlotHandle} sourceInput */
function targetInputForCopy(target, sourceInput) {
  let input = target.inputs.byName(sourceInput.name);
  if (input || !sourceInput.isWidgetInput) return input;

  const widget = target.widgets.get(sourceInput.name);
  if (!widget) return undefined;
  const options = {
    widget: widget.name,
    widgetConfig: sourceInput.widgetConfig(),
  };
  input = target.inputs.add(sourceInput.name, sourceInput.type, options);
  return input;
}

/** @param {GraphHandle} graph @param {NodeHandle} source @param {NodeHandle} target */
export function copyInputConnections(graph, source, target) {
  let copied = 0;
  for (const sourceInput of source.inputs.all()) {
    const link = sourceInput.link();
    if (!link) continue;
    const origin = graph.node(link.sourceNodeId);
    const output = origin?.outputs.byId(link.sourceSlotId)
      ?? origin?.outputs.at(link.sourceIndex);
    const input = targetInputForCopy(target, sourceInput);
    if (output && input && output.connectTo(target.id, input.id)) copied += 1;
  }
  return copied;
}

/** @param {GraphHandle} graph @param {NodeHandle} target */
export function nearestCompatibleInputs(graph, target) {
  /** @type {Map<string, InputMatch>} */
  const wanted = new Map();
  for (const input of target.inputs.all()) {
    if (!input.isConnected && !wanted.has(input.type)) {
      wanted.set(input.type, {
        distance: Number.POSITIVE_INFINITY,
        input,
        output: undefined,
      });
    }
  }

  const targetPosition = target.getPosition();
  const targetSize = target.getSize();
  const targetY = targetPosition.y + targetSize.height / 2;
  for (const candidate of graph.nodes()) {
    if (sameNode(candidate, target)) continue;
    const position = candidate.getPosition();
    const size = candidate.getSize();
    const dx = targetPosition.x - (position.x + size.width);
    if (dx < 0) continue;
    const dy = targetY - (position.y + size.height / 2);
    const candidateDistance = Math.hypot(dx, dy);
    for (const output of candidate.outputs.all()) {
      const match = wanted.get(output.type);
      if (match && candidateDistance < match.distance) {
        match.distance = candidateDistance;
        match.output = output;
      }
    }
  }
  return [...wanted.values()].filter((match) => match.output);
}

/** @param {GraphHandle} graph @param {NodeHandle} target */
export function connectNearestInputs(graph, target) {
  return graph.batch(() => {
    let connected = 0;
    for (const match of nearestCompatibleInputs(graph, target)) {
      if (match.output?.connectTo(target.id, match.input.id)) connected += 1;
    }
    return connected;
  });
}

/** @param {GraphHandle} graph @param {NodeHandle} target */
export function copyNearestInputs(graph, target) {
  const source = nearestNode(graph, target);
  if (!source) return 0;
  return graph.batch(() => copyInputConnections(graph, source, target));
}

/** @param {NodeHandle} node */
export function hasConnections(node) {
  return node.inputs.all().some((slot) => slot.isConnected)
    || node.outputs.all().some((slot) => slot.isConnected);
}

/** @param {GraphHandle} graph @param {NodeHandle} target */
export function copyNearestConnections(graph, target) {
  if (hasConnections(target)) return 0;
  const source = nearestNode(graph, target);
  if (!source) return 0;
  return graph.batch(() => {
    let copied = copyInputConnections(graph, source, target);
    for (const sourceOutput of source.outputs.all()) {
      const targetOutput = target.outputs.byName(sourceOutput.name);
      if (!targetOutput) continue;
      for (const link of sourceOutput.links()) {
        if (targetOutput.connectTo(link.targetNodeId, link.targetSlotId)) copied += 1;
      }
    }
    return copied;
  });
}

/** @param {Comfy} [api] */
export function installConnectionHelper(api = comfy) {
  const installed = installations.get(api);
  if (installed) return installed;

  const stop = api.defs.extend(() => true, (builder) => {
    builder.addMenuItem({
      label: "Connection Helper",
      order: 80,
      items: (node) => [
        {
          label: "Connect nearest compatible inputs",
          run: () => connectNearestInputs(api.graph, node),
        },
        {
          label: "Copy inputs from nearest node",
          run: () => copyNearestInputs(api.graph, node),
        },
        {
          label: "Copy all connections from nearest node",
          run: () => copyNearestConnections(api.graph, node),
        },
      ],
    });
  });

  let disposed = false;
  const handle = {
    dispose() {
      if (disposed) return;
      disposed = true;
      stop();
      if (installations.get(api) === handle) installations.delete(api);
    },
  };
  installations.set(api, handle);
  return handle;
}

installConnectionHelper();
