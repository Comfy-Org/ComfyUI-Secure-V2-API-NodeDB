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
