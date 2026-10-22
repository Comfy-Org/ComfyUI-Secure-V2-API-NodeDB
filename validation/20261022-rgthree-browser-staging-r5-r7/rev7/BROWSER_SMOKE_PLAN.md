# Browser smoke plan: rgthree revision 7 candidate (r2)

**For BART.** Same setup as revision 6:
- Mode B overlay.
- `served-web/` comes from `stage/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/web/`, sha-checked against
  `STAGE_MANIFEST.json`.
- Host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`.

**What changed from revision 6:** 4 served modules (`base_node.js`, `label.js`, `node_mode_relay.js`,
`node_mode_repeater.js`). Imports and the file list are unchanged.

**Preparing S1-S3 (review M1):**
- Do not call `app.graph.clear()`. It changes the graph id without telling the worker, which drops the events on
  host r3 (state C, request R6-12).
- To start from an empty graph, load an empty workflow (`app.loadGraphData`), which sends an epoch.
- Before each key press, log the worker's `comfy.graph.id` (evaluated in the rgthree worker) next to the page's
  `app.graph.id`. If they differ and the press does nothing, class it as P (state C), not as a pack failure.

**Load conditions:** run S1-S3 twice:
- on the untouched startup graph, with no workflow load in the session;
- after loading a workflow.

Revision 6 failed in both.

| # | Required | Steps | Pass |
| --- | --- | --- | --- |
| S1 (R4) | yes | Rename a Label with the title editor to a longer, two-line text. Then rename a fresh Label. | The canvas draws the new text, and the node resizes to it. 0 packerrors. |
| S2 (R7) | yes | Add a fresh KSampler, after the page has loaded, and wire it into a Mute / Bypass Repeater. Optionally, record a second run with a KSampler that was already in the loaded workflow; that tests the triage's "worker starts after the document loaded" premise. Then: Press Ctrl+M on the Repeater, then again. Then press Ctrl+B. | The KSampler follows: 0 → 2 → 0, then 4. 0 packerrors. |
| S3 (R7b) | yes | Wire a Mute / Bypass Relay's output to the Repeater, with nothing wired into the Relay. Press Ctrl+M on the Relay, then again. | The Repeater, and through it the KSampler, follow the Relay: 0 → 2 → 0. 0 packerrors. |
| S4 | record only | **Menus.** Use a group holding a PreviewImage and a KSampler. **(a)** With no pre-selection, right-click the PreviewImage, then the KSampler. **(b)** Pre-select the PreviewImage, then right-click a Fast Muter in the group. For each menu, also record any console line "… visibility not yet computed for node N; showing it". | **Expected from the pack:** "Queue Selected" appears only where the right-click leaves an output node selected: (a) the PreviewImage, not (b). "Queue Group" appears on every node of a group that holds an output node. **Host r3 can differ in two ways.** First, an item whose answer is not computed yet shows anyway, with the console line; that is the host's fallback. Second, "Queue Group" can be hidden while the worker's structure replica is empty (request R6-12). Record which applies. This row is not a gate. |
| S5 | yes | **Regression:** R1 (Power Conductor: opt-in on, run, reload with a saved node), R2 (0 late-extend errors for the 13 own types), R3 (one POST via the PreviewImage menu), R5 (Combiner upgrade: wiring, title, one undo), and R9's counters. | As in revision 6's staging. |

## Gate

- S1, S2, S3 and S5 must pass. Then the node counts may move.
- S4 is evidence for the platform requests.
