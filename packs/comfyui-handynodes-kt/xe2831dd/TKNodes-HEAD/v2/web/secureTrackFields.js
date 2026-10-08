// Pack-owned controls; original backend widgets remain the serialized authority.
export function mountTrackRow(node, name, fields, { speaker = false } = {}) {
    const available = fields.map(([label, key]) => [label, node.widgets.get(key)])
        .filter(([, widget]) => widget);
    if (!available.length) return;
    for (const [, widget] of available) widget.setHidden(true);
    const disposers = [];
    let destroyed = false;
    return node.widgets.mount({
        name, height: 28, serialize: false, sendToPrompt: false,
        render(container) {
            const doc = container.ownerDocument;
            container.style.cssText = 'display:flex;gap:6px;align-items:center;box-sizing:border-box;padding:1px 0;width:100%';
            for (const [label, widget] of available) {
                const wrap = doc.createElement('div');
                wrap.style.cssText = 'flex:1;display:flex;align-items:center;gap:4px;background:#2a2a2a;border:1px solid #444;border-radius:4px;padding:3px 6px;min-width:0';
                const lbl = doc.createElement('span');
                lbl.textContent = label;
                lbl.style.cssText = 'font-size:10px;color:#aaa;white-space:nowrap;flex-shrink:0';
                const input = doc.createElement('input');
                input.type = 'number';
                input.step = '0.1';
                input.value = widget.getValue() ?? 0;
                input.style.cssText = 'flex:1;min-width:0;background:transparent;border:none;color:#fff;font-size:12px;text-align:right;outline:none';
                if (speaker) { input.min = '0'; input.max = '300'; }
                const commit = () => {
                    if (destroyed) return;
                    const value = parseFloat(input.value) || 0;
                    if (!Number.isFinite(value)) throw new RangeError('track value must be finite');
                    widget.setValue(value);
                };
                input.addEventListener('input', commit);
                disposers.push(() => input.removeEventListener('input', commit));
                disposers.push(widget.on('change', value => { input.value = value ?? 0; }));
                wrap.append(lbl, input);
                container.append(wrap);
            }
        },
        destroy() {
            if (destroyed) return;
            destroyed = true;
            for (const dispose of disposers.splice(0)) dispose();
        },
    });
}
// Active confined frontend graph; archival diagnostics are outside WEB_DIRECTORY.
