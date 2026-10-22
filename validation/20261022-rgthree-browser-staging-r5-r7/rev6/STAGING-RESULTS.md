# rgthree-comfy rev 6: browser staging results (BART, 2026-10-21, 21:55–22:07Z)

**Verdict: the gate is not met.**
- Three required rows fail: **R4** (redraw/resize part), **R7** and **R7b**. All three are the same defect: rev6's
  `onNodeChanged` handlers drop host r3's events.
- Every other row passes, and so do all the rev5 rows.
- Per the plan, the node counts stay at rev 4's. R5 passes, so nothing needs reporting on its own.

## Setup
- **Mode B, "overlay".** Session-only routes; nothing installed or deployed.
- **Packet:** zip `38a63002…`, `SHA256SUMS` `3ce548bd…`; all 88 entries verified. Every served response was sha-checked
  (0 mismatches, 0 non-200).
  - The zip was built on Windows, with backslash paths; `unzip` normalised them, with no traversal.
  - The plan header refers to `stage/…` and `STAGE_MANIFEST.json`, which aren't in the packet. Per `STAGING.md`, I used
    `served-web/` and `SHA256SUMS`.
- **Host, checked on every load:** host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`. The live gateway now
  carries the projection re-pin (`/rgthree/` alias admitted); that doesn't affect rev6, which doesn't use the alias.
- **`POST /api/prompt` (R3)** was answered inside the browser and never reached the server. The recorder kept node ids,
  class types and input names, plus the `extra_data` key names only; credential values were never stored.
- **Loads:** 9 cold loads (`runs/`):
  - `r6-rev5rows-default` (rev5 harness)
  - `r6-rows`
  - `r6-pc-on`: my harness error at reload (see R1); superseded by `r6-pc-on-b`
  - `r6-pc-on-b`
  - `r6-pc-off`
  - `r6-progress-off`
  - `r6-diag`, `r6-diag2`: diagnostics

## Rows
| # | Verdict | Evidence |
| --- | --- | --- |
| R1 | **PASS** | **Opt-in on:** registered 33 ms after graph-ready, with no delay of any kind. The node constructs (`code`, `Run`). Run fetched `lib/tree-sitter.wasm` and `lib/tree-sitter-python.wasm` (200, sha OK) and executed (worker logs `=====` and `value null`). The app saved the draft (`Comfy.Workflow.Draft.v2…`). After a reload with the opt-in still on, the Power Conductor came back as the registered class, with its widgets, no `has_errors` and no missing-node dialog. **Opt-in off:** not registered. **Known gap R6-4 (recorded):** the code box `mount:code` throws (no value handle). The first pc-on load failed in my harness, because it dismissed the app's `beforeunload` prompt and so cancelled its own reload. It was fixed and re-run. |
| R2 | **PASS** | **Late-extend errors** (`[nodeApi] … called after comfy.defs.define`): 0 for the 13 `DEFINED_NODE_TYPES` across all 9 loads. Other packs' residue (R6-3; GetNode/SetNode) runs 0–6 per load. **Menus:** with a PreviewImage selected inside a group, Fast Muter, Label and Bookmark each show both "Queue … Output Nodes (rgthree)" items. |
| R3 | **PASS** | **Via the PreviewImage menu:** 1 POST containing EmptyImage and PreviewImage. **Via the command** `rgthree.queueSelectedOutputNodes`, run through the frontend command store (no palette UI was driven): 1 POST, same nodes. 0 DataCloneError, 0 packerrors. |
| R4 | **FAIL** | **Fixed:** 0 `getProperties is not a function` (rev5 had 3 per load). The title editor sets the node title. **Fails:** the Label neither redraws nor resizes. The canvas still draws "Label acceptance / Second line" (`R4-label-renamed.png`), and the size stays 173×56. A fresh Label renamed to longer text also stays 79×12, in 3 graph variants (`diag2`). |
| R5 | **PASS** | One Node Collector at the Combiner's position; the Combiner is gone. Inputs 0–2 come from S0, S1, S2 in order; the output goes to the same 2 targets. The title reads "Mine". rAF 5 ms; a second menu opens. The expected host warning appeared: "Replacing node 4 … dropped 2 link(s): input '1', input '2'". **Undo:** one Ctrl+Z restores the Combiner. |
| R6 | **PASS** | Context Merge Big → "Convert To Context Merge" → Context Merge, whose item reads "Convert To Context Merge Big". |
| R7 | **FAIL** | Ctrl+M on the Repeater moves its own mode 0→2→0, but the wired KSampler stays at 0. 0 packerrors. |
| R7b | **FAIL** | Ctrl+M on the Relay moves its own mode 0→2→0, but the Repeater and the KSampler stay at 0. 0 packerrors. |
| R8 (optional) | PASS | With `rgthree.features.progress_bar.enabled=false`, the `Queue: n` badge is absent. |
| R9 | **PASS** | On every load: 0 module-load failures, 0 refusal rows, exactly the 8 expected notices, 0 DataCloneError. |

**rev5 rows** (the `STAGING.md` "must still pass" list), all from `r6-rev5rows-default`:
- **PASS:**
  - rows 1, 2 (220 × 200, 0 `/rgthree/`), 4, 5, 10 (Crystools 10/10, KJNodes 26/26) and 11;
  - 3: the progress bar mounts;
  - 7: counted case-sensitively;
  - 8, and 8b on both rings.
- **Row 6:** 36/36 types construct. The F-2 hook errors remain; they are the platform-gap class.

## Why R4, R7 and R7b fail (diagnostics `r6-diag` and `r6-diag2`)
- **Host r3 does announce the changes.** A page-side `comfy.onNodeChanged` listener received:
  - `{property:'mode', from:0, to:2}` for a Ctrl+M on the Repeater;
  - `{property:'mode', 2→0}` for an API mode set;
  - `{property:'title', 'Label (rgthree)'→'Diag rename'}` for the title editor.
- **The worker receives them.** A listener inside the worker saw `event` messages with keys
  `node, graphId, property, from, to`. The node is flattened to `id, graphId, type, inputs, outputs, widgets, comfyClass,
  isDeleted`.
- **rev6's handlers do nothing with them, and log no packerror.** This happens on the untouched startup graph too, not
  only after `app.graph.clear()` or `loadGraphData` (both of which change the graph id). So it isn't caused by my harness
  resetting the canvas.
- **Pointer, not proven:** base_node.js `changedNode()` first compares `event.graphId` with `comfy.graph.id`. On guest
  `c6b97a15`, that getter returns the cached `graphState.graphId ?? ''` without refreshing, while `root()` and
  `subgraphs()` refresh the graph view first. That is worth checking before anything else.

## Observations (not plan rows)
- **x1, as run by the rev5 harness** (no pre-selection; right-click on an unselected node): "Queue Group Output Nodes
  (rgthree)" no longer appears for any node in the group. PreviewImage shows only "Queue Selected". On rev5, it appeared
  for PreviewImage and KSampler. R2's specified case (PreviewImage pre-selected) passes.
- **In R2, right-clicking moved the selection to the clicked node,** yet "Queue Selected Output Nodes" was still listed.
  Clicking it there would queue nothing.

## Evidence
- **Harnesses:**
  - `harness/rev6-stage.mjs` (stages pc-on, pc-off, rows, progress-off, diag, diag2)
  - `../rgthree-rev5-staging/harness/rev5-stage2.mjs` (rev5 rows)
  - `../rgthree-rev5-staging/harness/summarize.py`
- **Per load:** `runs/*/RESULT.json`.
- **Screenshots:** `R1-pc-run.png`, `R1-pc-after-reload.png`, `R2-label-menu.png`, `R4-label-renamed.png`,
  `R5-after-upgrade.png`, `R8-topbar.png`, `diag2-*.png`, plus the rev5-row screenshots in `r6-rev5rows-default/`.
