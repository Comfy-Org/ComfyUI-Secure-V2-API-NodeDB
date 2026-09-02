import { comfy } from '/comfy/api/v2.js';

async function open_picker(node) {
    // Segment previews were cached in a process-global server table. SEGS are
    // now execution-scoped refs, so the text `picks` widget remains the secure
    // selection interface until core exposes a typed preview primitive.
    comfy.commands.notify({
        severity: 'warn',
        summary: 'SEGS picker unavailable',
        detail: 'Enter segment numbers in the picks widget (for example: 1, 3-5).',
        life: 5000,
    });
}


comfy.defs.extend("ImpactSEGSPicker", (b) => {
    b.onCreated((node) => {
        const pick = node.widgets.add({ type: "button", name: "pick", value: "image" });
        pick.on('activate', () => {
            open_picker(node);
        });
    });
});
