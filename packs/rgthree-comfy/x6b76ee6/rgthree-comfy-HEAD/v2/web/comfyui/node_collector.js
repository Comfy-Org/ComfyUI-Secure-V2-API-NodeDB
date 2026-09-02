import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { PassThroughFollowing } from "./base_any_input_connected_node.js";
import { defineCollectorNode } from "./base_node_collector.js";

// Node Collector — a virtual passthrough that gathers many links into one output — plus
// the deprecated "Node Combiner" and its in-place upgrade path.
//
// Neither node resolves to anything: both were `isVirtualNode` with no `applyToGraph`,
// so `execution: 'frontend'` with no `resolve` is exactly what they were. Everything
// downstream of a Collector is itself frontend-only.
//
// COSMETIC: (8) the "‼️ Update to Node Collector" entry was spliced into
//   `getExtraMenuOptions` at `options.length - 1`, i.e. above core's last item. It is
//   present; `b.addMenuItem` appends after every core entry, so it sits lower.
//
// WIRE FORMAT: unchanged for both types. `serialize_widgets` stays off, so the
// Combiner's deprecation notice occupies no `widgets_values` slot, exactly as the
// `ComfyWidgets["STRING"]` textarea did on a node that never set the flag.
const COMBINER_TYPE = "Node Combiner (rgthree)";
const COMBINER_TITLE = "‼️ Node Combiner [DEPRECATED]";
const NOTICE = 'The Node Combiner has been renamed to Node Collector. You can right-click and select "Update to Node Collector" to attempt to automatically update.';
// Rebuilds the node as a Collector, keeping position, size, properties and every link.
// New link ids are allocated, as they were originally: the old routine also rebuilt
// every link onto a freshly created node.
function updateCombinerToCollector(node) {
    const outgoing = [];
    for (const output of node.outputs.all()) {
        for (const link of output.links()) {
            outgoing.push({ from: output.index, toNodeId: link.targetNodeId, toIndex: link.targetIndex });
        }
    }
    const incoming = [];
    for (const input of node.inputs.all()) {
        const link = input.link();
        if (link) {
            incoming.push({ fromNodeId: link.sourceNodeId, fromIndex: link.sourceIndex, to: input.index });
        }
    }
    comfy.graph.batch(() => {
        const title = node.getTitle();
        const collector = comfy.graph.add(NodeTypesString.NODE_COLLECTOR, {
            title: title === COMBINER_TITLE ? undefined : title.replace("‼️ ", ""),
            position: node.getPosition(),
        });
        collector.setSize(node.getSize());
        for (const [key, value] of Object.entries(node.getProperties())) {
            collector.setProperty(key, value);
        }
        // The stabilization pass grows the input list as slots fill, but it runs on a
        // debounce and these links need somewhere to land now.
        const needed = incoming.reduce((most, link) => Math.max(most, link.to + 1), 1);
        while (collector.inputs.length < needed) {
            collector.inputs.add("", "*");
        }
        for (const link of incoming) {
            const source = comfy.graph.node(link.fromNodeId)?.outputs.at(link.fromIndex);
            if (!source) {
                throw new Error(`[rgthree.NodeCollector] lost the link from ${link.fromNodeId}:${link.fromIndex}.`);
            }
            source.connectTo(collector.id, { index: link.to });
        }
        for (const link of outgoing) {
            const source = collector.outputs.at(link.from);
            if (!source) {
                throw new Error(`[rgthree.NodeCollector] the new collector has no output ${link.from}.`);
            }
            source.connectTo(link.toNodeId, { index: link.toIndex });
        }
        node.remove();
    });
}
defineCollectorNode({
    type: NodeTypesString.NODE_COLLECTOR,
    following: PassThroughFollowing.REROUTE_ONLY,
    outputs: [{ name: "Output", type: "*" }],
});
defineCollectorNode({
    type: COMBINER_TYPE,
    title: COMBINER_TITLE,
    following: PassThroughFollowing.REROUTE_ONLY,
    outputs: [{ name: "Output", type: "*" }],
    onCreated(node) {
        // `ComfyWidgets["STRING"](…, {multiline: true})` followed by writes to
        // `note.inputEl.style` — a read-only styled textarea the pack builds itself,
        // which is what `mount` hands over.
        node.widgets.mount({
            name: "last_seed",
            render(container) {
                const inputEl = document.createElement("textarea");
                inputEl.value = NOTICE;
                inputEl.readOnly = true;
                inputEl.style.width = "100%";
                inputEl.style.height = "100%";
                inputEl.style.backgroundColor = "#332222";
                inputEl.style.fontWeight = "bold";
                inputEl.style.fontStyle = "italic";
                inputEl.style.opacity = "0.8";
                container.appendChild(inputEl);
            },
        });
    },
    onConfigured(node) {
        const title = node.getTitle();
        if (title !== COMBINER_TITLE && !title.startsWith("‼️")) {
            node.setTitle(`‼️ ${title}`);
        }
    },
    menuItems: [
        {
            label: "‼️ Update to Node Collector",
            run: updateCombinerToCollector,
        },
    ],
});
