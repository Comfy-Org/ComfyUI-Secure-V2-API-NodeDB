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
