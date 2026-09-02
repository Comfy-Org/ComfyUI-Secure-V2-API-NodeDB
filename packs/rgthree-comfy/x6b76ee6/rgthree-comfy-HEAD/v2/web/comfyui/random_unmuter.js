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
// FUNCTIONAL, minor: `onAfterRun` is the host's `promptQueued`, which is not dispatched
//   when nothing was accepted — a cancelled or fully rejected run leaves the chosen node
//   unmuted, where the original's `queue-end` sat in a `finally`. The next run restores
//   it before rolling again, so the state cannot accumulate, but it can persist between
//   two runs. An always-fires queue-end is the missing piece.
//
// `exposedActions = ["Mute all", "Enable all"]` is rgthree's own convention, read by the
// Fast Actions Button; it is `exposeActions` now (see base_node.js). This node never
// overrode `handleAction`, so both entries are listed and inert — which is exactly what
// they were, and dropping them would quietly change the button's dropdown.
// LIMITATION: a handle addresses the graph on screen, so an unmuter inside a subgraph
//   the user is not looking at is skipped rather than rolled. The original read
//   `node.graph` and did not care.
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
        unmuterNodes.delete(nodeKey(node));
        temporarilyEnabled.delete(nodeKey(node));
    },
    menuItems: [helpMenuItem(NodeTypesString.RANDOM_UNMUTER, HELP)],
});
