import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend('LTXDirectorGuide', (builder) => {
    builder.hideWidget('retake_mode');
    builder.onCreated((node) => node.widgets.get('retake_mode')?.setHidden(true));
    builder.onConfigured((node) => node.widgets.get('retake_mode')?.setHidden(true));
});
