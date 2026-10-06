# SDupscale Tiled Size — Secure Nodes V2

Source: https://github.com/Windecay/ComfyUI-SDupcaleTiledSize
Pinned commit: `8869dbd17e8fb7afb7dd8990b26bb4baaae07027` (`x8869dbd`).

Actual unmocked entrypoint census: **1 Python node supported**, 0 rejected,
0 pending; 0 frontend extensions, JS-only nodes or routes. ID, class name,
display name, category, all ordered inputs/defaults/widget limits, and all
four output socket types/names/order are unchanged.

## Intent, authority and exact behavior

This is a tile-size helper for UltimateSDUpscale, not an upscaler. The arithmetic
remains pack-owned: clamp factor >=4 to4; truncate scaled dimensions before
the tile-block comparison; use ceil to divide oversized dimensions; truncate
again; then round dimensions upward to multiples of16. The original helper
is retained exactly. Zero, bounded negative and very large positive factors
retain their direct-call math (large positive factors clamp before multiplying).

Only public `ImageRef.spatial_shape()` is called. The **same input ImageRef** is
returned, and the real outer executor returns the **same tensor object**.
No image buffer reading, copying, resizing, device movement or allocation is
performed. The node declares **zero permissions**, with no inspect/raw access.
Unused upstream Torch/Pillow/regex imports are removed; no new API, host hook,
model dependency, network, filesystem or mutable global state is introduced.

## Bounds and explicit typed-boundary normalization

Image H/W metadata must be1..16384. Tiled block must be a nonboolean integer
1..2048 (its original widget remains512..2048). Factor must be a finite
nonboolean real scalar >=-1,000,000; positive values >=4 safely clamp to4.
These bounds prevent pathological scalar output and preserve the registered
schema's normal behavior. Malformed channels/rank are rejected by the existing
spatial-shape broker; invalid scalars are rejected before any broker call.
The pack allocates no pixel buffers, so image batch size/dtype/device/stride
and even empty batches are passed through without reinterpretation.

Exact parity is proved for the standard **BHWC IMAGE contract**. The existing
public SDK additionally accepts **HWC** images; these use their actual H/W.
The upstream direct 3-D call accidentally indexes width/channels as H/W. That
out-of-contract indexing bug is deliberately **not** recreated; coordinator
approved this normalization, and tests prove both behaviors differ. No extra
inspect permission is added solely to recover malformed legacy rank details.
Zero/invalid tile blocks and nonfinite factors fail closed, rather than
reproducing upstream's accidental division errors or NaN-to4 coercion.

## Persistence disposition

**No durable state.** Results derive entirely from explicit inputs. There are
no endpoints, caches, settings, files or authored values to survive renders.
Fresh recreated pack filesystems and different confined guest processes for
user A/B/A give the same math and independent image passthrough. No durable
storage service is needed.

## Evidence and limitations

`tests/test_sdupscale_tiled_size_secure_conversion.py` covers actual census,
full schema/manifest parity, int/ceil/16-rounding thresholds, randomized math,
upper clamping and direct finite scalar quirks, tensor aliasing/layout/type,
SDK HWC normalization, malformed/resource bounds, real zero-capability guest,
outer executor identity, real raw/inspect denial, failed-guest-call recovery,
fresh-render/user isolation, exact pristine hashes, canonical declarations,
cache hygiene and byte-exact patch reconstruction. Meta-device images prove
that even enormous admitted images require only metadata, not computation or
materialized buffers. This is not a claim of GPU kernel execution (none exists).

The real confined guest is tested on macOS; Linux sandbox enforcement is not
exercised. GPU image identity is not tested on hardware; no device operations
are introduced. Frontend tests are not applicable.

Upstream pyproject references an **absent LICENSE** file. No license grant or
replacement license is invented. This missing upstream document remains a
packaging/licensing caveat for distribution; all five tracked pristine files
are captured byte-exact, including their original CRLF line endings.
