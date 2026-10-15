# Conversion evidence and provenance

Upstream https://github.com/WX-NPS1598/ComfyUI-Auto_Crop_By_NPS
Pin 61a42319c40944099fcc1e8466b2bf4fbf293ccc (x61a4231), July 2024.
The pinned repository has no LICENSE or license declaration. No terms have been
invented; this record is provenance, not a grant of permission.

Actual-loader census: one Python node AutoCropByNPS supported, zero rejected or
pending; zero frontend/JS-only nodes/routes. No weights or external services.
The original algorithm is retained except the global Image.MAX_IMAGE_PIXELS=None
assignment is removed. The Pillow decompression-bomb policy stays intact.

Preserves negative fractional crop integer rounding, positive borders based on
original dimensions, white RGB/RGBA and 255 mask fills, nearest clockwise rotation
with expansion, per-frame uint8 conversion/wrapping, CPU float32 result tensors,
independent IMAGE/MASK batches and dimensions, and None/empty-batch outputs.
Controls, IDs, schema slider metadata, outputs and category are preserved.

Finite floating tensors, image BHWC RGB/RGBA, mask BHW, H/W 2..8192, batch 0..64;
finite non-bool numeric controls within the original schema. Combined input and
output/intermediate elements each <=16,777,216. Cropped, padded and exact rotated
geometry is checked before Pillow allocation. Inverted/unrecoverably empty crops
fail explicitly; no successful result is fabricated. No private SDK constructors.
SDK_REFS=False and SDK_PERMISSIONS=('raw',), no files/network/models/graph/storage.

Persistence disposition: no durable pack state. The legacy class's five fields
are unused initial values; the execution reads only arguments. All controls and
linked inputs travel in normal workflow serialization. Local tensor/Pillow
temporaries are render-local; there are no endpoints, files, caches, counters or
browser storage. Tests recreate pack files and a fresh guest and prove identical
results without state carryover. No cloud KV continuity claim is made or needed.

Evidence covers pristine differential pixels for crop/expansion/rotation/RGBA,
optional and empty batches, per-input geometry; pre-allocation resource rejection,
input/RNG/Pillow-policy isolation, real guest/raw denial/outer IMAGE+MASK typing,
fresh-render reset, canonical stubs/manifest and byte-exact patch roundtrip.
CPU paths are proven; GPU input transfer behavior is untested and not claimed.
Raw denial is proven for tensor-bearing calls. With both inputs absent there is
no raw tensor access: the guest can safely return (None, None) without raw access.
