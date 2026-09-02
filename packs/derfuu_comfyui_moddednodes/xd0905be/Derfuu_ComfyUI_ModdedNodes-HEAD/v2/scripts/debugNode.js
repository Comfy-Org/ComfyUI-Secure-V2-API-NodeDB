import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend('DF_To_text_(Debug)', (builder) => {
    builder.onExecuted((node, result) => {
        for (const name of node.widgets.names()) {
            node.widgets.remove(name);
        }
        node.widgets.add({
            type: 'textarea',
            name: 'DEBUG INFO',
            value: String(result.text?.[0] ?? ''),
            disabled: true,
        });
    });
});
