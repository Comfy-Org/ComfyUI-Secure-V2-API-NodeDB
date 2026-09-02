# Secure Nodes V2 conversion

- Pack: `comfyui-resolution-master`
- Upstream: `https://github.com/Azornes/Comfyui-Resolution-Master`
- Pinned commit: `02bc2df967d53780913033578fd85b2afefae8c6`
- Release: `x02bc2df`
- Backend: 1 supported, 0 rejected, 0 pending
- Frontend: 1 supported, 0 rejected, 0 pending

## Behavior ledger

`ResolutionMaster` keeps the upstream preset matching, aspect-ratio fitting,
scaling, snap, WAN/Qwen/Flux model-profile calculations, rescale-factor logic,
and empty-latent selection in this pack. Its optional image is an opaque
`ImageRef`; only the bounded spatial shape crosses into the guest. Empty
latents are created by the generic bounded `LatentRef.empty` primitive. Both
the ordinary 4-channel / 8x and Flux.2 128-channel / 16x layouts are exercised
through a real guest session.

The old process-global dimension cache and HTTP calculation routes existed to
bridge the unrestricted browser extension to Python. They are no longer part
of the V2 runtime. Execution returns bounded `resolution_master` UI metadata,
and the extension consumes it through `onExecuted`. Directly linked gallery
selection state is read only through the typed `graph.widget_values` service.

The frontend extension was rebuilt on the V2 definition lifecycle and mounted
Remote DOM/canvas surface. It provides preset/category selection, manual and
modifier-key canvas sizing, swap/snap, model calculations, three scaling
modes, auto-detect options, latent/batch controls, and bounded custom-preset
persistence through `comfy.storage`. It has no parent realm, ambient DOM,
same-origin, unrestricted network, timer, or graph-canvas access.

## Security and bounds

The node requests only `graph`, and only while checking the widget values of
its directly linked input producer. Permission denial is fail-closed before
image inspection or latent creation. It does not request raw tensor access,
filesystem, network, subprocess, output, model-download, or secrets
capabilities, and it declares no external weights.

The upstream schema permits zero dimensions, 32K edges, and batch 4096. V2
keeps that workflow schema for compatibility, while the canonical latent
primitive rejects zero-cell latents and enforces its existing 16K edge,
batch-64, divisibility, and 16,777,216-element safety limits. Non-multiple
pixel dimensions preserve upstream floor-division semantics before the
bounded call. Resource-exhausting latent requests are deliberately never
permitted.

## API result

The only conversion gap was a generic bound: Flux.2 legitimately needs 128
latent channels. The shared `latent.empty` channel ceiling now admits 128
while retaining all dimension, batch, ratio, and total-element checks. No
pack algorithm moved into core and no vendor API was added.
