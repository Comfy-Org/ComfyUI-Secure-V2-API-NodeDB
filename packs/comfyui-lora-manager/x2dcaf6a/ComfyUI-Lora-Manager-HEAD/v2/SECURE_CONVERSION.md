> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 21 of 21 converted; 18 tested (scoped), 1 converted but untested/partly tested,
> 2 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> Status line: source 21/21 · scoped runtime 18/21 · certificates 0/21 · node-facing routes 0 behavior-tested · frontend 0/17 browser-tested.
> **Live: Load Image Metadata fails on every image (revision 7, 2026-10-20).** The live service has no `piexif`, which the
> node imports on every run, and this pack declares no dependency profile. No other node imports a package the live
> service lacks. See "Revision 7".

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
| Unet Loader (LoraManager) | partial | queue parity 3/3; real extracted SD1.5 UNet bf16 CPU secure-Guest workflow | GGUF path not implemented (rejected clearly; the live service also lacks the host-installed ComfyUI-GGUF and `gguf` package the SDK GGUF verb needs); installed gVisor workflow |
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
| Lora Info (LoraManager) | converted-untested | - (backend is a no-op, as upstream) | frontend source selection; filename/notes |
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
| GGUF UNet loading | PENDING — dependency-gated until the upstream path is shown to work in the runtime with a small GGUF; the SDK verb also needs a host-installed ComfyUI-GGUF and the `gguf` package, which the live service lacks |
| Third-party dependencies on the live service (`piexif` for Load Image Metadata; `brotli` for compressed AVIF brob) | PENDING — this pack declares no dependency profile and the live service provides neither; Load Image Metadata fails there (Revision 7) |
| Remaining in-graph routes and settings | PENDING — 9 routes written in `secure_routes/` and 3 registrations held in `held-registration/`; none registered or behavior-tested yet |

## Open test gates

- Load Image Metadata: compressed AVIF brob/JXL; full/rotated AVIF animation; HDR rendering; admitted piexif profile and installed gVisor/browser/selector lifecycle.
- Prompt/Text library lifecycle and persistence; LoRA Text Loader syntax/library/cache.
- TriggerWord Toggle and Stack Combiner restore/identity; Lora Pool edit and persistence.
- Debug Metadata and Metadata Overwrite with wired model/sampler fields.
- Multi-root ordering for Stacker, Randomizer, Cycler and Save Image.
- LoRA Syntax → Path additional parser cases and installed workflow.
- Further real model branches and installed gVisor workflows for Checkpoint and Unet loaders (SD1.5 CPU pre-flights passed).
- Installed runtime + gVisor TEST workflows of this source, one per node family, then whole-node certificates (0/21 today).
- Node-facing routes, settings and widgets: behavior tests in a browser (0 tested today); negative tests for every Pending item.
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
| Load Image Metadata (LoraManager) | assets, storage, raw |

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
- Checkpoint and Unet model dropdowns are filled from core's `/models/checkpoints` and `/models/diffusion_models`;
  their queue validators check the selected name, because remote dropdowns carry no static options.
- `secure_full_library_nodes.py`, `secure_pool_editor.py`, `secure_text_nodes.py`: in-progress modules, not registered.
- `secure-nodes.json`: the node manifest, generated by the backend manifest generator (21 nodes, web directory
  `secure_web`, Python `>=3.13,<3.14`, no routes registered yet).
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
