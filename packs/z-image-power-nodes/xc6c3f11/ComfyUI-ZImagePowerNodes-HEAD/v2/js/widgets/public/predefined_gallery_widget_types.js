import { GallerySelectionController } from './gallery_selection_controller.js';
const DEFAULT_GALLERY_CACHE_BUSTER = Math.floor(Date.now() / 3600000);

/** Public widget registration; catalogue/delegate/dialog implementations belong to the pack. */
export function installPredefinedGalleryWidgetTypes(comfy, sources) {
    const types = ['ZIPN_PREDEFINED_STYLE','ZIPN_PREDEFINED_PALETTE'];
    const active = [];
    const renders = new Set();
    const restored = [];
    let installed = true;
    const stopDefinition = comfy.defs.extend(def => def.type.endsWith(' //ZImagePowerNodes'), builder => {
        builder.onConfigured((node,data) => {
            const matching = active.filter(item => comfy.sameEntity(item.node,node));
            if (matching.length) {
                for (const item of matching) item.restore(data);
            } else {
                const snapshot = structuredClone(data);
                const existing = restored.find(item => comfy.sameEntity(item.node,node));
                if (existing) existing.data = snapshot;
                else restored.push({node,data:snapshot});
            }
        });
        builder.onCreated(node => queueMicrotask(() => {
            if (!installed || node.isDeleted) return;
            const order = node.widgets.names();
            for (const widget of node.widgets.all()) {
                if (!types.includes(widget.widgetType)) continue;
                if (active.some(item => item.name === widget.name && comfy.sameEntity(item.node,node))) continue;
                const options = {};
                const previous = widget.getOptions() ?? {};
                for (const key of ['height','allow_variants','endpoint','images_url','dialog','cache_buster','zipnNativeValue']) {
                    if (key in previous) options[key] = previous[key];
                }
                const definition = {name:widget.name,type:widget.widgetType,value:widget.getValue(),options};
                node.widgets.remove(widget.name);
                node.widgets.add(definition);
            }
            node.widgets.reorder(order);
            const pending = restored.findIndex(item => comfy.sameEntity(item.node,node));
            if (pending >= 0) restored.splice(pending,1);
        }));
    });
    const stops = types.map(type => comfy.defs.defineWidgetType(type, {
        defaultValue:null,serialize:true,height:40,
        render(container,_value,name,context) {
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;width:100%;padding:0 14px;box-sizing:border-box';
            const previous = document.createElement('button');
            const next = document.createElement('button');
            const choice = document.createElement('button');
            const label = document.createElement('span');
            const caption = document.createElement('span');
            const thumbnail = document.createElement('span');
            previous.textContent = '◀';next.textContent = '▶';label.textContent = name;
            previous.setAttribute('aria-label','Previous '+name);
            next.setAttribute('aria-label','Next '+name);
            choice.setAttribute('aria-label','Select '+name);
            previous.style.width = next.style.width = '24px';
            choice.style.cssText = 'display:flex;align-items:center;justify-content:space-between;flex:1;min-width:0';
            caption.style.whiteSpace = 'pre-line';
            choice.append(label,caption,thumbnail);row.append(previous,choice,next);container.append(row);
            let record = null;
            let disposed = false;
            const stopReady = context.onNodeReady(node => {
                const widget = node.widgets.get(name);
                if (!widget) return;
                const kwargs = context.getOptions();
                const options = {height:40,allow_variants:false,cache_buster:DEFAULT_GALLERY_CACHE_BUSTER,endpoint:'',dialog:{},...kwargs};
                const style = type === 'ZIPN_PREDEFINED_STYLE';
                const delegate = style ? sources.styleDelegate(options.endpoint,options.images_url ?? '')
                    : sources.paletteDelegate(options.endpoint);
                // Original GalleryWidget owns a nullable value before its
                // asynchronous catalogue arrives. Keep that component state
                // and serialize it through the published destination hook.
                const state = {current:'zipnNativeValue' in kwargs ? kwargs.zipnNativeValue : kwargs.default};
                const refresh = () => {
                    if (disposed || !record) return;
                    const controller = record.controller;
                    const index = controller.selectedIndex;
                    const item = controller.itemArray[index];
                    const text = delegate.getItemText(item,controller.value,options);
                    caption.textContent = typeof text === 'string' ? text.split('\n').slice(0,2).join('\n') : text.slice(0,2).join('\n');
                    if (record.previewItem !== item || record.previewValue !== controller.value) {
                        record.stopThumbnail?.();
                        record.stopThumbnail = delegate.mountThumbnail?.(thumbnail,item,controller.value,options);
                        record.previewItem = item;record.previewValue = controller.value;
                    }
                    previous.disabled = !(index > 0);
                    next.disabled = !(index < controller.itemArray.length - 1);
                    widget.setHeight(options.height);
                    container.style.height = `${options.height}px`;
                    row.style.height = `${options.height}px`;
                    widget.setOption('zipnNativeValue',state.current);
                };
                const controller = new GallerySelectionController(widget,options,delegate,refresh,state);
                widget.setOption('margin',0);
                const restore = data => {
                    const values = data.widgets_values;
                    const index = node.widgets.names().indexOf(name);
                    if (Array.isArray(values) && index >= 0 && index < values.length) {
                        state.current = values[index];
                        // Core already wrote this restored value. The raw DOM
                        // cell's null coalescing must not erase its meaning.
                    }
                    refresh();
                };
                const item = {node,name,controller,restore,refresh,state,options};
                record = item;active.push(item);
                const stopChange = widget.on('change',value => {state.current=value;refresh();});
                const stopSerialize = widget.on('beforeSerialize',event => event.setSerializedValue(state.current));
                const old = restored.find(saved => comfy.sameEntity(saved.node,node));
                if (old && !('zipnNativeValue' in kwargs)) restore(old.data);
                refresh();
                controller.ready.then(() => {if (!disposed && record === item) refresh();});
                return () => {
                    controller.dispose();item.stopThumbnail?.();stopChange();stopSerialize();
                    const index = active.indexOf(item);if (index >= 0) active.splice(index,1);
                    if (record === item) record = null;
                };
            });
            const left = () => {if (record) record.controller.selectedIndex -= 1;};
            const right = () => {if (record) record.controller.selectedIndex += 1;};
            const launch = () => {
                if (!record) return;
                const {controller,options} = record;
                const style = type === 'ZIPN_PREDEFINED_STYLE';
                const dialogConfig = {title:style ? 'Visual Styles' : 'Color Palettes',
                    size:style ? 'default' : 'small',view_mode:style ? 'grid' : 'list',
                    icon:style ? 'mdi.mdi-image-multiple-outline' : 'mdi.mdi-palette-outline',
                    endpoint:options.endpoint,...(style ? {images_url:options.images_url ?? ''} : {}),...options.dialog};
                sources.launchDialog(style ? 'style' : 'palette',dialogConfig,controller.value,selected => {
                    if (!disposed && record?.controller === controller) controller.forceUpdate(selected);
                });
            };
            previous.addEventListener('click',left);next.addEventListener('click',right);choice.addEventListener('click',launch);
            const teardown = () => {
                if (disposed) return;
                disposed = true;renders.delete(teardown);stopReady();
                previous.removeEventListener('click',left);next.removeEventListener('click',right);
                choice.removeEventListener('click',launch);row.remove();
            };
            renders.add(teardown);return teardown;
        }
    }));
    return {dispose() {
        installed = false;
        for (const teardown of [...renders]) teardown();
        restored.splice(0);stopDefinition();for (const stop of stops) stop();
    }};
}
