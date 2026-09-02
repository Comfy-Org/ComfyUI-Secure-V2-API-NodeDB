import { NodeTypesString } from "./constants.js";
import { defineFastGroupsModeChanger } from "./fast_groups_muter.js";

// Fast Groups Bypasser — Fast Groups Muter with mode `bypass` instead of `never`.
// Every gap it inherits is documented in fast_groups_muter.js.
defineFastGroupsModeChanger({
    type: NodeTypesString.FAST_GROUPS_BYPASSER,
    modeOff: "bypass",
    offAction: "Bypass all",
    helpActions: "bypass and enable",
});
