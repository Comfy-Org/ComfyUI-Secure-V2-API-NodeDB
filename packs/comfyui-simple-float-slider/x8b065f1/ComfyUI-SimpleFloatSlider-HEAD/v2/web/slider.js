import { comfy } from "/comfy/api/v2.js";

const TYPES = {
  ConfigurableIntSlider: {
    integer: true,
    configurable: true,
    defaultValue: 50,
    defaultMin: 0,
    defaultMax: 100,
    defaultPrecision: 0,
    defaultStep: 1,
  },
  SimpleFloatSlider: {
    integer: false,
    configurable: false,
    defaultValue: 0.5,
    defaultMin: 0,
    defaultMax: 1,
    defaultPrecision: 2,
    defaultStep: 0.01,
  },
  ConfigurableFloatSlider: {
    integer: false,
    configurable: true,
    defaultValue: 0.5,
    defaultMin: 0,
    defaultMax: 1,
    defaultPrecision: 2,
    defaultStep: 0.01,
  },
};

const states = new Map();

function stateKey(node) {
  return `${node.graphId ?? "visible"}:${node.id}`;
}

function finiteNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function integerStep(value) {
  const parsed = Math.round(finiteNumber(value, 1));
  return parsed < 1 ? 1 : parsed;
}

function precisionStep(precision) {
  return precision === 0 ? 1 : Number((10 ** -precision).toFixed(precision));
}

function snapToGrid(value, base, step) {
  if (!(step > 0)) return value;
  return Number((base + Math.round((value - base) / step) * step).toFixed(10));
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function widgetNumber(widget, fallback, integer = false) {
  const parsed = finiteNumber(widget?.getValue(), fallback);
  return integer ? Math.round(parsed) : parsed;
}

function formatValue(state, value) {
  return state.spec.integer ? String(Math.round(value)) : value.toFixed(state.precision);
}

function writeMountedValue(state, value) {
  if (!state.mountedValue || Object.is(state.mountedValue.get(), value)) return;
  state.writing = true;
  try {
    state.mountedValue.set(value);
  } finally {
    state.writing = false;
  }
}

function renderValue(state) {
  if (!state.slider || !state.display) return;
  state.slider.min = String(state.minimum);
  state.slider.max = String(state.maximum);
  state.slider.step = "any";
  state.slider.value = String(state.value);
  state.display.textContent = formatValue(state, state.value);
  const denominator = state.maximum - state.minimum;
  const percent = denominator === 0
    ? 0
    : ((state.value - state.minimum) / denominator) * 100;
  const bounded = Math.max(0, Math.min(100, percent));
  state.slider.style.setProperty("--slider-fill", `${bounded}%`);
}

function applyBounds(state, commit = true) {
  const next = clamp(state.rawValue, state.minimum, state.maximum);
  state.value = state.spec.integer ? Math.round(next) : next;
  if (commit) writeMountedValue(state, state.value);
  renderValue(state);
}

function syncConfiguration(state, regrid = false) {
  const { spec, config } = state;
  state.minimum = widgetNumber(config.minimum, spec.defaultMin, spec.integer);
  state.maximum = widgetNumber(config.maximum, spec.defaultMax, spec.integer);
  state.precision = spec.integer
    ? 0
    : Math.max(0, Math.min(4, widgetNumber(config.precision, spec.defaultPrecision, true)));
  if (spec.integer) {
    state.step = integerStep(config.step?.getValue() ?? spec.defaultStep);
  } else {
    const candidate = widgetNumber(config.step, spec.defaultStep);
    state.step = candidate > 0 ? candidate : state.step;
  }
  if (regrid) {
    state.rawValue = snapToGrid(state.rawValue, state.minimum, state.step);
    if (spec.integer) state.rawValue = Math.round(state.rawValue);
    state.dragAnchor = undefined;
  }
  applyBounds(state);
}

function setConfigVisible(state, visible) {
  state.configVisible = Boolean(visible);
  for (const widget of state.configWidgets) widget?.setHidden(!state.configVisible);
  if (state.toggle) {
    state.toggle.textContent = state.configVisible ? "▴ configure" : "▾ configure";
  }
}

function commitRawValue(state, value) {
  const parsed = finiteNumber(value, state.value);
  state.rawValue = state.spec.integer ? Math.round(parsed) : parsed;
  state.dragAnchor = undefined;
  applyBounds(state);
}

function mountedInput(state, doc) {
  const wrap = style(doc.createElement("div"), {
    width: "100%",
    padding: "4px 10px 8px",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "7px",
    color: "#e8eaf0",
    fontFamily: "monospace",
  });
  const display = style(doc.createElement("button"), {
    minWidth: "100px",
    padding: "3px 16px",
    border: "0",
    borderRadius: "6px",
    background: "rgba(0, 0, 0, 0.30)",
    color: "#e8eaf0",
    fontFamily: "monospace",
    fontSize: "28px",
    fontWeight: "700",
    letterSpacing: "2px",
    cursor: "pointer",
  });
  display.type = "button";
  display.setAttribute("aria-label", "Edit slider value");
  const slider = style(doc.createElement("input"), {
    width: "100%",
    height: "18px",
    cursor: "pointer",
    accentColor: "#5ac8ff",
  });
  slider.type = "range";
  slider.setAttribute("aria-label", "Slider value");
  state.display = display;
  state.slider = slider;

  slider.addEventListener("input", () => {
    if (state.disposed) return;
    if (state.dragAnchor === undefined) state.dragAnchor = state.value;
    const candidate = finiteNumber(slider.value, state.value);
    const snapped = snapToGrid(candidate, state.dragAnchor, state.step);
    state.rawValue = state.spec.integer ? Math.round(snapped) : snapped;
    applyBounds(state);
  });
  slider.addEventListener("change", () => {
    state.dragAnchor = undefined;
  });

  const wheel = (event) => {
    if (state.disposed) return;
    event.preventDefault();
    event.stopPropagation();
    const direction = event.deltaY < 0 ? 1 : -1;
    let next = clamp(state.value + direction * state.step, state.minimum, state.maximum);
    if (state.spec.integer) next = Math.round(next);
    else next = Number(next.toFixed(state.precision));
    commitRawValue(state, next);
  };
  display.addEventListener("wheel", wheel, { passive: false });
  slider.addEventListener("wheel", wheel, { passive: false });

  display.addEventListener("click", () => {
    if (state.disposed || state.editor) return;
    const editor = style(doc.createElement("input"), {
      width: "130px",
      padding: "2px 8px",
      border: "1.5px solid rgba(90, 190, 255, 0.75)",
      borderRadius: "6px",
      outline: "none",
      background: "rgba(0, 0, 0, 0.55)",
      color: "#e8eaf0",
      fontFamily: "monospace",
      fontSize: "24px",
      textAlign: "center",
    });
    editor.type = "number";
    editor.value = formatValue(state, state.value);
    editor.step = String(state.step);
    state.editor = editor;
    display.replaceWith(editor);
    editor.focus();
    editor.select();

    let done = false;
    const finish = (commit) => {
      if (done) return;
      done = true;
      if (commit) {
        const parsed = Number(editor.value);
        if (Number.isFinite(parsed)) {
          let next = clamp(parsed, state.minimum, state.maximum);
          if (state.spec.integer) next = Math.trunc(next);
          else next = Number(next.toFixed(state.precision));
          commitRawValue(state, next);
        }
      }
      state.editor = undefined;
      editor.replaceWith(display);
      renderValue(state);
    };
    editor.addEventListener("blur", () => finish(true));
    editor.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        finish(true);
      } else if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        finish(false);
      }
    });
  });

  wrap.append(display, slider);
  if (state.spec.configurable) {
    const toggle = style(doc.createElement("button"), {
      padding: "0",
      border: "0",
      background: "transparent",
      color: "rgba(90, 190, 255, 0.75)",
      fontFamily: "monospace",
      fontSize: "10px",
      letterSpacing: "1px",
      cursor: "pointer",
    });
    toggle.type = "button";
    toggle.addEventListener("click", () => setConfigVisible(state, !state.configVisible));
    state.toggle = toggle;
    wrap.append(toggle);
  }
  setConfigVisible(state, false);
  renderValue(state);
  return wrap;
}

function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  for (const unsubscribe of state.unsubscribers.splice(0)) unsubscribe();
  if (states.get(state.key) === state) states.delete(state.key);
  state.mountedValue = undefined;
  state.slider = undefined;
  state.display = undefined;
  state.editor = undefined;
  state.toggle = undefined;
}

function install(node, spec) {
  const key = stateKey(node);
  dispose(states.get(key));
  const original = node.widgets.get("value");
  const initial = finiteNumber(original?.getValue(), spec.defaultValue);
  const config = {
    minimum: node.widgets.get("min_value"),
    maximum: node.widgets.get("max_value"),
    precision: node.widgets.get("precision"),
    step: node.widgets.get("step"),
  };
  const state = {
    key,
    node,
    spec,
    config,
    configWidgets: [config.minimum, config.maximum, config.precision, config.step].filter(Boolean),
    minimum: spec.defaultMin,
    maximum: spec.defaultMax,
    precision: spec.defaultPrecision,
    step: spec.defaultStep,
    rawValue: spec.integer ? Math.round(initial) : initial,
    value: initial,
    dragAnchor: undefined,
    configVisible: false,
    writing: false,
    disposed: false,
    mountedValue: undefined,
    mount: undefined,
    slider: undefined,
    display: undefined,
    editor: undefined,
    toggle: undefined,
    unsubscribers: [],
  };
  states.set(key, state);
  node.widgets.remove("value");
  state.mount = node.widgets.mount({
    name: "value",
    height: spec.configurable ? 81 : 66,
    defaultValue: state.rawValue,
    serialize: true,
    sendToPrompt: true,
    render(container, mountedValue) {
      state.mountedValue = mountedValue;
      state.unsubscribers.push(mountedValue.onChange((value) => {
        if (state.disposed || state.writing) return;
        state.rawValue = finiteNumber(value, spec.defaultValue);
        if (spec.integer) state.rawValue = Math.round(state.rawValue);
        state.dragAnchor = undefined;
        // Workflow restoration may deliver the value before its saved bounds.
        // Keep the authored raw value and wait for configuration to settle
        // before writing a clamped value back into the workflow cell.
        applyBounds(state, false);
      }));
      container.replaceChildren(mountedInput(state, container.ownerDocument));
    },
    destroy() {
      dispose(state);
    },
  });
  node.widgets.move("value", 0);
  node.setSizeConstraints({ minWidth: 220, autoHeight: true });

  for (const widget of [config.minimum, config.maximum, config.precision]) {
    if (widget) state.unsubscribers.push(widget.on("change", () => syncConfiguration(state)));
  }
  if (config.step) {
    state.unsubscribers.push(config.step.on("change", () => syncConfiguration(state, true)));
  }
  syncConfiguration(state);
  setConfigVisible(state, false);
  return state;
}

for (const [nodeType, spec] of Object.entries(TYPES)) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => install(node, spec));
    builder.onConfigured((node) => {
      const state = states.get(stateKey(node));
      if (!state || state.disposed) return;
      // MountedValue.onChange already captured the restored value. Do not read
      // the currently clamped host cell here: a bound-change notification may
      // have arrived between value restoration and this configured hook.
      syncConfiguration(state);
      setConfigVisible(state, false);
    });
    builder.onRemoved((node) => dispose(states.get(stateKey(node))));
  });
}
