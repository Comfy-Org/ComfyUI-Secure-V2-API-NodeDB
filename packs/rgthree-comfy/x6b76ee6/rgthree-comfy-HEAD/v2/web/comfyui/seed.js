import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { exposeActions } from "./base_node.js";
const LAST_SEED_BUTTON_LABEL = "♻️ (Use Last Queued Seed)";
const SPECIAL_SEED_RANDOM = -1;
const SPECIAL_SEED_INCREMENT = -2;
const SPECIAL_SEED_DECREMENT = -3;
const SPECIAL_SEEDS = [SPECIAL_SEED_RANDOM, SPECIAL_SEED_INCREMENT, SPECIAL_SEED_DECREMENT];
// Handles hold no arbitrary properties, so the last queued seed lives here and the
// entry is dropped in onRemoved.
const lastSeedByNode = new Map();
// One roll per prompt build, shared by its two halves: graphToPrompt serializes the
// embedded workflow first and collects the prompt inputs second, so the first writes
// the entry and the second consumes it.
const rolledSeedByNode = new Map();
// Drops a roll the prompt pass never consumed — a muted node, or a build that threw.
// `promptQueued` does not fire on a failed queue, so a fresh build overwriting the
// entry is what actually keeps it from ever being read stale.
comfy.queue.onAfterRun(() => {
    rolledSeedByNode.clear();
});
function seedWidgetOf(node) {
    const seedWidget = node.widgets.get("seed");
    if (!seedWidget) {
        throw new Error(`[rgthree.Seed] node ${node.id} has no "seed" widget.`);
    }
    return seedWidget;
}
// `exposedActions` / `handleAction`, which the Fast Actions Button invokes on this node
// from a neighbour. Keyed by type rather than hung on the class, since a handle has no
// `constructor` — see base_node.js.
exposeActions(NodeTypesString.SEED, ["Randomize Each Time", "Use Last Queued Seed"], (node, action) => {
    const seedWidget = seedWidgetOf(node);
    if (action === "Randomize Each Time") {
        seedWidget.setValue(SPECIAL_SEED_RANDOM);
    }
    else if (action === "Use Last Queued Seed") {
        const lastSeed = lastSeedByNode.get(node.id);
        seedWidget.setValue(lastSeed != null ? lastSeed : seedWidget.getValue());
        const lastSeedButton = node.widgets.get("USE_LAST_SEED");
        if (!lastSeedButton) {
            throw new Error(`[rgthree.Seed] node ${node.id} has no "USE_LAST_SEED" widget.`);
        }
        lastSeedButton.setLabel(LAST_SEED_BUTTON_LABEL);
        lastSeedButton.setDisabled(true);
    }
});
comfy.defs.extend(NodeTypesString.SEED, (b) => {
    function generateRandomSeed(node) {
        let step = seedWidgetOf(node).getOptions()?.step || 1;
        const randomMin = Number(node.getProperty("randomMin") || 0);
        const randomMax = Number(node.getProperty("randomMax") || 1125899906842624);
        const randomRange = (randomMax - randomMin) / (step / 10);
        let seed = Math.floor(Math.random() * randomRange) * (step / 10) + randomMin;
        if (SPECIAL_SEEDS.includes(seed)) {
            seed = 0;
        }
        return seed;
    }
    function getSeedToUse(node) {
        const inputSeed = Number(seedWidgetOf(node).getValue());
        const lastSeed = lastSeedByNode.get(node.id);
        let seedToUse = null;
        if (SPECIAL_SEEDS.includes(inputSeed)) {
            if (typeof lastSeed === "number" && !SPECIAL_SEEDS.includes(lastSeed)) {
                if (inputSeed === SPECIAL_SEED_INCREMENT) {
                    seedToUse = lastSeed + 1;
                }
                else if (inputSeed === SPECIAL_SEED_DECREMENT) {
                    seedToUse = lastSeed - 1;
                }
            }
            if (seedToUse == null || SPECIAL_SEEDS.includes(seedToUse)) {
                seedToUse = generateRandomSeed(node);
            }
        }
        return seedToUse !== null && seedToUse !== void 0 ? seedToUse : inputSeed;
    }
    function addLastSeedValue(node) {
        if (node.widgets.get("last_seed")) {
            return;
        }
        let stopWatching = null;
        node.widgets.mount({
            name: "last_seed",
            defaultValue: "",
            serialize: true,
            render(container, value) {
                const inputEl = document.createElement("textarea");
                inputEl.readOnly = true;
                inputEl.style.width = "100%";
                inputEl.style.height = "100%";
                inputEl.style.fontSize = "0.75rem";
                inputEl.style.textAlign = "center";
                inputEl.value = String(value.get());
                container.appendChild(inputEl);
                stopWatching = value.onChange((v) => {
                    inputEl.value = String(v);
                });
            },
            destroy() {
                stopWatching === null || stopWatching === void 0 ? void 0 : stopWatching();
                stopWatching = null;
            },
        });
    }
    b.onCreated((node) => {
        // onCreated fires when the node joins a graph, which can happen more than
        // once for one node; the old onNodeCreated ran only at construction, and
        // widgets.add() throws on a duplicate name.
        if (node.widgets.get("🎲 Randomize Each Time")) {
            return;
        }
        console.log("SEED NODE STARTED!");
        node.setSerializeWidgets(true);
        node.setProperty("randomMax", 1125899906842624);
        node.setProperty("randomMin", 0);
        const seedWidget = seedWidgetOf(node);
        seedWidget.setValue(SPECIAL_SEED_RANDOM);
        node.widgets.remove("control_after_generate");
        node.widgets
            .add({ type: "button", name: "🎲 Randomize Each Time", value: "", options: { serialize: false } })
            .on("activate", () => {
            seedWidget.setValue(SPECIAL_SEED_RANDOM);
        });
        node.widgets
            .add({ type: "button", name: "🎲 New Fixed Random", value: "", options: { serialize: false } })
            .on("activate", () => {
            seedWidget.setValue(generateRandomSeed(node));
        });
        const lastSeedButton = node.widgets.add({
            type: "button",
            name: "USE_LAST_SEED",
            value: "okay",
            options: { width: 50, serialize: false },
        });
        lastSeedButton.on("activate", () => {
            const lastSeed = lastSeedByNode.get(node.id);
            seedWidget.setValue(lastSeed != null ? lastSeed : seedWidget.getValue());
            lastSeedButton.setLabel(LAST_SEED_BUTTON_LABEL);
            lastSeedButton.setDisabled(true);
        });
        lastSeedButton.setLabel(LAST_SEED_BUTTON_LABEL);
        lastSeedButton.setDisabled(true);
        // The node in one hook. The widget keeps the sentinel the user typed, and so
        // does the saved workflow, while the queued prompt and the workflow copy
        // embedded in it both carry the seed actually rolled for this run — which is
        // what `handleApiHijacking` used to do by rewriting both halves of the payload
        // from a single roll, after graphToPrompt had built them.
        seedWidget.on("beforeSerialize", (e) => {
            if (e.context === "workflow") {
                return;
            }
            if (e.context === "embedded") {
                // graphToPrompt serializes the embedded workflow before it walks the
                // widgets for the prompt, so the roll happens here and the prompt pass
                // reuses it — one seed per build, in both halves, or the image records
                // a run that never happened. Muted and bypassed nodes are skipped, as
                // handleApiHijacking skipped them: nothing runs, so nothing to record.
                const mode = node.getMode();
                if (mode === "never" || mode === "bypass") {
                    return;
                }
                const rolled = getSeedToUse(node);
                rolledSeedByNode.set(node.id, rolled);
                e.setSerializedValue(rolled);
                return;
            }
            const rolled = rolledSeedByNode.get(node.id);
            rolledSeedByNode.delete(node.id);
            const seedToUse = rolled !== undefined ? rolled : getSeedToUse(node);
            e.setSerializedValue(seedToUse);
            lastSeedByNode.set(node.id, seedToUse);
            if (seedToUse != seedWidget.getValue()) {
                lastSeedButton.setLabel(`♻️ ${seedToUse}`);
                lastSeedButton.setDisabled(false);
            }
            else {
                lastSeedButton.setLabel(LAST_SEED_BUTTON_LABEL);
                lastSeedButton.setDisabled(true);
            }
            const lastSeedValue = node.widgets.get("last_seed");
            if (lastSeedValue) {
                lastSeedValue.setValue(`Last Seed: ${seedToUse}`);
            }
        });
    });
    b.onConfigured((node) => {
        if (node.getProperty("showLastSeed")) {
            addLastSeedValue(node);
        }
    });
    b.onExecuted((node, result) => {
        console.log(`SEED ON EXECUTED. #${node.id}.`, result.raw);
    });
    b.onPropertyChanged((node, e) => {
        if (e.name === "randomMax") {
            e.setValue(Math.min(1125899906842624, Number(e.value)));
        }
        else if (e.name === "randomMin") {
            e.setValue(Math.max(-1125899906842624, Number(e.value)));
        }
    });
    b.onRemoved((node) => {
        console.log("SEED NODE onRemoved!");
        lastSeedByNode.delete(node.id);
        rolledSeedByNode.delete(node.id);
    });
    b.addMenuItem({
        label: "Show/Hide Last Seed Value",
        run: (node) => {
            node.setProperty("showLastSeed", !node.getProperty("showLastSeed"));
            if (node.getProperty("showLastSeed")) {
                addLastSeedValue(node);
            }
            else {
                node.widgets.remove("last_seed");
            }
        },
    });
});
// COSMETIC: no property metadata — `RgthreeSeed["@randomMax"] = {type: "number"}`
//   told the properties panel to edit those two as numbers. They still work, still
//   save, and are still clamped by `onPropertyChanged`; they are free-text fields.
// REFUSED, not a gap: `addConnectionLayoutSupport` put the input and output on chosen
//   sides by patching `getConnectionPos` on the node class. Deciding where the renderer
//   draws a socket is refused rather than pending — see utils.js.
// COSMETIC: (8) node menu entries are appended. "Show/Hide Last Seed Value" was
//   spliced in at `options.length - 1`, so it sat above the last core entry; it is
//   present, one place further down.
// WIRE FORMAT: unchanged for the saved workflow — `widgets_values` is still
//   `[seed, "", "", "okay"]` (the three buttons pass `options.serialize` only, so
//   they keep their slots), plus a trailing string when the last-seed readout is
//   shown. A save serializes outside `graphToPrompt`, so the seed slot keeps the
//   sentinel there exactly as before. The embedded copy does now carry the rolled
//   seed in that slot, which is the point — but ComfyUI's "Export" menu item writes
//   `graphToPrompt().workflow` to a file, so that export carries the rolled seed
//   too. The original hijacked `api.queuePrompt`, which an export never reaches.
//   One divergence: the readout is refreshed from inside the seed widget's
//   own beforeSerialize handler, which runs *during* the prompt build rather than
//   after it, so the `last_seed` input in that prompt now carries this run's text
//   instead of the previous run's. The backend does not declare `last_seed`.
