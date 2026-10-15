> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 31 of 31 upstream converted; 24 tested (scoped), 7 converted but untested/partly tested,
> 0 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — Z-Image Power Nodes (`z-image-power-nodes`)

"Tested (scoped)" means the node's backend behaviour passed the conversion lane's original-versus-V2
subset (31 node IDs, 71 original-model cases), through the public SDK. It is not a whole-node certificate.
The 7 "partly tested" nodes depend on the pack's custom frontend widgets. Those widgets were rewritten
onto the public frontend API and source-reviewed, and the transport passes 9/9 protocol tests, but browser
acceptance is still open.

## Provenance

Upstream https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes at commit
`c6c3f11e558d25f89d8fbf9f92485ebff79aa5e1` (key `xc6c3f11`). The pristine tree beside `v2/` is
byte-exact at that commit (415 files). `v2/` is a complete copy of the pack with the conversion
applied. Two TEST-only oracle catalogue declarations were removed from the production manifest.
Their helper modules remain as test support and are not registered.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode, including the original
`//ZImagePowerNodes` suffix and the deprecated/experimental subcategories).

| Node id | Disposition | Evidence or gap |
| --- | --- | --- |
| `ZSamplerTurbo2Simple //ZImagePowerNodes` | tested (scoped) | Backend subset; public sampling (`raw`, `sample`, `inspect`). |
| `ZSamplerTurbo2 //ZImagePowerNodes` | tested (scoped) | Backend subset; public sampling. |
| `ZSamplerTurbo2Advanced //ZImagePowerNodes` | tested (scoped) | Backend subset; public sampling. |
| `ZSamplerTurboX21 //ZImagePowerNodes` | tested (scoped) | Backend subset; public sampling with `closures`. |
| `ZSamplerTurbo //ZImagePowerNodes` | converted, partly tested | Backend subset passes. Its separator widgets need browser acceptance. |
| `ZSamplerTurboAdvanced //ZImagePowerNodes` | converted, partly tested | Same as ZSamplerTurbo. |
| `ZSamplerTurbo2Laboratory //ZImagePowerNodes` | converted, partly tested | Same as ZSamplerTurbo. |
| `StylePromptEncoder2 //ZImagePowerNodes` | converted, partly tested | Backend subset passes. The style gallery widgets need browser acceptance. |
| `StyleStringInjector2 //ZImagePowerNodes` | converted, partly tested | Backend subset passes. The style gallery widgets need browser acceptance. |
| `MyTop10Styles //ZImagePowerNodes` | converted, partly tested | Backend subset passes, and the single-run controller is on the public queue API. Exact per-submission advancement for multi-run batches waits on the host accepted-submission callback (pending). |
| `MyTop10StylesEditor //ZImagePowerNodes` | converted, partly tested | Backend subset passes. The editor widgets need browser acceptance. |
| `StylePromptEncoderX22Advanced //ZImagePowerNodes` | tested (scoped) | Backend subset. |
| `StylePromptEncoder //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `PhotoStylePromptEncoder //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `IllustrationStylePromptEncoder //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `StylePromptEncoderX21 //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `CustomStylePromptEncoderX21 //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `StyleStringInjector //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node). |
| `StyleLibraryV10 //ZImagePowerNodes` | tested (scoped) | Backend subset (experimental node). |
| `PaletteLibraryV20 //ZImagePowerNodes` | tested (scoped) | Backend subset (experimental node). |
| `EmptyZImageLatentImage //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `VAEEncodeSoftInpainting //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `AdvancedVAEDecoderX21 //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `LoadZImageModel //ZImagePowerNodes` | tested (scoped) | Backend subset; logical model names (`assets`, `models`). |
| `LoadQwen34bModel //ZImagePowerNodes` | tested (scoped) | Backend subset; logical model names (`assets`, `models`). |
| `ComfyKitchenAttentionEnabler //ZImagePowerNodes` | tested (scoped) | Backend subset; public `ModelRef.patch("attention_impl")`. |
| `ImageFilter //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `ImageGridBuilder //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `ImageLabeler2 //ZImagePowerNodes` | tested (scoped) | Backend subset (`raw`). |
| `ImageLabeler //ZImagePowerNodes` | tested (scoped) | Backend subset (deprecated node, `raw`). |
| `SaveImage //ZImagePowerNodes` | tested (scoped) | Backend subset; managed output plus the node's own graph metadata (`output`, `graph.metadata`). |

## Refused techniques (never-do) and their public replacements

No user-visible node or feature is refused. Only these techniques are:

1. **Attaching handlers directly to the host's server process** (`PromptServer.instance.routes`,
   `nodes/routes.py` lines 27–183). That runs pack code inside the shared server, outside any sandbox.
   *Replacement:* two routes declared in the manifest (`/zi_power/palettes/by_version`, `/zi_power/styles/by_version`),
   which run in the pack's sandbox, plus a declared static directory for style samples.
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
   (`js/common.js:37`, `js/widgets/gallery_dialog.js:1088`). *Replacement:* public `comfy` handles, `comfy.backend` calls to
   the declared routes, and pack-owned dialog styles (`js/widgets/public/*`).
6. **Standalone developer scripts** (`scripts/bulkgen.py` HTTP calls, `scripts/wfmigrator.py` file writes) are shipped
   unchanged as files but are never imported or executed by the node runtime.

## Pending capabilities (not yet supported)

- Exact Top-10 advancement for every accepted submission in a multi-run batch needs the host's
  accepted-submission callback, which awaits committed host writes before the next prompt is built.
  The callback is source-reviewed and passes its protocol tests but is not deployed. Single-run advancement works through the public queue API.

## Open test gates

- Native frontend unit stage (ComfyApp) for the accepted-submission callback and the widget controllers.
- Real-browser acceptance of the galleries, separators, user-input combos, and the Top-10 editor/controller.
- Four original-versus-converted ordinary queue cases: fixed, single "next", two-run "next", rejected "next".
- gVisor admission and whole-pack acceptance review.

## Authority and permissions

- Samplers: `raw`, `sample`, `inspect` (`ZSamplerTurboX21` adds `closures`).
- Loaders: `assets`, `models`. Attention enabler: `inspect`.
- Image utilities, latent and VAE nodes: `raw`. SaveImage: `raw`, `output`, `graph.metadata`.
- Style, palette, prompt and Top-10 nodes need no SDK permissions. No frontend permissions are requested.
- Routes: the two declared GET routes above. Static: `zimage-power-style-samples` -> `styles/samples`.

## Assets and weights

No model weights are committed. Users supply the Z-Image Turbo diffusion model, the Qwen3-4B text encoder and a
VAE through the managed model catalogue (safetensors or GGUF as upstream). The pack ships only its own
small images (README banner, icon, style sample thumbnails).

