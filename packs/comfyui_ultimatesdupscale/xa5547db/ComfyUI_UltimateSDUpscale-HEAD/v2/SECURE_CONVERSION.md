# Secure Nodes 2.0 conversion

Pinned upstream commit: `a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df`.

- Backend nodes converted: 4/4 (`UltimateSDUpscale`, `UltimateSDUpscaleNoUpscale`, `UltimateSDUpscaleCustomSample`,
  `UltimateSDUpscaleGuider`).
- Rejected nodes: 0.
- Frontend modules requiring conversion: 0.

## How the conversion works (repair round r1)

`_secure_nodes.py` is a port of the pack's own tile pipeline:
- `usdu_nodes.py` with the `usdu_patch.py` sizing and batching patches;
- `modules/processing.py`, `modules/upscaler.py` and `modules/images.py`;
- the `usdu_utils.py` helpers;
- the bundled `ultimate-upscale.py` script.

The value-handling lines are the original's: the drawn tile masks and crop regions, the Lanczos resizes, the Gaussian
mask blur, the gradient seam masks, alpha compositing and the 8-bit image round trips. Comments of the form `file:line`
point at the pinned source.

The functions are `async`, and the model-owned steps cross the SDK as opaque references:
- `ImageUpscaleWithModel` becomes `UpscaleModelRef.upscale(image, tile_size=512)`. That is ComfyUI's tiled runner with
  512-pixel tiles and 32-pixel overlap, clamped, on the node's original IMAGE, as in the original.
- `VAEEncode`, `VAEDecode` and `VAEDecodeTiled(..., 512)` become `VaeRef.encode`, `decode` and `decode_tiled(..., 512)`.
- `common_ksampler` and `SamplerCustom` become `ctx.sample`. The host runs `comfy.sample.sample` or
  `comfy.sample.sample_custom` with `prepare_noise(latent, seed)`.
- `sample_with_guider` becomes `ctx.sample(guider=...)`.
- `crop_model_cond` becomes `ModelRef`/`GuiderRef.spatial_crop_inputs`.
- `crop_cond`: conditioning without area, mask, GLIGEN, ControlNet or reference-latent rows passes through unchanged,
  as in the original. Rows with that metadata go through `CondRef.spatial_crop`.

The module-level `shared` state of the original is held per node call.

## Upstream behaviour kept on purpose

- The seam-fix passes sample with the main `denoise`. The original sets `p.denoising_strength` from
  `seam_fix_denoise`, but its sampler reads `p.denoise`, so `seam_fix_denoise` has no effect.
- The original's sizing is kept:
  - the canvas is `round(size * upscale_by / 8) * 8`;
  - tiles are `tile + padding`, rounded to 8;
  - band-pass tiles are `seam_fix_width + 2 * seam_fix_padding` by the image height;
  - half-tile passes use the tile size.

## Parity (tier 1, CPU gate)

`tests/test_comfyui_ultimatesdupscale_parity.py` runs the original modules (V1) and this port (V2) side by side.
Both use the same deterministic stand-ins for the model-owned operations (`tests/usdu_fakeops.py`). For 22 cases it
compares:
- the output IMAGE, exactly;
- the full sequence of model-owned calls, with argument and result digests;
- stdout;
- error type and message.

The cases cover all four nodes, Linear, Chess and None redraw, every seam-fix mode, uniform and non-uniform tiles,
odd image sizes, tiled decode, image batches, tile batches, upscale factors 0.5 to 3, the Lanczos path without a
model, custom sampler and sigmas, the guider node, and the batch-size assertion. A one-level change to one output
value turns the comparator red.

## Known differences

Plain text conditioning on an ordinary model gives the original's output exactly. The differences below need spatial
conditioning, model patches, or unusual inputs.

1. **Spatial conditioning.** Area, mask, GLIGEN, ControlNet/T2I hints and reference latents are cropped per tile by
   the host's spatial conditioning crop, not by the pack's `crop_cond`. The pack's crop cannot run in the guest,
   because conditioning stays engine-side. The previous V2 did the same. The host crop differs from the original:
   - Hints are resampled bilinearly, not nearest-exact, and the crop window is rounded differently.
   - An area row that does not intersect the tile is dropped. The original keeps that row without its area.
   - Masks are resized at latent resolution, not with PIL at tile resolution.
   - In a tile batch (`batch_size` > 1) every tile uses the first tile's region. The original concatenates one hint
     per tile.
2. **Model patches.** DiffSynth / Z-Image control patches are cropped by their own `spatial_crop_inputs`, not by the
   pack's `crop_model_cond`, which re-encodes the cropped image at native size.
3. **RGBA input with an upscale model** fails. The host upscale has no separate alpha path, while stock
   `ImageUpscaleWithModel` upscales alpha bilinearly.
4. **Empty sigmas** (a scheduler with denoise 0) are refused by the host sampler. The original returns the tile
   unchanged.
5. **Size limits.** A working canvas above 67,108,864 pixels (batch × width × height) is refused by name, as are tiles
   beyond the SDK's image and crop limits. The original has no limit.
6. **Frozen sampler and scheduler menus.** These come from the frozen schemas; the original reads ComfyUI's live
   lists.
7. **Progress and logs.** Progress is reported per tile through the SDK. The original's console progress bar and
   debug log lines are not printed; its `print` lines are.
8. **Errors.** Errors raised during execution reach the host through the sandbox transport as
   `WireError("<Type>: <message>")`. The message text is preserved.
