# Secure Nodes V2 conversion

Upstream: <https://github.com/Koushakur/ComfyUI-DenoiseChooser>

Pinned commit: `57b8a372e9291e050c725b987ae1722f11b93143`

Release: `x57b8a37`

## Census

- Backend: 1 supported, 0 rejected, 0 pending.
- Frontend: 0 extensions.
- Routes and settings: none.

The actual pinned registration loader exports exactly
`DenoiseChooser|Koushakur`. The conversion preserves its node ID, display
name, category, input names and bounds, output types, latent identity, empty
versus non-empty selection, and percentage normalization.

## Security boundary

The node declares `raw` because its intended behavior depends on whether any
element of the latent sample tensor is non-zero. It reads that bounded tensor
inside the raw-compute guest, performs only `count_nonzero`, and returns the
original opaque `LatentRef`; it does not reconstruct or mutate the latent.
There is no filesystem, network, subprocess, model, route, UI, or ambient host
authority.
