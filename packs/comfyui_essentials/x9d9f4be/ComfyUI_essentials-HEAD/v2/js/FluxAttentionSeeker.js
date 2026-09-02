import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend("FluxAttentionSeeker+", (b) => {
    b.onCreated((node) => {
        node.widgets.add({ type: "button", name: "RESET ALL", value: null }).on("activate", () => {
            node.widgets.all().forEach(w => {
                if (w.widgetType === "slider") {
                    w.setValue(1.0);
                }
            });
        });

        node.widgets.add({ type: "button", name: "ZERO ALL", value: null }).on("activate", () => {
            node.widgets.all().forEach(w => {
                if (w.widgetType === "slider") {
                    w.setValue(0.0);
                }
            });
        });

        node.widgets.add({ type: "button", name: "REPEAT FIRST", value: null }).on("activate", () => {
            var clip_value = undefined;
            var t5_value = undefined;
            node.widgets.all().forEach(w => {
                if (w.name.startsWith('clip_l')) {
                    if (clip_value === undefined) {
                        clip_value = w.getValue();
                    }
                    w.setValue(clip_value);
                } else if (w.name.startsWith('t5')) {
                    if (t5_value === undefined) {
                        t5_value = w.getValue();
                    }
                    w.setValue(t5_value);
                }
            });
        });
    });
});

comfy.defs.extend("SD3AttentionSeekerLG+", (b) => {
    b.onCreated((node) => {
        node.widgets.add({ type: "button", name: "RESET L", value: null }).on("activate", () => {
            node.widgets.all().forEach(w => {
                if (w.widgetType === "slider" && w.name.startsWith('clip_l')) {
                    w.setValue(1.0);
                }
            });
        });
        node.widgets.add({ type: "button", name: "RESET G", value: null }).on("activate", () => {
            node.widgets.all().forEach(w => {
                if (w.widgetType === "slider" && w.name.startsWith('clip_g')) {
                    w.setValue(1.0);
                }
            });
        });

        node.widgets.add({ type: "button", name: "REPEAT FIRST", value: null }).on("activate", () => {
            var clip_l_value = undefined;
            var clip_g_value = undefined;
            node.widgets.all().forEach(w => {
                if (w.name.startsWith('clip_l')) {
                    if (clip_l_value === undefined) {
                        clip_l_value = w.getValue();
                    }
                    w.setValue(clip_l_value);
                } else if (w.name.startsWith('clip_g')) {
                    if (clip_g_value === undefined) {
                        clip_g_value = w.getValue();
                    }
                    w.setValue(clip_g_value);
                }
            });
        });
    });
});

comfy.defs.extend("SD3AttentionSeekerT5+", (b) => {
    b.onCreated((node) => {
        node.widgets.add({ type: "button", name: "RESET ALL", value: null }).on("activate", () => {
            node.widgets.all().forEach(w => {
                if (w.widgetType === "slider") {
                    w.setValue(1.0);
                }
            });
        });

        node.widgets.add({ type: "button", name: "REPEAT FIRST", value: null }).on("activate", () => {
            var t5_value = undefined;
            node.widgets.all().forEach(w => {
                if (w.name.startsWith('t5')) {
                    if (t5_value === undefined) {
                        t5_value = w.getValue();
                    }
                    w.setValue(t5_value);
                }
            });
        });
    });
});
