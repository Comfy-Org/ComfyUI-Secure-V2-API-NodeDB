# Secure Nodes V2 conversion

Pinned upstream: `bba4c36401ebdf7ff4914a9cbce8de3f398ca4e9`.

## Census and disposition

- Backend: 10 supported, 0 rejected, 0 pending.
- Frontend: 1 registration supported, 0 rejected, 0 pending.
- Routes and startup behavior: none.

The Divide-and-Conquer tensor math, ratio helpers, sequence generation, and
readout formatting remain pack-side. Pixel-manipulating nodes use the bounded
`raw` tier. Optional model upscaling calls the existing host-owned
`UpscaleModelRef.upscale` operation with the pinned 512-pixel tiled behavior.

`Load Images into List` remains supported for logical subfolders of ComfyUI's
managed input directory through `ctx.assets.list`, `resolve`, and `load_image`.
The legacy acceptance of an arbitrary host filesystem path is intentionally
rejected on security grounds: a workflow value does not grant authority to
enumerate any directory on the machine.

Sequence size, tile count, and tile dimensions are bounded so malformed
workflows fail instead of hanging the guest or allocating without limit.
