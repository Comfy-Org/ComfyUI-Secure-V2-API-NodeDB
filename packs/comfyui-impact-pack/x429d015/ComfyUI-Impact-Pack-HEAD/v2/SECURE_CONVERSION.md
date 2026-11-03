# Secure conversion status

Pinned upstream commit: `429d0159ad429e64d2b3916e6e7be9c22d025c3c`.

The frozen upstream surface contains 197 backend node mappings:

- 195 are supported by concrete Secure Nodes 2.0 handlers.
- 2 are deliberately rejected: `ImpactRemoteBoolean` and `ImpactRemoteInt`.

The two rejected nodes are test-category prompt mutators. Their upstream
`onprompt_for_remote` hook locates another node by numeric ID and overwrites an
arbitrary boolean or numeric widget in the submitted prompt before execution.
That cross-node mutation, rather than the server hook used to implement it, is
the behavior being rejected. Secure workflows should express the value through
an ordinary graph connection or a supported graph-control node.

No node is classified as rejected because a dependency, model format, or V2
primitive is merely missing. Detector, classifier, SAM, inpaint, sampling,
detailer, SEGS, and pipe orchestration remains pack-side. Core is used for
typed model operations and confined asset, output, graph, UI, and sampling
primitives.

All pack-declared model downloads are pinned Hugging Face weights with hashes.
They are brokered into the managed model catalogue and reused after the first
verified download.

Impact Subpack's Ultralytics detectors are rebuilt and run inside this isolated
pack runtime with `ultralytics==8.4.198` from the pack's dependency profile
(see "Fidelity repair r1" below). Core only resolves and parses the SafeTensors
asset.

`secure-nodes.json` is the authoritative sealed schema/permission census. The
operational classification and representative real-guest behavior are enforced
by `backend/tests/test_popular_pack_conversions.py`, including an explicit
`195 supported / 2 rejected` assertion.

## 2026-10-30 validator repair and C4-R1 - UNRUN-IN-GUEST

ImageReceiver and LatentReceiver restore their original named validators and receiver-inclusive signatures through managed assets.exists. Their existing assets authority is unchanged. Generator-defect workaround: real pinned packmanifest.encode_validation_inputs must encode genuine source classes; placeholder equality alone is insufficient. The bounded R3 proof confirms real overrides and mechanically derives CG fingerprint flags. This is metadata discovery only, not full schema or purpose execution.

The draft ONNX models grant is removed under C4-R1. _onnx_detector_provider (1457-1461) calls _onnx_detector.recipe (48) only; it builds a recipe rather than loading a model. Bound packdb 7cc6d977 L403-412 supplies names without models. Other preexisting grants are not automatically removed by the heuristic excess-grant census.

LatentReceiver / latent.remote remains **policy edit (reviewed)**: the available managed input-file catalogue is recursive and any-extension, broader than the original top-level .latent/.latent.png UI. Read authority and existing grants are unchanged. Incompatible selections can fail to load. Current webassets rejects kind=file refresh, though selected packdb can fill object_info. No matching deployment or original UI/file-error parity is claimed; managed empty/directory diagnostic differences remain unqualified.

Manifest uses the original indent-1 format with only the five intended field changes against main, after dropping the withdrawn ONNX grant; no whole-file reindent. The proof preserves input manifest bytes after checking encoded values. Stubs remain unchanged pending a qualified canonical pair. Source-only SDK checks, exact canonical replays, independent review and actual Guest/graph/model/browser qualification remain distinct. Root alone publishes changed files with Git modes.

## Fidelity repair r1 - Ultralytics detectors

- Impact Subpack's UltralyticsDetectorProvider now returns descriptors that name a weight in the host's
  Ultralytics catalogues (catalogue, name, menu value). Impact v2 reads that weight only through the engine,
  with `assets.load_state_dict(..., return_metadata=True)`. That is a converted safetensors state dict, whose
  metadata carries the checkpoint's `top_class`, architecture `yaml`, class `names` and `train_args`.
- `_ultralytics_detector.py` rebuilds the model from that yaml and loads the state dict strictly. It sets the
  model up the way Ultralytics' `load_checkpoint` and `Model._load` set up a loaded checkpoint (FP32, args,
  task, names, predictor overrides such as imgsz), then runs Ultralytics' own predictor.
- Detection, SEG building, dilation, cropping and label filtering are upstream code, copied verbatim. The
  sources are Impact Subpack `subcore.py`/`utils.py` and Impact Pack `SEGSLabelFilter`; line ranges and file
  hashes are in the module header. They serve BboxDetectorSEGS, BboxDetectorCombined, SegmDetectorSEGS,
  SegmDetectorCombined, and the detailers and pipes that take a detector.
- No pickle is parsed in the pack. A pickle-format name (.pt) loads only if the engine translates it to its
  converted safetensors file. Without that translation, or without the Ultralytics metadata, loading fails
  with a named `DetectorWeightError`.
- Replaced: the fixed yolov8x recipe, its own letterbox and NMS, and the integer-rounded SEG boxes.
- SEG values are upstream's. Masks travel as (1, h, w) float32 tensors, the confidence as a float and the
  bbox as a tuple of floats, because numpy values cannot cross the guest wire. Image batches of more than one
  image are refused, as before.
- The detector module is imported only on the detector path, so the pack's other nodes load without its
  dependency profile.
- `tests/test_detector_repair_r1.py` is the lane-gate parity test: synthetic models and images, original
  Impact Subpack code against these handlers.

## Fidelity repair r2 - SAM in the guest

- **SAMLoader** loads the model in this guest, as upstream's SAMLoader does:
  - The engine reads the checkpoint (`assets.resolve` + `load_state_dict` on the `sams` catalogue). A
    pickle-format name loads only through the engine's translation to its converted safetensors.
  - segment_anything builds vit_b, vit_l or vit_h by upstream's name rule and loads the state dict strictly.
  - The node returns a descriptor (name, device mode) that the SAM nodes resolve to the same guest model. No
    engine `models.load_sam` path is used.
- **SAM nodes.** SAMDetectorCombined, SAMDetectorSegmented, and the SAM step of the detailers and Simple Detector
  run upstream `make_sam_mask` / `make_sam_mask_segmented`: a SamPredictor per SEG, detection hints, mask
  selection, combining and cv2 dilation. SEGS AND MASK runs upstream `segs_bitwise_and_mask`. All of this code
  is copied verbatim in `_sam_runtime.py`.
- **SEG value types.** SEGS enter that code in upstream's types: 2-D float32 masks, and float32 boxes where
  Impact v2 carries float boxes, as Ultralytics detections do. They leave in Impact v2's layout.
- **Device.** The SAM model runs on this guest's torch device, and upstream's AUTO / Prefer GPU / CPU modes apply
  to that device.
- **Replaced:**
  - the engine SAM call, with its batched hint, selection and dilation reimplementation;
  - the SEGS-and-mask path that dropped SEGs whose mask became empty. Upstream keeps them, so the detailers'
    later SEGs keep their seeds.
- **Refused by name at SAMLoader:**
  - ESAM, which needs ComfyUI-YoloWorld-EfficientSAM;
  - SAM2 models, because the guest has no sam2 package;
  - names upstream's menu never lists (HQ-SAM, other extensions).
  ImpactSAM2VideoDetectorSEGS therefore refuses, since SAMLoader no longer yields a SAM2 model.
- **SAMDetectorSegmented outputs** are upstream's values in Impact v2's MASK layout:
  - the combined mask is (1, H, W) float32 (upstream: a 2-D float mask);
  - the per-SEG batch is (N, H, W) float32 (upstream: an (N, 1, H, W) bool batch).
- `tests/test_sam_repair_r2.py` is the lane-gate parity test. It runs a synthetic SAM model, synthetic SEGS and
  synthetic images through the original Impact code and through these handlers.

## Fidelity repair r3 - SEGS chain

- **MaskToSEGS** runs upstream `core.mask_to_segs`, copied verbatim in `_segs_upstream.py`: contours, crop
  regions, bbox fill, drop size and the label "A".
  - It replaces a reimplementation that used connected components, its own crop and drop rules, and numeric
    labels.
  - MaskToSEGS_for_AnimateDiff keeps its handler.
- **SegsToCombinedMask** runs upstream `core.segs_to_combined_mask`, also in `_segs_upstream.py`.
- **SEGS between nodes** travel in Impact v2's layout: masks as (1, h, w) float32, and plain ints and floats in
  place of numpy scalars, which cannot cross the guest wire.
- **ImpactSwitch, LatentSwitch and SEGSSwitch.**
  - For check_lazy_status, Core tags each Autogrow value as (value, original input name) and expects that name
    back.
  - A guest wire without tuple preservation delivers the pair as a list. The previous lazy check missed it, so
    the selected input was never evaluated.
  - The lazy check now accepts both forms, plus the tagged empty group, and asks for the original name.
- `tests/test_segs_repair_r3.py` is the lane-gate parity test:
  - MaskToSEGS → SegsToCombinedMask on synthetic masks, against the original Impact code;
  - the lazy-check contract through the wire, with and without tuple preservation.

## Fidelity repair r4 - SEGSPaste

- SEGSPaste runs upstream `SEGSPaste.doit`, together with the helpers it calls, copied verbatim in
  `_segs_paste_upstream.py`. The helpers are `segs_scale_match`, `tensor_paste`, `tensor_gaussian_blur_mask`,
  `tensor_resize`, and the crop and mask helpers.
- It replaces a reimplementation that differed from upstream in three ways: it resized crops and masks to the crop
  region, skipped the scale match, and feathered with its own blur.
- Boundary stand-ins, which are not upstream code:
  - the guest's torch device;
  - Core's `common_upscale`, taken from the pack's own copy in `_image_ops.py`;
  - Core's default launch arguments, so the result lands on the CPU.
- `tests/test_paste_repair_r4.py` is the lane-gate parity test. It runs synthetic SEGS and images through the
  original Impact code and through this handler.

## Fidelity repair r5 - PreviewBridge

- PreviewBridge now returns what upstream `PreviewBridge.doit` returns when no mask has been painted for the node:
  - the input images, and an empty 64x64 float32 mask, sent as (1, 64, 64) in Impact v2's MASK layout.
    Previously v2 returned an empty mask the size of the image.
  - With `block` enabled, an empty mask blocks both outputs, as upstream's `ExecutionBlocker(None)` does. v2 uses
    `graph.block()` for this, so the node declares the `graph.block` permission.
- Not available in V2: a mask painted in the mask editor and the images it saves. The guest cannot read them, so
  `restore_mask` has nothing to restore, and the node behaves like upstream's first run on a new node every time.
  The preview is still shown.
- `tests/test_preview_bridge_repair_r5.py` is the lane-gate parity test. It runs every block / restore_mask
  combination on two image sizes through the original node and through this handler.

## Fidelity repair r6 - detailers

- DetailerForEach and SEGSDetailer follow upstream line for line:
  - DetailerForEach (with its Debug, Pipe and AutoRetry forms, and FaceDetailer, which share it) follows
    `DetailerForEach.do_detail`;
  - SEGSDetailer follows `SEGSDetailer.do_detail`;
  - the per-SEG step in both follows `core.enhance_detail`.
- Their pixel work is upstream's own code, copied verbatim in `_detailer_upstream.py` and repair r4's
  `_segs_paste_upstream.py`: `segs_scale_match`, `crop_ndarray4`, `tensor_resize`, `tensor_gaussian_blur_mask`,
  `tensor_paste` and the RGBA helpers. The engine still encodes, samples and decodes.
- It replaces v2's own versions of these steps, which differed from upstream:
  - the blur of the paste mask and of the noise mask, which used a different kernel width;
  - the noise mask, which was resized to the upscaled crop before the sampler resized it again. It now reaches the
    sampler at crop size, as upstream's does;
  - the resizes up to the guide size and back, and the SEGS scale match.
- SEGSDetailer now matches upstream in four ways:
  - it crops every SEG from its input image, and pastes nothing;
  - it uses one seed for all SEGs in a batch pass;
  - it returns the crop for a SEG it does not detail;
  - it clears the SEG's ControlNet wrapper.
- Unchanged: the inpaint-model path, detailer hooks, ControlNet wrappers, wildcards, the refiner, and the
  AnimateDiff detailers.
- `tests/test_detailer_repair_r6.py` is the lane-gate parity test. No model can run in the gate, so both sides use
  the same deterministic stand-ins for the VAE encode, the sampler and the VAE decode. Everything else is compared
  exactly: DetailerForEach's six outputs, and SEGSDetailer followed by SEGSPaste.
