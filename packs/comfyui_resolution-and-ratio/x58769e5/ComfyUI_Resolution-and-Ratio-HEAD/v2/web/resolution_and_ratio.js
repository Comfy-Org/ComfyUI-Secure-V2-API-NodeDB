import { comfy } from "/comfy/api/v2.js";

// Schema widgets remain the authoritative workflow/prompt state. Only the two
// dimension editors are mounted: native activate does NOT mean drag release.
const states = new Map();
const TEXT_LIMIT = 65536;
const LINE_LIMIT = 1024;
const keyOf = (node) => `${node.graphId ?? "root"}:${node.id}`;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const gcd = (a, b) => b === 0 ? a : gcd(b, a % b);

function snapSize(raw) {
  const n = Math.round(Number(raw));
  if (!Number.isFinite(n)) return 8;
  const value = clamp(n, 8, 4096);
  return value <= 32 ? value : clamp(Math.round(value / 32) * 32, 32, 4096);
}

function parsePreset(text) {
  if (typeof text !== "string" || text.length > 128) return null;
  const match = /^(\d+)\s*[x*×]\s*(\d+)$/i.exec(text.trim());
  if (!match) return null;
  const w = Number(match[1]), h = Number(match[2]);
  if (!Number.isSafeInteger(w) || !Number.isSafeInteger(h) || w <= 0 || h <= 0) return null;
  return { w, h };
}

function presetValues(text) {
  if (typeof text !== "string" || text.length > TEXT_LIMIT || new TextEncoder().encode(text).length > TEXT_LIMIT) return null;
  const lines = text.split("\n");
  if (lines.length > LINE_LIMIT) return null;
  const values = ["Custom"], seen = new Set();
  for (const line of lines) {
    const size = parsePreset(line);
    if (!size || size.w < 512 || size.h < 512) continue;
    const label = `${size.w}x${size.h}`;
    if (!seen.has(label)) { seen.add(label); values.push(label); }
  }
  return values;
}

function dispose(state) {
  if (!state || state.dead) return;
  state.dead = true;
  for (const timer of state.timers) clearTimeout(timer);
  state.timers.clear();
  for (const off of state.off.splice(0)) off();
  state.drag = null;
  state.container?.replaceChildren();
  if (states.get(state.key) === state) states.delete(state.key);
}

function install(node) {
  const key = keyOf(node);
  dispose(states.get(key));
  const names = ["width", "height", "W_ratio", "H_ratio", "scale_percent", "reset", "swap", "preset", "custom_presets"];
  const w = Object.fromEntries(names.map((name) => [name, node.widgets.get(name)]));
  if (names.some((name) => !w[name])) throw new Error("ResolutionAndRatio schema widgets are missing");
  const values = Object.fromEntries(names.map((name) => [name, w[name].getValue()]));
  const state = { key, node, w, values, dead: false, timers: new Set(), off: [], drag: null, fields: {}, base: [snapSize(values.width), snapSize(values.height)] };
  states.set(key, state);
  const timer = (fn, delay) => {
    const id = setTimeout(() => { state.timers.delete(id); if (!state.dead) fn(); }, delay);
    state.timers.add(id);
  };
  const write = (name, value) => {
    if (state.dead || Object.is(values[name], value)) return;
    values[name] = value;
    w[name].setValue(value);
    if (state.fields[name]) state.fields[name].value = String(value);
  };
  const custom = () => write("preset", "Custom");
  const ratios = () => {
    const width = Math.max(1, Math.round(Number(values.width) || 0));
    const height = Math.max(1, Math.round(Number(values.height) || 0));
    const divisor = gcd(width, height);
    write("W_ratio", clamp(width / divisor, 1, 512));
    write("H_ratio", clamp(height / divisor, 1, 512));
  };
  const size = (width, height) => {
    write("width", snapSize(width)); write("height", snapSize(height));
    state.base = [values.width, values.height];
    write("scale_percent", 100);
  };
  const edited = (release) => {
    if (release) { write("width", snapSize(values.width)); write("height", snapSize(values.height)); }
    state.base = [snapSize(values.width), snapSize(values.height)];
    write("scale_percent", 100); ratios(); custom();
  };
  const presets = () => {
    const options = presetValues(values.custom_presets);
    w.preset.setOption("values", options ?? ["Custom"]);
    if (!options?.includes(values.preset)) custom();
    if (state.status) state.status.textContent = options ? "" : "Presets exceed 64 KiB or 1024 lines, or are not text.";
  };
  // The worker's replicated getValue is not refreshed by a subscription event.
  // Use its supplied scalar, not a stale replica. Pack writes update this local
  // mirror synchronously; delayed programmatic change events cannot recurse.
  const activate = (name, fn) => state.off.push(w[name].on("activate", (value) => { if (!state.dead) { values[name] = value; fn(); } }));
  activate("W_ratio", () => {
    const rw = Math.max(1, Number(values.W_ratio) || 1), rh = Math.max(1, Number(values.H_ratio) || 1);
    const height = Number(values.height) || 8;
    size((height / rh) * rw, height); ratios(); custom();
  });
  activate("H_ratio", () => {
    const rw = Math.max(1, Number(values.W_ratio) || 1), rh = Math.max(1, Number(values.H_ratio) || 1);
    const width = Number(values.width) || 8;
    size(width, (width / rw) * rh); ratios(); custom();
  });
  activate("scale_percent", () => {
    const percent = clamp(Number(values.scale_percent) || 100, 10, 200);
    write("width", snapSize(state.base[0] * percent / 100));
    write("height", snapSize(state.base[1] * percent / 100)); ratios(); custom();
  });
  activate("reset", () => { size(512, 512); ratios(); custom(); timer(() => write("reset", false), 200); });
  activate("swap", () => {
    const width = values.width; write("width", values.height); write("height", width);
    state.base.reverse(); ratios(); custom(); timer(() => write("swap", false), 200);
  });
  activate("preset", () => {
    const parsed = parsePreset(values.preset);
    if (parsed) { size(parsed.w, parsed.h); ratios(); }
  });
  activate("custom_presets", presets);
  // Programmatic writes trigger change, never activate. No change subscription
  // is necessary for these mounted-owned fields; configure reconstructs them.
  for (const name of ["width", "height"]) {
    w[name].setHidden(true);
    w[name].setOption("step2", 32);
  }
  for (const name of ["W_ratio", "H_ratio"]) w[name].setOption("step2", 1);
  // The mounted name is a stable host/worker UI key. Reconfiguration replaces
  // its guest tree/listeners, not the host widget: removing the host widget
  // would detach the already-owned renderer container for this same key.
  node.widgets.mount({
    name: "resolution_dimensions",
    render(container) {
      if (state.dead) return;
      state.container = container;
      const doc = container.ownerDocument;
      const root = doc.createElement("div");
      Object.assign(root.style, { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", padding: "6px" });
      const listen = (el, type, fn) => { el.addEventListener(type, fn); state.off.push(() => el.removeEventListener(type, fn)); };
      for (const name of ["width", "height"]) {
        const label = doc.createElement("label"), input = doc.createElement("input"), drag = doc.createElement("button");
        const caption = doc.createElement("span"); caption.textContent = name; label.append(caption);
        input.type = "number"; input.min = "8"; input.max = "4096"; input.step = "1";
        input.value = String(values[name]); input.setAttribute("aria-label", name);
        input.style.width = "100%";
        drag.type = "button"; drag.textContent = "↔ drag"; drag.setAttribute("aria-label", `Drag ${name}`);
        drag.style.touchAction = "none";
        state.fields[name] = input;
        listen(input, "input", () => {
          const value = Number(input.value);
          if (Number.isFinite(value)) { write(name, clamp(Math.round(value), 8, 4096)); edited(false); }
        });
        listen(input, "change", () => { write(name, snapSize(input.value)); edited(true); });
        listen(drag, "pointerdown", (event) => {
          if (event.button !== 0) return;
          state.drag = { name, id: event.pointerId, x: event.clientX, value: Number(values[name]) };
        });
        listen(drag, "pointermove", (event) => {
          const active = state.drag;
          if (!active || active.name !== name || active.id !== event.pointerId) return;
          write(name, clamp(Math.round(active.value + event.clientX - active.x), 8, 4096)); edited(false);
        });
        listen(drag, "pointerup", (event) => {
          if (state.drag?.name !== name || state.drag.id !== event.pointerId) return;
          state.drag = null; edited(true);
        });
        listen(drag, "pointercancel", (event) => {
          if (state.drag?.name !== name || state.drag.id !== event.pointerId) return;
          state.drag = null; edited(true);
        });
        label.append(input, drag); root.append(label);
      }
      state.status = doc.createElement("span"); state.status.style.gridColumn = "1 / -1";
      state.status.setAttribute("aria-live", "polite"); root.append(state.status); container.append(root); presets();
    },
  });
  // Configured hooks have restored values. Recompute rather than persisting
  // derived base dimensions in pack files/global browser storage.
  write("width", snapSize(values.width)); write("height", snapSize(values.height));
  state.base = [values.width, values.height]; ratios(); presets();
  const selected = parsePreset(values.preset);
  if (selected && (snapSize(selected.w) !== values.width || snapSize(selected.h) !== values.height)) custom();
  timer(presets, 100);
}

comfy.defs.extend("ResolutionAndRatio", (builder) => {
  builder.onCreated(install);
  builder.onConfigured(install);
  builder.onRemoved((node) => dispose(states.get(keyOf(node))));
});

export { snapSize, parsePreset, presetValues };
