# Secure Nodes V2 conversion

Upstream: <https://github.com/GavChap/ComfyUI-SD3LatentSelectRes>

Pinned commit: `d5867b6fedf58dbe4559904097b5e2eef3cacfb1`

Release: `xd5867b6`

## Census

- Backend: 2 supported, 0 rejected, 0 pending.
- Frontend: 0 extensions.
- Routes and settings: none.

Both selectors preserve their IDs, ordered resolution options, output-node
status, dimensions, orientation, batch behavior, latent layouts, and constant
`0.0609` samples. The immutable preset JSON is represented as pack code so the
guest requires no filesystem authority.

The upstream V2 node declares a combo default of `SD3`, which is not one of its
two choices. The secure schema repairs that metadata defect by using the first
actual option, `SD3/Flux/Z-Image/Qwen/etc`; execution behavior is unchanged.

## Security boundary

The nodes declare `raw` solely to create their custom 16- or 128-channel latent
tensors. Allocations are bounded before tensor creation and returned through an
opaque `LatentRef`. There is no filesystem, network, subprocess, model, UI, or
ambient host authority.
