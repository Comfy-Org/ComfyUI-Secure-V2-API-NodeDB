import { comfy } from '/comfy/api/v2.js';


const CONFIG_KEY = 'quadmoons/config-names-v1';
const samplerTypes = ['quadmoonKSampler', 'quadmoonRotationalSampler'];


function setUpscaleVisibility(node, selected = undefined) {
  const value = selected ?? node.widgets.get('upscale_latent')?.getValue();
  const enabled = value === 'Yes';
  node.widgets.get('upscale_method')?.setHidden(!enabled);
  node.widgets.get('ratio')?.setHidden(!enabled);
  node.setSizeConstraints({ autoHeight: true });
}


comfy.defs.extend('quadmoonThebutton', (builder) => {
  builder.onCreated((node) => {
    node.widgets.add({
      type: 'button', name: 'Stop Current Queue', value: null, serialize: false,
    }).on('activate', () => { void comfy.queue.interrupt(); });
    node.widgets.add({
      type: 'button', name: 'Start Queue', value: null, serialize: false,
    }).on('activate', () => { void comfy.queue.run(); });
    // Upstream's third button calls Manager's host-wide reboot route. A node
    // pack does not receive administrator authority merely by being loaded.
    node.widgets.add({
      type: 'button', name: 'Reboot (unavailable in Secure Nodes)', value: null,
      disabled: true, serialize: false,
    });
    node.setSizeConstraints({ autoHeight: true });
  });
});


for (const nodeType of samplerTypes) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => {
      node.widgets.get('upscale_latent')?.on(
        'change', (value) => setUpscaleVisibility(node, value),
      );
      setUpscaleVisibility(node);
    });
  });
}


async function readNames() {
  const raw = await comfy.storage.get(CONFIG_KEY);
  if (!Array.isArray(raw)) return [];
  return raw.filter((item) => typeof item === 'string' && item.length <= 1024).slice(0, 2048);
}


function applyConfigNames(node, names) {
  const widget = node.widgets.get('config_names');
  if (!widget || names.length === 0) return;
  widget.setOption('values', names);
  if (!names.includes(widget.getValue())) widget.setValue(names[0]);
}


comfy.defs.extend('quadmoonLoadConfigs', (builder) => {
  builder.onCreated((node) => {
    void readNames().then((names) => applyConfigNames(node, names));
  });
});


for (const nodeType of ['quadmoonSavePrompt', 'quadmoonSaveNeg']) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onExecuted((_node, result) => {
      const names = result?.raw?.config_names;
      if (!Array.isArray(names)) return;
      const bounded = names.filter((item) => typeof item === 'string' && item.length <= 1024).slice(0, 2048);
      void comfy.storage.set(CONFIG_KEY, bounded);
      for (const loader of comfy.graph.nodesOfType('quadmoonLoadConfigs')) {
        applyConfigNames(loader, bounded);
      }
    });
  });
}

// The pinned CLIP extension only reinstalled the same property descriptors
// already owned by ComfyUI. Encoding behavior is implemented by the nodes;
// no ambient widget prototype mutation is needed in V2.
