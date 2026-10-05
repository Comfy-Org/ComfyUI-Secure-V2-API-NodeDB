export const MIN_WIDTH = 200;
export const MIN_HEIGHT = 200;
export const HEADER_HEIGHT = 32;
export const RESIZE_SIZE = 22;

function finite(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function defaultGeometry(viewport) {
  const width = Math.min(520, Math.max(MIN_WIDTH, viewport.width));
  const height = Math.min(560, Math.max(MIN_HEIGHT, viewport.height));
  return clampGeometry({
    x: viewport.width - width - 60,
    y: 60,
    width,
    height,
  }, viewport);
}

export function sanitizeStoredGeometry(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const keys = ["x", "y", "width", "height"];
  if (!keys.every((key) => typeof value[key] === "number" && Number.isFinite(value[key]))) {
    return undefined;
  }
  return Object.freeze(Object.fromEntries(keys.map((key) => [key, value[key]])));
}

export function clampGeometry(value, viewport) {
  const viewportWidth = Math.max(1, finite(viewport?.width, 1));
  const viewportHeight = Math.max(1, finite(viewport?.height, 1));
  const width = Math.min(
    Math.max(finite(value?.width, MIN_WIDTH), MIN_WIDTH),
    Math.max(MIN_WIDTH, viewportWidth),
  );
  const height = Math.min(
    Math.max(finite(value?.height, MIN_HEIGHT), MIN_HEIGHT),
    Math.max(MIN_HEIGHT, viewportHeight),
  );
  return Object.freeze({
    x: Math.min(Math.max(finite(value?.x, 0), 0), Math.max(0, viewportWidth - width)),
    y: Math.min(Math.max(finite(value?.y, 0), 0), Math.max(0, viewportHeight - height)),
    width,
    height,
  });
}

export function dragGeometry(start, dx, dy, viewport) {
  return clampGeometry({ ...start, x: start.x + dx, y: start.y + dy }, viewport);
}

export function resizeGeometry(start, dx, dy, viewport) {
  const maxWidth = Math.max(MIN_WIDTH, viewport.width - start.x);
  const maxHeight = Math.max(MIN_HEIGHT, viewport.height - start.y);
  return Object.freeze({
    ...start,
    width: Math.min(Math.max(MIN_WIDTH, start.width + dx), maxWidth),
    height: Math.min(Math.max(MIN_HEIGHT, start.height + dy), maxHeight),
  });
}

export function panelRegions(geometry) {
  if (!geometry) return [];
  return Object.freeze([
    Object.freeze({
      kind: "rect",
      x: geometry.x,
      y: geometry.y,
      width: geometry.width,
      height: HEADER_HEIGHT,
    }),
    Object.freeze({
      kind: "rect",
      x: geometry.x + geometry.width - RESIZE_SIZE,
      y: geometry.y + geometry.height - RESIZE_SIZE,
      width: RESIZE_SIZE,
      height: RESIZE_SIZE,
    }),
  ]);
}
