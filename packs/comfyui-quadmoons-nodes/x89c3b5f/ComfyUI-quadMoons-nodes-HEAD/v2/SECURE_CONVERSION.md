# quadMoons Secure Nodes V2 conversion

Source: `https://github.com/traugdor/ComfyUI-quadMoons-nodes` at commit
`89c3b5f7272691285c9d5e954f6ea8003be216f3` (tree
`202cc9c4cc98fbc8b21f8158b089a175676db958`).

## Census and disposition

- Backend nodes: **23 supported, 0 rejected, 0 pending**.
- Frontend registrations: **3 supported registrations / behavior groups**.
- Routes: none.
- Rejected incidental side effects: the import-time rewrite/deletion of files
  inside another custom-node pack, and the Manager-only host reboot button.
  Neither is part of any backend node's data result. Queue start and interrupt
  remain available through the bounded V2 queue facade.

All 23 source node identifiers remain registered. Scalar conversion,
conditioning, A1111 PNG metadata parsing, Smart Nodes templates, latent
creation/batching, all four samplers, and the two-pass background replacement
are implemented. The embedded Efficiency Nodes copy does not contribute node
registrations at this pin; only its advanced prompt-weighting algorithm is
retained pack-side. Its examples remain ordinary documentation assets.

## Security boundary

- Checkpoints are selected by catalogue name and loaded by `ctx.models`.
- Uploaded PNG metadata is read from a managed input `AssetRef`.
- Smart Nodes' mutable JSON file is replaced by the pack's scoped
  `ctx.storage` namespace; the same model-hash/config-name behavior is kept.
- CLIP and VAE modules and model weights never enter the guest. Existing
  `ClipRef`, `VaeRef`, conditioning, and sampling operations perform those
  host-owned steps.
- Tensor arithmetic that defines the pack—normalization, prompt embedding
  weighting, SEGS-mask assembly, latent batching, and deterministic batch
  noise—runs in the isolated guest under `raw` only where required.
- No network, subprocess, ambient filesystem, dynamic import, or host module
  authority is granted.

## API/TDD result

No new API surface is introduced. Every supported behavior composes frozen V2
operations already documented in the Python API TDD: managed assets, scoped
storage, catalogue model loading, CLIP/VAE refs, sampling, raw bounded buffers,
and the opaque frontend queue/widget facade. Consequently this conversion has
no new TDD decision to add.

The upstream Smart Negative node can emit a STRING on a CONDITIONING socket
when both saved and fallback text are empty. That is an invalid Comfy value;
V2 normalizes this broken edge to valid empty-prompt conditioning rather than
allowing a downstream type failure.
