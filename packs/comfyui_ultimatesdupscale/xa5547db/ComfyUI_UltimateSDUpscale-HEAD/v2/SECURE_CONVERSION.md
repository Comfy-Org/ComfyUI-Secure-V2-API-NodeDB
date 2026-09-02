# Secure Nodes 2.0 conversion

Pinned upstream commit: `a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df`.

- Backend nodes converted: 4/4.
- Rejected nodes: 0.
- Frontend modules requiring conversion: 0.
- Tile planning, chess/linear ordering, padded crops, masks, batching,
  compositing, and all three seam-fix strategies remain pack-side.
- Text-only tile groups retain batched sampling. Groups carrying area, mask,
  GLIGEN, ControlNet, or reference-latent metadata are sampled per tile so
  every spatial hint is cropped against the correct tile origin.
- Model- and guider-owned spatial guidance uses the reusable
  `spatial_crop_inputs` primitive. Tile planning remains here; the core-owned
  DiffSynth and Z-Image control patches crop and clone their own images,
  inpaint images, masks, and encoded guidance without shared-state mutation.
- Upscale-model inference, VAE encode/decode, and diffusion sampling use
  opaque Secure Nodes 2.0 references.
- The custom-sampler node preserves its `SAMPLER` and `SIGMAS` inputs; the
  guider node preserves `GUIDER`, `SAMPLER`, and `SIGMAS` without exposing
  any live model object to the guest.
