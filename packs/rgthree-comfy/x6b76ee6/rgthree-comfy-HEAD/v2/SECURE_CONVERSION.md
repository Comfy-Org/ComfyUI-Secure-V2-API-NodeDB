> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request (revision 3).
> Nodes: 37 of 40 upstream converted; 5 tested (scoped), 13 converted but untested/partly tested,
> 22 partial or missing: 19 converted with a behaviour blocked by a missing host capability, 3 missing or pending.
> Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — rgthree-comfy (`rgthree-comfy`)

## What this revision contains

- **Base:** in-progress revision 2, as merged on corpus main. Revision 2 is kept in the corpus but held from the registry,
  because its `prompt_service.js` raises DataCloneErrors in the sandbox; revision 3 fixes that.
- **Changed in revision 3** (no frontend module may be lost because the host refuses one registration):
  - `web/comfyui/sandbox_limits.js` (new). Every registration the host refuses goes through `whereSupported`: a refused
    hook (`onBeforeConnect`, `onUnplacedLink`, `onDragOver`, `onDrop`) or a menu item with a label function costs only that
    behaviour, and is reported once per node type. Any other error is re-thrown.
  - The guarded registrations are in `base_any_input_connected_node.js`, `base_power_prompt.js`, `context.js`,
    `dynamic_context.js`, `feature_import_individual_nodes.js` and `power_primitive.js`. Each lost behaviour is listed under
    *Blocked behaviours* below.
  - `web/common/prompt_service.js`: the queue members the sandbox cannot carry yet (`queue.onPendingChanged`,
    `queue.onInterrupted`) are treated as unavailable and reported once. The progress bar shows less instead of raising a
    DataCloneError at login. `queue.pending()` is read when its answer arrives.
  - **Browser evidence:** a read-only run on the live host, with these revision-3 files served to that one browser session
    and everything else live:
    - all 54 rgthree entry modules load (live with revision 1: 43);
    - no DataCloneError;
    - the 10 previously failing node types register and construct;
    - 29 one-time notices name each lost behaviour.
- **Changed in revision 2** (kept):
  - Backend (`py/secure_nodes.py`, `py/_secure.py`, `secure-nodes.json`). Three fixes found by original-comparison runs:
    - Lora Loader Stack resolves the exact selected name and declares an input validator, so real selections pass prompt
      validation and missing names are rejected there.
    - SDXL Empty Latent Image builds its latent with the SDK's latent op and now carries `downscale_ratio_spacial`, as the
      original does.
    - Power Prompt and SDXL Power Prompt - Positive apply prompt-tag LoRA strengths outside ±100, as the original does.
  - `secure-nodes.json` regenerated with the backend's manifest generator plus its `validation_inputs` fix, which is sent to
    the backend owner for review. Lora Loader Stack now carries its validator's argument names. Every node also gains
    `"loop_boundary": null`, which current Core's schema adds. Node schemas are otherwise unchanged.
  - `web/common/rgthree_api.js`: `getLoras` reads the LoRA catalogue through the public models API
    (`comfy.models.list('loras')`). The pack names the folder and the host chooses the route, instead of the pack fetching
    the core route `/models/loras`, which a sandboxed pack may no longer reach. 1 negative control plus 4 hermetic cases.
    The host must provide `comfy.models.list` for the list to load.
  - This report:
    - dispositions updated from the backend original-comparison runs;
    - two refused-technique descriptions corrected (Power Puter; runtime writes in the pack folder);
    - one technique added (the bundled host-update script).
- **Revision 1** (kept): the registered Label revision (draft PR #6) plus 16 tested frontend files: the 14-file first repair
  tranche, `display_any.js` (F14), and `media/svgs.js` (worker-safe logo URL).
- **Held back** (listed as open):
  - The Reroute definition and the F01 connection-layout port, which wait on host renderer prerequisites S01–S04. All four
    pass their tests, but the deployed frontend does not yet carry S01–S03. A combined S01–S04 frontend patch against the
    deployed sources is in preparation.
  - The optional Dynamic Context backend, which waits on the repeated-output API.
- **Resolved since revision 1:** the startup callback error (`comfy.defs.onRefreshed` inside the sandbox). The host fix is
  deployed and passed browser acceptance on 2026-10-15: no DataCloneError at login, and a refresh reaches the pack's
  worker.

## Provenance

Upstream https://github.com/rgthree/rgthree-comfy at commit `6b76ee6f2c5a007710b5a16f97c94330d6ecc871`
(key `x6b76ee6`). The pristine tree beside `v2/` is byte-exact at that commit (258 files). `v2/src_web/` is an unchanged
copy of upstream's TypeScript sources, kept for reference. The converted, served frontend is `v2/web/`. Upstream has
40 node IDs: 37 enabled by default and 3 opt-in (Dynamic Context, Dynamic Context Switch, Power Conductor).
Of the defaults, 24 have Python classes and 13 are frontend-only.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode). "Tested (scoped)" means every
part the node has upstream (backend and/or custom frontend) passed executed original-comparison tests and no
pack-side gap is open. Deployment-wide gates (live browser, asset delivery, gVisor) still apply to every node.

| Node id | Disposition | Evidence or gap |
| --- | --- | --- |
| `KSampler Config (rgthree)` | tested (scoped) | Backend native cases pass; no custom frontend. |
| `Power Conductor (rgthree)` | tested (scoped) | Opt-in. The tested repair ships here: numeric modes/IDs, explicit labels via `getLabel`, pack-owned group toggles. |
| `Image Resize (rgthree)` | tested (scoped) | Backend native cases: 150/150 equal the original. That is 10 sizes × 5 scaling methods × 3 fit modes, compared tensor-for-tensor with current Core's scaling. No custom frontend. |
| `Lora Loader Stack (rgthree)` | tested (scoped) | Fixed in revision 2: exact-name resolution (the previous v2 fuzzy-matched names) and an input validator. Backend native cases: 8/8 equal the original. Validator checks: 21/21, run in the Guest. One accepted difference, listed below. No custom frontend. |
| `SDXL Empty Latent Image (rgthree)` | tested (scoped) | Fixed in revision 2: the latent carries `downscale_ratio_spacial` like the original. Backend native cases: 72/72 equal the original. No custom frontend. |
| `Any Switch (rgthree)` | converted, partly tested | Backend native cases pass. F01 connection layouts are not in this revision. |
| `Display Any (rgthree)` | converted, partly tested | Backend native cases pass; the F14 serialization fix ships here. F01 is open. An own-node PNG metadata candidate passed separately and is not in this revision. |
| `Display Int (rgthree)` | converted, partly tested | Backend native cases pass; F14 ships here. F01 is open. |
| `Fast Groups Bypasser (rgthree)` | converted, partly tested | Tested repair ships here (row state, graph-scoped identities, saved filters). F10 fit-group navigation is open. |
| `Fast Groups Muter (rgthree)` | converted, partly tested | Tested repair ships here. F10 is open. |
| `Image Inset Crop (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Image or Latent Size (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Label (rgthree)` | converted, partly tested | Browser: Classic 7/9 edits persist, Vue 8/9. The remaining focus race is a host renderer fix, still pending. |
| `Power Lora Loader (rgthree)` | converted, partly tested | Backend native cases pass. The tested repair ships here: authored model info, row info actions, stale-request guard. Since revision 2 its LoRA list comes from `comfy.models.list('loras')`. Open: F01, F03, F04, F13. |
| `Power Puter (rgthree)` | converted, partly tested | Backend native cases pass on the bounded evaluator. F03 and F04 are open. |
| `Seed (rgthree)` | converted, partly tested | Backend native cases pass. An own-node PNG metadata candidate passed separately and is not in this revision. F01 is open. |
| `Image Comparer (rgthree)` | converted, partly tested | Backend native cases: 5/6 equal the original, including preview pixels and PNG metadata. With an empty image batch, v2 raises where the original skips; this is open. The comparer widget is untested, and F01 is open. |
| `Bookmark (rgthree)` | converted, untested | Frontend-only; its button-settings repair ships here. F09 (hidden-subgraph navigation) and F11 (keyboard) are open. |
| `Context (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18), and the "Convert to …" menu item, whose label depends on the node (a fixed-label replacement is planned). F01 is open. |
| `Context Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18), and the "Convert to …" menu item, whose label depends on the node (a fixed-label replacement is planned). F01 is open. |
| `Context Merge (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18), and the "Convert to …" menu item, whose label depends on the node (a fixed-label replacement is planned). F01 is open. |
| `Context Merge Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18), and the "Convert to …" menu item, whose label depends on the node (a fixed-label replacement is planned). F01 is open. |
| `Context Switch (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18), and the "Convert to …" menu item, whose label depends on the node (a fixed-label replacement is planned). F01 is open. |
| `Context Switch Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18), and the "Convert to …" menu item, whose label depends on the node (a fixed-label replacement is planned). F01 is open. |
| `Power Primitive (rgthree)` | converted, PARTIAL | Backend native cases pass. Blocked: the "Show/Hide Type Selector Widget" menu item, whose label depends on state (a fixed-label replacement is planned); "Set type" works. The rest of its frontend is untested. |
| `Random Unmuter (rgthree)` | converted, PARTIAL | The tested failed-attempt cleanup repair ships here. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node rules. F07 (independent choice per batch item) and F01 are open. |
| `Power Prompt (rgthree)` | converted, PARTIAL | Fixed in revision 2: prompt-tag LoRA strengths outside ±100 apply as in the original. Backend native cases: 72/72 equal the original. Blocked: refusing links from disabled outputs, connection filtering (`onBeforeConnect`; F17). The rest of the frontend is untested; F01 is open. |
| `Power Prompt - Simple (rgthree)` | converted, PARTIAL | Backend native cases: 16/16 equal the original. Blocked: refusing links from disabled outputs, connection filtering (`onBeforeConnect`; F17). The rest of the frontend is untested; F01 is open. |
| `SDXL Power Prompt - Positive (rgthree)` | converted, PARTIAL | Backend native cases pass, including the revision-2 prompt-tag strength fix. Blocked: refusing links from disabled outputs, connection filtering (`onBeforeConnect`; F17). F01 is open. |
| `SDXL Power Prompt - Simple / Negative (rgthree)` | converted, PARTIAL | Backend native cases: 36/60 equal the original on current Core. In the other 24, the original's sized SDXL encode is broken on current Core and returns no conditioning, while v2 returns the conditioning the original intends; this is an accepted difference, listed below. Blocked: refusing links from disabled outputs, connection filtering (`onBeforeConnect`; F17). F01 is open. |
| `Fast Actions Button (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. F01 and F11 are open. |
| `Fast Bypasser (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. F01 is open. |
| `Fast Muter (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. F01 is open. |
| `Mute / Bypass Relay (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. F01 is open. |
| `Mute / Bypass Repeater (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. F01 is open. |
| `Node Collector (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. F01 is open. |
| `Node Combiner (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Blocked: connection filtering (`onBeforeConnect`; F17), i.e. the cycle guard and per-node connection rules. Otherwise untested. Legacy node. F01 is open. |
| `Reroute (rgthree)` | missing | The frontend definition is not in this revision. A candidate exists, and host prerequisites S01–S04 pass their tests (S04's final run: 418/418). They are not yet all in the deployed frontend. F05 and F06 are open. |
| `Dynamic Context (rgthree)` | pending capability | Opt-in, disabled upstream by default. Needs a public repeated-output API (F02); a runtime test of that candidate is approved. Its connection filtering is guarded like the others (F17). |
| `Dynamic Context Switch (rgthree)` | pending capability | Same as Dynamic Context. |

## Refused techniques (never-do) and their public replacements

No whole user feature is refused. Only these techniques are; each feature they served has a public
replacement or is listed as *not yet* with its prerequisite. Line numbers refer to the pristine upstream tree.

1. **Patching host classes, prototypes and global tables.** This changes behaviour for every node and every pack in the session.
   Upstream instances:
   - `LGraphCanvas.prototype.processKey` (web/comfyui/services/key_events_services.js:17–18);
   - `drawNode` and `getNodeOnPos` (web/comfyui/label.js:132–145);
   - `LiteGraph.isValidConnection` (web/comfyui/utils.js:688);
   - `slot_types_default_out` (web/comfyui/context.js:113–115, dynamic_context_base.js:184–188);
   - `LiteGraph.ContextMenu` (web/comfyui/menu_auto_nest.js:10);
   - `processMouseDown` (web/comfyui/rgthree.js:249–250);
   - `drawGroups` (web/comfyui/feature_group_fast_toggle.js:85–86).

   *Replacements:* per-type `comfy.defs.extend` hooks, `isTypeCompatible`, public slot handles, and the Label
   presentation/canvas APIs. Not yet: group-header toggles (F08) and keyboard shortcuts (F11).
2. **Reading host-private objects or symbols** (`Object.getOwnPropertySymbols` on widgets,
   web/comfyui/utils_deprecated_comfyui.js:10). This crosses the isolation boundary and breaks between versions. *Replacement:* public widget
   handles (`getLabel`, `getOptions`, `getValue`).
3. **Injecting into host DOM** (`app.menu.settingsGroup.element.before`, web/comfyui/comfy_ui_bar.js:18,84; progress
   bar and message containers on `document.body`, web/comfyui/rgthree.js:222–229, 613–624). The host owns its DOM. *Replacement:* public
   chrome contributions (action buttons, top-bar badges) and `comfy.ui`. Not yet: the two-track progress-bar presentation (F12).
4. **Mutating the raw link table** (`app.graph.links[...]`, web/comfyui/reroute.js:307–430). This bypasses validation and undo
   and can corrupt graphs. *Replacement:* public link and slot handles. Not yet: Reroute insertion (F05).
5. **Intercepting or rewriting the built prompt** (`app.graphToPrompt` / `api.queuePrompt` wrappers, web/comfyui/rgthree.js:499–508,
   web/common/prompt_service.js:85). That exposes and alters other nodes' data. *Replacement:* public queue hooks
   (`onBeforeRun`, `onAfterRun`). Not yet: per-submission preparation (F07) and API-workflow import (F13).
6. **Hijacking in-flight canvas gestures** (`canvas.connecting_links`, web/comfyui/reroute.js:53, 116–142). The host owns gestures.
   *Replacement:* not yet; needs a host-owned link-gesture contribution (F05).
7. **Enumerating other packs and calling their lifecycle callbacks** (`comfyapp.extensions.map(...)`,
   web/comfyui/rgthree.js:285–293). That interferes across packs. *Replacement:* none needed; the host runs each pack's own hooks.
8. **Unrestricted attribute access in Power Puter's expression interpreter.** It does not call `eval`, but it resolves arbitrary
   attributes of live objects (`getattr(item, attr)`, py/power_puter.py:569), guarded only by a short blocklist. That exposes
   host internals to workflow text. *Replacement:* the bounded evaluator in `v2/py/safe_puter.py`.
9. **Host-wide VRAM purge** (`purge_vram` → `unload_all_models` / `soft_empty_cache`, py/power_puter.py:63–74, 152).
   This evicts other users' models. *Replacement:* none; the host manages memory.
10. **Writing to the host's file system at runtime, and serving it from raw routes on the host server:**
    - deleting ComfyUI's `web/extensions/rgthree*` with `shutil.rmtree` at import (`__init__.py:86–92`), which is outside the pack;
    - writing `rgthree_config.json` into the pack's own install folder (py/config.py:49,55);
    - JSON writes and removes (py/utils.py:128,149);
    - userdata files under the pack's folder (py/utils_userdata.py:21–29). The path join there has no `..` check, so a
      crafted name can reach outside the folder;
    - model-info sidecars written next to model files (py/server/utils_info.py:452);
    - the `/rgthree/api/*` routes (py/server/*.py).

    *Replacements:* public settings and pack storage (`services/config_service.js`, `common/model_info_storage.js`) and core
    authenticated routes. Not yet: provider-backed model info (F03) and the JS↔Python storage bridge (F04).
11. **Disclosing absolute host model paths** (`folder_paths.get_full_path`, py/power_lora_loader.py:72,
    py/server/routes_model_info.py:152–160, py/server/utils_info.py:416). That exposes the host layout. *Replacement:* logical
    names through the `assets` permission.
12. **Unaudited network fetches by the pack** (Civitai via `requests`, py/server/utils_info.py:327–339; update
    check via `aiohttp`, py/pyproject.py:49–56). *Replacement:* not yet; needs an admitted metadata provider (F03).
13. **Updating the host installation and other packs.** The bundled `__update_comfy__.py` script runs `git pull` across
    ComfyUI and every custom node, and runs `git restore .` where local changes block the pull. That rewrites code the pack
    does not own. *Replacement:* none needed in a pack. v2 never imports or runs the script (it is pristine-only); the host's
    own tooling updates installations.

## Accepted differences

- **Lora Loader Stack.** An invalid LoRA name is reported as `custom_validation_failed` on all four selector inputs, with
  the details prefixed `lora_0N - `. The original reports one `value_not_in_list` on the offending input. After the prefix,
  the details text is the original's. Cause: Core reports a failing `validate_inputs` once per validator input.
- **SDXL Power Prompt - Simple / Negative.** With CLIP width and height set, v2 returns the conditioning that the original
  computes with its intended (pre-V3) SDXL encode. On current Core the original's call fails and returns no conditioning.
  With an SD1 CLIP, v2 falls back to the plain encode described by the original's own log message.

## Blocked behaviours (missing host capability, not refused)

The host refuses these registrations because it would need their result synchronously. Since revision 3 a refusal costs
only the behaviour below, never the module. Each one is reported once in the console, by node type.

| Behaviour | Needs | Nodes |
| --- | --- | --- |
| Connection filtering: the cycle guard ("time paradox") and per-node connection rules | A connection policy the host can evaluate without a synchronous worker call (F17) | Fast Muter, Fast Bypasser, Node Collector, Node Combiner, Mute / Bypass Repeater, Mute / Bypass Relay, Fast Actions Button, Random Unmuter; Dynamic Context (opt-in) |
| Refusing links from disabled outputs | Same as above (F17) | Power Prompt, Power Prompt - Simple, SDXL Power Prompt - Positive, SDXL Power Prompt - Simple / Negative |
| Link fan-out when a link is dropped on empty canvas | A host-owned unplaced-link contribution (F18) | the six Context nodes |
| Menu items whose label depends on node state | None. A replacement with fixed labels and `when` predicates is planned for the next revision. | the six Context nodes ("Convert to …"); Power Primitive ("Show/Hide Type Selector Widget") |
| Dropping a workflow or image onto a node to import its values | A host node-drop contribution (F19) | all node types (pack feature) |
| Progress bar: queue size and interruption updates | Sandbox subscriptions for the published `queue.onPendingChanged` and `queue.onInterrupted` (F20) | rgthree progress bar |

## Pending items (not yet supported)

- F02 — repeated (dynamic) outputs for the opt-in Dynamic Context nodes.
- F03 — model metadata provider: trained words, Civitai details and images.
- F04 — same-user JS↔Python model-info storage continuity.
- F05 — Reroute insertion/reposition during an unfinished link drag.
- F06 — remaining Reroute presentation parity: per-link colour, low-zoom label suppression.
- F07 — Random Unmuter choosing independently for each prompt in a batch.
- F08 — fast toggle actions in group headers.
- F09 — Bookmark navigation into a hidden subgraph with the original viewport offset.
- F10 — Fast Groups navigation that fits the whole group.
- F11 — widget-configured keyboard shortcuts in the sandboxed realm.
- F12 — the original configurable two-track progress bar.
- F13 — Power LoRA Loader rows from API-format workflows; A1111 parameter import.
- F16 — delivery of the pack's model-browser and link-fixer pages.
- F17 — connection policy for sandboxed packs (replaces the synchronous `onBeforeConnect`).
- F18 — host-owned contribution for links dropped on empty canvas (replaces `onUnplacedLink`).
- F19 — host node-drop contribution (replaces `onDragOver`/`onDrop`).
- F20 — sandbox subscriptions for `queue.onPendingChanged` and `queue.onInterrupted`.
- Power Prompt LoRA and embedding insert combos when the model list exceeds the worker's definition bounds
  (needs a public model-catalogue read).

## Open test gates

- Host renderer prerequisites S01–S04 for the F01 layout port (24 node IDs). All four pass their tests. They still have
  to be deployed together as one frontend patch.
- Backend native cases running inside the Guest (sandboxed), and Core prompt validation at runtime for the Lora Loader Stack
  validator. Its checks pass structurally and in the Guest.
- Image Comparer with an empty image batch.
- Original-comparison runs for the eight frontend-only nodes listed as untested.
- Label browser acceptance after the host focus-race fix.
- Live asset delivery and CORS for `/rgthree/*` static files, including the logo.
- gVisor admission and whole-pack acceptance review.

## Authority and permissions

- No SDK permissions (12 nodes): the Context family, Any Switch, Display Int, KSampler Config, Seed, Power Prompt - Simple,
  SDXL Power Prompt - Simple / Negative.
- `assets` (4): Lora Loader Stack, Power Lora Loader, Power Prompt, SDXL Power Prompt - Positive.
- `raw` (7): Display Any, Image Inset Crop, Image Resize, Image or Latent Size, Power Primitive, Power Puter, SDXL Empty Latent Image.
- `ui` (1): Image Comparer.
- Frontend: `web/comfyui` loads into the sandboxed pack worker; static directory `rgthree` -> `web`. No pack HTTP routes.
  Runtime: Python >=3.13,<3.14.

## Assets and weights

No weights are committed. LoRAs, checkpoints, CLIP and embeddings come from the user's managed model catalogue.

