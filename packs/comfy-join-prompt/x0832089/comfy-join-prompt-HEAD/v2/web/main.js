import { comfy } from "/comfy/api/v2.js";

const TYPE = "jupo.JoinPrompt.JoinPrompt";
const states = new Map();
const key = (node) => JSON.stringify([node.graphId, node.id]);
const eligible = (node) => !!node && (node.type === TYPE || node.comfyClass === TYPE);
const alive = (state) => !state.removed && !!state.node.snapshot();
const bounded = (config) => new TextEncoder().encode(JSON.stringify(config)).length <= 65536;

function readConfig(node, data = {}) {
  let saved = data.jupoJoinPrompt;
  if (!saved || typeof saved !== "object") saved = data.properties ?? node.getProperties();
  let options = {};
  try { options = JSON.parse(node.widgets.get("options")?.getValue() || "{}"); } catch {}
  const delimiter = saved?.delimiter ?? options?.delimiter ?? "";
  const cleanup = saved?.cleanup ?? options?.cleanup ?? false;
  return { delimiter: typeof delimiter === "string" ? delimiter : "", cleanup: !!cleanup };
}

function sync(state) {
  if (!alive(state) || state.syncing) return;
  state.syncing = true;
  try {
    state.node.setProperty("delimiter", state.config.delimiter);
    state.node.setProperty("cleanup", state.config.cleanup);
    const widget = state.node.widgets.get("options");
    widget?.setHidden(true);
    widget?.setValue(JSON.stringify(state.config));
  } finally { state.syncing = false; }
}

function initialize(node, data) {
  const id = key(node);
  const previous = states.get(id);
  previous?.dialog?.close();
  if (previous) previous.removed = true;
  const state = { node, config: readConfig(node, data), removed: false, syncing: false, dialog: null };
  states.set(id, state);
  const socket = node.inputs.byName("options");
  if (socket) node.inputs.remove(socket.id);
  sync(state);
  return state;
}

function open(node) {
  if (!eligible(node) || !node.snapshot()) return;
  const state = states.get(key(node)) ?? initialize(node);
  state.dialog?.close();
  let active = true;
  const disposers = [];
  const dispose = () => { active = false; for (const off of disposers.splice(0)) off(); };
  const handle = comfy.ui.showDialog({
    key: `jupo.JoinPrompt.Config.${encodeURIComponent(key(node))}`,
    title: "Join Prompt Config",
    render(container) {
      const doc = container.ownerDocument;
      const create = (tag, text) => { const el = doc.createElement(tag); if (text) el.textContent = text; return el; };
      const bind = (el, event, fn) => { el.addEventListener(event, fn); disposers.push(() => el.removeEventListener(event, fn)); };
      const delimiterLabel = create("label", "delimiter");
      const delimiter = create("input");
      delimiter.type = "text"; delimiter.value = state.config.delimiter; delimiter.maxLength = 65536;
      delimiterLabel.append(delimiter);
      const cleanupLabel = create("label", "cleanup");
      const cleanup = create("input"); cleanup.type = "checkbox"; cleanup.checked = state.config.cleanup;
      cleanupLabel.append(cleanup);
      const close = create("button", "Close"); close.type = "button";
      bind(delimiter, "change", () => {
        if (!active || !alive(state)) return;
        if (!bounded({ ...state.config, delimiter: delimiter.value })) { delimiter.value = state.config.delimiter; return; }
        state.config.delimiter = delimiter.value; sync(state);
      });
      bind(cleanup, "change", () => {
        if (!active || !alive(state)) return;
        if (!bounded({ ...state.config, cleanup: cleanup.checked })) { cleanup.checked = state.config.cleanup; return; }
        state.config.cleanup = cleanup.checked; sync(state);
      });
      bind(close, "click", () => state.dialog?.close());
      container.append(delimiterLabel, cleanupLabel, close);
    },
    onKeyDown(event) { if (event.key === "Escape") state.dialog?.close(); },
    destroy: dispose,
  });
  if (!active || !alive(state)) handle.close();
  else state.dialog = handle;
}

comfy.defs.extend(TYPE, (builder) => {
  builder.hideWidget("options");
  builder.onCreated((node) => initialize(node));
  builder.onConfigured((node, data) => initialize(node, data));
  builder.onSerialize((node) => ({ jupoJoinPrompt: { ...(states.get(key(node))?.config ?? readConfig(node)) } }));
  builder.onPropertyChanged((node, event) => {
    const state = states.get(key(node));
    if (!state || state.syncing || !alive(state)) return;
    if (event.name === "delimiter") {
      if (typeof event.value !== "string" || !bounded({ ...state.config, delimiter: event.value })) { event.reject(); return; }
      state.config.delimiter = event.value;
    } else if (event.name === "cleanup") {
      if (!bounded({ ...state.config, cleanup: !!event.value })) { event.reject(); return; }
      state.config.cleanup = !!event.value;
    }
    else return;
    sync(state);
  });
  builder.onRemoved((node) => {
    const state = states.get(key(node));
    if (state) { state.removed = true; state.dialog?.close(); states.delete(key(node)); }
  });
  builder.addMenuItem({ label: "Open Config Dialog", when: eligible, run: open });
});

comfy.commands.register({
  id: "jupo.JoinPrompt.OpenConfigDialog", label: "Open JoinPrompt Config", scope: "canvas",
  run() { const node = comfy.graph.selection().find(eligible); if (node) open(node); },
});
