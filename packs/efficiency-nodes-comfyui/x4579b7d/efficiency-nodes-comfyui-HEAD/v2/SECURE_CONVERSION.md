# Secure conversion notes

Pinned upstream commit: `4579b7d6076b2870998a08f5d37883fbc8261ff2`. The sealed node schemas and permissions are in `secure-nodes.json`.

## Repair round r1: SCRIPT values in the original's shapes

These nodes now put the original's tuples in the SCRIPT dict. Before this round they wrote dicts with named keys.
- Noise Control Script: `script["noise"] = (rng_source, cfg_denoiser, add_seed_noise, seed, weight)`
  (`efficiency_nodes.py:4047-4050`).
- Tiled Upscaler Script: `script["tile"] = (upscale_by, tile_size, tiling_strategy, tiling_steps, seed, denoise,
  tile_controlnet, strength)` (`efficiency_nodes.py:4233-4240`). With strategy "none" the incoming script passes
  through unchanged, as in the original; it is None when nothing is connected.
- XY Plot: `{"xyplot": (X_type, X_value, Y_type, Y_value, grid_spacing, Y_label_orientation, cache_models,
  xyplot_as_output_image, my_unique_id, dependencies)}` (`efficiency_nodes.py:2369-2455`).
  - `cache_models` keeps the widget's "True"/"False".
  - Only X values are cleaned for Checkpoint/VAE plots: the original's Y branch repeats the X condition.
  - "XY_Capsule" inputs pass the same-type check, as in the original.

The samplers turn these tuples back into the fields their sampling code uses (`_script_noise`, `_script_tile`,
`_script_xyplot`), so sampling itself is unchanged by this round.

Known differences:
- The ControlNet slot of a "tile" tuple, when used, holds the platform's ControlNet handle instead of the loaded model
  object.
- The HighRes-Fix Script entry keeps its named-key form. The original's tuple holds a Python class and loaded models,
  which have no portable value.
- The original's script nodes add their entry to the incoming dict in place. V2 adds it to a copy, so an earlier node's
  output does not change afterwards.

## Repair round r2: Tiled Upscaler Script samples like the original

KSampler's tile pass now follows the original's code paths (`efficiency_nodes.py:651-673`, `py/bnk_tiled_samplers.py`).
Before this round, V2 had its own sampler ("sample each tile and feather the overlaps"), so its images differed.

How it runs:
- Decode the latent, unless an image is already there. Resize it with ImageScaleBy nearest-exact and VAE-encode it.
- Then run the pack's vendored BlenderNeko TiledKSampler (`py/bnk_tiled_samplers.py`, `sample_common`), step for step:
  - The noise is `comfy.sample.prepare_noise` (seed, batch_index), or the Noise Control Script's noise when that
    script is attached, as inside KSampler (Efficient).
  - Except with "padded", the latent is pre-noised with `sigmas[start] * process_latent_out(noise)`. The start sigma
    comes from the host's schedule (`ModelRef.sampling_sigma_delta`) and is exact, because every core schedule ends
    at 0.
  - Tiles, steps and masks come from the original tiling ("simple", "random", "random strict", "padded"). The helpers
    are `py/bnk_tiling.py`, copied verbatim to `_bnk_tiling.py`.
  - Each tile's partial schedule (start/last step) runs host-side through `ctx.sample`, with the original's tile noise
    (zero, or with "padded" the tile's slice of the full noise) and tile mask. The result is written back the same way.

Known differences, all named refusals or the original's own errors:
- With use_controlnet, the original applies the ControlNet with the legacy ControlNetApply and slices its hint per
  tile. V2 refuses by name.
- Conditioning with ControlNet, area, mask or GLIGEN entries is refused, because the original slices those per tile.
  Reference latents are refused too, because the host check groups them with the others.
- Pre-noising is exact only for latent formats whose `process_out` is `latent / scale_factor` (SD1, SD2, SDXL, SVD).
  Other model families are refused, except with "padded", which does not pre-noise.
- With an AYS scheduler and dpm_2, dpm_2_ancestral, uni_pc or uni_pc_bh2, the original's sampler drops the schedule's
  penultimate sigma; the host's AYS schedule does not. That combination is refused.
- A latent with a noise mask fails as it does in the original: `comfy.sample.prepare_mask` no longer exists in core.
- With "tiled" VAE decoding, the original's `VAEEncodeTiled().encode(vae, pixels, 320)` fails, because core requires
  `overlap`. V2 raises the same TypeError.

Known private SDK use: with "padded", each tile's noise slice reaches `ctx.sample(noise=...)` through
`sdk.TensorRef._from_raw` (`_bnk_sample_tile`), as before this round. This stays until the SDK has a public TensorRef
constructor for a node's own tensor, or `ctx.sample` accepts such a tensor as noise.
