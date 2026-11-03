# Secure Nodes V2 conversion

Pinned upstream commit: `97807467bf7ff4ea01d529fcd6e666758f34e3c1`
Upstream: `https://github.com/wallish77/wlsh_nodes` (GPL-3.0)

## Census and terminal status

- Every node id of the pinned package (39) is registered with its original
  schema, frozen from the original (`_frozen_nodes.json`). The served node
  info equals the original's (`tests/test_wlsh_schemas.py`).
- Converted (13 of 39):
  - numbers and text: `SDXL Steps (WLSH)`, `Multiply Integer (WLSH)`,
    `SDXL Resolutions (WLSH)`, `Resolutions by Ratio (WLSH)`,
    `Simple String Combine (WLSH)`;
  - empty latents: `Empty Latent by Size (WLSH)`, `Empty Latent by Ratio (WLSH)`,
    `Empty Latent by Pixels (WLSH)`, `SDXL Quick Empty Latent (WLSH)`;
  - images: `Image Scale by Shortside (WLSH)`,
    `Upscale by Factor with Model (WLSH)`;
  - models: `Checkpoint Loader w/Name (WLSH)`, `KSamplerAdvanced (WLSH)`.
- Every other id is refused by name at queue time ("not converted to Secure
  Nodes V2 yet"), and again at run time. Nothing is approximated.
  `Image Save with Prompt (WLSH)` and `Image Save with Prompt/Info (WLSH)` name
  their own reason: they write their files with Pillow directly (PNG text
  chunks in their own order, JPEG, TIFF or GIF, overwriting names built from
  the clock), and byte-equal output through the V2 image writer is not
  established yet.
- Requires guest SDK base 0cd9adec or later (`ImageRef.from_value`).
- Frontend extensions: none upstream.
- Licence: upstream's GPL-3.0 `LICENSE` is carried unchanged in this
  directory. This document lists what was changed and why.

## What runs where

- The number, text and empty-latent nodes run the original's bodies in the
  guest. The empty latents are the original's CPU float32 zeros.
- `Image Scale by Shortside` runs the original's body on the exact input
  pixels, with Core's `comfy.utils.common_upscale` copied verbatim in
  `_core_utils.py`.
- `Upscale by Factor with Model` runs the original's body. Core's
  `comfy.utils.tiled_scale` (verbatim in `_core_utils.py`) tiles the image as
  the original asks (192-pixel tiles, overlap 8). Each tile goes to the host's
  upscale model untiled, which is the original's own `upscale_model(tile)`
  call; the model and its weights stay on the host. The original's clamp and
  Core's `common_upscale` then run on the result.
- `Checkpoint Loader w/Name` loads through the host's checkpoint loader, which
  makes the same Core call as the original (`load_checkpoint_guess_config`
  with VAE, CLIP and the embeddings folders). The name output is the original's
  own parse of the menu name. The menu is filled by the host from its own
  checkpoints folder, never by the pack.
- `KSamplerAdvanced (WLSH)` samples through the host's sampler with the
  original's arguments (Core's `common_ksampler` steps) and returns the same
  INFO dict. Like upstream, it never forces a full denoise.
- `_core_utils.json` records the copied Core definitions' lines and sha256 and
  proves that every global name they use resolves as it does in Core
  (`vendor_core.py`; `tests/test_wlsh_vendor.py` reruns it in the gate).

## Known differences

- `KSamplerAdvanced (WLSH)`: for a latent that carries
  `downscale_ratio_spacial` or `downscale_ratio_temporal` (some video latents),
  Core passes them to `fix_empty_latent_channels` and drops them from the
  output; the host's sampler keeps them and does not pass them. Ordinary
  latents are unaffected.
- Sampler and scheduler menus are frozen copies of Core's lists on the
  conversion core. Choices that other installed packs add at runtime are not
  mirrored.
- Image outputs are finite and hold at most 4096 images (V2 images).
- Verified on CPU. On a GPU host the upscale tiles and the sampler run on the
  GPU in both versions.

## Verification

All tests run on CPU without weights, on seeded tiny synthetic models (a 2x
Compact upscaler loaded through Core's own loader, an SD1.5-shaped UNet). No
checkpoints, workflows or media are used. Each test runs as a plain gate run
with the pack root at `/pack`. The V2 side runs in real guests started through
`tests/_wlsh_sealed_guest_entry.py`, whose import audit refuses any import by
pack code outside the standard library, the sealed guest lock
(`tests/guest_lock_modules.json`) and the declared profile (none).

- `tests/test_wlsh_parity.py`: every converted node against the original,
  every option and edge values. The checkpoint loader is compared at Core's
  loader call (every bound argument) with a recording stand-in for the
  checkpoint file. A 1-ulp change to one V2 output must turn the comparison
  red.
- `tests/test_wlsh_schemas.py`: every node's node info, in process and as
  served from the manifest, against the original's.
- `tests/test_wlsh_vendor.py`: `_core_utils.py` re-derived from the gate's
  Core and compared byte-for-byte.
- `tests/encode_manifest.py`: manifest regeneration and loader check.
- `tests/test_production_load.py`: every manifest row resolved the way the
  guest resolves it (only the row's module imported, without the pack's
  `__init__.py`), in process and through a real guest.
- `tests/freeze_wlsh.py` captures the frozen schemas from the original.
