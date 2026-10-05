# ComfyUI-ConditioningMultiplyAdvanced

Adds a `Conditioning Multiply Advanced` node for scheduling conditioning strength while preserving non-floating tensors such as token ids.

The default mode scales:

- the main conditioning tensor
- `pooled_output`
- `t5xxl_weights`

It preserves integer tensors such as Anima `t5xxl_ids`, avoiding embedding dtype failures caused by generic recursive conditioning multiply nodes.

## Settings

- `start_multiplier`: multiplier at `start_percent`.
- `end_multiplier`: multiplier at `end_percent`.
- `start_percent` / `end_percent`: denoise-progress window for the transition.
- `curve`: interpolation curve from `start_multiplier` to `end_multiplier`.
- `outside_window`: behavior outside the transition window.
	- `hold`: before the window uses `start_multiplier`; after the window uses `end_multiplier`.
	- `baseline`: outside the window uses `1.0`.
	- `linear_extrapolate`: continues the linear multiplier trend outside the window.
- `segments`: number of conditioning ranges used to approximate the curve. Higher values are smoother but add more conditioning entries.
- `tensor_scope`: selects which float tensors are multiplied.
- `non_float_behavior`: `preserve` leaves integer/bool tensors unchanged; `error` raises if one is encountered.
- `metadata_keys`: comma-separated metadata tensor keys to scale when metadata scaling is enabled.
- `log_summary`: prints tensor counts for debugging.
