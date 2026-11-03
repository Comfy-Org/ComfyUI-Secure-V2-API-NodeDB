# Secure Nodes V2 conversion

Pinned upstream commit: `205d66a9d8035e3ad2ba6c61b7ebf7871664e472`  
Upstream: `https://github.com/alexopus/ComfyUI-Image-Saver`

## Census and terminal status

- Backend nodes supported: **31/31**.
- Backend nodes rejected: **0**.
- Backend nodes pending: **0**.
- Frontend extensions supported: **1/1** (`ComfyUI-Image-Saver`).
- Frontend extensions rejected or pending: **0**.

Every frozen backend mapping has a concrete sandbox handler:

- `Checkpoint Loader with Name (Image Saver)`
- `UNet loader with Name (Image Saver)`
- `Image Saver`
- `Image Saver Simple`
- `Image Saver Metadata`
- `Make Image Saver Simple Config`
- `Make Image Saver Metadata Config`
- `Make Image Saver Pipe`
- `Edit Image Saver Pipe`
- `Read Image Saver Pipe`
- `Image Saver (From Pipe)`
- `Sampler Selector (Image Saver)`
- `Scheduler Selector (Image Saver)`
- `Scheduler Selector (inspire) (Image Saver)`
- `Scheduler Selector (Eff.) (Image Saver)`
- `Input Parameters (Image Saver)`
- `Any to String (Image Saver)`
- `Workflow Input Value (Image Saver)`
- `Seed Generator (Image Saver)`
- `String Literal (Image Saver)`
- `Width/Height Literal (Image Saver)`
- `Cfg Literal (Image Saver)`
- `Int Literal (Image Saver)`
- `Float Literal (Image Saver)`
- `Conditioning Concat Optional (Image Saver)`
- `RandomShapeGenerator`
- `Empty Latent (Image Saver)`
- `Civitai Hash Fetcher (Image Saver)`
- `Random Tag Picker (Image Saver)`
- `Random Character Picker (Image Saver)`
- `Random Artist Picker (Image Saver)`

## Behavior and boundary

Filename tokens, sanitizing, counters, collision suffixes, metadata formatting,
prompt resource discovery, Civitai response matching, pipe editing, CSV sampling,
and random-shape drawing remain pack-side algorithms.

The host supplies only reusable primitives:

- managed asset selection, bounded reads, listings, and SHA-256 digests;
- typed checkpoint/UNet loading and typed image, latent, and conditioning refs;
- exact-name PNG/JPEG/WebP output, workflow JSON sidecars, and UI result records;
- read-only access to one submitted workflow input;
- a typed `integrations.civitai` pass-through for bounded model/version lookups.

The guest receives no filesystem path, prompt/workflow metadata, credential,
host object, or ambient network authority. Civitai matching and formatting stay
inside this pack; HTTP and credentials stay in the typed host integration. The
legacy `.civitai.info` filesystem cache is not reproduced.

JPEG output follows the format's bounded EXIF behavior without losing the
image: on overflow, the host drops broker prompt metadata, then broker workflow
metadata, then optional pack EXIF. PNG and WebP retain their full metadata.
Sidecar names participate in the pack's collision scan and are written
new-only, so a prior JSON artifact is never overwritten or left behind after a
partial image/sidecar collision.

The frontend replacement imports only `/comfy/api/v2.js`. Core already handles
its native PNG/WebP workflow import. This pack registers the missing JPEG case
through `comfy.workflow.registerImporter`, using a bounded pack-side parser for
the exact EXIF ASCII tags written by the output primitive. It does not patch
ComfyUI's file handler, read a host `File`, access a parent DOM, or use network
APIs.

## Selector outputs and Core's choice lists

The original's selectors return Core's own choice lists as their output
types: Sampler Selector, the three Scheduler Selectors, Input Parameters'
`sampler` and `scheduler`, and Read Image Saver Pipe's `sampler_name` and
`scheduler_name`. V2 declares each of these outputs as a COMBO output whose
options are exactly that list (`_secure_runtime.py`, `_output`). A Core that
reports a COMBO output's declared options as its type then validates a link
into a list-typed input, such as KSampler's `sampler_name` and `scheduler`,
exactly as it does for the original: the lists must share a choice. A Core
that reports every COMBO output as the plain string `COMBO` refuses those
links (return type mismatch). The pack cannot change that.

The menus and output choices are frozen copies of Core's lists in
`_schemas.json`. `tests/refreeze_core_lists.py` refreshes them from the
original running on the deployment Core. It only adds choices that the newer
Core provides, and it leaves the checkpoint and UNet menus alone, because the
host serves those from its model folders. Choices that other installed packs
add to Core's lists at runtime, such as extra schedulers, are not mirrored.
Where the original offers one of them, the V2 menu refuses it. A link from a
V2 selector into a host input that offers such extras still validates,
because the lists share their Core choices.

## Models and verification

This pack declares no additional model weights and performs no runtime
downloads. Model files named in metadata are resolved from managed catalogues
and identity-cached SHA-256 digests are computed by the host.

Conversion verification covers the exact pristine byte snapshot and node
census, generated schema/manifest/stub equality, patch freshness and round
trip, real guest execution of every backend mapping, pristine differential
checks for metadata/pipes/CSV/shape/latent behavior, all three output formats,
collision and sidecar behavior, typed Civitai calls, denied capabilities and
path traversal, and a DOM-free worker-realm JPEG importer harness.

`tests/test_combo_outputs.py` compares the original with the served V2
nodes on CPU without weights. It covers every node's object_info outputs,
Core's prompt validation with selector links into KSampler (including
refused controls), and every selector choice returned by a real guest.
`tests/encode_manifest.py` regenerates `secure-nodes.json` with the live
encoder and loads it with the real loader.
