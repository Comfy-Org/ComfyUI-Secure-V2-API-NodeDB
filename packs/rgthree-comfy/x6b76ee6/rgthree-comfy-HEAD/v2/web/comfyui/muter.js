import { NodeTypesString } from "./constants.js";
import { defineModeChangerNode } from "./base_node_mode_changer.js";

// Fast Muter — one toggle per connected node, muting or unmuting it. The body is
// `defineModeChangerNode`; every gap it inherits is documented there and in
// base_any_input_connected_node.js.
//
// `exposedActions = ["Mute all", "Enable all", "Toggle all"]` and the `handleAction`
// that runs them are rgthree's own cross-node action convention, read by the Fast
// Actions Button; both are declared through `exposeActions` now. See
// base_node_mode_changer.js.
//
// The `loadedGraphNode` hook that seeded `node._tempWidth` from `node.size[0]` is not a
// gap and has no replacement here: the width is captured and restored around each
// mutation instead (`pinWidth`), so there is nothing to seed.
//
// WIRE FORMAT: unchanged. One `*` input and one `OPT_CONNECTION` output as before, the
// input list grows and is renamed exactly as before, and `serialize_widgets` is off so
// no toggle reaches `widgets_values`.
defineModeChangerNode({ type: NodeTypesString.FAST_MUTER, modeOn: "always", modeOff: "never", offAction: "Mute all" });
