// Opt-in source component. Registry transport and browser verification are pending.
const LORA_NODE_CLASSES = new Set([
  'Lora Loader (LoraManager)', 'Lora Stacker (LoraManager)',
  'WanVideo Lora Select (LoraManager)', 'Create Hook LoRA (LoraManager)',
]);
const TARGET_WIDGET_NAMES = new Set(['ckpt_name', 'unet_name']);
const TEXT_CAPABLE_CLASSES = new Set([
  'Prompt (LoraManager)', 'Text (LoraManager)', 'CLIPTextEncode',
]);
const PRIMITIVE_NODE_TYPES = new Set([
  'PrimitiveNode', 'PrimitiveInt', 'PrimitiveFloat', 'PrimitiveString',
  'PrimitiveBoolean', 'PrimitiveStringMultiline',
]);

/** @param {Comfy} comfy */
function documentGraphs(comfy) {
  const root = comfy.graph.root();
  return root ? [root, ...comfy.graph.subgraphs()] : [];
}

/** @param {NodeHandle} node */
function resolveTextWidget(node) {
  const widgets = node.widgets.all();
  const textTypes = new Set(['string', 'customtext']);
  return widgets.find(widget => {
    const type = typeof widget.widgetType === 'string' ? widget.widgetType.toLowerCase() : '';
    return textTypes.has(type) || type.includes('string');
  }) ?? widgets.find(widget => widget.name && !widget.name.startsWith('_')) ?? null;
}

/**
 * Native also checks input.widget.name before input.name. The published input
 * handle exposes only the latter: renamed widget/socket association is held.
 * @param {NodeHandle} node
 * @param {string} name
 */
function widgetInput(node, name) {
  return node.inputs.byName(name);
}

/** @param {NodeHandle} node */
function isPromptWidgetConnected(node) {
  const widget = resolveTextWidget(node);
  return widget ? widgetInput(node, widget.name)?.isConnected ?? false : false;
}

/**
 * Document-scoped description. `mode` stays in the public API's symbolic form;
 * the original route's numeric-mode projection remains an integration task.
 * @param {Comfy} comfy
 */
export function describeWorkflowNodes(comfy) {
  const nodes = [];
  for (const graph of documentGraphs(comfy)) {
    for (const node of graph.nodes()) {
      if (node.isDeleted) continue;
      const widgetNames = node.widgets.all().map(widget => widget.name)
        .filter(name => typeof name === 'string' && name.length > 0);
      const supportsLora = LORA_NODE_CLASSES.has(node.comfyClass);
      const hasTargetWidget = widgetNames.some(name => TARGET_WIDGET_NAMES.has(name));
      const hasTextWidget = TEXT_CAPABLE_CLASSES.has(node.comfyClass);
      const markerRole = node.getProperty('lm_marker_role') ?? null;
      if (!supportsLora && !hasTargetWidget && !hasTextWidget && !markerRole) continue;
      const textWidgetConnected = hasTextWidget || markerRole === 'send_prompt_target'
        ? isPromptWidgetConnected(node) : false;
      nodes.push({
        node_id: node.id,
        graph_id: graph.id,
        graph_name: typeof graph.name === 'string' && graph.name.trim() ? graph.name : null,
        bgcolor: node.getBgColor() ?? node.getColor() ?? null,
        title: node.getTitle() || node.comfyClass,
        type: node.comfyClass,
        comfy_class: node.comfyClass,
        public_mode: node.getMode(),
        marker_role: markerRole,
        capabilities: {
          supports_lora: supportsLora,
          has_text_widget: hasTextWidget && !textWidgetConnected,
          text_widget_connected: textWidgetConnected,
          widget_names: widgetNames,
        },
      });
    }
  }
  return nodes;
}

// Deliberately retain native JavaScript coercion for non-string values.
export function appendWorkflowWidgetValue(current, incoming) {
  return current + (current && current.length > 0 ? ' ' : '') + incoming;
}

/**
 * Commit through the public widget protocol, including callbacks and saved
 * values. Native replacement/append and direct Primitive redirection retained.
 * @param {Comfy} comfy
 * @param {{node_id?: string | number, id?: string | number, graph_id?: string,
 * action?: string, widget_name?: string, value?: WidgetValue, mode?: string}} message
 * @param {() => void} refresh
 */
export function applyWorkflowWidgetUpdate(comfy, message, refresh) {
  const nodeId = message?.node_id ?? message?.id;
  const widgetName = message?.widget_name;
  if (nodeId == null || (!message?.action && !widgetName)) return false;
  const graphs = documentGraphs(comfy);
  const root = comfy.graph.root();
  const graph = graphs.find(scope => scope.id === message.graph_id) ?? root;
  const node = graph?.node(String(nodeId));
  if (!node || node.isDeleted) return false;

  let target;
  if (message.action === 'inject_text') {
    target = resolveTextWidget(node);
    if (!target) return false;
    if (widgetInput(node, target.name)?.isConnected) {
      refresh();
      return false;
    }
  } else if (widgetName) {
    target = node.widgets.get(widgetName);
    if (!target) return false;
  } else return false;

  if (widgetName) {
    // Physical source matches native direct-link semantics; reroute resolution
    // would change which node is edited.
    const source = widgetInput(node, widgetName)?.source();
    const primitive = source ? graph.node(source.nodeId) : undefined;
    if (primitive && !primitive.isDeleted && PRIMITIVE_NODE_TYPES.has(primitive.type)) {
      target = primitive.widgets.at(0) ?? target;
    }
  }
  const value = target.getValue();
  const updated = message.mode === 'append'
    ? appendWorkflowWidgetValue(value, message.value)
    : message.value;
  target.setValue(updated);
  return true;
}

/**
 * Listener ownership for converted registry consumers. `refresh` must be
 * supplied by the pack's implemented registry controller; no route is assumed.
 * @param {Comfy} comfy
 * @param {(force?: boolean) => void} refresh
 */
export function registerWorkflowRegistryEvents(comfy, refresh) {
  let disposed = false;
  let timer;
  const schedule = () => {
    if (disposed) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = undefined;
      if (!disposed) refresh();
    }, 500);
  };
  const stop = [];
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    clearTimeout(timer);
    for (const unsubscribe of stop.reverse()) unsubscribe();
  };
  try {
    stop.push(comfy.backend.on('lora_registry_refresh', () => {
      if (!disposed) refresh(true);
    }));
    stop.push(comfy.backend.on('lm_widget_update', detail => {
      if (!disposed) applyWorkflowWidgetUpdate(comfy, detail, () => refresh(true));
    }));
    stop.push(comfy.onWorkflowLoaded(() => { if (!disposed) refresh(); }));
    stop.push(comfy.onNodeChanged(schedule, { scope: 'document' }));
    stop.push(comfy.defs.extend(/.*/, builder => {
      builder.onCreated(schedule);
      builder.onConfigured(schedule);
      builder.onRemoved(schedule);
      builder.onConnectionsChanged(schedule);
      builder.onPropertyChanged(schedule);
    }));
    stop.push(comfy.onReady(() => { if (!disposed) refresh(); }));
    return dispose;
  } catch (error) {
    dispose();
    throw error;
  }
}
