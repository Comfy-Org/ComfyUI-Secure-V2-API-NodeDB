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
//
// `comfy.graph.replace` does the rebuild: position, a title the user changed, colours,
// mode, the properties both types declare and the size carry over, every outgoing link
// and every incoming link with a slot on the new node is re-made, and it is one undo
// step. A fresh Collector has a single input, so a link into the Combiner's second or
// later input would have no slot. The upgrade therefore leaves a claim, which the new
// Collector's `onCreated` takes (`claimUpgrade`): it grows the inputs and connects what is
// still unconnected. In process, `onCreated` runs inside `replace`, before the links are
// re-made, so every link gets its own slot. Under sandbox guest c6b97a15 it runs after
// the host has answered, when `replace` has already dropped those links, and the claim
// re-makes them.
//
// Revision 5 added the Collector with `graph.add` and wired it at once. The guest answers
// a just-added node asynchronously and, until then, its input list reads as empty, so
// the loop that grew it never ended.
const UPGRADE_CLAIM_MS = 3000;
const pendingUpgrades = [];
function dropUpgrade(upgrade) {
    const index = pendingUpgrades.indexOf(upgrade);
    if (index >= 0) {
        pendingUpgrades.splice(index, 1);
    }
}
function updateCombinerToCollector(node) {
    const incoming = [];
    for (const input of node.inputs.all()) {
        const link = input.link();
        if (link) {
            incoming.push({ fromNodeId: link.sourceNodeId, fromIndex: link.sourceIndex, to: input.index });
        }
    }
    const title = node.getTitle();
    const upgrade = { graphId: node.graphId ?? "", incoming, expires: Date.now() + UPGRADE_CLAIM_MS };
    pendingUpgrades.push(upgrade);
    comfy.graph.batch(() => {
        // `replace` matches a link to the new node's slots by name before index. These
        // inputs are named after their sources' titles, so an empty one would land on the
        // Collector's unnamed first input and one named "Output" would be dropped. Each is
        // named by its index for the rebuild; the Collector renames its inputs as it
        // stabilizes.
        for (const input of node.inputs.all()) {
            input.modify({ name: String(input.index) });
        }
        let collector;
        try {
            collector = comfy.graph.replace(node.id, NodeTypesString.NODE_COLLECTOR);
        }
        finally {
            if (!collector) {
                dropUpgrade(upgrade);
            }
        }
        // `replace` keeps only a title the user changed; the original also took the "‼️ "
        // marker off it.
        if (collector && title !== COMBINER_TITLE) {
            collector.setTitle(title.replace("‼️ ", ""));
        }
    });
}
function claimUpgrade(collector) {
    const now = Date.now();
    for (const upgrade of [...pendingUpgrades]) {
        if (upgrade.expires < now) {
            dropUpgrade(upgrade);
        }
    }
    const upgrade = pendingUpgrades.find((u) => u.graphId === (collector.graphId ?? ""));
    if (!upgrade) {
        return;
    }
    dropUpgrade(upgrade);
    const needed = upgrade.incoming.reduce((most, link) => Math.max(most, link.to + 1), 1);
    for (let count = collector.inputs.length; count < needed; count++) {
        collector.inputs.add("", "*");
    }
    for (const link of upgrade.incoming) {
        if (collector.inputs.at(link.to)?.isConnected) {
            continue;
        }
        const source = comfy.graph.node(link.fromNodeId)?.outputs.at(link.fromIndex);
        if (!source) {
            console.warn(`[rgthree.NodeCollector] lost the link from ${link.fromNodeId}:${link.fromIndex}.`);
            continue;
        }
        source.connectTo(collector.id, { index: link.to });
    }
}
defineCollectorNode({
    type: NodeTypesString.NODE_COLLECTOR,
    following: PassThroughFollowing.REROUTE_ONLY,
    outputs: [{ name: "Output", type: "*" }],
    // A Collector restored from saved data (a load, a paste, an undo) is never the
    // replacement: `replace` builds a fresh node and configures nothing before it joins.
    onCreated(node, event) {
        if (!event?.restored) {
            claimUpgrade(node);
        }
    },
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
