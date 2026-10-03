import { DATA_VERSION, GRAPH_DATA_KEY, TOOLS } from "./constants.js";

function clampNumber(value, min, max, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, number));
}

function normalizePoint(point) {
  if (!Array.isArray(point) || point.length < 2) {
    return null;
  }

  const x = Number(point[0]);
  const y = Number(point[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }

  return [x, y];
}

function normalizeBounds(bounds) {
  if (!Array.isArray(bounds) || bounds.length < 4) {
    return null;
  }

  const x = Number(bounds[0]);
  const y = Number(bounds[1]);
  const width = Number(bounds[2]);
  const height = Number(bounds[3]);
  if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) {
    return null;
  }

  return [x, y, width, height];
}

function normalizeStroke(stroke, index) {
  if (!stroke || typeof stroke !== "object") {
    return null;
  }

  const tool = stroke.tool === TOOLS.ERASER ? TOOLS.ERASER : TOOLS.BRUSH;
  const points = Array.isArray(stroke.points)
    ? stroke.points.map(normalizePoint).filter(Boolean)
    : [];

  if (!points.length) {
    return null;
  }

  return {
    id: typeof stroke.id === "string" && stroke.id ? stroke.id : `stroke-${index}`,
    tool,
    color: typeof stroke.color === "string" && stroke.color ? stroke.color : "#ffb347",
    size: clampNumber(stroke.size, 1, 256, 10),
    points,
  };
}

function normalizeSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return null;
  }

  const image = typeof snapshot.image === "string" && snapshot.image.startsWith("data:image/")
    ? snapshot.image
    : null;
  const width = clampNumber(snapshot.width, 1, 4096, NaN);
  const height = clampNumber(snapshot.height, 1, 4096, NaN);
  const bounds = normalizeBounds(snapshot.bounds);

  if (!image || !Number.isFinite(width) || !Number.isFinite(height) || !bounds) {
    return null;
  }

  return {
    mimeType: typeof snapshot.mimeType === "string" && snapshot.mimeType ? snapshot.mimeType : "image/png",
    image,
    width,
    height,
    bounds,
  };
}

export function createEmptyDocument() {
  return {
    version: DATA_VERSION,
    strokes: [],
    snapshot: null,
  };
}

export function normalizeDocument(data) {
  if (!data || typeof data !== "object") {
    return createEmptyDocument();
  }

  const strokes = Array.isArray(data.strokes)
    ? data.strokes.map((stroke, index) => normalizeStroke(stroke, index)).filter(Boolean)
    : [];
  const snapshot = normalizeSnapshot(data.snapshot);

  return {
    version: DATA_VERSION,
    strokes,
    snapshot,
  };
}

export function cloneDocument(documentData) {
  return {
    version: DATA_VERSION,
    strokes: documentData.strokes.map((stroke) => ({
      id: stroke.id,
      tool: stroke.tool,
      color: stroke.color,
      size: stroke.size,
      points: stroke.points.map((point) => [point[0], point[1]]),
    })),
    snapshot: documentData.snapshot
      ? {
          mimeType: documentData.snapshot.mimeType,
          image: documentData.snapshot.image,
          width: documentData.snapshot.width,
          height: documentData.snapshot.height,
          bounds: [...documentData.snapshot.bounds],
        }
      : null,
  };
}

export function readDocumentFromGraph(graph) {
  return normalizeDocument(graph?.extra?.[GRAPH_DATA_KEY]);
}

function markGraphDirty(graph) {
  graph?.setDirtyCanvas?.(true, true);
}

export function writeDocumentToGraph(graph, documentData) {
  if (!graph) {
    return;
  }

  const normalized = normalizeDocument(documentData);
  const hasContent = normalized.strokes.length > 0 || Boolean(normalized.snapshot);

  graph.beforeChange?.();
  try {
    graph.extra ||= {};
    if (hasContent) {
      graph.extra[GRAPH_DATA_KEY] = normalized;
    } else {
      delete graph.extra[GRAPH_DATA_KEY];
    }
  } finally {
    graph.afterChange?.();
    markGraphDirty(graph);
  }
}
