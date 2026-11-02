# Secure Nodes 2.0 conversion

Pinned upstream commit: `2f18256c5b5063937106f29a8e0a7db3ae3869b7`

Status: **29/29 backend nodes supported, 0 rejected**. The pack also defines
one frontend-only node, `Show Metadata [Crystools]`; it is supported through
the read-only V2 graph surface, so the complete node census is **30/30**.

The secure entrypoint imports only `_secure_nodes.py`. It does not import the
upstream initializer, start the hardware-monitor daemon, register pack-owned
HTTP routes, or expose filesystem paths. The browser monitor polls ComfyUI's
existing `/system_stats` endpoint and displays the RAM/VRAM totals the host
publishes. It does not recreate the upstream background process.

Pack-side code retains the Crystools behavior:

- primitives, typed lazy switches, lists, pipes, and debugger formatting;
- bounded image decoding and image metadata parsing;
- preview metadata/cache behavior and metadata-aware image save;
- confined UTF-8 JSON loading, extraction, and structural comparison;
- metadata extraction/comparison and the Stats latent passthrough;
- frontend prompt/workflow diagnostics assembled from read-only node, widget,
  input-resolution, and link snapshots.

Core additions are limited to reusable primitives: metadata-aware image
save/preview, bounded read-only system resource totals, and extension-filtered
managed-asset listings. No Crystools algorithm or monitor loop was moved into
core.

Extra model weights: none. If a future node declares weights, the Secure Nodes
policy permits only pinned, hash-verified Hugging Face weight files, provisioned
once into the managed cache before execution; node execution never downloads
them repeatedly.

Verification includes deterministic schema/manifest/stub generation, patch
round-trip validation, syntax checks for every shipped JavaScript module, an
iframe-only frontend metadata-viewer harness, traversal rejection, and a real
guest execution census covering all 29 backend nodes.

## 2026-10-29 validation/menu repair - UNRUN-IN-GUEST

The image loader regains its original named validator and invalid-image message, using the existing assets domain for managed-file existence and original annotation slicing. Read JSON has no new validator: its current asset route is filled by host L1-r2, pending the exact deployment receipt. Native path diagnostics and directory-versus-file edge cases are not claimed equivalent to the confined assets provider. Image/JSON processing algorithms and schemas are unchanged.

This revision is source-only. Historical test/status rows remain unchanged. Both target-base static checks, independent review and canonical pristine replays are separate from any actual Guest/graph/model/browser qualification; no new node algorithm was run.

## 2026-10-29 independent review correction R2 - UNRUN-IN-GUEST

Independent review corrections and publication limitations are recorded below.

Generator-defect workaround: the current discovery generator omits inherited hooks. Changed validation_inputs rows must be emitted by the real pinned packmanifest.encode_validation_inputs from genuine source classes in bounded isolated discovery, then match the inert gate and independent review. The bounded real-source encoder proof now passes: 43 declared validator rows across six packs, including the 16 changed signature rows, were emitted by pinned packmanifest4c6772a3 and all six resulting manifests are byte-identical. PROOF.json SHA256 ad7e5710761da87f89e0c2d45f1a317d383cff5462f28066ff27271ef734445e. Only this report was updated after that proof; node code and manifest bytes are unchanged. This is signature encoding, not full schema discovery or execution parity. Regenerate and byte-compare when the fixed canonical generator exists. Stubs pending canonical 0cd9adec pair; existing pyi/d.ts files are untouched. No new Guest, algorithm, graph, model or browser execution. Only Root publishes changed files, preserving Git modes; local replay bundle ZIPs are not publication artifacts.
