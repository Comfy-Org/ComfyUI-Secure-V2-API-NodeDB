import { comfy } from '/comfy/api/v2.js';

const CONFIG = {
  vsLinx_BypassOnBool: { boolInput: 1, widget: 'bypass', trueMode: 'bypass' },
  vsLinx_MuteOnBool: { boolInput: 1, widget: 'mute', trueMode: 'never' },
};
const STATE_NODE = 'vsLinx_BypassMuteOnState';
const PIPE_IN = 'vsLinx_AnyToPipe';
const PIPE_OUT = 'vsLinx_PipeToAny';
const active = new Map();
const keyFor = (node) => `${node.graphId ?? ''}:${node.id}`;

function scopeFor(graphId) {
  if (!graphId || comfy.graph.id === graphId) return comfy.graph;
  const root = comfy.graph.root();
  if (root?.id === graphId) return root;
  return comfy.graph.subgraphs().find((scope) => scope.id === graphId);
}

function peer(node, id, graphId = node.graphId) {
  return scopeFor(graphId)?.node(String(id));
}

function sourceOf(node, index, crossBoundary = true) {
  const input = node.inputs.at(index);
  if (!input?.isConnected) return undefined;
  if (!crossBoundary) {
    const source = input.source();
    return source ? { node: peer(node, source.nodeId), outputIndex: source.outputIndex } : undefined;
  }
  const source = input.resolvedSource();
  return source?.kind === 'output'
    ? { node: peer(node, source.nodeId, source.graphId), outputIndex: source.outputIndex }
    : undefined;
}

function typeMatches(first, second) {
  return comfy.defs.isTypeCompatible(String(first || '*'), String(second || '*'));
}

function booleanWidget(node) {
  return node.widgets.all().find((widget) => typeof widget.getValue() === 'boolean');
}

function resolveInputBoolean(node, index, seen) {
  const source = sourceOf(node, index);
  if (source?.node) return resolveBoolean(source.node, source.outputIndex, seen);
  const input = node.inputs.at(index);
  const widget = input ? node.widgets.get(input.name) : undefined;
  const value = widget?.getValue();
  return typeof value === 'boolean' ? value : null;
}

function resolveBoolean(node, outputIndex = 0, seen = new Set()) {
  if (!node || node.isDeleted) return null;
  const token = `${node.graphId ?? ''}:${node.id}:${outputIndex}`;
  if (seen.has(token)) return null;
  seen.add(token);
  if (node.getMode() === 'never') return false;
  if (node.getMode() === 'bypass') {
    const outputType = node.outputs.at(outputIndex)?.type;
    for (const input of node.inputs.all()) {
      if (typeMatches(input.type, outputType)) {
        const source = sourceOf(node, input.index);
        return source?.node ? resolveBoolean(source.node, source.outputIndex, seen) : false;
      }
    }
    return false;
  }
  if (node.type === 'vsLinx_BooleanFlip') {
    const value = resolveInputBoolean(node, 0, seen);
    return value === null ? null : !value;
  }
  if (node.type === 'vsLinx_BooleanAndOperator' || node.type === 'vsLinx_BooleanOrOperator') {
    const left = resolveInputBoolean(node, 0, new Set(seen));
    const right = resolveInputBoolean(node, 1, new Set(seen));
    if (left === null || right === null) return null;
    return node.type.endsWith('AndOperator') ? left && right : left || right;
  }
  if (node.type === PIPE_OUT) {
    const pipe = sourceOf(node, 0);
    if (pipe?.node?.type === PIPE_IN) return resolveInputBoolean(pipe.node, outputIndex, seen);
  }
  for (const input of node.inputs.all()) {
    if (!input.isConnected) continue;
    const value = resolveInputBoolean(node, input.index, new Set(seen));
    if (value !== null) return value;
  }
  const value = booleanWidget(node)?.getValue();
  return typeof value === 'boolean' ? value : null;
}

function downstreamTargets(node) {
  const output = node.outputs.at(0);
  if (!output) return [];
  const targets = [];
  for (const edge of output.targets()) {
    const target = peer(node, edge.nodeId);
    if (!target) continue;
    if (target.type !== PIPE_IN) {
      targets.push(target);
      continue;
    }
    const pipeOutput = target.outputs.at(0);
    for (const packed of pipeOutput?.targets() ?? []) {
      const unpack = peer(target, packed.nodeId);
      if (unpack?.type !== PIPE_OUT) continue;
      for (const unpacked of unpack.outputs.at(edge.inputIndex)?.targets() ?? []) {
        const finalTarget = peer(unpack, unpacked.nodeId);
        if (finalTarget) targets.push(finalTarget);
      }
    }
  }
  return targets;
}

function setDownstream(node, mode) {
  for (const target of downstreamTargets(node)) {
    if (target.getMode() !== mode) target.setMode(mode);
  }
}

function retype(node) {
  const input = node.inputs.at(0);
  const output = node.outputs.at(0);
  let type = input?.connectedType;
  if (!type && output) {
    for (const target of output.targets()) {
      type = peer(node, target.nodeId)?.inputs.at(target.inputIndex)?.type;
      if (type && type !== '*') break;
    }
  }
  type = type && type !== '*' ? type : '*';
  input?.modify({ type });
  output?.modify({ type, label: type === '*' ? 'out' : String(type) });
}

function evaluate(node) {
  const config = CONFIG[node.type];
  if (config) {
    const source = sourceOf(node, config.boolInput);
    const resolved = source?.node
      ? resolveBoolean(source.node, source.outputIndex)
      : node.widgets.get(config.widget)?.getValue();
    if (typeof resolved === 'boolean') {
      const widget = node.widgets.get(config.widget);
      if (source?.node && widget?.getValue() !== resolved) widget?.setValue(resolved);
      setDownstream(node, resolved ? config.trueMode : 'always');
    }
    retype(node);
    return;
  }
  if (node.type !== STATE_NODE) return;
  let mode = 'always';
  const mirrorOwn = node.widgets.get('mirror_own_state')?.getValue() === true;
  if (mirrorOwn && ['bypass', 'never'].includes(node.getMode())) mode = node.getMode();
  else {
    const cross = node.widgets.get('ignore_subgraph_boundary')?.getValue() === true;
    const source = sourceOf(node, 1, cross);
    const sourceMode = source?.node?.getMode();
    if (sourceMode === 'bypass' || sourceMode === 'never') mode = sourceMode;
  }
  setDownstream(node, mode);
  retype(node);
}

function start(node) {
  stop(node);
  const removers = [];
  for (const name of ['bypass', 'mute', 'ignore_subgraph_boundary', 'mirror_own_state']) {
    const unsubscribe = node.widgets.get(name)?.on('change', () => evaluate(node));
    if (typeof unsubscribe === 'function') removers.push(unsubscribe);
  }
  node.widgets.get('ignore_subgraph_boundary')?.setLabel('Ignore subgraph boundary');
  node.widgets.get('mirror_own_state')?.setLabel("Mirror this node's own bypass/mute");
  node.setSerializeWidgets(true);
  const timer = setInterval(() => evaluate(node), 200);
  active.set(keyFor(node), { node, timer, removers });
  evaluate(node);
}

function stop(node) {
  const state = active.get(keyFor(node));
  if (state) {
    clearInterval(state.timer);
    for (const unsubscribe of state.removers) unsubscribe();
  }
  active.delete(keyFor(node));
}

for (const type of [...Object.keys(CONFIG), STATE_NODE]) {
  comfy.defs.extend(type, (builder) => {
    builder.onCreated(start);
    builder.onConfigured(start);
    builder.onConnectionsChanged((node) => evaluate(node));
    builder.onRemoved(stop);
  });
}

comfy.queue.onBeforeRun(() => {
  for (const { node } of active.values()) evaluate(node);
});
