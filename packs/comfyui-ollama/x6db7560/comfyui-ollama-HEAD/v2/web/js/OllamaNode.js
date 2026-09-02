import { comfy } from "/comfy/api/v2.js";


const TARGETS = [
  "OllamaGenerate",
  "OllamaGenerateAdvance",
  "OllamaVision",
  "OllamaConnectivityV2",
];
const instances = new Map();


function nodeKey(node) {
  return `${String(node.graphId ?? "")}:${String(node.id)}`;
}


comfy.defs.extend(TARGETS, (builder) => {
  builder.onCreated(async (node) => {
    const urlWidget = node.widgets.get("url");
    const modelWidget = node.widgets.get("model");
    if (!urlWidget || !modelWidget) return;

    const refresh = builder.def.type === "OllamaConnectivityV2"
      ? node.widgets.add({
          type: "button",
          name: "ollama_reconnect",
          value: null,
          serialize: false,
        })
      : undefined;
    refresh?.setLabel("🔄 Reconnect");

    const state = { generation: 0, subscriptions: [] };
    instances.set(nodeKey(node), state);

    const updateModels = async () => {
      const generation = ++state.generation;
      refresh?.setDisabled(true);
      refresh?.setLabel("⏳ Fetching...");
      try {
        const models = await comfy.integrations.ollama.listModels({
          endpoint: String(urlWidget.getValue() || ""),
        });
        if (generation !== state.generation) return;
        const values = Array.isArray(models)
          ? models.filter((value) => typeof value === "string")
          : [];
        const previous = String(modelWidget.getValue() || "");
        modelWidget.setOption("values", values);
        if (values.includes(previous)) {
          modelWidget.setValue(previous);
        } else if (values.length > 0) {
          modelWidget.setValue(values[0]);
        }
      } catch (error) {
        if (generation !== state.generation) return;
        console.error("Ollama model discovery failed", error);
        comfy.commands.notify({
          severity: "error",
          summary: "Ollama connection error",
          detail: "Make sure the configured Ollama endpoint is available",
          life: 5000,
        });
      } finally {
        if (generation === state.generation) {
          refresh?.setDisabled(false);
          refresh?.setLabel("🔄 Reconnect");
        }
      }
    };

    state.subscriptions.push(urlWidget.on("change", updateModels));
    if (refresh) {
      state.subscriptions.push(refresh.on("activate", updateModels));
    }
    await updateModels();
  });

  builder.onRemoved((node) => {
    const state = instances.get(nodeKey(node));
    if (!state) return;
    state.generation += 1;
    for (const unsubscribe of state.subscriptions) unsubscribe();
    instances.delete(nodeKey(node));
  });
});
