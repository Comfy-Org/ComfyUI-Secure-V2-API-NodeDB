> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 21 of 21 converted; 16 tested (scoped), 3 converted but untested/partly tested,
> 2 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> Status line: source 21/21 · scoped runtime 16/21 · certificates 0/21 · node-facing routes 0 behavior-tested · frontend 0/17 browser-tested.

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

## Per-node status

Dispositions: tested (scoped) = runtime evidence for the listed scope only; converted-untested = source
converted, no runtime evidence yet; partial = known missing behavior. No node has a whole-node certificate.

| Node id | Disposition | Evidence (scoped) | Open gap |
| --- | --- | --- | --- |
| Prompt (LoraManager) | tested (scoped) | shared gVisor workflow (R50) | authored library import/persistence/cache; frontend sync |
| Text (LoraManager) | tested (scoped) | shared gVisor workflow (R50) | wildcard/library lifecycle; frontend |
| Lora Loader (LoraManager) | tested (scoped) | gVisor workflows (R51/R52/R55); queue validator native-vs-Guest parity 2/2 + permission-denial control | cache acquisition on all paths; opaque metadata; other model branches; frontend |
| LoRA Text Loader (LoraManager) | tested (scoped) | gVisor workflows (R51/R52/R55) | syntax/library/cache/metadata; frontend |
| Checkpoint Loader (LoraManager) | converted-untested | - | real model load and consumer; scanner roots; queue-time check of the remote checkpoint list (empty static options, no validator) |
| Unet Loader (LoraManager) | partial | - | GGUF path not implemented; real diffusion-model load; same remote-list queue check |
| TriggerWord Toggle (LoraManager) | tested (scoped) | gVisor workflow (R6) | lifecycle/restore/state; transport identity |
| Lora Stacker (LoraManager) | tested (scoped) | native-vs-Guest parity: getter 8 cases, strict queue validator 28, metadata lifecycle 8 phases, stale-file deletion 2 | multi-root order; installed queue; frontend |
| Lora Stack Combiner (LoraManager) | tested (scoped) | gVisor workflows (R6/R7) | tuple transport/identity; editor lifecycle |
| Save Image (LoraManager) | tested (scoped) | gVisor (R72/R80); native parity: byte-identical PNGs from the real cache, 24 resource/formatter cases, 12 caught-error/WebP-continuation cases | multi-root; installed JPEG EXIF/HWC; WebP workflow metadata (pending SDK); recipe/no-counter/overwrite; frontend |
| Debug Metadata (LoraManager) | tested (scoped) | gVisor workflow (R66) | wired opaque model/sampler fields; ancestry |
| WanVideo Lora Select (LoraManager) | tested (scoped) | gVisor workflow (R78) | trained WAN consumer; discovery/multi-root; frontend |
| WanVideo Lora Select From Text (LoraManager) | tested (scoped) | gVisor workflow (R78) | trained WAN consumer; discovery/multi-root; frontend |
| Lora Pool (LoraManager) | tested (scoped) | gVisor workflow (R49) | mutation/persistence/preview; frontend seed/index |
| Lora Randomizer (LoraManager) | tested (scoped) | native-vs-Guest parity: getter 10 cases, strict queue validation 22 + 2 error controls, fixed mode 5 | full queue; global RNG; multi-root; frontend |
| Lora Cycler (LoraManager) | tested (scoped) | native-vs-Guest parity: 14 cases | multi-root/tie order; mutation/cache; frontend index |
| Lora Info (LoraManager) | converted-untested | - (backend is a no-op, as upstream) | frontend source selection; filename/notes |
| LoRA Syntax → Path (LoraManager) | converted-untested | - | path rule approved (library-relative names); parser tests; negative test that no host path is emitted |
| Create Hook LoRA (LoraManager) | tested (scoped) | gVisor workflows (R64/R70) | CLIP hooks need the SetClipHooks host operation; lifecycle |
| Metadata Overwrite (LoraManager) | tested (scoped) | gVisor workflow (R8) | wired MODEL/SAMPLER identity; ancestry |
| Load Image Metadata (LoraManager) | partial | - | queue-time image check missing (upstream rejects a missing image at queue time); annotated [input]/[output]/[temp] names unsupported; 18-output parity; catalogue lookup |

## Refused techniques (never do) and public replacements

| Refused technique | Public replacement |
| --- | --- |
| Emitting absolute host filesystem paths from a node (upstream LoRA Syntax → Path output) | Library-relative names: the path under its LoRA root, `/`-separated, with extension (what ComfyUI LoRA loaders accept). A negative test must show no host path is ever emitted. |
| Importing ComfyUI internals from node code (`comfy`, `folder_paths`, `nodes`, `server`, `execution`, ...) | `comfy_api.latest` (`io` schemas and `sdk` context) only |
| Reading or writing model folders and sidecar files directly (directory walks, `.metadata.json` next to models) | SDK assets (`list`, `resolve`, `exists`, `digest`, image loading) and pack-owned durable records in SDK storage |
| Process-global services started at import (scanner registries, background tasks, websocket broadcasts) | A pack-owned catalogue cache refreshed through the SDK; per-node outputs and UI payloads |
| Registering handlers directly on the ComfyUI server | Declared secure routes (`secure_routes/`); registration is still held, see Pending |

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
| GGUF UNet loading | PENDING — dependency-gated until the upstream path is shown to work in the runtime with a small GGUF |
| Remaining in-graph routes and settings | PENDING — 9 routes written in `secure_routes/` and 3 registrations held in `held-registration/`; none registered or behavior-tested yet |

## Open test gates

- Load Image Metadata: queue-time image check, catalogue lookup, 18-output parity with the original.
- Prompt/Text library lifecycle and persistence; LoRA Text Loader syntax/library/cache.
- TriggerWord Toggle and Stack Combiner restore/identity; Lora Pool edit and persistence.
- Debug Metadata and Metadata Overwrite with wired model/sampler fields.
- Multi-root ordering for Stacker, Randomizer, Cycler and Save Image.
- LoRA Syntax → Path parser tests and the no-host-path negative test.
- Real model loads (CPU): Checkpoint Loader, Unet Loader; queue-time checks of their remote model lists.
- Installed runtime + gVisor TEST workflows of this source, one per node family, then whole-node certificates (0/21 today).
- Node-facing routes, settings and widgets: behavior tests in a browser (0 tested today); negative tests for every Pending item.
- Dependency profile: `piexif` is imported lazily by metadata recovery and is not yet declared for the runtime.
- Independent whole-pack review and certificate.

## Authority and permissions (declared per node)

| Node id | SDK permissions |
| --- | --- |
| Prompt (LoraManager) | storage, raw |
| Text (LoraManager) | storage |
| Lora Loader (LoraManager) | assets, storage, raw |
| LoRA Text Loader (LoraManager) | assets, storage, raw |
| Checkpoint Loader (LoraManager) | models |
| Unet Loader (LoraManager) | models |
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
| Lora Info (LoraManager) | (none) |
| LoRA Syntax → Path (LoraManager) | assets |
| Create Hook LoRA (LoraManager) | models, assets, storage |
| Metadata Overwrite (LoraManager) | (none) |
| Load Image Metadata (LoraManager) | assets, models, storage, raw |

## Assets and weights

- No weights or model files are shipped. Nodes use the user's own LoRA, checkpoint, UNet and image files through
  the SDK assets API, from the folders the host exposes.
- Test fixture used for scoped runs (not committed): an SD1.5 LCM LoRA from the shared model cache
  (`lcm-sd15-lora`, sha256 `8f90d840e075ff588a58e22c6586e2ae9a6f7922996ee6649a7f01072333afe4`).
- `requirements.txt` is upstream's, unchanged; the converted nodes use the standard library, `torch` (runtime)
  and, lazily, `piexif`.

## What is in v2/

- `secure_*.py`, `secure_services/`, `secure_algorithms/`, `native_metadata/`, `snapshot_metadata.py`: the converted nodes.
- `secure_web/`: the in-graph frontend served from `WEB_DIRECTORY`; `secure_routes/` and `held-registration/`: unregistered route work.
- `secure_full_library_nodes.py`, `secure_pool_editor.py`, `secure_text_nodes.py`: in-progress modules, not registered.
- `secure-nodes.json`: the node manifest, generated by the backend manifest generator (21 nodes, web directory
  `secure_web`, Python `>=3.13,<3.14`, no routes registered yet).
- `pyproject.toml`: upstream's file with `requires-python = ">=3.13,<3.14"` added (the runtime declaration).
- Every other file is the upstream file unchanged. Internal review notes and private test harnesses are not published.
