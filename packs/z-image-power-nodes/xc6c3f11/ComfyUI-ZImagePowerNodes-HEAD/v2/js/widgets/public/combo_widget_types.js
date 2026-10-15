/** Public registration for the two original user-input combo widget types. */
import { UserInputComboController } from './user_input_combo_controller.js';

export function installUserInputComboWidgetTypes(comfy) {
    const active = [];
    const stops = [];
    const renders = new Set();
    const types = ['ZIPN_STYLE', 'ZIPN_PALETTE'];
    let installed = true;
    function sync(node) {
        for (const record of active) {
            if (!comfy.sameEntity(record.node, node)) continue;
            record.controller.syncSource();
            record.refresh();
        }
    }
    stops.push(comfy.defs.extend(def => def.type.endsWith(' //ZImagePowerNodes'), builder => {
        builder.onCreated(node => queueMicrotask(() => {
            if (!installed || node.isDeleted) return;
            // Core disposes a DOM widget's renderer when its node is removed.
            // Reinserted nodes need fresh declared widgets, at the same names
            // and positions, rather than reviving a disposed DOM context.
            const order = node.widgets.names();
            for (const widget of node.widgets.all()) {
                if (!types.includes(widget.widgetType)) continue;
                if (active.some(record => record.name === widget.name && comfy.sameEntity(record.node, node))) continue;
                const old = widget.getOptions() ?? {};
                const options = {};
                for (const key of ['user_input', 'item_marker', 'include_none', 'values', 'options']) {
                    if (key in old) options[key] = old[key];
                }
                const definition = {name:widget.name,type:widget.widgetType,value:widget.getValue(),options};
                node.widgets.remove(widget.name);
                node.widgets.add(definition);
            }
            node.widgets.reorder(order);
            sync(node);
        }));
        builder.onConnectionsChanged(node => sync(node));
        builder.onConfigured(node => {
            for (const record of active) {
                if (comfy.sameEntity(record.node, node)) record.controller.lastInputText = null;
            }
            sync(node);
        });
    }));
    for (const type of types) {
        stops.push(comfy.defs.defineWidgetType(type, {
            defaultValue: '',
            serialize: true,
            render(container, value, name, context) {
                const select = document.createElement('select');
                select.setAttribute('aria-label', name);
                select.style.width = '100%';
                container.append(select);
                let disposed = false;
                let readyRecord = null;
                function refresh() {
                    if (disposed) return;
                    const values = context.getOptions().values;
                    const options = Array.isArray(values) ? values : [];
                    select.replaceChildren(...options.map(item => {
                        const option = document.createElement('option');
                        option.value = String(item);
                        option.textContent = String(item);
                        return option;
                    }));
                    select.value = String(value.get() ?? '');
                }
                const change = () => value.set(select.value);
                select.addEventListener('change', change);
                // Native combo options are read when the picker opens, even
                // when a still-valid selection means no value-change event.
                select.addEventListener('pointerdown', refresh);
                select.addEventListener('focus', refresh);
                const stopValue = value.onChange(refresh);
                const stopReady = context.onNodeReady(node => {
                    const widget = node.widgets.get(name);
                    if (!widget) return;
                    const kwargs = context.getOptions();
                    const config = {user_input:'user_input',item_marker:'>>>',include_none:false,values:[],...kwargs};
                    // The original passes config.options, rather than values,
                    // to its controller. Preserve that original distinction.
                    const controller = new UserInputComboController(widget, node, config.user_input,
                        config.options, config.include_none ? 'none' : '', config.item_marker, comfy.graph);
                    controller.onOptionsChanged = refresh;
                    const record = {node,name,controller,refresh};
                    readyRecord = record;
                    active.push(record);
                    // Node insertion can precede restored connections. The
                    // native first periodic check also follows construction.
                    queueMicrotask(() => {
                        if (disposed || readyRecord !== record) return;
                        controller.checkAndSyncOptions();
                        refresh();
                    });
                    return () => {
                        controller.dispose();
                        const index = active.indexOf(record);
                        if (index >= 0) active.splice(index, 1);
                        if (readyRecord === record) readyRecord = null;
                    };
                });
                refresh();
                const teardown = () => {
                    if (disposed) return;
                    disposed = true;
                    renders.delete(teardown);
                    stopReady();
                    stopValue();
                    select.removeEventListener('change', change);
                    select.removeEventListener('pointerdown', refresh);
                    select.removeEventListener('focus', refresh);
                    select.remove();
                };
                renders.add(teardown);
                return teardown;
            }
        }));
    }
    return {dispose() {
        installed = false;
        for (const teardown of [...renders]) teardown();
        for (const record of active.splice(0)) record.controller.dispose();
        for (const stop of stops.splice(0)) stop();
    }};
}
