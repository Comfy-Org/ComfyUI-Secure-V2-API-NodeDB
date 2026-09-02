export const commonPrefix = '🪛';
export function displayContext(b, index = 0, serialize_widgets = false) {
    function populate(node, text) {
        const names = node.widgets.names();
        const pos = names.indexOf('text');
        if (pos !== -1) {
            for (const name of names.slice(pos)) {
                node.widgets.remove(name);
            }
        }
        node.setSerializeWidgets(serialize_widgets);
        if (Array.isArray(text) && index !== undefined && text[index] !== undefined) {
            text = text[index];
        }
        node.widgets.add({
            type: 'textarea',
            name: 'text',
            value: text || '',
            disabled: true,
            options: { serialize: false },
        });
        node.setSizeConstraints({ autoHeight: true });
    }
    b.onExecuted((node, result) => {
        populate(node, result.raw.text);
    });
    b.onConfigured((node, data) => {
        if (data.widgets_values?.length) {
            populate(node, data.widgets_values);
        }
    });
}
