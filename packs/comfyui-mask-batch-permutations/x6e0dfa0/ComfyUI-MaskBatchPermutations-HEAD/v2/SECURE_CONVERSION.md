# Conversion evidence

Upstream: https://github.com/curiousjp/ComfyUI-MaskBatchPermutations
Pin: 6e0dfa07a139f49bb5e8d20799e1e24598208820 (x6e0dfa0).

Actual-loader census: 3 Python registrations, all supported; 0 rejected/pending.
No frontend extensions, JS-only nodes, routes, or weights. README's older
two-node statement is not the registration census. algorithm.py is byte-identical
to the pinned __init__.py; only the public V3 wrappers and bounds are new.

Preserved: bit-pattern mask order/max unions/empty-mask slot; base-(N+1) image
enumeration; exact mask==1 selection; later-mask overlap precedence; first base
image only in detailer; ordered straight-alpha compositing for every base frame;
RGB candidates' last channel used as alpha (upstream quirk); empty candidates;
empty masks; dtype, inputs and RNG isolation. Permutation/detailer allocations
remain CPU allocations as upstream specifies; flatten preserves base device.
Flatten's mixed-dtype indexed-assignment error is preserved, not silently cast.

Security bounds: finite floating tensors; H/W 1..8192; up to 64 image frames,
12 masks, 4096 output combinations; each input/output at most 16,777,216 elements;
output elements times mask/candidate work factor at most 134,217,728.
Matching image/mask geometry and devices; detailer RGB only, flatten RGB/RGBA.
These explicit pre-allocation bounds reject excessive or malformed requests,
not approximate or silently truncate them. No new shared APIs or private ref
constructors. SDK_REFS=False and SDK_PERMISSIONS=('raw',).

Evidence: exact schema/loader/manifest census; pristine differential cases,
enumeration/order/overlap/alpha edge assertions; input/RNG isolation; malformed
and exponential-allocation guards; real isolated guest and raw denial for all
nodes; real outer IMAGE/MASK executor typing; canonical stub/license checks;
byte-exact pristine-to-V2 patch reconstruction. CPU paths are proven; GPU-specific
behavior is untested and is not claimed. No interactive/frontend behavior exists.
