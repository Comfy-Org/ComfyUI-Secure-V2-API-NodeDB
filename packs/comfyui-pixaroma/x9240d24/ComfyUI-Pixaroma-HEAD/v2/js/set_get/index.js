// ╔═══════════════════════════════════════════════════════════════╗
// ║  Set / Get Pixaroma - wireless "named variable" node pair     ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Pixaroma's own wireless "named variable" node pair, in a PRIVATE namespace:
// classes PixaromaSetNode / PixaromaGetNode with their own registry
// (js/set_get/scope.mjs) that only ever scans Pixaroma Set/Get. It coexists with
// any other pack's Set/Get-style nodes in one workflow with zero interference.
//
// Both are pure-frontend VIRTUAL nodes (isVirtualNode = true): their Python def
// is metadata only (library name, category, search), and they never reach the
// prompt. Resolution at submission goes straight through to the real
// source via getInputLink (same-graph) + resolveVirtualOutput (subgraph). Works
// in both Classic and Nodes 2.0, and inside subgraphs (native path verified on
// frontend 1.45.15).

import { app } from "../../../scripts/app.js";
import { registerPixaromaSetNode } from "./set_node.mjs";
import { registerPixaromaGetNode } from "./get_node.mjs";
import { SET_TYPE, GET_TYPE } from "./scope.mjs";
import { startValuePoll } from "./value_preview.mjs";
import { SETTING_ID, recolorAllGets } from "./colors.mjs";
import { registerNodeAccent } from "../shared/node_settings.mjs";
import "./help.mjs"; // registers help for both nodes (convention #16)

// ComfyUI builds a class from each Python def (nodes/node_set_get.py) and
// registerCustomNodes below then puts OUR class in its place. But Refresh Node
// Definitions (the R key, the old Refresh button, and the refresh the
// missing-models check runs) registers every def AGAIN and never calls
// registerCustomNodes, so after one refresh every new, pasted or reopened Set /
// Get was ComfyUI's bare def class: no name picker on the Get, not virtual, sent
// to the backend and handing None downstream (Discord report, reproduced
// 2026-09-27 with D:\Claude Tests\_setget\refresh_harness.mjs). LiteGraph calls
// onNodeTypeReplaced whenever a registered type is replaced (declared in
// LiteGraphGlobal, unused by the frontend), so fill that slot, chained, and put
// our class back the moment anything else takes its place.
const OURS = {};
function keepOurClasses() {
  const LG = window.LiteGraph;
  if (!LG || LG.__pixSgKeepOurs) return;
  LG.__pixSgKeepOurs = true;
  const prev = LG.onNodeTypeReplaced;
  LG.onNodeTypeReplaced = function (type, base) {
    if (typeof prev === "function") {
      try {
        prev.apply(this, arguments);
      } catch (e) {
        console.error(e);
      }
    }
    const ours = OURS[type];
    // Re-registering fires this hook again with base === ours, which stops here.
    // registerNodeType blanks the category again, so carry it across.
    if (ours && base !== ours) {
      const category = ours.category;
      LG.registerNodeType(type, ours);
      ours.category = category;
    }
  };
}

app.registerExtension({
  name: "Pixaroma.SetGet",
  // No Settings-panel row: this option lives on the node itself (the gear in
  // the selection toolbar / the right-click entry). The setting id is unchanged
  // and merely unregistered, so an existing choice carries over; the read site
  // supplies the default for the unset case.
  registerCustomNodes() {
    OURS[SET_TYPE] = registerPixaromaSetNode();
    OURS[GET_TYPE] = registerPixaromaGetNode();
    keepOurClasses();
  },
  setup() {
    startValuePoll();
  },
});

// No colour block: a Set / Get node's colour IS its node body colour, which
// ComfyUI's own right-click Colors menu already owns. The panel hosts the
// pairing option, which used to sit in the global Settings panel. Registered on
// BOTH classes so the gear appears whichever half of the pair is selected.
for (const cls of ["PixaromaSetNode", "PixaromaGetNode"]) {
  registerNodeAccent(cls, {
    title: "Set and Get",
    accent: false,
    rows: [
      { kind: "toggle", setting: SETTING_ID, defaultValue: true,
        label: "Get matches its Set's colour",
        hint: "Matching pairs are easy to spot. Off leaves Gets on their own colour." },
    ],
    onRowChange: () => recolorAllGets(),
  });
}
