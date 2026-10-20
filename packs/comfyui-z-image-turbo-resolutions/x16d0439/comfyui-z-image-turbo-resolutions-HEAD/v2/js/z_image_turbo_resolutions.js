import { comfy } from "/comfy/api/v2.js";

const RESOLUTIONS = {
    "1024": [
        "1024x1024 (1:1)",
        "1152x896 (9:7)",
        "896x1152 (7:9)",
        "1152x864 (4:3)",
        "864x1152 (3:4)",
        "1248x832 (3:2)",
        "832x1248 (2:3)",
        "1280x720 (16:9)",
        "720x1280 (9:16)",
        "1344x576 (21:9)",
        "576x1344 (9:21)"
    ],
    "1280": [
        "1280x1280 (1:1)",
        "1440x1120 (9:7)",
        "1120x1440 (7:9)",
        "1472x1104 (4:3)",
        "1104x1472 (3:4)",
        "1536x1024 (3:2)",
        "1024x1536 (2:3)",
        "1536x864 (16:9)",
        "864x1536 (9:16)",
        "1680x720 (21:9)",
        "720x1680 (9:21)"
    ],
    "1536": [
        "1536x1536 (1:1)",
        "1728x1344 (9:7)",
        "1344x1728 (7:9)",
        "1728x1296 (4:3)",
        "1296x1728 (3:4)",
        "1872x1248 (3:2)",
        "1248x1872 (2:3)",
        "2048x1152 (16:9)",
        "1152x2048 (9:16)",
        "2016x864 (21:9)",
        "864x2016 (9:21)"
    ]
};

comfy.defs.extend("ZImageTurboResolutions", (builder) => {
    if (builder.def.category !== "image/resolution") return;
    builder.onCreated((node) => {
        const resolutionWidget = node.widgets.get("resolution");
        const ratioWidget = node.widgets.get("ratio");
        if (!resolutionWidget || !ratioWidget) return;

        const updateRatioOptions = (resolution) => {
            const ratios = RESOLUTIONS[resolution] || [];
            ratioWidget.setOption("values", ratios);
            if (!ratios.includes(ratioWidget.getValue())) {
                ratioWidget.setValue(ratios[0]);
            }
        };

        const stop = resolutionWidget.on("change", updateRatioOptions);
        resolutionWidget.on("removed", stop);
        updateRatioOptions(resolutionWidget.getValue());
    });
});
