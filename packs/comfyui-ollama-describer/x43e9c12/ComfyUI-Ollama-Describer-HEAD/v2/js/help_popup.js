import { comfy } from '/comfy/api/v2.js';


function showHelp(node, title, description) {
  comfy.ui.showDialog({
    key: `OllamaDescriber.help.${node.type}.${node.id}`,
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


// The legacy extension painted a question mark into LiteGraph, performed its
// own hit testing, and attached document-global pointer handlers. A host menu
// and host dialog preserve the help affordance in both supported renderers.
comfy.defs.extend(
  (def) => def.category.startsWith('Ollama') && def.description.length > 0,
  (builder) => {
    const { title, description } = builder.def;
    builder.addMenuItem({
      label: 'Show Ollama node help',
      run: (node) => showHelp(node, title, description),
    });
  },
);
