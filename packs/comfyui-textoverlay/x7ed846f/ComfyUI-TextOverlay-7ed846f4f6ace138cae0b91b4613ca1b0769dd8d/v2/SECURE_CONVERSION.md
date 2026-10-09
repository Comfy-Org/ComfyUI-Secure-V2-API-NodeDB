# TextOverlay bounded local conversion

Complete six-file upstream/release 1.0.1 source at historical Git
7ed846f4f6ace138cae0b91b4613ca1b0769dd8d. One backend ID `Text Overlay`,
no frontend/routes/model/service. The pristine tree is unchanged.

Only the native font reader boundary changes: `font` retains its STRING schema
and default `ariblk.ttf`, interpreted as a portable basename under managed
INPUT `textoverlay/<font>`. No system/arbitrary path search is allowed. Full
size/range/tail/re-size transport admits at most 2 MiB before Pillow's original
BytesIO TrueType reader. A genuine missing admitted asset and an invalid native
font retain the default-font fallback. Permissions, confinement and resource
errors propagate; they are not turned into success/default output. Same-length
concurrent file replacement is not an atomic snapshot guarantee.

All source text wrapping, alignment, line spacing, 3-digit HEX whole-string
repetition bug, float-to-uint8 quantization, batch-local font/layout cache,
float32 output and admitted native errors remain exact. A fresh source instance
per call is consistent with its first-frame `use_cache=False` reset.

Profile: dense contiguous CPU HWC/BHWC without autograd, 64 frames, each axis
at most 16384; 32 MiB conservative input/output, 256 MiB projected aggregate
workspace, 4096 UTF8 text bytes, 255-byte font label, 16,777,216 projected glyph
work, schema scalar ranges and pre-operation geometry/glyph/font bounds. Rank,
layout/device/oversize resources outside this local profile visibly refuse.
Parser/native font heap allocations are not claimed as a host-hard quota.

Python 3.13 inherited Torch/NumPy/Pillow runtime with no sealed profile. Positive
font evidence requires explicit caller-supplied hash-bound installed macOS font
data; no font is shipped and no distribution rights or Linux font identity are
inferred. Default fallback is measured separately. Public inspect/raw/assets
grants provide only typed descriptions, numerical buffers and confined assets;
no models/host object recovery/output/network grants.

The source references LICENSE in pyproject but ships no LICENSE payload. Local
conversion is authorized; later source/font publication permission remains a
separate qualification. No Cloud, GPU, sealed deployment or completion count is
claimed until independent coordinator intake.
