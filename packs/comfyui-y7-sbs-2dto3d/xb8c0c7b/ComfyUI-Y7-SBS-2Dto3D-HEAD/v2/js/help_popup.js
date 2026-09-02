import { comfy } from '/comfy/api/v2.js';


function showHelp(node, title, description) {
  comfy.ui.showDialog({
    key: `Y7.SBS.help.${node.type}.${node.id}`,
    title,
    render(container) {
      const content = document.createElement('pre');
      content.textContent = description;
      content.style.whiteSpace = 'pre-wrap';
      content.style.maxWidth = '72ch';
      content.style.margin = '0';
      container.appendChild(content);
    },
  });
}


// The legacy extension painted a question mark and attached document-global
// pointer handlers. A host menu and host-mounted dialog retain the same safe
// help readout without reaching outer-page DOM or renderer internals.
comfy.defs.extend(
  (def) => def.category === 'Y7 SBS' && (def.description?.length ?? 0) > 0,
  (builder) => {
    const { title, description } = builder.def;
    builder.addMenuItem({
      label: 'Show Y7 SBS help',
      run: (node) => showHelp(node, title, description),
    });
  },
);
