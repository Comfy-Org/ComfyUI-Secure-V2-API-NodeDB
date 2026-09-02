import { comfy } from '/comfy/api/v2.js';


function addSaveNode(source) {
  const output = source.outputs.at(0);
  if (!output || output.type !== 'IMAGE') {
    throw new Error('[Save Image Extended] source slot 0 is no longer IMAGE');
  }

  const saveNode = comfy.graph.add('SaveImageExtended');
  const sourcePosition = source.getPosition();
  saveNode.setPosition({
    x: sourcePosition.x + source.getSize().width + 30,
    y: sourcePosition.y,
  });
  comfy.graph.select([saveNode]);
  output.connectTo(saveNode.id, { index: 0 });
}


// SIE.QuickNodes: preserve the upstream right-click convenience without
// replacing node prototypes or receiving renderer objects.
comfy.defs.extend(
  (def) => def.outputs[0]?.type === 'IMAGE',
  (builder) => {
    builder.addMenuItem({
      label: '💾 Add SaveImageExtended',
      run: addSaveNode,
    });
  },
);
