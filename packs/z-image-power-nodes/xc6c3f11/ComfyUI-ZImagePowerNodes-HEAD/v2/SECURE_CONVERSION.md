> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 31 of 31 upstream converted; 24 tested (scoped), 7 converted but untested/partly tested,
> 0 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> **Live UI blocked for 18 nodes (revision 3, 2026-10-20).** The live stack cannot register this pack's 6 custom
> widget types, so 18 nodes (the 7 partly tested plus 11 tested (scoped)) cannot be queued from the UI there.
> Their backend-scoped results stand. See "Revision 3".

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — Z-Image Power Nodes (`z-image-power-nodes`)

"Tested (scoped)" means the node's backend behaviour passed the conversion lane's original-versus-V2
subset (31 node IDs, 71 original-model cases), through the public SDK. It is not a whole-node certificate.
The 7 "partly tested" nodes depend on the pack's custom frontend widgets. Those widgets were rewritten
onto the public frontend API and source-reviewed, and the transport passes 9/9 protocol tests, but browser
acceptance is still open. Revision 2 changes only the frontend (Top-10 queue controller, entry module,
route calls) and this report; the node counts are unchanged because no browser test has run.
Revision 3 changes only this report. It records that the custom widget types cannot register on the live
stack, which blocks 18 nodes in the live UI, and it labels the 11 affected tested (scoped) nodes "backend only;
live UI blocked".

## Provenance

Upstream https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes at commit
`c6c3f11e558d25f89d8fbf9f92485ebff79aa5e1` (key `xc6c3f11`). The pristine tree beside `v2/` is
byte-exact at that commit (415 files). `v2/` is a complete copy of the pack with the conversion
applied. Two TEST-only oracle catalogue declarations were removed from the production manifest.
Their helper modules remain as test support and are not registered.

## Revision 3 (2026-10-20, docs only)

Only this report changes. No code, manifest or test changed, and nothing was run: the finding below comes from
reading the source of the live stack and of `v2/`.

**The six custom widget types do not register on the live stack.** The pack's frontend registers `ZIPN_SEPARATOR`,
`ZIPN_STYLE`, `ZIPN_PALETTE`, `ZIPN_PREDEFINED_STYLE`, `ZIPN_PREDEFINED_PALETTE` and `ZIPN_STYLE_GALLERY_BUTTON`
only through the published `comfy.defs.defineWidgetType`. The live sandbox (host-stack r3, guest `c6b97a15`) does
not implement it. The call goes through the sandbox's generic RPC proxy, the type's `render` function cannot cross
the worker boundary (DataCloneError), and the registration is rejected. The live host has no widget-type bridge
either. By the published API, an input whose type is not registered becomes a socket and its value is dropped.
Each affected node has required ZIPN inputs, so a prompt built in the UI in which one of them feeds an output is
rejected with "Required input is missing". Linking does not help: no node outputs the separator, gallery-button or
predefined-gallery types, and the only nodes that output `ZIPN_STYLE`/`ZIPN_PALETTE` (StyleLibraryV10,
PaletteLibraryV20) are blocked themselves.

Affected: 18 of 31 nodes.
- The 7 partly tested nodes: ZSamplerTurbo, ZSamplerTurboAdvanced, ZSamplerTurbo2Laboratory, StylePromptEncoder2,
  StyleStringInjector2, MyTop10Styles, MyTop10StylesEditor.
- 11 tested (scoped) nodes, now labelled "backend only; live UI blocked": ZSamplerTurbo2Simple, ZSamplerTurbo2,
  ZSamplerTurbo2Advanced, ZSamplerTurboX21, ImageFilter, ImageLabeler2, StyleLibraryV10, PaletteLibraryV20,
  StylePromptEncoderX21, StylePromptEncoderX22Advanced, CustomStylePromptEncoderX21.

The other 13 nodes have no custom-type input and are unaffected.

Counts are unchanged. The backend-scoped results stand for all 24 tested nodes; for the 11 above they do not
cover use from the live UI. The block lifts when the platform ships the `defineWidgetType` bridge (guest half and
host bridge), which has been requested from the platform owners. The browser acceptance spec is the gate:
`validation/20261020-z-image-live-widget-registration/ACCEPTANCE_SPEC.md`. Its first check (each widget type registers rather than becoming a
socket) is expected to fail on the live stack until the bridge ships.

The same source reading predicts two limits that remain after the bridge ships:
- The separator line takes its width from `ResizeObserver`, which is inert in the live sandbox, so `divider`
  separators would show as blank space of the right height.
- Choosing a gallery card with the mouse relies on `closest()`, which the live sandbox's element facade does not
  implement. The keyboard path (search, then Enter) does not need it.

Both are rows of the acceptance spec.

Corrections to revision 2:
- "Live guest `76f287a6` has no sandbox-side `defineWidgetType`; gallery widget registration needs a browser
  check" understated the gap. By source, registration cannot succeed on that guest or on the current live guest
  `c6b97a15`.
- "With the controller failing, the entry module kept all 6 gallery widget types registered" describes the
  revision 2 harness, which used a fake host. On the live stack none of the 6 register.

Evidence: `validation/20261020-z-image-live-widget-registration/`. It holds the input census from
`v2/secure-nodes.json`, source line references with file hashes (including the earlier guest `76f287a6`), and the
acceptance spec.

## Revision 2 (2026-10-15)

1. **Top-10 "next" now uses the deployed queue event.** Revision 1 advanced only through
   `comfy.queue.onAcceptedSubmission`, which the deployed host does not have. In the sandbox an unknown
   `comfy.*` member is a generic RPC proxy, so the call returned a promise that rejected (the listener
   cannot be structured-cloned) and "next" never advanced. **Revision 1's statement that single-run
   advancement worked through the public queue API was wrong for the deployed host.** Revision 2 uses
   `comfy.queue.onAfterRun`. That event fires once per Run attempt, after the whole batch loop, and only
   when at least one prompt was accepted. It carries `{promptIds, submissions, rejected}`. The controller
   advances once per accepted prompt (`promptIds.length` steps) and never for a rejected one.
2. **Installation never throws.** If any subscription fails, the Top-10 controller disposes every
   subscription it had registered before the failure and stays off. A failure can be synchronous, or
   arrive later as a rejected registration acknowledgement. The style gallery widgets are installed
   separately in `js/widgets.js` and keep working. Revision 1 disposed the galleries when the controller
   threw, and leaked the subscriptions registered before the throw.
   *Correction to the earlier lane finding that revision 1's installation throws:* in the deployed sandbox
   it did not throw. The unknown member is an RPC proxy, so the call returned a promise that rejected with
   an unhandled DataCloneError, the labels still worked, and "next" never advanced. Its dispose also failed,
   because it called promise-shaped registration results as functions. Revision 1 threw only on a host
   object that simply lacks the member.
3. **The legacy `afterQueued` controller is removed from `v2/`.** `js/my_top_styles.js` is deleted; see
   "Frontend entry modules" below.
4. **Own routes are called by relative path.** Own routes are called as `zi_power/<route>` relative paths,
   matching the existing declarations as mounted by route v3. The frontend calls
   `comfy.backend.fetch('zi_power/styles/by_version?v=…')` and
   `comfy.backend.fetch('zi_power/palettes/by_version?v=…')`. The manifest keeps the original declarations
   (`/zi_power/styles/by_version`, `/zi_power/palettes/by_version`). Route v3 accepts their legacy leading
   `/` as the same relative path and serves them at `/ext/<namespace>/zi_power/…`. The host adds the pack's
   namespace. There is no leading `/`, no `/ext/…`, and no `ownUrl`/`ownFetch`. The node schemas still pass
   the original endpoint strings to the widgets. `js/widgets/public/own_routes.js` maps exactly the two
   declared routes to their relative form and refuses any other endpoint without making a request. This
   keeps revision 1's route behaviour.

### Top-10 queue differential (controller level)

The ORIGINAL controller (pristine `js/my_top_styles.js` with its editor, common and timer modules,
unmodified) runs under a minimal LiteGraph/app fake. Its host loop follows the deployed frontend: an
accepted prompt runs `afterQueued` inside the batch loop, and a refused one breaks the loop first. The
CONVERTED controller runs against a fake sandboxed `comfy` whose `queue.onAfterRun` follows the deployed
semantics above. Widget writes cross an asynchronous boundary in that fake. Both sides use MOE's sealed r48
graphs, and the original side reproduces r48's sealed expectations.

| Case | Original: submitted → final | Revision 2: submitted → final | Result |
| --- | --- | --- | --- |
| fixed | [1] → 1 | [1] → 1 | match |
| single-run "next" | [1] → 2 | [1] → 2 | match |
| two-run "next" (two Runs, batch 1) | [1], [2] → 1 | [1], [2] → 1 | match |
| rejected "next" | [1] refused → 1 | [1] refused → 1 | match |
| batch = 2 "next" (one Run) | [1][2] → 1 | [1][1] → 1 | documented difference: final matches |

The negative control is the revision 1 controller on the same harness. With the deployed proxy shape it
gives single-run "next" [1] → 1 (no advance) and raises an unhandled DataCloneError. On a host object that
simply lacks the member, its installation throws and leaks `onWorkflowLoaded`. Robustness checks also pass.
Installation did not throw in any of 9 failure shapes. Every subscription registered before a failure was
disposed, including 12 widget listeners when the 13th failed. With the controller failing, the entry module
kept all 6 gallery widget types registered.

The test ran in one bounded container (512 MiB, 1 CPU, no network, read-only root), which was removed
afterwards. Evidence: lane `zimage-lane-20261015/rev2`, run2, `RESULT.json` sha256 `63491d54…`. The same
run checks the route mapping: the pack fetches only `zi_power/styles/by_version?v=…` and
`zi_power/palettes/by_version?v=…`, the live host's own-route builder turns them into
`/ext/<namespace>/zi_power/…`, and both match the manifest's declarations as route v3 mounts them.
It is not a browser test. The fakes do not cover real worker timing, Vue rendering, workflow switches
during a Run, subgraphs or partial execution.

## SaveImage //ZImagePowerNodes: Registry 2.0.0 → 2.1.1 (this pin) → v2 — COMPATIBLE, no migration

- The node id, widget order and hidden inputs are unchanged across 2.0.0, 2.1.1 and v2, and the node
  has no outputs in any of them. The widgets are `filename_prefix` (default `"ZImage"`), then
  `civitai_compatible_metadata` (default `True`); the hidden inputs are `prompt` and `extra_pnginfo`.
  A 2.0.0 workflow loads and runs unchanged. The Registry 2.0.0 zip is byte-identical to tag `v2.0.0`,
  and all 18 bundled 2.0.0 workflows are byte-identical in 2.1.1 and in `v2/`.
- Only the injected CivitAI metadata text differs, because of upstream's own 2.0.0 → 2.1.x changes:
  width and height are read from the latent node, ZSamplerTurbo is labelled `"zsampler_turbo"`, and
  `find_prompt` also reads an input named `prompt`. Pixels, file naming and the `prompt`/`workflow` PNG
  chunks are unchanged.
- The conversion writes through host-managed output with the node's own graph metadata. It needs a runtime
  with `png_text` support: the always-on engine has it, the older deploy-packs engine `12bbadf8ac04` does
  not. The bundled `ZImage/%date%/ZI` prefix keeps its subfolder and counter scheme. Prefixes are
  normalised with `os.path.normpath`, so unusual prefixes (a trailing `/`, `a//b`) may name files
  differently; the default and bundled prefixes are unaffected.
- Evidence is a source comparison of the three trees and the bundled workflows. MOE's exact PNG parity
  runs used prefix `"native"`; the subfolder/date prefix was not exercised.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode, including the original
`//ZImagePowerNodes` suffix and the deprecated/experimental subcategories).

| Node id | Disposition | Evidence or gap |
| --- | --- | --- |
| `ZSamplerTurbo2Simple //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (separator `divider`). Backend subset; public sampling (`raw`, `sample`, `inspect`). |
| `ZSamplerTurbo2 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (separators `divider`, `divider2`). Backend subset; public sampling. |
| `ZSamplerTurbo2Advanced //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (separators `divider`, `divider2`). Backend subset; public sampling. |
| `ZSamplerTurboX21 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (separator `divider1`). Backend subset; public sampling with `closures`. |
| `ZSamplerTurbo //ZImagePowerNodes` | converted, partly tested | Backend subset passes. **Live UI blocked** (separator `divider`): it cannot be queued from the live UI until the bridge ships. Browser acceptance (spec checks 0, B1) waits on it. |
| `ZSamplerTurboAdvanced //ZImagePowerNodes` | converted, partly tested | Same as ZSamplerTurbo (separator `divider`). |
| `ZSamplerTurbo2Laboratory //ZImagePowerNodes` | converted, partly tested | Same as ZSamplerTurbo (separators `divider1`-`divider4`). |
| `StylePromptEncoder2 //ZImagePowerNodes` | converted, partly tested | Backend subset passes. **Live UI blocked** (gallery button `gallery`, separator `spacer`): it cannot be queued from the live UI until the bridge ships. Browser acceptance (spec checks 0, B1, B2) waits on it. |
| `StyleStringInjector2 //ZImagePowerNodes` | converted, partly tested | Backend subset passes. **Live UI blocked** (gallery button `gallery`): it cannot be queued from the live UI until the bridge ships. Browser acceptance (spec checks 0, B2) waits on it. |
| `MyTop10Styles //ZImagePowerNodes` | converted, partly tested | Backend subset passes. "next" advances through the deployed `comfy.queue.onAfterRun`. In the controller differential, fixed, single-run, two-run and rejected match the original. With batch > 1, every prompt of a Run carries the starting selection, though the final selection matches (Pending). Browser queue run open. **Live UI blocked** (separator `divider`): it cannot be queued from the live UI until the bridge ships, so no browser queue run is possible yet (spec checks 0, B1, B3, C1-C5). |
| `MyTop10StylesEditor //ZImagePowerNodes` | converted, partly tested | Backend subset passes. **Live UI blocked** (gallery buttons `gallery_1`-`gallery_10`, separators `spacer_1`-`spacer_9`): it cannot be queued from the live UI until the bridge ships. Browser acceptance (spec checks 0, B1, B2, B3) waits on it. |
| `StylePromptEncoderX22Advanced //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (user-input combos `style`, `palette`). Backend subset. |
| `StylePromptEncoder //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `PhotoStylePromptEncoder //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `IllustrationStylePromptEncoder //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `StylePromptEncoderX21 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (galleries `style`, `palette`). Backend subset (deprecated node). |
| `CustomStylePromptEncoderX21 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (user-input combo `custom_style`). Backend subset (deprecated node). |
| `StyleStringInjector //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `StyleLibraryV10 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (gallery `style`). Backend subset (experimental node). |
| `PaletteLibraryV20 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (gallery `palette`). Backend subset (experimental node). |
| `EmptyZImageLatentImage //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `VAEEncodeSoftInpainting //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `AdvancedVAEDecoderX21 //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `LoadZImageModel //ZImagePowerNodes` | tested (scoped) | Backend subset; logical model names (`assets`, `models`). |
| `LoadQwen34bModel //ZImagePowerNodes` | tested (scoped) | Backend subset; logical model names (`assets`, `models`). |
| `ComfyKitchenAttentionEnabler //ZImagePowerNodes` | tested (scoped) | Backend subset; public `ModelRef.patch("attention_impl")`. |
| `ImageFilter //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (separators `divider1`-`divider3`). Backend subset (`raw`). |
| `ImageGridBuilder //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `ImageLabeler2 //ZImagePowerNodes` | tested (scoped) | **Backend only; live UI blocked** (separator `divider1`). Backend subset (`raw`). |
| `ImageLabeler //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node, `raw`). |
| `SaveImage //ZImagePowerNodes` | tested (scoped) | Backend subset; managed output plus the node's own graph metadata (`output`, `graph.metadata`). 2.0.0 workflows compatible (see above). |

## Frontend entry modules

The manifest declares `web_directory: "js"` (`__init__.py`: `WEB_DIRECTORY='./js'`). Core's
`/extensions` lists every `**/*.js` file under each web directory. The secure-nodes host takes over every
listed extension (`match: () => true`) and loads each file as an entry module into the pack's one worker.
The converted frontend is `js/widgets.js` with `js/widgets/public/*`.

- `js/my_top_styles.js` is **removed** from `v2/`. It was the upstream `afterQueued` controller (one step per
  accepted prompt, inside the batch loop), and the host listed and loaded it as an entry beside the
  converted controller. In the sandbox it cannot initialise: its `../../../scripts/app.js` import is the
  frontend's shim `export const app = window.comfyAPI.app.app`, and the worker's `window` has no
  `comfyAPI`. That is from reading the source; no browser check was run. But wherever it did run (overlay
  disabled, or a future legacy shim), "next" would have advanced twice. Nothing in `v2/` imports it.
- The other unconverted upstream modules remain in `js/` and `js/widgets/`. Every one of them that
  registers behaviour imports the legacy `scripts/app.js` or `scripts/ui.js`, directly or through its
  imports. Their own-route calls (`widgets/ui_styles.js`, `widgets/ui_palettes.js`) use the same relative
  helper. Removing them is a follow-up.

## Refused techniques (never-do) and their public replacements

No user-visible node or feature is refused. Only these techniques are:

1. **Attaching handlers directly to the host's server process** (`PromptServer.instance.routes`,
   `nodes/routes.py` lines 27–183). That runs pack code inside the shared server, outside any sandbox.
   *Replacement:* two routes declared in the manifest, which run in the pack's sandbox. The frontend reaches
   them by relative path (`zi_power/styles/by_version`, `zi_power/palettes/by_version`) through
   `comfy.backend.fetch`. Style samples come from a declared static directory.
2. **Opening model files by absolute host path** (`folder_paths.get_full_path_or_raise`,
   `nodes/load_zimage_model.py:100`, `nodes/load_qwen34b_model.py:126`). That exposes the host layout and allows unconfined reads.
   *Replacement:* logical model names through the `models`/`assets` permissions.
3. **Writing images straight into the host output directory** (`nodes/save_image.py:83`). That bypasses
   ownership and conflict rules. *Replacement:* managed output publication with the node's own graph metadata.
4. **Calling a host node implementation directly** (`execute_node("ModelAttentionBackend")`,
   `nodes/comfy_kitchen_attention_enabler.py:64`). That bypasses the executor's permission model.
   *Replacement:* the public, model-scoped `ModelRef.patch("attention_impl", ...)`.
5. **Frontend reach into host internals.** Upstream touches `app.graph`/`app.ui` (`js/common.js`, `js/comfyui_bridge.js`),
   calls raw `api.fetchApi` (`js/widgets/ui_styles.js:84`, `ui_palettes.js:81`) and injects styles into the host `<head>`
   (`js/common.js:37`, `js/widgets/gallery_dialog.js:1088`). It also attaches `afterQueued` to a widget
   (`js/my_top_styles.js:82`). *Replacement:* public `comfy` handles, relative `comfy.backend.fetch` calls to the pack's
   own routes, `comfy.queue.onAfterRun`, and pack-owned dialog styles (`js/widgets/public/*`).
6. **Standalone developer scripts** (`scripts/bulkgen.py` HTTP calls, `scripts/wfmigrator.py` file writes) are shipped
   unchanged as files but are never imported or executed by the node runtime.

## Pending capabilities (not yet supported)

- **Exact per-submission Top-10 advancement for batch > 1** needs a per-submission host hook, for example
  the specified `comfy.queue.onAcceptedSubmission`, which is not deployed. Today, with batch = N > 1,
  all N prompts of a Run carry the selection the Run started with, and the N steps follow the Run. The
  original built prompt i+1 after advancing. The final selection matches the original, and the submitted
  selections differ. This is the one accepted difference, and it closes when such a hook ships. Repeated
  Runs queued faster than the advance reaches the host can also reuse a selection; this is not measured.

- **Custom widget types in the sandbox** need the `defineWidgetType` bridge (guest half and host bridge), which
  the live stack does not have. Until it ships, 18 nodes cannot be queued from the UI (see "Revision 3").

## Open test gates

- Real-browser acceptance of the galleries, separators, user-input combos and the Top-10 editor/controller,
  including a real queue run of "next" on the deployed host. The revision 2 differential uses fakes of the
  host queue and the worker boundary. Spec:
  `validation/20261020-z-image-live-widget-registration/ACCEPTANCE_SPEC.md`. It can pass only after the
  `defineWidgetType` bridge ships.
- The `defineWidgetType` bridge (guest half and host bridge). The live stack (guest `c6b97a15`; earlier
  `76f287a6`) has none, so the 6 widget types cannot register and 18 nodes cannot be queued from the UI
  (see "Revision 3"). This is a platform gap, not a refusal. Check 0 of the acceptance spec is its test.
- The gallery catalogue end to end on the deployed backend: the relative `zi_power/<route>` calls against
  the route v3 mount of the existing declarations.
- Native frontend unit stage (ComfyApp) for the widget controllers.
- gVisor admission and whole-pack acceptance review.

## Authority and permissions

- Samplers: `raw`, `sample`, `inspect` (`ZSamplerTurboX21` adds `closures`).
- Loaders: `assets`, `models`. Attention enabler: `inspect`.
- Image utilities, latent and VAE nodes: `raw`. SaveImage: `raw`, `output`, `graph.metadata`.
- Style, palette, prompt and Top-10 nodes need no SDK permissions. No frontend permissions are requested,
  and the frontend uses no storage.
- Routes: the two declared GET routes above, called as `zi_power/<route>` relative paths. Static: `zimage-power-style-samples` -> `styles/samples`.

## Assets and weights

No model weights are committed. Users supply the Z-Image Turbo diffusion model, the Qwen3-4B text encoder and a
VAE through the managed model catalogue (safetensors or GGUF as upstream). The pack ships only its own
small images (README banner, icon, style sample thumbnails).
