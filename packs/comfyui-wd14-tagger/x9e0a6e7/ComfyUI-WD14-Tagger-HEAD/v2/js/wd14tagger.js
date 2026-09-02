import { comfy } from '/comfy/api/v2.js';


const TAGGER = 'WD14Tagger|pysssss';
const QUICK_PROPERTY = 'pysssss.wd14.quickInterrogate';
const TAG_WIDGET_PREFIX = 'wd14_tags_';


function clearTagWidgets(node) {
  for (const name of node.widgets.names()) {
    if (name.startsWith(TAG_WIDGET_PREFIX)) node.widgets.remove(name);
  }
}


function normalizedTags(result) {
  const value = result?.raw?.tags;
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item ?? ''));
}


function showTagDialog(node, tags) {
  comfy.ui.showDialog({
    key: `pysssss.wd14.tags.${node.graphId ?? 'graph'}.${node.id}`,
    title: 'WD14 Tags',
    render(container) {
      const text = document.createElement('pre');
      text.textContent = tags.join('\n\n');
      text.style.whiteSpace = 'pre-wrap';
      text.style.maxWidth = '80ch';
      text.style.margin = '0';
      container.appendChild(text);
    },
  });
}


function addTaggerFor(source) {
  const output = source.outputs.all().find((slot) => slot.type === 'IMAGE');
  if (!output) return;
  const tagger = comfy.graph.add(TAGGER);
  const position = source.getPosition();
  const size = source.getSize();
  tagger.setPosition({ x: position.x + size.width + 30, y: position.y });
  tagger.setProperty(QUICK_PROPERTY, true);
  if (!output.connectTo(tagger.id, { index: 0 })) {
    tagger.remove();
    return;
  }
  comfy.graph.select([tagger]);
  void comfy.queue.run({ nodes: [tagger] }).catch((error) => {
    console.error('[WD14 Tagger] quick interrogation failed', error);
  });
}


// The legacy extension drew a private download progress pill by monkey-patching
// every node prototype.  Downloads are now declared host provisioning work, so
// normal host execution/download progress supplies that behavior in both
// renderers without pack drawing or a private event channel.
comfy.defs.extend(TAGGER, (builder) => {
  builder.onExecuted((node, result) => {
    const tags = normalizedTags(result);
    clearTagWidgets(node);
    tags.forEach((value, index) => {
      node.widgets.add({
        type: 'textarea',
        name: `${TAG_WIDGET_PREFIX}${index + 1}`,
        value,
        disabled: true,
        options: { serialize: false },
      });
    });
    node.setSizeConstraints({ autoHeight: true });
    if (node.getProperty(QUICK_PROPERTY) === true) {
      node.setProperty(QUICK_PROPERTY, false);
      showTagDialog(node, tags);
    }
  });
});


// The old menu called a pack-owned HTTP route with a renderer image URL.  The
// V2 action instead connects the real IMAGE output to a normal WD14 node and
// partially queues it.  No filesystem path, ambient network request, or host DOM access
// is granted, and the resulting tagger remains visible and reusable.
comfy.defs.extend(
  (def) =>
    def.type !== TAGGER && def.outputs.some((output) => output.type === 'IMAGE'),
  (builder) => {
    builder.addMenuItem({
      label: 'WD14 Tagger',
      run: addTaggerFor,
    });
  },
);
