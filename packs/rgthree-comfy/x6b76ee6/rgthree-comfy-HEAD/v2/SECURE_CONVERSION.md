> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 37 of 40 upstream converted; 2 tested (scoped), 35 converted but untested/partly tested,
> 3 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — rgthree-comfy (`rgthree-comfy`)

## What this revision contains

- **Base:** the registered Label revision (draft PR #6, commit `e7f5d08`). That is main `317175f` plus `label.js`, the new
  `label_drawing.js`, and `comfy-api.d.ts`.
- **Added:** 16 frontend files whose existing tests pass:
  - 14 files from the first repair tranche, covered by 70 focused original-comparison cases:
    - `web/comfyui/comfy_ui_bar.js`, `dialog_info.js`, `fast_groups_muter.js`, `power_conductor.js`, `power_lora_loader.js`,
      `random_unmuter.js`, `rgthree.js`, `services/config_service.js`, `widget_controls.js`
    - `web/common/model_info_service.js`, `model_info_storage.js`, `progress_bar.js`, `prompt_service.js`, `rgthree_api.js`
  - `web/comfyui/display_any.js` (F14 output serialization, checked against the original as an oracle).
  - `web/common/media/svgs.js`. Its logo now resolves against the module's own URL; that fixes an invalid-URL fetch in the
    sandboxed worker (6 hermetic cases).
- **Held back** (left at the PR #6 version and listed as open):
  - the Reroute definition and the F01 connection-layout port, both waiting on host renderer prerequisites S01–S04;
  - the optional Dynamic Context backend, waiting on the repeated-output API;
  - the host-side `comfy.defs.onRefreshed` fix, which is a separate host deployment.

## Provenance

Upstream https://github.com/rgthree/rgthree-comfy at commit `6b76ee6f2c5a007710b5a16f97c94330d6ecc871`
(key `x6b76ee6`). The pristine tree beside `v2/` is byte-exact at that commit (258 files). Upstream has
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
| `Any Switch (rgthree)` | converted, partly tested | Backend native cases pass. F01 connection layouts are not in this revision. |
| `Context (rgthree)` | converted, partly tested | Backend native cases pass; F01 is open. |
| `Context Big (rgthree)` | converted, partly tested | Backend native cases pass; F01 is open. |
| `Context Merge (rgthree)` | converted, partly tested | Backend native cases pass; F01 is open. |
| `Context Merge Big (rgthree)` | converted, partly tested | Backend native cases pass; F01 is open. |
| `Context Switch (rgthree)` | converted, partly tested | Backend native cases pass; F01 is open. |
| `Context Switch Big (rgthree)` | converted, partly tested | Backend native cases pass; F01 is open. |
| `Display Any (rgthree)` | converted, partly tested | Backend native cases pass; the F14 serialization fix ships here. F01 is open. An own-node PNG metadata candidate passed separately and is not in this revision. |
| `Display Int (rgthree)` | converted, partly tested | Backend native cases pass; F14 ships here. F01 is open. |
| `Fast Groups Bypasser (rgthree)` | converted, partly tested | Tested repair ships here (row state, graph-scoped identities, saved filters). F10 fit-group navigation is open. |
| `Fast Groups Muter (rgthree)` | converted, partly tested | Tested repair ships here. F10 is open. |
| `Image Inset Crop (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Image or Latent Size (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Label (rgthree)` | converted, partly tested | Browser: Classic 7/9 edits persist, Vue 8/9. The remaining focus race is a host renderer fix, still pending. |
| `Power Lora Loader (rgthree)` | converted, partly tested | Backend native cases pass. The tested repair ships here: authored model info, row info actions, stale-request guard. Open: F01, F03, F04, F13, and the startup callback error until the host `defs.onRefreshed` fix is deployed. |
| `Power Primitive (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Power Puter (rgthree)` | converted, partly tested | Backend native cases pass on the bounded evaluator. F03 and F04 are open. |
| `Random Unmuter (rgthree)` | converted, partly tested | The tested failed-attempt cleanup repair ships here. F07 (independent choice per batch item) and F01 are open. |
| `SDXL Power Prompt - Positive (rgthree)` | converted, partly tested | Backend native cases pass. F01 is open, plus the startup callback error (host fix pending). |
| `Seed (rgthree)` | converted, partly tested | Backend native cases pass. An own-node PNG metadata candidate passed separately and is not in this revision. F01 is open. |
| `Image Comparer (rgthree)` | converted, untested | Backend behaviour is not yet exercised; F01 is open. |
| `Image Resize (rgthree)` | converted, untested | Backend only; schema validated, behaviour not yet exercised. |
| `Lora Loader Stack (rgthree)` | converted, untested | Backend only; schema validated, behaviour not yet exercised. |
| `SDXL Empty Latent Image (rgthree)` | converted, untested | Backend only; schema validated, behaviour not yet exercised. |
| `Power Prompt (rgthree)` | converted, untested | Backend behaviour is not yet exercised. F01 is open, plus the startup callback error (host fix pending). |
| `Power Prompt - Simple (rgthree)` | converted, untested | Same as Power Prompt. |
| `SDXL Power Prompt - Simple / Negative (rgthree)` | converted, untested | Same as Power Prompt. |
| `Bookmark (rgthree)` | converted, untested | Frontend-only; its button-settings repair ships here. F09 (hidden-subgraph navigation) and F11 (keyboard) are open. |
| `Fast Actions Button (rgthree)` | converted, untested | Frontend-only. F01 and F11 are open. |
| `Fast Bypasser (rgthree)` | converted, untested | Frontend-only. F01 is open. |
| `Fast Muter (rgthree)` | converted, untested | Frontend-only. F01 is open. |
| `Mute / Bypass Relay (rgthree)` | converted, untested | Frontend-only. F01 is open. |
| `Mute / Bypass Repeater (rgthree)` | converted, untested | Frontend-only. F01 is open. |
| `Node Collector (rgthree)` | converted, untested | Frontend-only. F01 is open. |
| `Node Combiner (rgthree)` | converted, untested | Legacy frontend-only node. F01 is open. |
| `Reroute (rgthree)` | missing | The frontend definition is not in this revision. A candidate exists: host prerequisites S01–S03 pass and S04 is in progress. F05 and F06 are open. |
| `Dynamic Context (rgthree)` | pending capability | Opt-in, disabled upstream by default. Needs a public repeated-output API (F02); a runtime test of that candidate is approved. |
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
8. **Unrestricted evaluation in Power Puter**, reaching arbitrary attributes of live objects (`getattr(item, attr)`,
   py/power_puter.py:569). That puts arbitrary code on the host. *Replacement:* the bounded evaluator in `v2/py/safe_puter.py`.
9. **Host-wide VRAM purge** (`purge_vram` → `unload_all_models` / `soft_empty_cache`, py/power_puter.py:63–74, 152).
   This evicts other users' models. *Replacement:* none; the host manages memory.
10. **Writing or deleting host files outside the pack**, and serving them from raw routes on the host server:
    - `shutil.rmtree` of ComfyUI `web/extensions/rgthree*` at import (`__init__.py:86–92`);
    - `rgthree_config.json` in the install directory (py/config.py:49,55);
    - JSON writes and removes (py/utils.py:128,149; py/utils_userdata.py:21–29);
    - model-info sidecars (py/server/utils_info.py:452);
    - the `/rgthree/api/*` routes (py/server/*.py).

    *Replacements:* public settings and pack storage (`services/config_service.js`, `common/model_info_storage.js`) and core
    authenticated routes. Not yet: provider-backed model info (F03) and the JS↔Python storage bridge (F04).
11. **Disclosing absolute host model paths** (`folder_paths.get_full_path`, py/power_lora_loader.py:72,
    py/server/routes_model_info.py:152–160, py/server/utils_info.py:416). That exposes the host layout. *Replacement:* logical
    names through the `assets` permission.
12. **Unaudited network fetches by the pack** (Civitai via `requests`, py/server/utils_info.py:327–339; update
    check via `aiohttp`, py/pyproject.py:49–56). *Replacement:* not yet; needs an admitted metadata provider (F03).

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
- Power Prompt LoRA and embedding insert combos when the model list exceeds the worker's definition bounds
  (needs a public model-catalogue read).
- Startup callback errors (`comfy.defs.onRefreshed` inside the sandbox): a host fix is written and tested,
  with 1 negative control plus 8 cases passing, and is awaiting review and deployment.

## Open test gates

- Host renderer prerequisites S01–S04 for the F01 layout port (24 node IDs). S04 has one failure under diagnosis.
- Backend behaviour runs for Image Comparer, Image Resize, Lora Loader Stack, Power Prompt, Power Prompt - Simple,
  SDXL Empty Latent Image, and SDXL Power Prompt - Simple / Negative.
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

