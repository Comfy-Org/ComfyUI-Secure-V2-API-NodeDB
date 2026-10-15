/** Deprecated original gallery input, using published widget and lifecycle APIs. */
export function installStyleGalleryButtonWidgetType(comfy, sources) {
    const type = 'ZIPN_STYLE_GALLERY_BUTTON';
    const active = [];
    const renders = new Set();
    let installed = true;
    const stopDefinition = comfy.defs.extend(def => def.type.endsWith(' //ZImagePowerNodes'), builder => {
        builder.onCreated(node => queueMicrotask(() => {
            if (!installed || node.isDeleted) return;
            const order = node.widgets.names();
            for (const widget of node.widgets.all()) {
                if (widget.widgetType !== type || active.some(item => item.name === widget.name && comfy.sameEntity(item.node,node))) continue;
                const definition = {name:widget.name,type,value:null,options:{...widget.getOptions()}};
                node.widgets.remove(widget.name);
                node.widgets.add(definition);
            }
            node.widgets.reorder(order.filter(name => node.widgets.get(name)));
        }));
    });
    const stopType = comfy.defs.defineWidgetType(type, {
        defaultValue:null,serialize:true,
        render(container,_value,name,context) {
            const parts = name.split('_');
            let variant = parts.length > 1 ? parts[parts.length - 1] : '';
            if (variant.match(/^[0-9]+$/) === null) variant = '';
            const title = `Select Style${variant ? ' ' + variant : ''}`;
            const button = document.createElement('button');
            button.textContent = `🖼️  ${title} ...`;
            button.setAttribute('aria-label',title);
            button.style.width = '100%';
            container.append(button);
            let record = null;
            let disposed = false;
            const stopReady = context.onNodeReady(node => {
                const widget = node.widgets.get(name);
                if (!widget) return;
                let cancelled = false;
                const stopSerialize = widget.on('beforeSerialize',event => event.setSerializedValue(null));
                let item = null;
                // Reconstruction adds the widget before restoring its order.
                // Read its preceding input once that public reorder completes.
                queueMicrotask(() => {
                    if (cancelled || disposed || node.isDeleted) return;
                    const prevIndex = node.widgets.names().indexOf(name) - 1;
                    const previous = node.widgets.all()[prevIndex];
                    // Both original custom user-input factories return a
                    // native combo; their published type retains that identity.
                    if (!previous || !['combo','ZIPN_STYLE','ZIPN_PALETTE'].includes(previous.widgetType)) {
                        console.error('Style Gallery Button must follow a Combo Widget!');
                        queueMicrotask(() => {if (!disposed && !node.isDeleted) node.widgets.remove(name);});
                        return;
                    }
                    const options = {dialog_title:title,prev_index:prevIndex,...context.getOptions()};
                    widget.setOption('dialog_title',options.dialog_title);
                    widget.setOption('prev_index',options.prev_index);
                    item = {node,name,options};
                    record = item;active.push(item);
                });
                return () => {
                    cancelled = true;
                    stopSerialize();
                    const index = active.indexOf(item);if (index >= 0) active.splice(index,1);
                    if (record === item) record = null;
                };
            });
            const launch = () => {
                if (!record) return;
                const {node,options} = record;
                const previous = node.widgets.all()[options.prev_index];
                const currentStyle = previous.getValue()?.replace(/^"|"$/g,'');
                sources.launchStyleDialog(options.endpoint || '',options.images_url || '',options.dialog || {},currentStyle,selectedStyle => {
                    if (disposed || record?.node !== node || node.isDeleted) return;
                    if (selectedStyle != '' && selectedStyle != '-' && selectedStyle != 'none') {
                        if (!selectedStyle.startsWith('"')) selectedStyle = `"${selectedStyle}"`;
                    }
                    // The published commit runs the callback chain and redraws.
                    // Same-value commits retain the host's documented no-op rule.
                    previous.setValue(selectedStyle);
                });
            };
            button.addEventListener('click',launch);
            const teardown = () => {
                if (disposed) return;
                disposed = true;renders.delete(teardown);stopReady();
                button.removeEventListener('click',launch);button.remove();
            };
            renders.add(teardown);return teardown;
        }
    });
    return {dispose() {
        installed = false;
        for (const teardown of [...renders]) teardown();
        stopDefinition();stopType();
    }};
}
