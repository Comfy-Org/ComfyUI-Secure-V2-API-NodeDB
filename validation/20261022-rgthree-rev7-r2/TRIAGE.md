# rgthree-comfy revision 7 r2: triage of BART's revision 6 staging (MERVYN, 2026-10-21; r2 2026-10-22)

**r2:** addresses the independent review (`rgthree-rev7-review-20261022/REVIEW.md`, CLEAR_WITH_NOTES).
- The requests are renumbered, because R6-11 was already taken. The structure-replica request is now **R6-12** and
  the stale-copy request **R6-13**.
- R6-12 is extended.
- The state C limitation and the untouched paths are recorded.

**Sources:**
- BART: `chat_4d673d17c618/rgthree-rev6-staging/STAGING-RESULTS.md`, plus its run logs `runs/*/RESULT.json`.
- The live guest `c6b97a15` and host-entry `63d9437e`. Line numbers are in `rgthree-storm-20261015/lanes/startup/host-stack-r3/candidate/`.

**Classes:** **P** platform, **K** pack, **B** both.

## Classification

| # | Finding | Class | Evidence | Revision 7 |
| --- | --- | --- | --- | --- |
| 1 | **R4, R7, R7b (one symptom, two causes):** after a rename, the Label does not redraw; the Repeater's and Relay's mode does not propagate. 0 packerrors. | **B** | See *Cause* below. In short: revision 6's `changedNode` keyed on `comfy.graph.id`, which reads `''` on the live guest, and the handlers read the new title or mode from snapshots the guest never updates. | Addressed pack-side, untested (`base_node.js`, `label.js`, Relay, Repeater). Platform requests R6-12 and R6-13. Still dropped in state C (below). |
| 2 | **Observation 1:** with no pre-selection, "Queue Group Output Nodes" is gone for nodes in a group, though revision 5 showed it. | **P**, not a regression | See *Observations*: revision 5's display was the host's fallback for an answer it never got. | Recorded. No pack change. The items' visibility checks are the same in revisions 5, 6 and 7; `menu_queue_node.js` itself changed in revision 6, but not those checks. |
| 3 | **Observation 2:** "Queue Selected" was still listed after a right-click moved the selection. | **P** (host fallback) | See *Observations*: the host showed the item because the worker had not yet answered. | Recorded. Revision 6's smoke row R2 wrongly expected "Queue Selected" there, so its pass rested on the fallback. The revision 7 plan corrects it. |

## Cause of finding 1

**Revision 6's `changedNode` compared `event.graphId` with `comfy.graph.id`:**
- On the guest, that getter is `graphState.graphId ?? ''` and triggers no refresh (2409).
- `root()` and `subgraphs()` trigger an asynchronous refresh (2291-2309) but answer from the current replica (2433-2440).
- The replica's structure arrives only with:
  - an epoch, when a workflow loads (host 2682-2686; guest 2958-2965);
  - a `graphview`, before a gesture, sent only to packs that have already read structure (host 2429-2431, 2800-2805; guest 2967-2970);
  - a refresh answer. The guest drops that answer if the pack wrote in between (2305).
- `init` carries no structure (2925-2956). A worker that starts after the document loaded therefore holds `graphId` undefined, the getter reads `''`, and every event was dropped silently.

**The new value is not in the node either:**
- The `event` message merges no snapshot (3053-3064). The host sends only the sanitised arguments (2543-2561).
- So `getTitle()` and `getMode()` still read the value from before the change. BART's capture shows that `to` carries the new value: litegraph numbers for mode, the string for title.

**Revision 7:**
- `changedNode` looks the node up by id on the graph on screen. This uses node snapshots, which the guest holds for every node it has seen (`viewFor` 2212-2224, and before any epoch `offScreen()` is false, 1634-1635). It keeps the node only if its own `graphId` equals the event's.
- The scopes are only a fallback, for graphs not on screen.
- The Label lays out `event.to` as its title. The Repeater and Relay use `changedMode(event)`, which maps 0-4 to the published `NodeMode` names. They fall back to `getMode()`.

## Observations 2 and 3

The guest computes each item's visibility per node and sends it to the host (`refreshMaterializedViews`, 1288-1313, with `rightClickCtx` 2344-2355). The host reads it at menu-open. If no answer exists yet, the host shows the item and logs "visibility not yet computed … showing it" (`buildMenu`, 2936-2959).

**Observation 2 (Queue Group):**
- In BART's revision 5 x1 run, the host logs that warning for nodes 1 and 2, for both items. So the displayed items were the host's fallback. KSampler even showed "Queue Selected" with nothing output-capable selected.
- In revision 6's x1 run there is no such warning, so the answers were computed:
  - "Queue Selected" was correct: true on PreviewImage, false on KSampler.
  - "Queue Group" was false, because `comfy.graph.groups()` reads the same structure replica as finding 1 (2447-2450 → 2357-2358).

**Observation 3 (Queue Selected after the selection moved):**
- In revision 6's `r6-rows` run, the host logs "not yet computed" for nodes 1-4, for both items. So the items in R2 were shown by fallback.
- The computed answer for a right-click on an unselected Fast Muter, Label or Bookmark is "Queue Selected" hidden, because the right-click makes that node the selection.

## Known limitation: state C (review M1)

**Trigger:** the replica was seeded for one graph, and the graph id then changed with no epoch. `app.graph.clear()`
does that: BART's diag2 shows `99196d81…` → `458da615…`.

**What happens:**
- `mergeSnapshot` files the new graph's nodes under a scope that `graph.node()` never reads (1648-1660).
- `root()` and `subgraphs()` do not list that scope.
- So revisions 6 and 7 both drop the event until a refresh answer lands, which the guest discards if the pack wrote
  meanwhile (2305).

**Status:**
- It is not a regression.
- It is recorded as a group G case (`RECORDED LIMITATION state C`). Both revisions drop the event there.
- The fix is R6-12, as extended below.
- The smoke plan avoids `app.graph.clear()`.

## Also affected, not changed (needs R6-13; review L2)

The same stale node copies make these lag behind a mode or title change on host r3:
- the Relay's mode when its inputs drive it (`handleLinkedNodes` reads linked nodes' `getMode()`);
- the Fast Muter and Bypasser toggle state (`base_node_mode_changer.js`);
- Node Collector input names (the stabilizer reads linked nodes' `getTitle()`).

Their rows stay PARTIAL on host r3 for that reason too. S3 is unaffected, because nothing is wired into the Relay.

## Platform requests (new; same owner as R6-1 to R6-11)

**R6-12: seed and keep the guest's structure replica (extended in r2).**
- Send `_graphState()` with `init`, or an epoch as soon as a worker registers.
- Re-request a refresh answer instead of dropping it when the pack wrote meanwhile (guest 2305).
- Send a fresh structure snapshot, as an epoch or a `graphview`, whenever the id of the graph on screen changes
  without a workflow load. `app.graph.clear()` is one case; this is state C.
- Affects `comfy.graph.id`, `root()`, `subgraphs()`, `groups()`, `links()`, `nodeAt()` and `version`, and every materialized menu `when` that reads them. That includes rgthree's "Queue Group Output Nodes".

**R6-13: `onNodeChanged` must not leave the guest's copy stale.**
- Merge a fresh snapshot of the changed node before calling listeners. The host has the node.
- Together with R6-1, `event.node.getTitle()` and `getMode()` would then answer the new value.

## Evidence

- **`REV6_UNIT_TESTS.json`:** 63/63 in r2.
  - r2 adds `to: 0` (S2's second press), an unknown mode string and a non-string title.
  - r2 replaces the misleading "replica from another document" check with the recorded state C case.
  - r1 had 60: revision 6 r2's 49, plus 11 in group G, which uses a guest model with an unseeded or stale replica and stale snapshots.
  - Revision 6's Label, Repeater and Relay fail on that model, as the negative control: "the event is dropped", "nothing repeated", "nothing relayed".
  - Revision 7 passes, including a subgraph whose node shares an id with a root node, and the 0-4 / name / missing-`to` mode cases.
- **`REV6_MUTANTS.json`:** 23/23 killed in r2, which adds M21-M23: mode 0, unknown strings and a non-string title.
  r1 had 20 (revision 6 r2's 14, plus M15-M20):
  - M15: `changedNode` reverted to revision 6;
  - M16: the Label ignores `event.to`;
  - M17 and M18: the Repeater and Relay read the stale mode;
  - M19: `changedMode` ignores numbers;
  - M20: the graph check is dropped.
- **Test-model fix:** the walk stubs now read the node's slots through its handle. Without that, M12 (the Repeater using the event's copy) survived.
