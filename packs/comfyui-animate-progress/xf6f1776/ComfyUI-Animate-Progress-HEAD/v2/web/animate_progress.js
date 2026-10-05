import { comfy } from "/comfy/api/v2.js";

const STORAGE_KEY = "animate-progress/settings.json";
const MAX_SETTINGS_BYTES = 8192;
const GIFS = Object.freeze(Array.from(
  { length: 34 },
  (_, index) => `giphy${String(index + 1).padStart(2, "0")}.gif`,
));
const BAR_STYLES = Object.freeze([
  "default", "scanner", "pulsing", "plasma", "barber",
  "cosmic-weave", "dna-helix", "marching-ants",
]);
const DEFAULTS = Object.freeze({
  enabled: true,
  selectedGif: "random",
  gifHeight: 60,
  gifTop: -55,
  shadowEnabled: true,
  shadowBlur: 3,
  barStyle: "default",
  gradientColor1: "#00c3ff",
  gradientColor2: "#ff00c3",
  gradientColor3: "#00ffc9",
  gradientColor3Alpha: 0,
  fadeInOut: true,
});

let activeState;
let generation = 0;

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function finite(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? clamp(parsed, minimum, maximum) : fallback;
}

function color(value, fallback) {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value)
    ? value.toLowerCase()
    : fallback;
}

function boolean(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

function sanitizeSettings(value) {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
  return {
    enabled: boolean(source.enabled, DEFAULTS.enabled),
    selectedGif: source.selectedGif === "random" || GIFS.includes(source.selectedGif)
      ? source.selectedGif
      : DEFAULTS.selectedGif,
    gifHeight: finite(source.gifHeight, DEFAULTS.gifHeight, 20, 150),
    gifTop: finite(source.gifTop, DEFAULTS.gifTop, -150, 50),
    shadowEnabled: boolean(source.shadowEnabled, DEFAULTS.shadowEnabled),
    shadowBlur: finite(source.shadowBlur, DEFAULTS.shadowBlur, 0, 20),
    barStyle: BAR_STYLES.includes(source.barStyle)
      ? source.barStyle
      : DEFAULTS.barStyle,
    gradientColor1: color(source.gradientColor1, DEFAULTS.gradientColor1),
    gradientColor2: color(source.gradientColor2, DEFAULTS.gradientColor2),
    gradientColor3: color(source.gradientColor3, DEFAULTS.gradientColor3),
    gradientColor3Alpha: finite(
      source.gradientColor3Alpha, DEFAULTS.gradientColor3Alpha, 0, 1,
    ),
    fadeInOut: boolean(source.fadeInOut, DEFAULTS.fadeInOut),
  };
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function listen(state, element, type, listener, options) {
  element.addEventListener(type, listener, options);
  const remove = () => element.removeEventListener(type, listener, options);
  state.domListeners.push(remove);
  return remove;
}

function notifyStorageFailure(error) {
  comfy.commands.notify({
    severity: "warn",
    summary: "Animate Progress settings were not saved",
    detail: error instanceof Error ? error.message : String(error),
  });
}

async function loadSettings() {
  try {
    const raw = await comfy.storage.get(STORAGE_KEY);
    if (raw === undefined) return { ...DEFAULTS };
    if (raw.length > MAX_SETTINGS_BYTES) throw new Error("Stored settings exceed 8 KiB");
    return sanitizeSettings(JSON.parse(raw));
  } catch (error) {
    notifyStorageFailure(error);
    return { ...DEFAULTS };
  }
}

function runnerUrl(name) {
  if (!GIFS.includes(name)) throw new Error("Unknown runner");
  return new URL(`./runners/${name}`, import.meta.url).href;
}

function selectedRunner(state) {
  if (state.settings.selectedGif !== "random") return state.settings.selectedGif;
  const index = clamp(Math.floor(Math.random() * GIFS.length), 0, GIFS.length - 1);
  return GIFS[index];
}

function rgba(hex, alpha) {
  const red = Number.parseInt(hex.slice(1, 3), 16);
  const green = Number.parseInt(hex.slice(3, 5), 16);
  const blue = Number.parseInt(hex.slice(5, 7), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function applySettings(state) {
  const { progressRoot, progressBar, runner } = state.dom;
  if (!progressRoot || !progressBar || !runner) return;
  const settings = state.settings;
  runner.style.height = `${settings.gifHeight}px`;
  runner.style.top = `${settings.gifTop}px`;
  runner.style.filter = settings.shadowEnabled
    ? `drop-shadow(2px 2px ${settings.shadowBlur}px rgba(0, 0, 0, 0.7))`
    : "none";

  const base = `linear-gradient(to right, ${settings.gradientColor1}, ${settings.gradientColor2}, ${rgba(settings.gradientColor3, settings.gradientColor3Alpha)})`;
  Object.assign(progressBar.style, {
    background: base,
    backgroundSize: "",
    backgroundRepeat: "",
    animation: "none",
    boxShadow: "none",
  });
  switch (settings.barStyle) {
    case "scanner":
      progressBar.style.background = `${base}, linear-gradient(to right, transparent, rgba(255,255,255,0.8), transparent)`;
      progressBar.style.backgroundSize = "100% 100%, 15% 100%";
      progressBar.style.backgroundRepeat = "no-repeat";
      progressBar.style.animation = "ap-tech-scanner 2s ease-in-out infinite";
      break;
    case "pulsing":
      progressBar.style.animation = "ap-pulsing-glow 2s ease-in-out infinite";
      break;
    case "plasma":
      progressBar.style.background = `linear-gradient(-45deg, ${settings.gradientColor1}, ${settings.gradientColor2}, ${settings.gradientColor3}, #ff00c3)`;
      progressBar.style.backgroundSize = "400% 400%";
      progressBar.style.animation = "ap-plasma-flow 10s ease infinite";
      break;
    case "barber":
      progressBar.style.background = `repeating-linear-gradient(45deg, ${settings.gradientColor1}, ${settings.gradientColor1} 10px, ${settings.gradientColor2} 10px, ${settings.gradientColor2} 20px)`;
      progressBar.style.animation = "ap-barber-pole 1s linear infinite";
      break;
    case "cosmic-weave":
      progressBar.style.background = [
        `linear-gradient(60deg, ${settings.gradientColor1} 12%, transparent 12.5%, transparent 87%, ${settings.gradientColor1} 87.5%, ${settings.gradientColor1})`,
        `linear-gradient(-60deg, ${settings.gradientColor2} 12%, transparent 12.5%, transparent 87%, ${settings.gradientColor2} 87.5%, ${settings.gradientColor2})`,
        `linear-gradient(60deg, ${settings.gradientColor3} 12%, transparent 12.5%, transparent 87%, ${settings.gradientColor3} 87.5%, ${settings.gradientColor3})`,
        `linear-gradient(-60deg, ${settings.gradientColor1} 12%, transparent 12.5%, transparent 87%, ${settings.gradientColor1} 87.5%, ${settings.gradientColor1})`,
      ].join(",");
      progressBar.style.backgroundSize = "20px 35px";
      progressBar.style.animation = "ap-cosmic-weave 2s linear infinite";
      break;
    case "dna-helix":
      progressBar.style.background = [
        `linear-gradient(45deg, ${settings.gradientColor1} 25%, transparent 25%)`,
        `linear-gradient(-45deg, ${settings.gradientColor1} 25%, transparent 25%)`,
        `linear-gradient(45deg, transparent 75%, ${settings.gradientColor2} 75%)`,
        `linear-gradient(-45deg, transparent 75%, ${settings.gradientColor2} 75%)`,
      ].join(",");
      progressBar.style.backgroundSize = "20px 20px";
      progressBar.style.animation = "ap-dna-helix 1s linear infinite";
      break;
    case "marching-ants":
      progressBar.style.background = `repeating-linear-gradient(to right, ${settings.gradientColor1} 0, ${settings.gradientColor1} 10px, transparent 10px, transparent 20px)`;
      progressBar.style.backgroundSize = "40px 100%";
      progressBar.style.animation = "ap-marching-ants 1s linear infinite";
      break;
    default:
      break;
  }
  progressRoot.style.transition = settings.fadeInOut ? "opacity 0.5s ease-in-out" : "none";
  if (!settings.enabled) finishProgress(state);
}

function updateProgressPosition(state) {
  const percent = `${(state.progress * 100).toFixed(2)}%`;
  state.dom.progressBar.style.width = percent;
  state.dom.runner.style.left = percent;
}

function beginProgress(state, detail) {
  if (state.disposed || !state.settings.enabled || !detail || typeof detail !== "object") return;
  const value = Number(detail.value);
  const maximum = Number(detail.max);
  if (!Number.isFinite(value) || !Number.isFinite(maximum) || maximum <= 0) return;
  const wasRunning = state.running;
  state.running = true;
  state.progress = clamp(value / maximum, 0, 1);
  if (!wasRunning) {
    state.runnerName = selectedRunner(state);
    state.dom.runner.src = runnerUrl(state.runnerName);
  }
  if (state.hideTimer !== undefined) {
    clearTimeout(state.hideTimer);
    state.hideTimer = undefined;
  }
  state.dom.progressRoot.style.display = "block";
  updateProgressPosition(state);
  if (state.animationFrame !== undefined) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = requestAnimationFrame(() => {
    state.animationFrame = undefined;
    if (!state.disposed && state.running) state.dom.progressRoot.style.opacity = "1";
  });
}

function finishProgress(state) {
  if (!state || state.disposed) return;
  state.running = false;
  if (state.animationFrame !== undefined) {
    cancelAnimationFrame(state.animationFrame);
    state.animationFrame = undefined;
  }
  if (state.hideTimer !== undefined) clearTimeout(state.hideTimer);
  const root = state.dom.progressRoot;
  if (!root) return;
  root.style.opacity = "0";
  state.hideTimer = setTimeout(() => {
    state.hideTimer = undefined;
    if (!state.disposed && !state.running) root.style.display = "none";
  }, 500);
}

function syncDialog(state) {
  state.dialogSync?.(state.settings);
}

function updateSetting(state, key, value) {
  if (state.disposed) return Promise.resolve();
  const next = sanitizeSettings({ ...state.settings, [key]: value });
  state.settings = next;
  state.writeRevision += 1;
  const revision = state.writeRevision;
  applySettings(state);
  syncDialog(state);
  state.saveQueue = state.saveQueue.then(async () => {
    try {
      await comfy.storage.set(STORAGE_KEY, JSON.stringify(next));
      state.persistedSettings = next;
    } catch (error) {
      if (!state.disposed && revision === state.writeRevision) {
        state.settings = state.persistedSettings;
        applySettings(state);
        syncDialog(state);
      }
      if (!state.disposed) notifyStorageFailure(error);
    }
  });
  return state.saveQueue;
}

function clearDialog(state, closeHost = true) {
  const handle = state.dialogHandle;
  state.dialogHandle = undefined;
  state.dialogSync = undefined;
  for (const remove of state.dialogListeners.splice(0)) remove();
  if (closeHost) handle?.close();
}

function dialogListen(state, element, type, listener) {
  element.addEventListener(type, listener);
  state.dialogListeners.push(() => element.removeEventListener(type, listener));
}

function makeRow(doc, labelText, control, valueLabel) {
  const row = style(doc.createElement("label"), {
    display: "grid",
    gridTemplateColumns: "155px minmax(180px, 1fr) 58px",
    alignItems: "center",
    gap: "10px",
    fontSize: "13px",
  });
  const label = doc.createElement("span");
  label.textContent = labelText;
  const value = doc.createElement("span");
  value.textContent = valueLabel ?? "";
  value.style.textAlign = "right";
  row.append(label, control, value);
  return { row, value };
}

function renderSettings(state, container) {
  const doc = container.ownerDocument;
  const root = style(doc.createElement("section"), {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    minWidth: "470px",
    maxWidth: "620px",
    maxHeight: "72vh",
    overflowY: "auto",
    padding: "4px",
    fontFamily: "sans-serif",
  });
  root.setAttribute("aria-label", "Animate Progress settings");
  const setters = new Map();

  const checkbox = (key, label) => {
    const input = doc.createElement("input");
    input.type = "checkbox";
    input.dataset.setting = key;
    const { row } = makeRow(doc, label, input);
    setters.set(key, (settings) => { input.checked = settings[key]; });
    dialogListen(state, input, "change", () => { void updateSetting(state, key, input.checked); });
    root.append(row);
  };
  const range = (key, label, minimum, maximum, step, suffix, digits = 0) => {
    const input = doc.createElement("input");
    input.type = "range";
    input.dataset.setting = key;
    input.min = String(minimum);
    input.max = String(maximum);
    input.step = String(step);
    const built = makeRow(doc, label, input);
    setters.set(key, (settings) => {
      input.value = String(settings[key]);
      built.value.textContent = `${Number(settings[key]).toFixed(digits)}${suffix}`;
    });
    dialogListen(state, input, "input", () => { void updateSetting(state, key, Number(input.value)); });
    root.append(built.row);
  };
  const colorInput = (key, label) => {
    const input = doc.createElement("input");
    input.type = "color";
    input.dataset.setting = key;
    const { row } = makeRow(doc, label, input);
    setters.set(key, (settings) => { input.value = settings[key]; });
    dialogListen(state, input, "input", () => { void updateSetting(state, key, input.value); });
    root.append(row);
  };

  checkbox("enabled", "Enable plugin");

  const gifHeading = doc.createElement("strong");
  gifHeading.textContent = "GIF animation";
  root.append(gifHeading);
  const gifControls = style(doc.createElement("div"), {
    display: "grid",
    gridTemplateColumns: "1fr 150px",
    gap: "10px",
  });
  const gifList = style(doc.createElement("div"), {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(76px, 1fr))",
    gap: "4px",
    maxHeight: "145px",
    overflowY: "auto",
  });
  const preview = style(doc.createElement("img"), {
    display: "none",
    maxWidth: "150px",
    maxHeight: "140px",
    objectFit: "contain",
    alignSelf: "center",
  });
  preview.alt = "Runner preview";
  const gifButtons = new Map();
  for (const name of ["random", ...GIFS]) {
    const button = doc.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.dataset.value = name;
    dialogListen(state, button, "click", () => { void updateSetting(state, "selectedGif", name); });
    if (name !== "random") {
      dialogListen(state, button, "mouseenter", () => {
        preview.src = runnerUrl(name);
        preview.style.display = "block";
      });
    }
    gifButtons.set(name, button);
    gifList.append(button);
  }
  dialogListen(state, gifList, "mouseleave", () => { preview.style.display = "none"; });
  gifControls.append(gifList, preview);
  root.append(gifControls);
  setters.set("selectedGif", (settings) => {
    for (const [name, button] of gifButtons) {
      button.setAttribute("aria-pressed", String(name === settings.selectedGif));
    }
  });

  range("gifHeight", "GIF size (height)", 20, 150, 1, "px");
  range("gifTop", "GIF position (top)", -150, 50, 1, "px");
  checkbox("shadowEnabled", "Enable GIF shadow");
  range("shadowBlur", "Shadow blur", 0, 20, 1, "px");

  const styleSelect = doc.createElement("select");
  styleSelect.dataset.setting = "barStyle";
  for (const name of BAR_STYLES) {
    const option = doc.createElement("option");
    option.value = name;
    option.textContent = name;
    styleSelect.append(option);
  }
  const { row: styleRow } = makeRow(doc, "Bar style", styleSelect);
  setters.set("barStyle", (settings) => { styleSelect.value = settings.barStyle; });
  dialogListen(state, styleSelect, "change", () => { void updateSetting(state, "barStyle", styleSelect.value); });
  root.append(styleRow);

  colorInput("gradientColor1", "Bar gradient start");
  colorInput("gradientColor2", "Bar gradient middle");
  colorInput("gradientColor3", "Bar gradient end");
  range("gradientColor3Alpha", "End color opacity", 0, 1, 0.01, "", 2);
  checkbox("fadeInOut", "Fade in/out effect");

  const done = doc.createElement("button");
  done.type = "button";
  done.textContent = "Done";
  dialogListen(state, done, "click", () => clearDialog(state));
  root.append(done);
  container.replaceChildren(root);
  state.dialogSync = (settings) => {
    for (const setter of setters.values()) setter(settings);
  };
  syncDialog(state);
}

function openSettings(state) {
  if (state.disposed) return;
  clearDialog(state);
  state.dialogHandle = comfy.ui.showDialog({
    key: "animate-progress.settings",
    title: "Animate Progress Bar Settings",
    render: (container) => renderSettings(state, container),
    onKeyDown: (event) => {
      if (event.key === "Escape") clearDialog(state);
    },
    destroy: () => clearDialog(state, false),
  });
}

function mountProgressPanel(state) {
  return comfy.ui.mountViewportPanel({
    id: "animate-progress.progress",
    anchor: "bottom-center",
    offsetY: 6,
    width: 600,
    maxHeight: 160,
    ariaLabel: "Animated execution progress",
    render(container) {
      const doc = container.ownerDocument;
      const animations = doc.createElement("style");
      animations.textContent = `
        @keyframes ap-tech-scanner{0%{background-position:-15% 0,-15% 0}50%{background-position:0 0,115% 0}100%{background-position:0 0,115% 0}}
        @keyframes ap-pulsing-glow{0%{box-shadow:0 0 5px rgba(255,255,255,.2)}50%{box-shadow:0 0 15px 5px rgba(24,247,255,.7)}100%{box-shadow:0 0 5px rgba(255,255,255,.2)}}
        @keyframes ap-plasma-flow{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
        @keyframes ap-barber-pole{0%{background-position:0 0}100%{background-position:20px 0}}
        @keyframes ap-cosmic-weave{0%{background-position:0 0}100%{background-position:40px 70px}}
        @keyframes ap-dna-helix{0%{background-position:0 0}100%{background-position:40px 0}}
        @keyframes ap-marching-ants{0%{background-position:0 0}100%{background-position:40px 0}}
      `;
      const root = style(doc.createElement("div"), {
        position: "relative",
        width: "100%",
        height: "5px",
        backgroundColor: "var(--comfy-input-bg)",
        borderRadius: "2px",
        boxShadow: "0 0 10px rgba(0,0,0,0.5)",
        display: "none",
        opacity: "0",
        pointerEvents: "none",
      });
      const bar = style(doc.createElement("div"), {
        position: "absolute",
        left: "0",
        top: "0",
        height: "100%",
        width: "0%",
        borderRadius: "10px",
      });
      const runner = style(doc.createElement("img"), {
        position: "absolute",
        left: "0%",
        transform: "translateX(-50%)",
        imageRendering: "pixelated",
        zIndex: "1",
      });
      runner.alt = "Animated progress runner";
      root.append(bar, runner);
      container.replaceChildren(animations, root);
      state.dom.progressRoot = root;
      state.dom.progressBar = bar;
      state.dom.runner = runner;
      applySettings(state);
    },
  });
}

function mountSettingsButton(state) {
  return comfy.ui.mountViewportPanel({
    id: "animate-progress.settings-button",
    anchor: "bottom-right",
    offsetX: 12,
    offsetY: 240,
    width: 48,
    maxHeight: 48,
    ariaLabel: "Animate Progress controls",
    render(container) {
      const button = style(container.ownerDocument.createElement("button"), {
        width: "40px",
        height: "40px",
        borderRadius: "50%",
        cursor: "pointer",
        fontSize: "24px",
        border: "1px solid var(--p-button-secondary-border-color)",
        backgroundColor: "var(--p-button-secondary-background)",
        color: "#fff",
      });
      button.type = "button";
      button.textContent = "🔜";
      button.title = "Animate Progress settings";
      button.setAttribute("aria-label", "Open Animate Progress settings");
      listen(state, button, "click", () => openSettings(state));
      container.replaceChildren(button);
      state.dom.settingsButton = button;
    },
  });
}

function subscribe(state) {
  state.unsubscribers.push(
    comfy.backend.on("progress", (detail) => beginProgress(state, detail)),
    comfy.backend.on("execution_error", () => finishProgress(state)),
    comfy.queue.onInterrupted(() => finishProgress(state)),
    comfy.queue.onRejected(() => finishProgress(state)),
    comfy.queue.onPendingChanged((pending) => {
      if (pending === 0) finishProgress(state);
    }),
    comfy.onExecutingNodeChanged((node) => {
      if (!node && state.running && comfy.queue.pending() === 0) finishProgress(state);
    }),
  );
}

function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  if (state.animationFrame !== undefined) cancelAnimationFrame(state.animationFrame);
  if (state.hideTimer !== undefined) clearTimeout(state.hideTimer);
  clearDialog(state);
  for (const unsubscribe of state.unsubscribers.splice(0).reverse()) unsubscribe();
  for (const remove of state.domListeners.splice(0).reverse()) remove();
  for (const panel of state.panels.splice(0).reverse()) panel.remove();
  state.dom = {};
  if (activeState === state) activeState = undefined;
}

async function mount() {
  const ownGeneration = ++generation;
  dispose(activeState);
  const settings = await loadSettings();
  if (ownGeneration !== generation) return;
  const state = {
    settings,
    persistedSettings: settings,
    writeRevision: 0,
    saveQueue: Promise.resolve(),
    progress: 0,
    running: false,
    runnerName: undefined,
    animationFrame: undefined,
    hideTimer: undefined,
    disposed: false,
    panels: [],
    unsubscribers: [],
    domListeners: [],
    dialogListeners: [],
    dialogHandle: undefined,
    dialogSync: undefined,
    dom: {},
  };
  activeState = state;
  state.panels.push(mountProgressPanel(state), mountSettingsButton(state));
  subscribe(state);
}

comfy.onReady(() => { void mount(); });
