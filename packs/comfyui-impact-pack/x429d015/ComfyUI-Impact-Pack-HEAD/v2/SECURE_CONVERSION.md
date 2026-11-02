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

Impact Subpack's tensor-only YOLOv8x person/face recipe is assembled and run
inside this isolated pack runtime using the exact `ultralytics==8.3.162`
dependency. Core only resolves and parses the SafeTensors asset.

`secure-nodes.json` is the authoritative sealed schema/permission census. The
operational classification and representative real-guest behavior are enforced
by `backend/tests/test_popular_pack_conversions.py`, including an explicit
`195 supported / 2 rejected` assertion.

## 2026-10-30 validator repair and C4-R1 - UNRUN-IN-GUEST

ImageReceiver and LatentReceiver restore their original named validators and receiver-inclusive signatures through managed assets.exists. Their existing assets authority is unchanged. Generator-defect workaround: real pinned packmanifest.encode_validation_inputs must encode genuine source classes; placeholder equality alone is insufficient. The bounded R3 proof confirms real overrides and mechanically derives CG fingerprint flags. This is metadata discovery only, not full schema or purpose execution.

The draft ONNX models grant is removed under C4-R1. _onnx_detector_provider (1457-1461) calls _onnx_detector.recipe (48) only; it builds a recipe rather than loading a model. Bound packdb 7cc6d977 L403-412 supplies names without models. Other preexisting grants are not automatically removed by the heuristic excess-grant census.

LatentReceiver / latent.remote remains **policy edit (reviewed)**: the available managed input-file catalogue is recursive and any-extension, broader than the original top-level .latent/.latent.png UI. Read authority and existing grants are unchanged. Incompatible selections can fail to load. Current webassets rejects kind=file refresh, though selected packdb can fill object_info. No matching deployment or original UI/file-error parity is claimed; managed empty/directory diagnostic differences remain unqualified.

Manifest uses the original indent-1 format with only the five intended field changes against main, after dropping the withdrawn ONNX grant; no whole-file reindent. The proof preserves input manifest bytes after checking encoded values. Stubs remain unchanged pending a qualified canonical pair. Source-only SDK checks, exact canonical replays, independent review and actual Guest/graph/model/browser qualification remain distinct. Root alone publishes changed files with Git modes.
