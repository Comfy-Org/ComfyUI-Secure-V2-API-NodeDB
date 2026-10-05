# Changelog

## 0.3.0 - 2026 August 5

### Added

- Add reversible `pad` sizing that preserves pixel aspect ratio while producing
  divisible diffusion dimensions.
- Add `Apply Autosize Transform` for applying the recorded image geometry to
  aligned masks.
- Add `Restore Autosized Image/Mask` for removing diffusion padding and
  returning to the exact source dimensions.
- Append reusable transform metadata to Image/Mask Autosize outputs.

## 0.2.0 - 2026 July 31

### Changed

- Rebuilt Image Autosize with ComfyUI's V3 node API.
- Renamed the node display name to `Image/Mask Autosize`.
- Accept `IMAGE` or `MASK` inputs and return the matching type.
- Add `constraint_priority` with `min_size` and `max_size` policies.
- Use ComfyUI's shared resize implementation to preserve device, dtype, and
  tensor precision for native interpolation modes.
- Replace the `multiplier` output with `scale_x` and append `scale_y`.
- Report scales from the actual intermediate resize dimensions before an
  anchored crop.
- Prevent divisible-dimension rounding from producing a zero-sized output.
- Replace the Pillow interpolation list with `nearest-exact`, `bilinear`,
  `area`, `bicubic`, and `lanczos`.

### Compatibility

- Existing output index 3 now returns `scale_x`; `scale_y` is output index 4.
- The default `min_size` priority preserves the previous sizing order.
- Workflows using `nearest`, `box`, or `hamming` must select a supported
  interpolation mode.
- Existing `IMAGE` workflows, input names, node ID, and the first three output
  positions remain unchanged.
