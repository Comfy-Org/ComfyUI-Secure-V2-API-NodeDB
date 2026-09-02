import { NodeTypesString } from "./constants.js";
import { defineModeChangerNode } from "./base_node_mode_changer.js";

// Fast Bypasser — Fast Muter with `bypass` instead of `never`. Every gap it inherits is
// documented in base_node_mode_changer.js and base_any_input_connected_node.js, and its
// "Bypass all" / "Enable all" / "Toggle all" actions are declared through the same
// `exposeActions` registry.
defineModeChangerNode({ type: NodeTypesString.FAST_BYPASSER, modeOn: "always", modeOff: "bypass", offAction: "Bypass all" });
