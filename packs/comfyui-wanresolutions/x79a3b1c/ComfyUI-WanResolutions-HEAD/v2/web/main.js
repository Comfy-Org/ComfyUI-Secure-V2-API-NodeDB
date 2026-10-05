import { comfy } from "/comfy/api/v2.js";


const CONFIGS = {
  WanResolutions: {
    fallback: "1:1",
    official: [[1280, 720], [720, 1280], [832, 480], [480, 832]],
    presets: {
      "1:1": [[480, 480, "Fast Draft"], [640, 640, "Preview"], [832, 832, "High Detail"], [960, 960, "Wan 2.2 Native"]],
      "2:3": [[384, 576, "Fast Draft"], [512, 768, "Preview"], [672, 1008, "High Detail"], [768, 1168, "Wan 2.2 Native"]],
      "3:2": [[576, 384, "Fast Draft"], [768, 512, "Preview"], [1008, 672, "High Detail"], [1168, 768, "Wan 2.2 Native"]],
      "3:4": [[432, 576, "Fast Draft"], [576, 768, "Preview"], [720, 960, "High Detail"], [816, 1104, "Wan 2.2 Native"]],
      "4:3": [[576, 432, "Fast Draft"], [768, 576, "Preview"], [960, 720, "High Detail"], [1104, 816, "Wan 2.2 Native"]],
      "9:16": [[352, 624, "Fast Draft"], [480, 848, "Preview"], [624, 1104, "High Detail"], [720, 1280, "Wan 2.2 Native"]],
      "16:9": [[624, 352, "Fast Draft"], [848, 480, "Preview"], [1104, 624, "High Detail"], [1280, 720, "Wan 2.2 Native"]],
    },
  },
  MiniMaxH3Resolutions: {
    fallback: "16:9",
    presets: {
      "1:1": [[512, 512, "Draft (0.25 MP)"], [640, 640, "Preview (0.40 MP)"], [768, 768, "1K (0.56 MP)"], [960, 960, "720P Class (0.90 MP)"], [1024, 1024, "High Detail (1.00 MP)"], [1152, 1152, "1.5K (1.27 MP)"], [1440, 1440, "1080P Class (2.00 MP)"], [1536, 1536, "2K (2.25 MP)"]],
      "3:4": [[448, 576, "Draft (0.25 MP)"], [576, 736, "Preview (0.40 MP)"], [672, 896, "1K (0.56 MP)"], [832, 1120, "720P Class (0.90 MP)"], [864, 1184, "High Detail (1.00 MP)"], [992, 1344, "1.5K (1.27 MP)"], [1248, 1664, "1080P Class (2.00 MP)"], [1344, 1760, "2K (2.25 MP)"]],
      "4:3": [[576, 448, "Draft (0.25 MP)"], [736, 576, "Preview (0.40 MP)"], [896, 672, "1K (0.56 MP)"], [1120, 832, "720P Class (0.90 MP)"], [1184, 864, "High Detail (1.00 MP)"], [1344, 992, "1.5K (1.27 MP)"], [1664, 1248, "1080P Class (2.00 MP)"], [1760, 1344, "2K (2.25 MP)"]],
      "9:16": [[384, 672, "Draft (0.25 MP)"], [480, 864, "Preview (0.40 MP)"], [576, 1024, "1K (0.56 MP)"], [736, 1280, "720P Class (0.90 MP)"], [768, 1344, "High Detail (1.00 MP)"], [864, 1536, "1.5K (1.27 MP)"], [1088, 1920, "1080P Class (2.00 MP)"], [1152, 2048, "2K (2.25 MP)"]],
      "16:9": [[672, 384, "Draft (0.25 MP)"], [864, 480, "Preview (0.40 MP)"], [1024, 576, "1K (0.56 MP)"], [1280, 736, "720P Class (0.90 MP)"], [1344, 768, "High Detail (1.00 MP)"], [1536, 864, "1.5K (1.27 MP)"], [1920, 1088, "1080P Class (2.00 MP)"], [2048, 1152, "2K (2.25 MP)"]],
      "21:9": [[768, 320, "Draft (0.25 MP)"], [992, 416, "Preview (0.40 MP)"], [1184, 512, "1K (0.56 MP)"], [1472, 640, "720P Class (0.90 MP)"], [1536, 672, "High Detail (1.00 MP)"], [1760, 768, "1.5K (1.27 MP)"], [2208, 960, "1080P Class (2.00 MP)"], [2336, 992, "2K (2.25 MP)"]],
    },
  },
  LTXResolutions: {
    fallback: "1:1",
    presets: {
      "1:1": [[320, 320, "Stage 1 Preview"], [640, 640, "Fast Iteration"], [768, 768, "Balanced"], [960, 960, "HD Output"], [1184, 1184, "High Detail"], [1440, 1440, "Full HD Output"]],
      "2:3": [[256, 384, "Stage 1 Preview"], [512, 768, "Fast Iteration"], [640, 960, "Balanced"], [768, 1152, "HD Output"], [960, 1440, "High Detail"], [1152, 1728, "Full HD Output"]],
      "3:2": [[384, 256, "Stage 1 Preview"], [768, 512, "Fast Iteration"], [960, 640, "Balanced"], [1152, 768, "HD Output"], [1440, 960, "High Detail"], [1728, 1152, "Full HD Output"]],
      "3:4": [[256, 352, "Stage 1 Preview"], [512, 704, "Fast Iteration"], [640, 864, "Balanced"], [864, 1152, "HD Output"], [1056, 1408, "High Detail"], [1248, 1664, "Full HD Output"]],
      "4:3": [[352, 256, "Stage 1 Preview"], [704, 512, "Fast Iteration"], [864, 640, "Balanced"], [1152, 864, "HD Output"], [1408, 1056, "High Detail"], [1664, 1248, "Full HD Output"]],
      "9:16": [[288, 512, "Stage 1 Preview"], [544, 960, "Fast Iteration"], [672, 1184, "Balanced"], [736, 1312, "HD Output"], [864, 1536, "High Detail"], [1088, 1920, "Full HD Output"]],
      "16:9": [[512, 288, "Stage 1 Preview"], [960, 544, "Fast Iteration"], [1184, 672, "Balanced"], [1312, 736, "HD Output"], [1536, 864, "High Detail"], [1920, 1088, "Full HD Output"]],
    },
  },
};

const states = new WeakMap();

function rowsFor(config, aspect) {
  return config.presets[aspect] ?? config.presets[config.fallback];
}

function aspectIsLandscape(aspect) {
  const match = /^\s*(\d+)\s*:\s*(\d+)\s*$/.exec(String(aspect ?? ""));
  return !match || Number(match[1]) >= Number(match[2]);
}

function officialLabels(config, aspect) {
  const landscape = aspectIsLandscape(aspect);
  let sizes = config.official.filter(([width, height]) => (width >= height) === landscape);
  if (!sizes.length) sizes = config.official;
  return [...sizes]
    .sort((left, right) => left[0] * left[1] - right[0] * right[1])
    .map(([width, height]) => `Official ${Math.min(width, height)}P — ${width}×${height}`);
}

function labelsFor(config, aspect, officialOnly) {
  if (officialOnly && config.official) return officialLabels(config, aspect);
  return rowsFor(config, aspect).map(([width, height, note]) => `${note} — ${width}×${height}`);
}

function normalizeText(value) {
  return String(value ?? "").toLowerCase().replaceAll(/[()]/g, "").replaceAll(/\s+/g, " ").trim();
}

function parseSize(value) {
  const match = /(\d+)\s*[x×]\s*(\d+)/i.exec(String(value ?? ""));
  return match ? { width: Number(match[1]), height: Number(match[2]) } : null;
}

function tierIndex(config, aspect, value) {
  const rows = rowsFor(config, aspect);
  const normalized = normalizeText(value);
  const byNote = rows
    .map((row, index) => ({ row, index }))
    .sort((left, right) => normalizeText(right.row[2]).length - normalizeText(left.row[2]).length)
    .find(({ row }) => normalized.includes(normalizeText(row[2])));
  if (byNote) return byNote.index;
  const numbered = /^\s*(\d+)\s*[.)]/.exec(String(value ?? ""));
  if (numbered) return Math.max(0, Math.min(Number(numbered[1]) - 1, rows.length - 1));
  const size = parseSize(value);
  if (size) {
    const found = rows.findIndex(([width, height]) => width === size.width && height === size.height);
    if (found >= 0) return found;
  }
  return 0;
}

function sizeFor(config, aspect, value) {
  const parsed = parseSize(value);
  if (parsed) return parsed;
  const row = rowsFor(config, aspect)[tierIndex(config, aspect, value)];
  return { width: row[0], height: row[1] };
}

function nearest(options, target) {
  let best = options[0];
  let delta = Infinity;
  for (const option of options) {
    const size = parseSize(option);
    if (!size) continue;
    const next = Math.abs(size.width * size.height - target.width * target.height);
    if (next < delta) {
      best = option;
      delta = next;
    }
  }
  return best;
}

function dispose(node) {
  const state = states.get(node);
  if (!state) return;
  states.delete(node);
  for (const unsubscribe of state.unsubscribers) unsubscribe();
}

function sync(node, config, preferred = {}) {
  const aspectWidget = node.widgets.get("aspect_ratio");
  const resolutionWidget = node.widgets.get("resolution");
  if (!aspectWidget || !resolutionWidget) return;
  const aspect = preferred.aspect_ratio ?? aspectWidget.getValue() ?? config.fallback;
  const official = Boolean(preferred.official_only ?? node.widgets.get("official_only")?.getValue());
  const options = labelsFor(config, aspect, official);
  const wanted = preferred.resolution ?? resolutionWidget.getValue();
  const next = options.includes(wanted)
    ? wanted
    : nearest(options, sizeFor(config, aspect, wanted));
  if (aspectWidget.getValue() !== aspect) aspectWidget.setValue(aspect);
  resolutionWidget.setOption("values", options);
  if (resolutionWidget.getValue() !== next) resolutionWidget.setValue(next);
}

function install(node, config) {
  dispose(node);
  const unsubscribers = [];
  const aspect = node.widgets.get("aspect_ratio");
  const official = node.widgets.get("official_only");
  if (aspect) unsubscribers.push(aspect.on("change", (value) => sync(node, config, { aspect_ratio: value })));
  if (official) unsubscribers.push(official.on("change", (value) => sync(node, config, { official_only: value })));
  states.set(node, { unsubscribers });
  sync(node, config);
}

function executionState(result) {
  const raw = result?.raw ?? result;
  const value = raw?.aspect_resolution_state ?? raw?.wanresolutions_state;
  return Array.isArray(value) ? value[0] : value;
}

for (const [nodeType, config] of Object.entries(CONFIGS)) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => install(node, config));
    builder.onConfigured((node) => sync(node, config));
    builder.onExecuted((node, result) => {
      const state = executionState(result);
      if (state && typeof state === "object") sync(node, config, state);
    });
    builder.onRemoved((node) => dispose(node));
  });
}
