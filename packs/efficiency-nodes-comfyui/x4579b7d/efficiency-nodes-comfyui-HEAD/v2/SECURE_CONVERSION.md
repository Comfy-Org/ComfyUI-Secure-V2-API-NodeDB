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
