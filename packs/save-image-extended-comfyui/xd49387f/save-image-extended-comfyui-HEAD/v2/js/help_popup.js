import { comfy } from '/comfy/api/v2.js';


// SIE.Contextmenu: the preference is host-rendered and persists under the
// upstream id. The old custom options callback is intentionally gone.
comfy.settings.declare({
  id: 'SIE.helpPopup',
  name: '💾 SIE: Help popups',
  category: ['Save Image Extended', 'Help'],
  tooltip: 'Show a node-menu action that opens the node description.',
  defaultValue: true,
  type: 'boolean',
});


function showHelp(node, title, description) {
  comfy.ui.showDialog({
    key: `SIE.help.${node.type}.${node.id}`,
    title,
    render(container) {
      const text = document.createElement('pre');
      text.textContent = description;
      text.style.whiteSpace = 'pre-wrap';
      text.style.maxWidth = '72ch';
      text.style.margin = '0';
      container.appendChild(text);
    },
  });
}


// SIE.HelpPopup: a host dialog and menu replace canvas drawing, hit-testing,
// global mouse listeners, remote script injection, and parent-DOM mutation.
comfy.defs.extend(
  (def) => def.category.startsWith('image') && def.description.length > 0,
  (builder) => {
    const { title, description } = builder.def;
    builder.addMenuItem({
      label: '💾 Show node help',
      when: () => comfy.settings.get('SIE.helpPopup') !== false,
      run: (node) => showHelp(node, title, description),
    });
  },
);
