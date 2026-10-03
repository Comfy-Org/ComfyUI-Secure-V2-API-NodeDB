# How the Secure V2 conversion works

H3 video latents use a five-step temporal pattern covering
`(1, 4, 4, 4, 4)` pixel frames. The Context node selects only a
phase-aligned tail, creates native MiniMax keyframe guides for those steps,
and optionally places the prior audio latent on the same timeline. When head
seeding is enabled, the same video steps are copied into the new latent and a
noise mask controls how firmly they are held.

The guest owns this selection, resampling, trim, and mask arithmetic. It sees
only raw values explicitly released through the `raw` permission. Live VAE and
conditioning objects remain on the host:

1. `LatentRef.value()` releases the selected latent value to the guest.
2. Heterogeneous video/audio streams cross as a tagged nested tensor.
3. `CondRef.with_minimax_h3_guides()` validates and installs native H3 guides.
4. `VaeRef` encodes frames or audio without exposing the live VAE.
5. `ImageRef.resize()` uses ComfyUI's canonical scaler on the host.

Project state is a bounded manifest in tenant-scoped pack storage. Videos and
state dictionaries are written through managed output operations and are
referenced later by logical output name. The frontend receives a sidebar
container from the host and addresses only the pack's declared private routes.

The secure build does not load compatibility patches, reach ComfyUI internals,
or expose host filesystem paths.
