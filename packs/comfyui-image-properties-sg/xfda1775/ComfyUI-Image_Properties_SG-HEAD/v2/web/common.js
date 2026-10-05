import { comfy } from "/comfy/api/v2.js";

const states = new WeakMap();
const STANDARD_RATIOS = [
  [1.0, "1:1"], [1.25, "5:4"], [1.33333, "4:3"], [1.5, "3:2"],
  [1.6, "16:10"], [1.66667, "5:3"], [1.77778, "16:9"],
  [1.88889, "17:9"], [2.0, "2:1"], [2.33333, "21:9"],
  [2.35, "2.35:1"], [2.39, "2.39:1"], [2.4, "12:5"],
];

function safeLines(value) {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 16).map((line) => String(line ?? "").slice(0, 2048));
}

function render(state) {
  if (!state.readout) return;
  state.readout.replaceChildren();
  for (const line of state.lines) {
    const row = state.readout.ownerDocument.createElement("div");
    row.className = line ? "image-properties-row" : "image-properties-spacer";
    row.textContent = line;
    state.readout.append(row);
  }
  state.mount?.setHeight(Math.max(22, 10 + state.lines.length * 18));
}

function applyLines(state, value, persist = true) {
  state.lines = safeLines(value);
  if (persist) state.node.setProperty("imageParamsText", state.lines);
  render(state);
}

function dispose(node) {
  const state = states.get(node);
  if (!state || state.disposed) return;
  state.disposed = true;
  states.delete(node);
  for (const unsubscribe of state.unsubscribers.splice(0)) unsubscribe();
  if (state.pendingImage) {
    state.pendingImage.onload = null;
    state.pendingImage.onerror = null;
    state.pendingImage.src = "";
    state.pendingImage = undefined;
  }
}

function closestRatio(decimal) {
  let best;
  let difference = Infinity;
  for (const [value, label] of STANDARD_RATIOS) {
    const candidate = Math.abs(value - decimal);
    if (candidate < difference) {
      difference = candidate;
      best = label;
    }
  }
  return difference <= 0.05 ? best : undefined;
}

function gcd(left, right) {
  while (right) [left, right] = [right, left % right];
  return left;
}

function previewLines(width, height) {
  const divisor = gcd(width, height);
  const widthRatio = width / divisor;
  const heightRatio = height / divisor;
  const decimal = width / height;
  const closest = closestRatio(decimal);
  const ratio = closest && closest !== `${widthRatio}:${heightRatio}`
    ? `Ratio: ${widthRatio}:${heightRatio} or ${decimal.toFixed(2)}:1 or ~${closest}`
    : `Ratio: ${widthRatio}:${heightRatio} or ${decimal.toFixed(2)}:1`;
  return [
    `${width}x${height} | ${(width * height / 1_000_000).toFixed(2)}MP`,
    ratio,
    `Tensor Size: ${(width * height * 3 * 4 / (1024 * 1024)).toFixed(2)}MB`,
  ];
}

function analyzeSelectedImage(state, value) {
  if (state.pendingImage) {
    state.pendingImage.onload = null;
    state.pendingImage.onerror = null;
    state.pendingImage.src = "";
  }
  if (typeof value !== "string" || !value) return;
  const normalized = value.replaceAll("\\", "/");
  const parts = normalized.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return;
  const filename = parts.pop();
  const subfolder = parts.join("/");
  const image = state.readout.ownerDocument.createElement("img");
  state.pendingImage = image;
  image.onload = () => {
    if (state.disposed || state.pendingImage !== image) return;
    applyLines(state, previewLines(image.naturalWidth, image.naturalHeight));
    state.pendingImage = undefined;
  };
  image.onerror = () => {
    if (state.pendingImage === image) state.pendingImage = undefined;
  };
  image.src = comfy.backend.assetUrl(
    `/view?filename=${encodeURIComponent(filename)}&type=input&subfolder=${encodeURIComponent(subfolder)}`,
  );
}

export function extendPropertiesNode(
  nodeType,
  { minWidth, liveImage = false, configure } = {},
) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => {
      dispose(node);
      const state = {
        node,
        lines: safeLines(node.getProperty("imageParamsText")),
        mount: undefined,
        readout: undefined,
        pendingImage: undefined,
        unsubscribers: [],
        disposed: false,
      };
      states.set(node, state);
      node.setSizeConstraints({ minWidth, autoHeight: true });
      state.mount = node.widgets.mount({
        name: "image_properties_readout",
        height: Math.max(22, 10 + state.lines.length * 18),
        serialize: false,
        sendToPrompt: false,
        render(container) {
          const style = container.ownerDocument.createElement("style");
          style.textContent = [
            ".image-properties-readout{box-sizing:border-box;padding:5px 8px;color:#ccc;",
            "font:12px/18px ui-monospace,SFMono-Regular,Consolas,monospace;",
            "white-space:pre-wrap;overflow-wrap:anywhere;pointer-events:none}",
            ".image-properties-spacer{height:9px}",
          ].join("");
          const readout = container.ownerDocument.createElement("div");
          readout.className = "image-properties-readout";
          container.replaceChildren(style, readout);
          state.readout = readout;
          render(state);
          if (liveImage) {
            analyzeSelectedImage(state, node.widgets.get("image")?.getValue());
          }
        },
        destroy() {
          dispose(node);
        },
      });
      if (liveImage) {
        const widget = node.widgets.get("image");
        const unsubscribe = widget?.on("change", (value) => analyzeSelectedImage(state, value));
        if (typeof unsubscribe === "function") state.unsubscribers.push(unsubscribe);
      }
      configure?.(node, state);
    });
    builder.onConfigured((node) => {
      const state = states.get(node);
      if (!state) return;
      applyLines(state, node.getProperty("imageParamsText"), false);
      configure?.(node, state);
    });
    builder.onExecuted((node, result) => {
      const state = states.get(node);
      if (state) applyLines(state, result?.text);
    });
    builder.onRemoved((node) => dispose(node));
  });
}

export function syncSaveWidgets(node, state) {
  const map = {
    "PNG (lossless, larger files)": ["png_compress_level"],
    "JPEG (lossy, smaller files)": [
      "jpeg_quality", "jpeg_optimize", "jpeg_subsampling",
    ],
    "WEBP (modern, good compression)": [
      "webp_quality", "webp_method", "webp_lossless",
    ],
    "BMP (uncompressed, largest)": [],
    "TIFF (flexible, lossless, limited support)": [
      "tiff_compression", "tiff_jpeg_quality",
    ],
  };
  const format = node.widgets.get("format");
  const apply = () => {
    const active = new Set(map[String(format?.getValue())] ?? []);
    for (const name of [
      "png_compress_level", "jpeg_quality", "jpeg_optimize",
      "jpeg_subsampling", "webp_quality", "webp_method", "webp_lossless",
      "tiff_compression", "tiff_jpeg_quality",
    ]) {
      node.widgets.get(name)?.setHidden(!active.has(name));
    }
  };
  if (!state.formatInstalled) {
    const unsubscribe = format?.on("change", apply);
    if (typeof unsubscribe === "function") state.unsubscribers.push(unsubscribe);
    state.formatInstalled = true;
  }
  apply();
}
