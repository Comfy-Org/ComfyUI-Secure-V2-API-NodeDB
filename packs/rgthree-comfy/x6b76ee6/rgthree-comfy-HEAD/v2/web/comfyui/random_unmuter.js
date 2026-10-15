import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { connectedInputNodes, defineAnyInputConnectedNode, nodeKey, setModeDeep, } from "./base_any_input_connected_node.js";
import { exposeActions, helpMenuItem } from "./base_node.js";

// Random Unmuter — when the graph is queued and every node wired into it is muted, it
// unmutes one at random for the duration of prompt building and mutes it again straight
// after, so each run picks a different branch.
//
// The window is `comfy.queue.onBeforeRun` / `onAfterRun`, which is where rgthree's own
// "queue" / "queue-end" events sat — it wrapped `app.queuePrompt` to raise a
// `processingQueue` flag and then did the work inside a second wrapper around
// `app.graphToPrompt`. Two differences follow from having only the outer pair:
//
// FUNCTIONAL, minor: the roll happened once per `graphToPrompt`, so a batch of 4 picked
//   four different branches. `onBeforeRun` fires once per queue call, so a batch now
//   runs the same branch four times.
// The cleanup returned by onBeforeRun now runs on every attempt outcome,
// including refusal and transport failure. onAfterRun alone is insufficient.
//
// `exposedActions = ["Mute all", "Enable all"]` is rgthree's own convention, read by the
// Fast Actions Button; it is `exposeActions` now (see base_node.js). This node never
// overrode `handleAction`, so both entries are listed and inert — which is exactly what
// they were, and dropping them would quietly change the button's dropdown.
// connectedInputNodes resolves through the node's own graph scope, including
// subgraphs that are not currently on screen.
const MODE_ALWAYS = "always";
const MODE_MUTE = "never";
const HELP = `
      <p>
        Use this node to unmute on of its inputs randomly when the graph is queued (and, immediately
        mute it back).
      </p>
      <ul>
        <li><p>
          NOTE: All input nodes MUST be muted to start; if not this node will not randomly unmute
          another. (This is powerful, as the generated image can be dragged in and the chosen input
          will already by unmuted and work w/o any further action.)
        </p></li>
        <li><p>
          TIP: Connect a Repeater's output to this nodes input and place that Repeater on a group
          without any other inputs, and it will mute/unmute the entire group.
        </p></li>
      </ul>
    `;
// Handles hold no arbitrary properties, so the live unmuters and the node each one has
// temporarily enabled live here, keyed by node id and dropped in onRemoved.
const unmuterNodes = new Map();
const temporarilyEnabled = new Map();
function restoreAll() {
    const held = [...temporarilyEnabled.values()];
    temporarilyEnabled.clear();
    if (!held.length) {
        return;
    }
    comfy.graph.batch(() => setModeDeep(held.filter((node) => !node.isDeleted), MODE_MUTE));
}
comfy.onReady(() => {
    comfy.queue.onBeforeRun(() => {
        // A run the backend refused never reports back, so anything still held from last
        // time is put away first.
        restoreAll();
        comfy.graph.batch(() => {
            for (const [id, node] of unmuterNodes) {
                if (node.isDeleted) {
                    continue;
                }
                const linkedNodes = connectedInputNodes(node);
                if (!linkedNodes.length || linkedNodes.some((n) => n.getMode() !== MODE_MUTE)) {
                    continue;
                }
                const chosen = linkedNodes[Math.floor(Math.random() * linkedNodes.length)];
                if (chosen) {
                    temporarilyEnabled.set(id, chosen);
                    setModeDeep([chosen], MODE_ALWAYS);
                }
            }
        });
        return restoreAll;
    });
    comfy.queue.onAfterRun(() => {
        restoreAll();
    });
});
exposeActions(NodeTypesString.RANDOM_UNMUTER, ["Mute all", "Enable all"], () => { });
defineAnyInputConnectedNode({
    type: NodeTypesString.RANDOM_UNMUTER,
    onCreated(node) {
        unmuterNodes.set(nodeKey(node), node);
    },
    onRemoved(node) {
        const key = nodeKey(node), chosen = temporarilyEnabled.get(key);
        if (chosen && !chosen.isDeleted) comfy.graph.batch(() => setModeDeep([chosen], MODE_MUTE));
        unmuterNodes.delete(key);
        temporarilyEnabled.delete(key);
    },
    menuItems: [helpMenuItem(NodeTypesString.RANDOM_UNMUTER, HELP)],
});
