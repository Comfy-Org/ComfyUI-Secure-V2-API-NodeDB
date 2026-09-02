# Secure Nodes 2.0 conversion

Pinned upstream commit: `557d882e184c7b702208cc7805659b10dfa06c59`.

Status: **171/171 backend nodes supported, 0 rejected**.

LayerStyle's image, mask, color, text, LUT, compositing, crop, transform,
grain, and detail algorithms remain pack-side. The secure entrypoint imports a
frozen schema and dispatches those algorithms inside the guest. It does not
import the upstream initializer, register HTTP routes, inspect arbitrary host
paths, or download anything directly.

Thin intent adapters cover the operations that cross the guest boundary:

- `LoadImagesFromPath` lists and reads only a selected directory under the
  managed ComfyUI input catalogue.
- `ImageTaggerSave` and V2 save through the output broker, including their text
  sidecar and preview behavior.
- `MaskPreview`, `QueueStop`, and both `PurgeVRAM` nodes use the closed UI,
  graph-control, and model-lifecycle capabilities.
- `ICMASK_DATA` and `Reel` are serialized as ordinary bounded values containing
  image refs rather than leaking pack-owned Python objects over the wire.
- SegFormer, background removal, and ViTMatte use opaque model refs. BLIP VQA
  is entirely pack-owned: the pack constructs the fixed architecture, carries
  its tokenizer vocabulary, caches the model in its guest process, and runs
  inference over brokered tensors. Label selection, trimap construction,
  PyMatting/guided-filter processing, pixel spread, compositing, and
  node-specific menus remain in the pack.

The reusable core additions are deliberately small: fixed semantic
segmentation, background-mask, and image-matting model primitives. No
LayerStyle node algorithm or model-specific BLIP API was transplanted into
core.

All additional model artifacts are weight files declared in
`secure-nodes.json`. They come only from pinned Hugging Face revisions, include
SHA-256 digests, and are marked `on_demand`. The host downloads only the
selected weight, installs it in the managed model catalogue, verifies it, and
reuses that installed file on later executions. The guest has no general
network path. Declared families are:

- SegFormer B2/B3 clothes and B3 fashion;
- RMBG 2.0;
- ViTMatte small and base;
- BLIP VQA base and capfilt-large.

The old generic DZ/MTB browser extension targeted unrelated node packs and
contained dead custom-route, queue, and graph code. V2's native widgets already
cover the only relevant COLOR input, and this pack exposes BOX rather than the
legacy BBOX widget, so those unused modules are not shipped. The retained node
palette imports only `/comfy/api/v2.js` and is tested in a realm with no
`window`, `document`, legacy app globals, or LiteGraph global.

Verification includes a deterministic 171-node schema/manifest census, pinned
weight declaration checks, JavaScript syntax and iframe-only intent tests,
patch round-trip validation, and one real guest-session execution of every
backend node. Model execution in the census uses deterministic test doubles so
the test exercises both brokered models and the pack-owned BLIP path without
downloading multi-GB weights.
