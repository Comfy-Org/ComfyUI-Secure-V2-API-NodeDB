# Browser smoke plan: rgthree revision 6 candidate (changed items only)

**For BART.** The setup matches the revision 5 staging:
- Mode B overlay: session-only Playwright routes, nothing installed.
- `/api/extensions` lists exactly the 73 rgthree entries.
- `/extensions/rgthree-comfy/<rel>` is served from this folder's `stage/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/web/`.
- Each response is sha-checked against `STAGE_MANIFEST.json`.

**Host:** host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`.

Revision 6 changes 14 served modules and `SECURE_CONVERSION.md` (see `V2_CHANGE_SUMMARY.md`). It adds or removes no
files, and every import and URL target stays the same. Rows R1-R8 (with R7b) below cover the changes; each lists what is expected to remain a platform gap, so that
it is recorded rather than failed. Row R9 is a short regression check.

## Rows

| # | Required | Steps | Pass |
| --- | --- | --- | --- |
| R1 | yes | **Power Conductor, opt-in on.** Store `rgthree.unreleased.power_conductor.enabled = true` and load normally: no import delay or other trick. Add the node, then click Run. Then save a workflow containing a Power Conductor and reload the page with the opt-in still on. Then load with the opt-in off. | Opt-in on: the type is registered, and with no added delay. The node constructs. Run still fetches both `.wasm` files and executes. After the reload, the saved Power Conductor comes back as itself, not as a missing type. On the guest the type can now register after the graph loads, so this is the case to watch. Opt-in off: the type is not registered. *Expected gap (R6-4):* the code box is absent. Record it; it does not fail this row. |
| R2 | yes | **Late registration (F-1).** Do 3 cold loads, and count console errors that match `[nodeApi] comfy.defs.extend('X') was called after comfy.defs.define('X')`. Then repeat x1: with a PreviewImage selected inside a group, right-click a Fast Muter, a Label and a Bookmark. | 0 such errors where X is one of the 13 rgthree-defined types (`DEFINED_NODE_TYPES` in `constants.js`). All three menus show both "Queue … Output Nodes (rgthree)" items. *Expected gap (R6-3):* errors naming another pack's types (for example GetNode or SetNode) may remain; record their count. |
| R3 | yes | **Queue items.** Route `POST /api/prompt` in Playwright to record the body and answer `{"prompt_id":"smoke","number":0,"node_errors":{}}`, so nothing runs. Select a PreviewImage, then use "Queue Selected Output Nodes (rgthree)" from its menu and from the command palette. | Each use posts one prompt containing the selected output node and its inputs. There is no DataCloneError and no packerror. One "DataCloneError" retry is internal and logs nothing. |
| R4 | yes | **Label title refresh.** Load `label-acceptance-workflow.json`. Then rename a Label with the title editor. | 0 `getProperties is not a function` packerrors (revision 5 had 3 per load). After the rename, the Label redraws with the new text and resizes to it. Optionally, spot-check 3 of the 9 dialog edits. |
| R5 | yes | **Node Combiner → Node Collector.** Load a workflow with a Node Combiner titled "‼️ Mine". Give it 3 connected inputs (from 3 different nodes, slots 0-2) and 2 outgoing links. Retitle the source of input 1 to "" and the source of input 2 to "Output": these exercise the rename to index before `replace`. Right-click it and choose "‼️ Update to Node Collector". | One Node Collector at the Combiner's position, and the Combiner is gone. Inputs 0-2 come from the same sources in the same order; its output goes to the same 2 targets. The title reads "Mine". The page stays responsive: rAF stays under 50 ms, and a second menu opens. The host's console warning "Replacing node … dropped 2 link(s)" is expected, because the pack re-makes those links next. Record whether undo restores the Combiner in one step or in several. |
| R6 | yes | **Context Merge Big.** Right-click a Context Merge Big, run its item, and right-click the result. | The item reads "Convert To Context Merge" and converts to Context Merge. The new node's item reads "Convert To Context Merge Big". |
| R7 | yes | **Repeater mode handler.** Wire a KSampler into a Mute / Bypass Repeater. Press Ctrl+M on the Repeater, then Ctrl+M again. | The KSampler's mode follows (0 → 2 → 0), with 0 packerrors. |
| R7b | yes | **Relay mode handler.** Wire a Mute / Bypass Relay's output to a Mute / Bypass Repeater (nothing wired into the Relay) and a KSampler into the Repeater. Press Ctrl+M on the Relay, then again. | The Repeater, and through it the KSampler, follow the Relay's mode; 0 packerrors. |
| R8 | no | **Stored setting announced.** Store `rgthree.features.progress_bar.enabled = false` and load. | The "Queue: n" badge is absent after load, or disappears within a second. |
| R9 | yes | **Regression.** Rerun revision 5's rows 1, 4, 5 and 11 counters, using the same harness. | 0 module-load failures. 0 refusal rows. Exactly the 8 expected `[rgthree-comfy]` notices (6 onUnplacedLink, onDragOver, onDrop). 0 DataCloneError. |

## Gate

- Rows R1-R7, R7b and R9 must pass. Then:
  - the node counts in `SECURE_CONVERSION.md` may move;
  - Power Conductor keeps "tested (scoped)", with its code box recorded as blocked on R6-4.
- If R5 fails, revision 6's other fixes still stand. Report R5 on its own: the Combiner upgrade is the change that
  depends most on host timing.
