> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 21 of 21 converted; 19 tested (scoped), 0 converted but untested/partly tested,
> 2 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> Status line: source 21/21 · scoped runtime 19/21 · certificates 0/21 · node-facing routes 3 declared, 0 working on live (request #15) · frontend 0/17 browser-tested.
> **Live: Load Image Metadata fails on every image (revision 7, 2026-10-20).** The live service has no `piexif`, which the
> node imports on every run, and this pack declares no dependency profile. No other node imports a package the live
> service lacks. See "Revision 7".
> **Revision 8 (2026-10-21):** the Unet Loader's GGUF branch is ported and tested (scoped) on the a2 base; on the live
> service it still fails until the host ships native ComfyUI-GGUF and the gguf package. See "Revision 8".
> **Revision 9 (2026-10-21):** Lora Info's frontend and its 3 routes are ported; the node is partial. Every route
> function needs platform request #15, so on live the widget shows "No LoRA selected" or route errors. See "Revision 9".
> **Revision 10 (2026-10-26):** one self-registering frontend entry, `secure_web/lm_frontends.js`. On the live service
> it activates the Prompt and Lora Stack Combiner sockets, Save Image's widget toggling, the Debug Metadata panel and
> Create Hook's `prev_hooks` socket; the LoRA rows and text widgets wait for the host's widget-type bridge (#11, r4a).
> Frontend logic is unit-tested on host fakes only, so the counts are unchanged. See "Revision 10".

# LoRA Manager — Secure V2 conversion (in progress)

## Provenance

- Upstream: https://github.com/willmiao/ComfyUI-Lora-Manager
- Pinned commit: `2dcaf6a30e50e6eace230c8311f25890a23473f0` (1034 tracked files; every blob verified against the commit).
- Registry name: `comfyui-lora-manager` (publisher `willmiao`).
- Mode: mirror. Node ids, display names and categories are the original ones.
- Conversion source: the integrated candidate with the merged common source (21 registered nodes, including the
  restored Lora Loader queue validator). Schemas and validator signatures of all 21 nodes were re-checked on the
  pinned SDK (Core `6257422`, backend `745b88f`) on 2026-10-15: 21/21 equal to the expected rows.
- `v2/__init__.py` registers the 21 nodes through `comfy_api.latest`; `WEB_DIRECTORY` is `./secure_web`
  (the in-graph frontend). Unchanged upstream files are carried as `copy` entries.

## Revision 10 (2026-10-26): self-registering frontends

Revision 10 adds `secure_web/lm_frontends.js`, which registers the pack's frontends when the host loads it, as
`lora_info.js` does, and changes only `secure_web/` and this report. Python, schemas, `secure-nodes.json` and every
other file are unchanged, and no node's disposition changes.

| Frontend | Live service (host-stack r3, guest c6b97a15) | Host-stack r4a (widget-type bridge #11; not deployed) |
| --- | --- | --- |
| Prompt: dynamic `trigger_wordsN` sockets | active | active; `text` becomes a text box |
| Lora Stack Combiner: dynamic `lora_stackN` sockets | active | active |
| Save Image: webp/jpeg widget toggling | active; the `%…%` filename expansion stays held (needs a `beforeSerialize` replacement value) | same |
| Debug Metadata: execution metadata panel | active; not restored from a saved workflow (needs the mount value handle) | same |
| Create Hook LoRA | adds the optional `prev_hooks` socket; its rows editor and text wait for r4a | rows editor and text, kept in sync |
| Lora Loader, Lora Stacker | inert: their inputs stay sockets, as before | rows editor and text, kept in sync; the Stacker gains its optional `lora_stack` socket |
| Text, WanVideo Lora Select | inert | text box and rows editor; saved-workflow restore only (WanVideo's edit-time sync stays held) |

- **Widget types.** LORAS, AUTOCOMPLETE_TEXT_LORAS and AUTOCOMPLETE_TEXT_PROMPT register through
  `comfy.defs.defineWidgetType`. On the live service the call is refused and nothing changes.
- **Saved workflows.** The original saves a hidden `{"version":1,"textWidgetName":"text"}` value before each autocomplete
  text, and core restores `widgets_values` by position, so on r4a an original save would land shifted by one. Each
  affected node recognises its exact layout in `onConfigured` and restores the values by name:
  - Lora Loader, Lora Stacker and Create Hook LoRA: `[meta, text, rows]`;
  - Prompt and Text: `[meta, text]`;
  - WanVideo Lora Select: `[low_mem_load, merge_loras, meta, text, rows]`.
  Rows go through the same normalization as the original LORAS widget setter. Older saves and this revision's own saves
  are left as they are. A WanVideo save from before `merge_loras` existed is placed by position, as on the live service
  today, and is not repaired.
- **Still held:** TriggerWord Toggle's frontend (a widget type cannot reproduce its prompt serializer exactly),
  autocomplete and keyboard insertion, node markers, manager settings, the workflow registry and templates, and the
  Lora Randomizer's and WanVideo Lora Select's own frontend behaviour.
- **Evidence:** 64/64 unit tests over hermetic host fakes of the live guest and r4a, and 7 mutants, each caught by its
  intended tests; a repeat run was byte-identical (`validation/20261026-lora-manager-rev10-frontends/`).
  - The retained first attempt (62/64) failed one test on a stale expectation, which the recorded run corrects.
  - This is frontend-logic evidence, not a browser run, a backend run or an original-versus-converted comparison.
  - The status line keeps "frontend 0/17 browser-tested", the counts stay 19/21 scoped, and the existing native and
    browser holds above and under Pending are unchanged.
- **Recorded difference** (inherited; Lora Loader, Lora Stacker, WanVideo Lora Select). A saved row with no `expanded`
  field and a CLIP strength different from its model strength restores with `expanded: true`, where the original
  restores `expanded: false`. Both strengths restore equal. A later strength edit in the rows editor can then differ,
  because only a collapsed row copies the strength to CLIP. The pack's own example rows all carry `expanded`.
- **Deliberate difference:** row on/off state is shown with inline styles, because the host sanitizer removes
  `aria-pressed`, `aria-checked` and `aria-expanded`.

## Revision 9 (2026-10-21): Lora Info frontend and routes

Revision 9 ports the Lora Info node's frontend and the 3 server routes it calls, and changes nothing else. The node's
backend stays a no-op, as upstream.

- `secure_web/lora_info.js` (new) mirrors the original `web/comfyui/lora_info.js` and `LoraInfoWidget.vue`: the
  wire-only `lora_source` input, the selection pushed from directly wired LoRA list nodes (stale answers dropped),
  clearing when the wire is removed, the Notes tab (file name, editable notes, Save with the original's toasts) and the
  Description tab. It registers itself through the public frontend API (`comfy.defs.extend`), calls only the pack's own
  routes with `comfy.backend.fetch` and pack-relative paths, and uses only members the live guest implements.
- `secure_services/lora_info_routes.py` (new) holds the 3 route handlers. They read the sidecar `.metadata.json`
  through read-only SDK `assets` calls, never a host path, and return logical names.
- `secure-nodes.json` gains a top-level `routes` list with these 3 routes. The 21 node rows, the runtime and the web
  directory are unchanged, and the node's own permissions stay (none).

| Route (pack-relative) | Handler | Permissions | Original |
| --- | --- | --- | --- |
| `GET /lm/loras/get-notes` | `get_notes` | assets, storage | `GET /api/lm/loras/get-notes?name=` |
| `GET /lm/loras/metadata` | `get_metadata` | assets | `GET /api/lm/loras/metadata?file_path=` |
| `POST /lm/loras/save-metadata` | `save_notes` | assets, storage | `POST /api/lm/loras/save-metadata` |

Recorded deliberate differences (`validation/20261021-lora-manager-lora-info-a2base-r3/PORT_NOTES.json`):
- Save writes the notes to a pack-owned storage record, never to the model's sidecar file. The record is shown instead
  of the sidecar notes when it exists.
- Descriptions are shown as plain text. The original renders third-party Civitai HTML with `v-html`, an XSS sink in
  the host page.
- The saved workflow keeps the logical file name, never a host path. An original workflow's absolute `filePath` is
  dropped.

Other recorded differences: two LoRAs with the same stem resolve the exact relative path first; only the default
sidecar layout is read; the original's side effects (default sidecar creation, example-image pruning, cache sync) are
absent.

Lora Info is **partial**: every route function (saved notes, sidecar notes, descriptions) needs platform request #15
(route assets runtime); on live today the widget shows 'No LoRA selected' / route errors; parity proven only under a
harness stand-in. Today a route call gets no execution runtime on the host, so its first `assets` call is refused
("no active execution for this guest"). No LoRA selection reaches the node on live yet either: the LoRA list widget it
listens to is not registered (request #11).

Evidence (`validation/20261021-lora-manager-lora-info-a2base-r3/`): one selected bounded run (Tier R) on the a2
base (core a2 `d1a9259`, backend a1 `894ead3`), sandbox off, no model.
- Live behaviour: 3 control rows on the unmodified backend, with no stand-in. All 3 routes are refused with
  "no active execution for this guest".
- Parity with the original's own handler and service code on synthetic sidecars. These rows ran under a test-harness
  stand-in that binds a runtime to each route call, labelled "parity under a harness stand-in for platform request #15
  (not live behaviour)". Its code and hash are in the evidence; it is not part of the pack. Results: notes 15 of 16
  cases equal plus 1 recorded difference, descriptions 11 of 11, save and read-back 16 of 16 checks.
- Frontend logic: 29 checks against a fake of the live guest API (Node.js, no browser). The browser smoke plan waits
  for request #15.
- Two earlier attempts failed in the test harness and in the run image, not in the port; both are kept on record.

A route request body near 1 MiB cannot reach its handler, because the host's wire frame limit (1 MiB including the
envelope) stops it first. This is recorded for the route documentation.

## Revision 8 (2026-10-21): Unet Loader GGUF branch

Revision 8 ports the Unet Loader's GGUF branch and changes nothing else. The `.gguf` branch now calls the public
`models.load_gguf_model`, which builds the model with the host's fixed ComfyUI-GGUF module exactly as the original
branch does (`gguf_sd_loader`, `GGMLOps`, `load_diffusion_model_state_dict` with metadata, `GGUFModelPatcher`). The
original resolves `weight_dtype` with `getattr(torch, weight_dtype, None)`, which is `None` for every option this node
offers, so the verb's default dequantization is the original's effective behaviour. Load failures keep the original's
"Failed to load GGUF diffusion model '<name>': ..." wrapper. The queue validator checks a `.gguf` name with a read-only
`assets.exists` in the diffusion-model roots (core's diffusion-model list holds no GGUF files), so the node gains the
`assets` permission, as the Checkpoint Loader has.

Evidence (`validation/20261021-lora-manager-unet-gguf-a2base-r3/`): one selected bounded run on the a2 base (deployed core plus the GGML SDK files; the GGUF
verb is identical to the deployed one), sandbox off, no model built. It shows construction-call parity with the
original GGUF branch on 3 fixtures (one under all 4 `weight_dtype` values), the same refusal on 2 more, 9 queue-validation
names, 4 mutants each caught by its intended check, and the manifest row equal to the backend encoders. Both sides used
the pristine upstream ComfyUI-GGUF loaded as a native custom node. Two earlier attempts failed in the test itself and
are kept on record.

Recorded deliberate differences (`validation/20261021-lora-manager-unet-gguf-a2base-r3/PORT_NOTES.json`):
- no `cached_patcher_init` reload factory on the returned model;
- the patch dtype is always the default (the original reads a shared class that an earlier ComfyUI-GGUF Advanced load
  can change);
- an unknown GGUF name is refused by the existence check instead of the scanner list, and LoRA Manager's extra scanner
  roots are not searched;
- an upper-case `.GGUF` name is refused at queue time (the original lists it and then fails in the standard loader);
- error texts name the logical file, never a host path, and the text after the wrapper carries the host exception's
  type name.

On the live service the GGUF branch still fails: the host has no native ComfyUI-GGUF and no `gguf` package
(request #12). The node's dropdown (`/models/diffusion_models`) does not list GGUF files, so GGUF names reach the node
from saved workflows or the API.

## Revision 7 (2026-10-20, docs only): live dependency status

Only this report changes. No code, manifest or test changed, and nothing was run.

**Load Image Metadata fails on the live service for every image.** For every image, the node's `execute` reads the
metadata source, and that path imports `piexif` first (`secure_services/image_metadata_source.py`,
`fields_from_bytes`). This pack's manifest declares no dependency profile, and a read-only filesystem check of the
live service on 2026-10-20 found no `piexif`. A queued run therefore passes validation (which only checks that the
image exists), decodes the pixels, and then fails with `ModuleNotFoundError: No module named 'piexif'`. The original
has the same requirement (`requirements.txt`; `py/utils/exif_utils.py` imports `piexif` at module level). The earlier
scoped tests supplied piexif 1.1.3 through a trusted dependency root, so their evidence holds only where piexif is
provided.

No other node is affected. An import census of every module the 21 registered nodes reach finds no other
third-party import besides the core-provided `torch`, `numpy`, `PIL` and `av`.

Related live facts, with no status change:
- Unet Loader's GGUF branch is refused in this conversion. The SDK verb a port would use (`models.load_gguf_model`)
  also needs a host-installed ComfyUI-GGUF custom node and its `gguf` package. The live service has neither.
- Compressed AVIF `brob` and JPEG XL are refused in this conversion. The live service has neither `brotli` nor a
  JPEG XL decoder.

Counts are unchanged. Load Image Metadata was already partial; its row now says that it is broken on live. A fix
needs a dependency profile that declares `piexif` (and `brotli` for compressed `brob`) and that the live service
provides.

Evidence: `validation/20261020-lora-manager-live-dependencies/` (import census, line references with file hashes, and the live check).

## Per-node status

Dispositions: tested (scoped) = runtime evidence for the listed scope only; converted-untested = source
converted, no runtime evidence yet; partial = known missing behavior. No node has a whole-node certificate.

| Node id | Disposition | Evidence (scoped) | Open gap |
| --- | --- | --- | --- |
| Prompt (LoraManager) | tested (scoped) | shared gVisor workflow (R50) | authored library import/persistence/cache; frontend sync |
| Text (LoraManager) | tested (scoped) | shared gVisor workflow (R50) | wildcard/library lifecycle; frontend |
| Lora Loader (LoraManager) | tested (scoped) | gVisor workflows (R51/R52/R55); queue validator native-vs-Guest parity 2/2 + permission-denial control | cache acquisition on all paths; opaque metadata; other model branches; frontend |
| LoRA Text Loader (LoraManager) | tested (scoped) | gVisor workflows (R51/R52/R55) | syntax/library/cache/metadata; frontend |
| Checkpoint Loader (LoraManager) | tested (scoped) | queue parity 3/3; real SD1.5 + LCM bf16 CPU secure-Guest workflow | extra scanner roots; base-model list; installed gVisor workflow |
| Unet Loader (LoraManager) | tested (scoped) | queue parity 3/3; real extracted SD1.5 UNet bf16 CPU secure-Guest workflow; GGUF branch (revision 8): a2 base: construction-call parity on 3 GGUF fixtures (one under all 4 weight_dtypes) and the same refusal on 2 more, queue validation (9 names), 4 mutants caught; deliberate differences per PORT_NOTES; fails on live until the host ships native ComfyUI-GGUF + gguf (request #12) | installed gVisor workflow; a real GGUF model load; LoRA Manager's extra scanner roots |
| TriggerWord Toggle (LoraManager) | tested (scoped) | gVisor workflow (R6) | lifecycle/restore/state; transport identity |
| Lora Stacker (LoraManager) | tested (scoped) | native-vs-Guest parity: getter 8 cases, strict queue validator 28, metadata lifecycle 8 phases, stale-file deletion 2 | multi-root order; installed queue; frontend |
| Lora Stack Combiner (LoraManager) | tested (scoped) | gVisor workflows (R6/R7) | tuple transport/identity; editor lifecycle |
| Save Image (LoraManager) | tested (scoped) | gVisor (R72/R80); native parity: byte-identical PNGs from the real cache, 24 resource/formatter cases, 12 caught-error/WebP-continuation cases; real SD1.5 + LCM CPU Guest run resolves LoRA hashes without sidecars, with and without prompt LoRA tags | multi-root; installed JPEG EXIF/HWC; WebP workflow metadata (pending SDK); recipe/no-counter/overwrite; frontend |
| Debug Metadata (LoraManager) | tested (scoped) | gVisor workflow (R66) | wired opaque model/sampler fields; ancestry |
| WanVideo Lora Select (LoraManager) | tested (scoped) | gVisor workflow (R78) | trained WAN consumer; discovery/multi-root; frontend |
| WanVideo Lora Select From Text (LoraManager) | tested (scoped) | gVisor workflow (R78) | trained WAN consumer; discovery/multi-root; frontend |
| Lora Pool (LoraManager) | tested (scoped) | gVisor workflow (R49) | mutation/persistence/preview; frontend seed/index |
| Lora Randomizer (LoraManager) | tested (scoped) | native-vs-Guest parity: getter 10 cases, strict queue validation 22 + 2 error controls, fixed mode 5 | full queue; global RNG; multi-root; frontend |
| Lora Cycler (LoraManager) | tested (scoped) | native-vs-Guest parity: 14 cases | multi-root/tie order; mutation/cache; frontend index |
| Lora Info (LoraManager) | partial | revision 9 (frontend + 3 declared routes), Tier R on the a2 base: 3 control rows show the live refusal; under a harness stand-in, notes 15/16 equal + 1 recorded difference, descriptions 11/11, save and read-back 16/16; frontend logic 29 checks (no browser) | every route function (saved notes, sidecar notes, descriptions) needs platform request #15 (route assets runtime); on live today the widget shows 'No LoRA selected' / route errors; parity proven only under a harness stand-in; no selection source on live (LoRA list widget, request #11); browser smoke (queued until #15) |
| LoRA Syntax → Path (LoraManager) | tested (scoped) | real CPU workflow: library-relative name with extension; saved PNG contains no host path | additional parser cases; installed gVisor workflow |
| Create Hook LoRA (LoraManager) | tested (scoped) | gVisor workflows (R64/R70) | CLIP hooks need the SetClipHooks host operation; lifecycle |
| Metadata Overwrite (LoraManager) | tested (scoped) | gVisor workflow (R8) | wired MODEL/SAMPLER identity; ancestry |
| Load Image Metadata (LoraManager) | partial | retained19-case managed decoder; 12 exact named-container and8 exact upstream12/10-bit PQ native comparisons on composed leaf; managed input/output/temp annotations; raw AVIF brob | **Broken on live: `piexif` missing (Revision 7).** compressed brob/JXL; full/rotated AVIF animation; HDR rendering; admitted piexif profile; installed gVisor and browser/selector lifecycle |

## Refused techniques (never do) and public replacements

| Refused technique | Public replacement |
| --- | --- |
| Emitting absolute host filesystem paths from a node (upstream LoRA Syntax → Path output) | Library-relative names: the path under its LoRA root, `/`-separated, with extension (what ComfyUI LoRA loaders accept). A negative test must show no host path is ever emitted. |
| Importing ComfyUI internals from node code (`comfy`, `folder_paths`, `nodes`, `server`, `execution`, ...) | `comfy_api.latest` (`io` schemas and `sdk` context) only |
| Reading or writing model folders and sidecar files directly (directory walks, `.metadata.json` next to models) | SDK assets (`list`, `resolve`, `exists`, `digest`, image loading) and pack-owned durable records in SDK storage |
| Process-global services started at import (scanner registries, background tasks, websocket broadcasts) | A pack-owned catalogue cache refreshed through the SDK; per-node outputs and UI payloads |
| Registering handlers directly on the ComfyUI server | Declared, pack-relative routes in `secure-nodes.json`, mounted by the host under the pack's own route base (the 3 Lora Info routes, revision 9); the routes in `secure_routes/` are still held, see Pending |
| Rendering third-party HTML (Civitai descriptions) in the host page with `v-html` | Plain text: tags stripped, entities decoded (Lora Info, revision 9) |

## Pending — not yet supported (can't yet, not never)

Out of scope for this milestone (node-facing acceptance first). Each must fail cleanly; negative tests are an open gate.

| Feature | Status |
| --- | --- |
| Standalone LoRA Manager web app (library pages, statistics, recipes pages, example images, settings pages) | PENDING — not yet supported, needs host-served pack pages with library storage and asset-management capabilities |
| Library management (rename, delete, bulk organize, metadata refresh from the manager) | PENDING — not yet supported, needs asset write/delete capabilities |
| CivitAI / CivArchive downloads and metadata sync | PENDING — not yet supported, needs an allow-listed provider network integration and asset write capability |
| Moving model files (move to folder, auto-organize) | PENDING — not yet supported, needs an asset move capability |
| WebP workflow metadata in Save Image | PENDING — not yet supported, needs the `webp_workflow_json` SDK argument |
| CLIP hooks in Create Hook LoRA | PENDING — not yet supported, needs the SetClipHooks host operation |
| Startup and multi-root catalogue parity (initial scan readiness, root order) | PENDING — not yet supported, needs a host-owned catalogue lifecycle contract |
| GGUF UNet loading on the live service | PENDING — ported and tested (scoped) in revision 8; the live service lacks the host-installed ComfyUI-GGUF and the `gguf` package the SDK GGUF verb needs (request #12) |
| Third-party dependencies on the live service (`piexif` for Load Image Metadata; `brotli` for compressed AVIF brob) | PENDING — this pack declares no dependency profile and the live service provides neither; Load Image Metadata fails there (Revision 7) |
| Remaining in-graph routes and settings | PENDING — 9 routes written in `secure_routes/` and 3 registrations held in `held-registration/`; none registered or behavior-tested yet (the 3 Lora Info routes of revision 9 are declared separately) |
| Lora Info on the live service | PENDING — the frontend and 3 routes are declared (revision 9), but every route call is refused on live until a route call gets an execution runtime (request #15); no LoRA selection reaches the node until the LoRA list widget is registered (request #11) |

## Open test gates

- Load Image Metadata: compressed AVIF brob/JXL; full/rotated AVIF animation; HDR rendering; admitted piexif profile and installed gVisor/browser/selector lifecycle.
- Prompt/Text library lifecycle and persistence; LoRA Text Loader syntax/library/cache.
- TriggerWord Toggle and Stack Combiner restore/identity; Lora Pool edit and persistence.
- Debug Metadata and Metadata Overwrite with wired model/sampler fields.
- Multi-root ordering for Stacker, Randomizer, Cycler and Save Image.
- LoRA Syntax → Path additional parser cases and installed workflow.
- Further real model branches and installed gVisor workflows for Checkpoint and Unet loaders (SD1.5 CPU pre-flights passed); a real GGUF UNet load (revision 8 is construction-call parity).
- Installed runtime + gVisor TEST workflows of this source, one per node family, then whole-node certificates (0/21 today).
- Node-facing routes, settings and widgets: behavior tests in a browser (0 tested today); negative tests for every Pending item.
- Lora Info: the 3 routes on a host with request #15 (live behaviour, not a stand-in); the browser smoke plan B1-B8 (queued for BART until #15), including whether an original workflow's saved value reaches the node (B3).
- Dependency profile: `piexif==1.1.3` admission requested; tests emulated that profile through a trusted runtime dependency root. The live service has no `piexif`, so Load Image Metadata fails there until a declared profile is admitted and provided (Revision 7).
- Independent whole-pack review and certificate.

## Authority and permissions (declared per node)

| Node id | SDK permissions |
| --- | --- |
| Prompt (LoraManager) | storage, raw |
| Text (LoraManager) | storage |
| Lora Loader (LoraManager) | assets, storage, raw |
| LoRA Text Loader (LoraManager) | assets, storage, raw |
| Checkpoint Loader (LoraManager) | models, assets (read-only existence check) |
| Unet Loader (LoraManager) | models, assets (read-only existence check of a GGUF name) |
| TriggerWord Toggle (LoraManager) | (none) |
| Lora Stacker (LoraManager) | assets, storage, raw |
| Lora Stack Combiner (LoraManager) | (none) |
| Save Image (LoraManager) | graph.metadata, assets, storage, raw, output |
| Debug Metadata (LoraManager) | graph.metadata |
| WanVideo Lora Select (LoraManager) | assets, storage |
| WanVideo Lora Select From Text (LoraManager) | assets, storage |
| Lora Pool (LoraManager) | (none) |
| Lora Randomizer (LoraManager) | assets, storage |
| Lora Cycler (LoraManager) | assets, storage |
| Lora Info (LoraManager) | (none) for the node (its backend is a no-op); its 3 routes declare their own, see below |
| LoRA Syntax → Path (LoraManager) | assets |
| Create Hook LoRA (LoraManager) | models, assets, storage |
| Metadata Overwrite (LoraManager) | (none) |
| Load Image Metadata (LoraManager) | assets, storage, raw |

Declared routes (revision 9). They are pack-relative; the host mounts them under the pack's own route base, and each
call runs with only the permissions listed.

| Route | Handler (`secure_services/lora_info_routes.py`) | SDK permissions |
| --- | --- | --- |
| `GET /lm/loras/get-notes` | `get_notes` | assets (read-only), storage (the pack's own notes records) |
| `GET /lm/loras/metadata` | `get_metadata` | assets (read-only) |
| `POST /lm/loras/save-metadata` | `save_notes` | assets (read-only existence check), storage (the pack's own notes records) |

## Assets and weights

- No weights or model files are shipped. Nodes use the user's own LoRA, checkpoint, UNet and image files through
  the SDK assets API, from the folders the host exposes.
- Test fixture used for scoped runs (not committed): an SD1.5 LCM LoRA from the shared model cache
  (`lcm-sd15-lora`, sha256 `8f90d840e075ff588a58e22c6586e2ae9a6f7922996ee6649a7f01072333afe4`).
- `requirements.txt` is upstream's, unchanged; the converted nodes use the standard library, `torch` (runtime)
  and, lazily, `piexif`.

## What is in v2/

- `secure_*.py`, `secure_services/`, `secure_algorithms/`, `native_metadata/`, `snapshot_metadata.py`: the converted nodes.
- `secure_web/`: the in-graph frontend served from `WEB_DIRECTORY`. `lora_info.js` (revision 9) and
  `lm_frontends.js` (revision 10) register themselves when loaded; the other modules only export functions. `secure_services/lora_info_routes.py`:
  the 3 declared Lora Info routes. `secure_routes/` and `held-registration/`: unregistered route work.
- Checkpoint and Unet model dropdowns are filled from core's `/models/checkpoints` and `/models/diffusion_models`;
  their queue validators check the selected name, because remote dropdowns carry no static options. GGUF names, which
  `/models/diffusion_models` does not list, are checked with a read-only `assets.exists` in the diffusion-model roots.
- `secure_full_library_nodes.py`, `secure_pool_editor.py`, `secure_text_nodes.py`: in-progress modules, not registered.
- `secure-nodes.json`: the node manifest, generated by the backend manifest generator (21 nodes, web directory
  `secure_web`, Python `>=3.13,<3.14`), plus a top-level `routes` list added in revision 9 (the 3 Lora Info routes,
  checked with the backend route decoder).
- `pyproject.toml`: upstream's file with `requires-python = ">=3.13,<3.14"` added (the runtime declaration).
- Every other file is the upstream file unchanged. Internal review notes and private test harnesses are not published.

## Revision 4 scoped evidence and limits (historical image decoder)

Load Image Metadata uses deployed public asset loading and storage.get. Its first-frame mask uses the declared SDK raw tier and digest-bound managed bytes. Sampling names are pinned to Core `6257422` (45 samplers, 9 schedulers), with a drift test in `tests/test_core_sampling_names.py`. Exact 8-bit PNG pixel/mask parity and float-alpha tolerance are scoped separately; lossy PIL/PyAV differences remain measured gaps.

Save Image first uses the pack LoRA cache, then resolves only missing logical names through the closed asset catalogue and storage.get, matching its checkpoint resource path. No global metadata hook is installed. The real SD1.5/LCM CPU run produced the expected LoRA SHA256 prefix in both Save configurations.

These CPU pre-flights use secure Guest dispatch with sandbox=none. They do not establish installed gVisor behavior or whole-node certificates. TEST workflows v3 cover 18 of 21 nodes in nine cases (eight ready; CLIP Hook blocked); Lora Info and the two WanVideo nodes need separate UI/model coverage. Frontend and route work remains pending and is not included in this revision.

Portable API prompts and asset instructions are included in `tests/workflows/`; weights and generated fixtures are not shipped.

## Revision 5 private draft: bounded managed image decoder

The image path now ports the pinned Core 6257422 image-only PyAV conversion and
animated-WebP Pillow fallback over digest-verified managed bytes. IMAGE is created
with public ImageRef.from_value and MASK through the existing declared raw tier.
It preserves core precision, alpha, orientation and frame batches in the tested
PNG/JPEG/WebP/TIFF/GIF profile. Nineteen image/mask comparisons were exactly equal
through actual backend Guest execution on CPU (sandbox none). All nineteen image
metadata field results matched the original pack reader. Seven pure decoder
controls verify error and batch-limit rejection. The old first-frame, 16-bit and
lossy-decoder limitations above describe revision 4; they are closed for these
tested revision 5 cases, not for arbitrary containers or runtime configurations.

Bounds: 16 MiB encoded input, 8192 per axis, 16,777,216 aggregate decoded pixels,
256 frames. Oversized batches raise rather than return a truncated animation.
Schema, RemoteOptions, permissions, validation and fingerprinting are unchanged.
No model weights or catalogue fixtures were required. Tests emulate the piexif
dependency profile; deployed admission and installed/gVisor/browser coverage stay
open. This revision is a private review draft, not a registry acceptance. Node
dispositions and whole-node certificate counts remain unchanged.

## Revision6: managed names and scoped AVIF metadata

Revision5 was a private draft, superseded by public revision6. The reviewed
private revision6 source supplies this public evaluation revision; open gates
and zero whole-node certificates remain unchanged.

Five exact source leaves compose the proved managed input/output/temp name
parser, AVIF pixel format gate, bounded raw brob metadata projection and native
filename-extension selection over private revision5. No dependency, SDK method,
schema, permission or RemoteOptions change is introduced. The brob scan follows
the pinned finite32-bit box stop/first-box rules; valid raw objects suppress EXIF,
while native fallback cases use ordinary metadata. Bounds reject excessive work:
4096 boxes,1MiB raw JSON,16384 JSON items/depth16,262144 bytes per extracted field,
plus existing encoded-image, geometry and decoded-frame/pixel limits.

The exact composed leaf has12 named-container cases and8 pinned official libavif
reference cases with native-equal IMAGE/MASK, managed fingerprints, metadata
seeds and ExifUtils fields. Genuine12-bit and three10-bit PQ first-stream profiles
were verified from decoded formats and transfer tags. Each test retains its
source/runtime binding; earlier annotation/ordinary/raw-brob/19-image proofs are
historical scoped evidence, not a new all-profile suite or whole-node certificate.

AVIF sequence inputs in these tests return one frame through both native core
LoadImage and the conversion. Full-sequence expectations FAILED and remain
recorded. Separate native diagnostics isolate a multi-frame EXIF-rotation encoder
segfault in Pillow11.3.0. Full/rotated animation and auxiliary-alpha reconstruction
remain unqualified. PQ output parity does not qualify HDR display, colorimetric
correctness or tone mapping. Compressed/binary brob, genuine JPEG XL, dependency
admission, installed/gVisor/browser workflows and existing route/selector holds
remain open. No reference image assets are added to the production pack.

The per-node classifications remain18 tested(scoped),1 converted-untested and
2 partial. Revision5's inherited MANIFEST counters16/3 were stale relative to
that revision's own21-row status table; the new manifest reconciles the counters
to existing classifications. Certificate and accepted-pack counts remain zero.
Revision6 is approved for IN PROGRESS / UNVERIFIED evaluation publication.
Registry admission and deployment are performed by the manager. Revision5 was
private and is superseded by6; every original proof/failure artifact is preserved.
