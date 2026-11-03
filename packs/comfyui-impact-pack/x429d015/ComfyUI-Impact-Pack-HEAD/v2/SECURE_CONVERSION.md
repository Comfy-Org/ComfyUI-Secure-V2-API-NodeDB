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
