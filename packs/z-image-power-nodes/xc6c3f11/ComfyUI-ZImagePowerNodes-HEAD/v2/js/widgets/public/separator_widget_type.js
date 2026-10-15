/** Original separator geometry and serialization through public widget APIs. */
export function separatorGeometry(width,options) {
    const mode = options.mode || 'spacer';
    const height = options.height || 20;
    return {mode,height,visible:mode !== 'spacer',left:Math.trunc(10),right:Math.trunc(width-10),
        centerY:Math.trunc(height/2+0.5),color:options.color || 'var(--comfy-native-node-box-color, currentColor)',
        thickness:options.thickness || (mode === 'dotted' ? 2 : mode === 'bold' ? 6 : 1),
        dash:mode === 'dotted' ? [2,2] : []};
}
export function installSeparatorWidgetType(comfy) {
    const renders = new Set();
    const active = [];
    let installed = true;
    const stopDefinition = comfy.defs.extend(def => def.type.endsWith(' //ZImagePowerNodes'), builder => {
        builder.onCreated(node => queueMicrotask(() => {
            if (!installed || node.isDeleted) return;
            const order = node.widgets.names();
            for (const widget of node.widgets.all()) {
                if (widget.widgetType !== 'ZIPN_SEPARATOR') continue;
                if (active.some(item => item.name === widget.name && comfy.sameEntity(item.node,node))) continue;
                const options = {};
                const old = widget.getOptions() ?? {};
                for (const key of ['socketless','mode','color','height','thickness']) {
                    if (key in old) options[key] = old[key];
                }
                const name = widget.name;
                node.widgets.remove(name);
                node.widgets.add({name,type:'ZIPN_SEPARATOR',value:null,options});
            }
            node.widgets.reorder(order);
        }));
        builder.onConfigured(node => {
            for (const item of active) if (comfy.sameEntity(item.node,node)) item.refresh();
        });
    });
    const stopType = comfy.defs.defineWidgetType('ZIPN_SEPARATOR', {
        defaultValue:null,serialize:true,height:20,
        render(container,_value,name,context) {
            const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
            const line = document.createElementNS('http://www.w3.org/2000/svg','line');
            svg.append(line);
            svg.style.width = '100%';
            svg.style.display = 'block';
            svg.setAttribute('aria-hidden','true');
            line.setAttribute('stroke-linecap','butt');
            container.append(svg);
            let disposed = false;
            let owner = null;
            let drawingWidth = null;
            function refresh() {
                if (disposed) return;
                const options = context.getOptions();
                // SVG coordinates use local layout units. A viewport rect
                // includes graph zoom and remains reserved for pointer math.
                const shape = separatorGeometry(drawingWidth ?? 0,options);
                svg.style.height = `${shape.height}px`;
                svg.setAttribute('height',String(shape.height));
                line.setAttribute('x1',String(shape.left));
                line.setAttribute('x2',String(shape.right));
                line.setAttribute('y1',String(shape.centerY));
                line.setAttribute('y2',String(shape.centerY));
                line.setAttribute('stroke',String(shape.color));
                line.setAttribute('stroke-width',String(shape.thickness));
                line.setAttribute('stroke-dasharray',shape.dash.join(' '));
                line.style.display = shape.visible && drawingWidth !== null ? '' : 'none';
                if (owner) owner.widgets.get(name)?.setHeight(shape.height);
            }
            const observer = new ResizeObserver(entries => {
                const entry = entries.find(item => item.target === container);
                if (!entry || !Number.isFinite(entry.contentRect.width)) return;
                drawingWidth = entry.contentRect.width;
                refresh();
            });
            observer.observe(container);
            const stopReady = context.onNodeReady(node => {
                owner = node;
                const widget = node.widgets.get(name);
                if (!widget) return;
                widget.setOption('socketless',true);
                widget.setOption('margin',0);
                const stopSerialize = widget.on('beforeSerialize',event => event.setSerializedValue(null));
                const item = {node,name,refresh};
                active.push(item);
                refresh();
                return () => {
                    stopSerialize();
                    const index = active.indexOf(item);
                    if (index >= 0) active.splice(index,1);
                    if (owner === node) owner = null;
                };
            });
            refresh();
            const teardown = () => {
                if (disposed) return;
                disposed = true;
                renders.delete(teardown);
                stopReady();observer.disconnect();svg.remove();
            };
            renders.add(teardown);
            return teardown;
        }
    });
    return {dispose() {
        installed = false;
        for (const teardown of [...renders]) teardown();
        stopDefinition();stopType();
    }};
}
