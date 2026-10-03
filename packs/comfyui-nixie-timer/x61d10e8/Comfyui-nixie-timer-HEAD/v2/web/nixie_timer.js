import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "NixieTimer";
const BASE_WIDTH = 320;
const BASE_HEIGHT = 104;
const THEME_MAP = new Map([
  ["红色", "red"],
  ["绿色", "green"],
  ["蓝色", "blue"],
  ["琥珀", "amber"],
  ["紫色", "purple"],
  ["青色", "cyan"],
  ["白色", "white"],
]);

const TRANSLATIONS = {
  zh: { clock: "世界时钟", timer: "推理耗时" },
  en: { clock: "World Clock", timer: "Inference Time" },
  ja: { clock: "ワールドクロック", timer: "推論時間" },
  ko: { clock: "월드 시계", timer: "추론 시간" },
  ru: { clock: "Мировые часы", timer: "Время вывода" },
  de: { clock: "Weltuhr", timer: "Inferenzzeit" },
  fr: { clock: "Horloge", timer: "Temps d'inférence" },
  es: { clock: "Reloj mundial", timer: "Tiempo de inferencia" },
  pt: { clock: "Relógio mundial", timer: "Tempo de inferência" },
  it: { clock: "Orologio", timer: "Tempo di inferenza" },
};

const PANEL_CSS = `
.nixie-node-body{--nc:#ff7a1a;--ng1:#ff4d00;--ng2:#e63a00;--nb:#331407;--nborder:#4a3520;--nlabel:#c98a4a;--nshadow:rgba(255,110,0,.18);background:linear-gradient(180deg,rgba(26,20,14,.95),rgba(11,8,5,.95));border:2px solid var(--nborder);border-radius:8px;padding:6px 8px 7px;box-shadow:inset 0 0 16px var(--nshadow);box-sizing:border-box;pointer-events:auto;overflow:hidden}
.nixie-node-body[data-theme="green"]{--nc:#52ff6e;--ng1:#1bff48;--ng2:#00d13a;--nb:#0d3314;--nborder:#1e4a2c;--nlabel:#5ec98a;--nshadow:rgba(80,255,120,.18)}
.nixie-node-body[data-theme="blue"]{--nc:#4da6ff;--ng1:#1a7bff;--ng2:#0059e6;--nb:#0d1f33;--nborder:#1e3a4a;--nlabel:#5ea9c9;--nshadow:rgba(80,160,255,.18)}
.nixie-node-body[data-theme="amber"]{--nc:#ffb52e;--ng1:#ff9200;--ng2:#e66f00;--nb:#33240d;--nborder:#4a3a1e;--nlabel:#c9a75e;--nshadow:rgba(255,170,60,.18)}
.nixie-node-body[data-theme="purple"]{--nc:#c77dff;--ng1:#a44dff;--ng2:#7a1ae6;--nb:#251233;--nborder:#3a1e4a;--nlabel:#a56ec9;--nshadow:rgba(180,110,255,.18)}
.nixie-node-body[data-theme="cyan"]{--nc:#3affd4;--ng1:#00e6b0;--ng2:#00b38a;--nb:#0d332b;--nborder:#1e4a40;--nlabel:#5ec9b4;--nshadow:rgba(60,255,210,.18)}
.nixie-node-body[data-theme="white"]{--nc:#f2f2f2;--ng1:#cfcfff;--ng2:#9f9fe6;--nb:#1a1a26;--nborder:#33334a;--nlabel:#9a9ac9;--nshadow:rgba(200,200,255,.18)}
.nixie-row{display:flex;align-items:center;justify-content:center;gap:2px;white-space:nowrap}.nixie-clock-row{margin-bottom:5px}.nixie-label{color:var(--nlabel);font-size:8px;letter-spacing:2px;text-align:center;margin:1px 0 4px;text-transform:uppercase;font-family:Consolas,"Courier New",monospace}.nixie-tube{position:relative;background:radial-gradient(circle at 50% 28%,var(--nb) 0%,#170803 55%,#0a0402 100%);border-radius:4px;padding:2px 3px 3px;min-width:1.02em;text-align:center;color:var(--nc);font-weight:700;line-height:1;font-family:Consolas,"Courier New",monospace;text-shadow:0 0 5px var(--nc),0 0 11px var(--ng1),0 0 22px var(--ng2);box-shadow:inset 0 0 8px var(--nshadow)}.nixie-tube.clock{font-size:13px}.nixie-tube.timer{font-size:21px;min-width:1.1em;padding:3px 4px 4px}.nixie-sep{color:var(--nc);font-weight:700;font-family:Consolas,"Courier New",monospace;text-shadow:0 0 6px var(--nc),0 0 12px var(--ng1);padding:0 1px;animation:nixie-blink 1s steps(1) infinite}.nixie-sep.clock{font-size:13px}.nixie-sep.timer{font-size:17px}.nixie-sep.off{animation:none;opacity:.35}@keyframes nixie-blink{50%{opacity:.15}}.nixie-node-body.paused .nixie-sep{animation:none;opacity:.35}.nixie-node-body.paused .nixie-tube{opacity:.7}
`;

const instances = new Map();
let sharedUnsubscribers = [];
let tickTimer;
let running = false;
let startTimestamp = 0;
let elapsed = 0;
let queueGeneration = 0;
let acceptedGeneration = 0;
let sawPending = false;

function stateKey(node) {
  return `${node.graphId ?? "visible"}:${node.id}`;
}

function locale() {
  const raw = comfy.settings.get("Comfy.Locale");
  const key = typeof raw === "string" ? raw.split("-")[0].toLowerCase() : "en";
  return TRANSLATIONS[key] ? key : "en";
}

function applyLocale(state) {
  const messages = TRANSLATIONS[locale()];
  if (!state.clockLabel || !state.timerLabel) return;
  state.clockLabel.textContent = messages.clock;
  state.timerLabel.textContent = messages.timer;
}

function applyLocaleToAll() {
  for (const state of instances.values()) applyLocale(state);
}

function applyTheme(state) {
  const value = state.node.widgets.get("tube_color")?.getValue();
  if (state.panel) state.panel.dataset.theme = THEME_MAP.get(String(value)) ?? "red";
}

function makeTubes(doc, text, className) {
  const fragment = doc.createDocumentFragment();
  for (const character of text) {
    if (character === " ") {
      fragment.append(doc.createTextNode(" "));
      continue;
    }
    const element = doc.createElement("span");
    if (character === ":") element.className = `nixie-sep ${className}`;
    else if (character === "-" || character === ".") element.className = `nixie-sep off ${className}`;
    else element.className = `nixie-tube ${className}`;
    element.textContent = character;
    fragment.append(element);
  }
  return fragment;
}

function twoDigits(value) {
  return String(value).padStart(2, "0");
}

function renderAll() {
  const now = new Date();
  const clock = `${now.getFullYear()}-${twoDigits(now.getMonth() + 1)}-${twoDigits(now.getDate())}-` +
    `${twoDigits(now.getHours())}:${twoDigits(now.getMinutes())}:${twoDigits(now.getSeconds())}`;
  const milliseconds = Math.max(0, Math.floor(running ? performance.now() - startTimestamp : elapsed));
  const seconds = Math.floor(milliseconds / 1000);
  const timer = `${twoDigits(Math.floor(seconds / 3600))}:` +
    `${twoDigits(Math.floor((seconds % 3600) / 60))}:${twoDigits(seconds % 60)}`;
  for (const state of instances.values()) {
    if (!state.clockRow || !state.timerRow) continue;
    const doc = state.clockRow.ownerDocument;
    state.clockRow.replaceChildren(makeTubes(doc, clock, "clock"));
    state.timerRow.replaceChildren(makeTubes(doc, timer, "timer"));
  }
}

function startTimer() {
  running = true;
  startTimestamp = performance.now();
  elapsed = 0;
  sawPending = comfy.queue.pending() > 0;
  for (const state of instances.values()) state.panel?.classList.remove("paused");
  renderAll();
}

function stopTimer() {
  if (!running) return;
  elapsed = Math.max(0, performance.now() - startTimestamp);
  running = false;
  sawPending = false;
  for (const state of instances.values()) state.panel?.classList.add("paused");
  renderAll();
}

function ensureSharedLifecycle() {
  if (sharedUnsubscribers.length) return;
  sharedUnsubscribers = [
    comfy.queue.onBeforeRun(() => {
      const generation = ++queueGeneration;
      acceptedGeneration = 0;
      startTimer();
      return () => queueMicrotask(() => {
        if (generation === queueGeneration && acceptedGeneration !== generation && comfy.queue.pending() === 0) {
          stopTimer();
        }
      });
    }),
    comfy.queue.onAfterRun((event) => {
      if (event.promptIds.length > 0) {
        acceptedGeneration = queueGeneration;
        sawPending = sawPending || comfy.queue.pending() > 0;
      } else {
        stopTimer();
      }
    }),
    comfy.queue.onRejected(stopTimer),
    comfy.queue.onPendingChanged((pending) => {
      if (pending > 0) sawPending = true;
      else if (running && sawPending) stopTimer();
    }),
    comfy.queue.onInterrupted(stopTimer),
    comfy.backend.on("execution_error", stopTimer),
    comfy.settings.onChange("Comfy.Locale", applyLocaleToAll),
  ];
  tickTimer = setInterval(renderAll, 100);
}

function releaseSharedLifecycle() {
  if (instances.size > 0) return;
  if (tickTimer !== undefined) clearInterval(tickTimer);
  tickTimer = undefined;
  for (const unsubscribe of sharedUnsubscribers.splice(0)) unsubscribe();
}

function applyScale(state, width) {
  if (state.disposed || !state.panel || !state.mount) return;
  if (state.animationFrame !== undefined) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = requestAnimationFrame(() => {
    state.animationFrame = undefined;
    if (state.disposed || !state.panel || !state.mount) return;
    const boundedWidth = Math.max(180, Number(width) || BASE_WIDTH);
    const scale = boundedWidth / BASE_WIDTH;
    state.panel.style.width = `${BASE_WIDTH}px`;
    state.panel.style.height = `${BASE_HEIGHT}px`;
    state.panel.style.transform = `scale(${scale})`;
    state.panel.style.transformOrigin = "top left";
    state.mount.setHeight(Math.max(BASE_HEIGHT, Math.round(BASE_HEIGHT * scale)));
  });
}

function buildPanel(state, container) {
  const doc = container.ownerDocument;
  const styles = doc.createElement("style");
  styles.textContent = PANEL_CSS;
  const panel = doc.createElement("div");
  panel.className = "nixie-node-body paused";
  const clockLabel = doc.createElement("div");
  clockLabel.className = "nixie-label";
  const clockRow = doc.createElement("div");
  clockRow.className = "nixie-row nixie-clock-row";
  const timerLabel = doc.createElement("div");
  timerLabel.className = "nixie-label";
  timerLabel.style.marginTop = "4px";
  const timerRow = doc.createElement("div");
  timerRow.className = "nixie-row";
  panel.append(clockLabel, clockRow, timerLabel, timerRow);
  container.replaceChildren(styles, panel);
  state.panel = panel;
  state.clockLabel = clockLabel;
  state.clockRow = clockRow;
  state.timerLabel = timerLabel;
  state.timerRow = timerRow;
  applyLocale(state);
  applyTheme(state);
  renderAll();
}

function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  if (state.animationFrame !== undefined) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = undefined;
  for (const unsubscribe of state.unsubscribers.splice(0)) unsubscribe();
  if (instances.get(state.key) === state) instances.delete(state.key);
  state.panel = undefined;
  state.clockRow = undefined;
  state.timerRow = undefined;
  releaseSharedLifecycle();
}

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => {
    const key = stateKey(node);
    dispose(instances.get(key));
    const state = {
      key,
      node,
      mount: undefined,
      panel: undefined,
      clockLabel: undefined,
      clockRow: undefined,
      timerLabel: undefined,
      timerRow: undefined,
      animationFrame: undefined,
      unsubscribers: [],
      disposed: false,
    };
    instances.set(key, state);
    ensureSharedLifecycle();
    node.setSizeConstraints({ minWidth: 180, autoHeight: true });
    state.mount = node.widgets.mount({
      name: "nixie_timer",
      height: BASE_HEIGHT,
      serialize: false,
      sendToPrompt: false,
      render(container) {
        buildPanel(state, container);
        applyScale(state, node.getSize().width);
      },
      destroy() {
        dispose(state);
      },
    });
    const color = node.widgets.get("tube_color");
    const unsubscribe = color?.on("change", () => applyTheme(state));
    if (typeof unsubscribe === "function") state.unsubscribers.push(unsubscribe);
  });
  builder.onConfigured((node) => {
    const state = instances.get(stateKey(node));
    applyTheme(state);
    applyLocale(state);
  });
  builder.onResized((node, size) => applyScale(instances.get(stateKey(node)), size.width));
  builder.onRemoved((node) => dispose(instances.get(stateKey(node))));
});
