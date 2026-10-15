import { comfy } from '/comfy/api/v2.js';
comfy.defs.extend('SimpleReadableMetadataSaveTextSG', builder => {
  builder.onCreated(node => {
    node.widgets.get('filename_prefix')?.setOption('placeholder', 'Enter filename prefix (e.g., output/myfile)');
    node.setSizeConstraints({ minWidth: 280, minHeight: 100 }); node.setSize({ width: 320, height: 120 });
  });
  builder.onExecuted((_node, result) => {
    const files = result?.raw?.text_files; if (Array.isArray(files)) console.log('[SaveTextFile] Files saved:', files);
  });
});
