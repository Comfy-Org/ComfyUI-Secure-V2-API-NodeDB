# ComfyUI-InpaintEasy — Secure Nodes V2 conversion

Upstream is pinned at `d631a03dea2397db27042f5e9ec34fce34b2cfb6`.

## Census

- Python nodes: 4 registered, 4 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- JavaScript-only nodes: 0.
- Backend routes: 0.

The converted IDs are `InpaintEasyModel`, `ImageAndMaskResizeNode`,
`CropByMask`, and `ImageCropMerge`.

## Authority and behavior

`InpaintEasyModel` uses the typed, host-owned VAE inpaint-conditioning and
ControlNet operations. The three image/mask utility nodes retain their bounded
Torch/NumPy algorithms in the isolated guest and request only the `raw`
capability needed for value-mode tensor transport. The pack has no network,
filesystem, process, environment, route, frontend, or arbitrary host authority.

The conversion preserves the registered schemas, the core inpaint and optional
ControlNet branches, every resize/crop mode, mask blur, empty-mask failure,
crop coordinates, merge behavior, tensor shapes/dtypes/batches, and upstream
failure behavior for malformed or out-of-range direct calls.

