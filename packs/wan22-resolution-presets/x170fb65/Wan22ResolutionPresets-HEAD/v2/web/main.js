import { comfy } from "/comfy/api/v2.js";

// =================================================================================
// FINAL CURATED MASTER RESOLUTIONS LIST
//
// This is the definitive list, focused on standard aspect ratios for the best UX.
// It removes niche/legacy resolutions in favor of clarity and ease of use.
//
// =================================================================================
export const MASTER_RESOLUTIONS_LIST = [
    // --- 1:1 Square ---
    { w: 480, h: 480, aspect_ratio: "1:1 Square", rule16: true, rule32: true },
    { w: 512, h: 512, aspect_ratio: "1:1 Square", rule16: true, rule32: true },
    { w: 768, h: 768, aspect_ratio: "1:1 Square", rule16: true, rule32: true },
    { w: 896, h: 896, aspect_ratio: "1:1 Square", rule16: true, rule32: true },
    { w: 1024, h: 1024, aspect_ratio: "1:1 Square", rule16: true, rule32: true },
    { w: 1280, h: 1280, aspect_ratio: "1:1 Square", rule16: true, rule32: true },
    { w: 1440, h: 1440, aspect_ratio: "1:1 Square", rule16: true, rule32: true },

    // --- 16:9 Landscape ---
    { w: 512, h: 288, aspect_ratio: "16:9 Landscape", rule16: true, rule32: true },
    { w: 768, h: 432, aspect_ratio: "16:9 Landscape", rule16: true, rule32: false },
    { w: 896, h: 512, aspect_ratio: "16:9 Landscape", rule16: true, rule32: true }, // Good for 5B
    { w: 1024, h: 576, aspect_ratio: "16:9 Landscape", rule16: true, rule32: true },
    { w: 1280, h: 704, aspect_ratio: "16:9 Landscape", rule16: true, rule32: true }, // Official 5B HD
    { w: 1280, h: 720, aspect_ratio: "16:9 Landscape", rule16: true, rule32: false },// Official 14B HD
    { w: 1344, h: 768, aspect_ratio: "16:9 Landscape", rule16: true, rule32: true },
    { w: 1536, h: 864, aspect_ratio: "16:9 Landscape", rule16: true, rule32: false },
    { w: 1600, h: 896, aspect_ratio: "16:9 Landscape", rule16: true, rule32: true },

    // --- 9:16 Portrait ---
    { w: 288, h: 512, aspect_ratio: "9:16 Portrait", rule16: true, rule32: true },
    { w: 432, h: 768, aspect_ratio: "9:16 Portrait", rule16: true, rule32: false },
    { w: 512, h: 896, aspect_ratio: "9:16 Portrait", rule16: true, rule32: true }, // Good for 5B
    { w: 576, h: 1024, aspect_ratio: "9:16 Portrait", rule16: true, rule32: true },
    { w: 704, h: 1280, aspect_ratio: "9:16 Portrait", rule16: true, rule32: true }, // Official 5B HD
    { w: 720, h: 1280, aspect_ratio: "9:16 Portrait", rule16: true, rule32: false },// Official 14B HD
    { w: 768, h: 1344, aspect_ratio: "9:16 Portrait", rule16: true, rule32: true },
    { w: 864, h: 1536, aspect_ratio: "9:16 Portrait", rule16: true, rule32: false },
    { w: 896, h: 1600, aspect_ratio: "9:16 Portrait", rule16: true, rule32: true },

    // --- 4:3 Landscape ---
    { w: 512, h: 384, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 640, h: 480, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 768, h: 576, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 960, h: 720, aspect_ratio: "4:3 Landscape", rule16: true, rule32: false },
    { w: 1024, h: 768, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 1152, h: 864, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 1280, h: 960, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 1408, h: 1056, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 1536, h: 1152, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },
    { w: 1600, h: 1200, aspect_ratio: "4:3 Landscape", rule16: true, rule32: true },

    // --- 3:4 Portrait ---
    { w: 384, h: 512, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 480, h: 640, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 576, h: 768, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 720, h: 960, aspect_ratio: "3:4 Portrait", rule16: true, rule32: false },
    { w: 768, h: 1024, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 864, h: 1152, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 960, h: 1280, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 1056, h: 1408, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 1152, h: 1536, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },
    { w: 1200, h: 1600, aspect_ratio: "3:4 Portrait", rule16: true, rule32: true },

    // --- 3:2 Landscape ---
    { w: 480, h: 320, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true },
    { w: 720, h: 480, aspect_ratio: "3:2 Landscape", rule16: true, rule32: false },
    { w: 768, h: 512, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true }, // Good for 5B
    { w: 960, h: 640, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true },
    { w: 1152, h: 768, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true },
    { w: 1200, h: 800, aspect_ratio: "3:2 Landscape", rule16: true, rule32: false },
    { w: 1344, h: 896, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true },
    { w: 1440, h: 960, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true },
    { w: 1536, h: 1024, aspect_ratio: "3:2 Landscape", rule16: true, rule32: true },

    // --- 2:3 Portrait ---
    { w: 320, h: 480, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true },
    { w: 480, h: 720, aspect_ratio: "2:3 Portrait", rule16: true, rule32: false },
    { w: 512, h: 768, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true }, // Good for 5B
    { w: 640, h: 960, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true },
    { w: 768, h: 1152, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true },
    { w: 800, h: 1200, aspect_ratio: "2:3 Portrait", rule16: true, rule32: false },
    { w: 896, h: 1344, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true },
    { w: 960, h: 1440, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true },
    { w: 1024, h: 1536, aspect_ratio: "2:3 Portrait", rule16: true, rule32: true },

    // --- 21:9 Cinematic (approx) ---
    { w: 1024, h: 432, aspect_ratio: "21:9 Cinematic", rule16: true, rule32: false },
    { w: 1280, h: 544, aspect_ratio: "21:9 Cinematic", rule16: true, rule32: false },
    { w: 1536, h: 656, aspect_ratio: "21:9 Cinematic", rule16: true, rule32: false },
    { w: 1792, h: 768, aspect_ratio: "21:9 Cinematic", rule16: true, rule32: true },
    { w: 2048, h: 880, aspect_ratio: "21:9 Cinematic", rule16: true, rule32: false },
];

export const VAE_HINTS = {
    "Wan2.2 - 14B Models (I2V/T2V)": "CRITICAL INFO: Use Wan2.1 VAE. Resolutions must be divisible by 16.",
    "Wan2.2 - 5B Model (TI2V)": "CRITICAL INFO: Use Wan2.2 VAE. Resolutions must be divisible by 32.",
};

const ASPECT_ORDER = [
    "16:9 Landscape", "9:16 Portrait", "4:3 Landscape", "3:4 Portrait",
    "3:2 Landscape", "2:3 Portrait", "1:1 Square", "21:9 Cinematic",
];
const states = new WeakMap();

export function filteredOptions(mode, aspectRatio) {
    const is14B = String(mode ?? "").includes("14B");
    const is5B = String(mode ?? "").includes("5B");
    const allowed = (row) => (is14B && row.rule16) || (is5B && row.rule32);
    const validRatios = new Set(MASTER_RESOLUTIONS_LIST.filter(allowed).map((row) => row.aspect_ratio));
    const ratios = ASPECT_ORDER.filter((ratio) => validRatios.has(ratio));
    const selectedAspect = ratios.includes(aspectRatio) ? aspectRatio : (ratios[0] ?? "");
    const resolutions = MASTER_RESOLUTIONS_LIST
        .filter((row) => row.aspect_ratio === selectedAspect && allowed(row))
        .sort((left, right) => left.w * left.h - right.w * right.h)
        .map((row) => `${row.w}x${row.h}`);
    return { ratios, selectedAspect, resolutions };
}

export function preferredResolution(resolutions, current) {
    if (resolutions.includes(current)) return current;
    return resolutions.find((value) =>
        value.endsWith("x720") || value.endsWith("x1280") || value.startsWith("1280x")
    ) ?? resolutions[Math.floor(resolutions.length / 2)] ?? resolutions[0] ?? "";
}

function dispose(node) {
    const state = states.get(node);
    if (!state) return;
    states.delete(node);
    for (const unsubscribe of state.unsubscribers) unsubscribe();
}

export function syncOptions(node) {
    const mode = node.widgets.get("mode");
    const aspect = node.widgets.get("aspect_ratio");
    const resolution = node.widgets.get("resolution");
    if (!mode || !aspect || !resolution) return;

    const selectedMode = String(mode.getValue() ?? "");
    mode.setOption("tooltip", VAE_HINTS[selectedMode] ?? "Select the model family.");
    const options = filteredOptions(selectedMode, String(aspect.getValue() ?? ""));
    aspect.setOption("values", options.ratios);
    if (aspect.getValue() !== options.selectedAspect) aspect.setValue(options.selectedAspect);
    resolution.setOption("values", options.resolutions);
    const next = preferredResolution(options.resolutions, String(resolution.getValue() ?? ""));
    if (resolution.getValue() !== next) resolution.setValue(next);
}

function install(node) {
    dispose(node);
    const unsubscribers = [];
    for (const name of ["mode", "aspect_ratio"]) {
        const widget = node.widgets.get(name);
        if (widget) unsubscribers.push(widget.on("change", () => syncOptions(node)));
    }
    states.set(node, { unsubscribers });
    syncOptions(node);
}

comfy.defs.extend("Wan22ResolutionPresets", (builder) => {
    builder.onCreated((node) => install(node));
    builder.onConfigured((node) => syncOptions(node));
    builder.onRemoved((node) => dispose(node));
});
