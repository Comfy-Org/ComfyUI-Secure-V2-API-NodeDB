export const EXTENSION_NAME = "ComfyJot.CanvasOverlay";
export const SIDEBAR_TAB_ID = "comfyjotSidebarLauncher";
export const GRAPH_DATA_KEY = "comfyjot";
export const DATA_VERSION = 2;
export const BRUSH_SIZE_MIN = 1;
export const BRUSH_SIZE_MAX = 48;

export const TOOLS = Object.freeze({
  BRUSH: "brush",
  ERASER: "eraser",
});

export const DEFAULT_BRUSH_SIZE = 10;
export const DEFAULT_COLOR = "#ffb347";
export const DEFAULT_SWATCHES = Object.freeze([
  "#ffb347",
  "#ff6b6b",
  "#ffd166",
  "#7bdff2",
  "#7ae582",
  "#c4b5fd",
  "#f8fafc",
  "#111827",
]);

export const SETTINGS = Object.freeze({
  DEFAULT_BRUSH_SIZE: "ComfyJot.Settings.DefaultBrushSize",
  SHOW_EXISTING_ON_LOAD: "ComfyJot.Settings.ShowExistingOnLoad",
});

export const COMMANDS = Object.freeze({
  TOGGLE_OVERLAY: "ComfyJot.ToggleOverlay",
  TOGGLE_INK: "ComfyJot.ToggleInk",
  UNDO: "ComfyJot.Undo",
  REDO: "ComfyJot.Redo",
  CLEAR: "ComfyJot.Clear",
});

export const TOOL_LABELS = Object.freeze({
  [TOOLS.BRUSH]: "Brush",
  [TOOLS.ERASER]: "Eraser",
});
