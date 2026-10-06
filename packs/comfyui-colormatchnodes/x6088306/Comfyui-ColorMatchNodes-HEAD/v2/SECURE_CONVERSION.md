# Elyetis ColorMatchNodes — Secure Nodes V2

Upstream: https://github.com/elyetis/Comfyui-ColorMatchNodes
Pin: `6088306cda0383cbfc5252e83f25b7de82152ae1`; release `x6088306`.
GPLv3 license retained; pristine tree stays byte-exact.

Actual-loader census: **2 Python supported / 0 rejected / 0 pending**:
`ColorMatch2Refs` and `ColorMatchBlendAutoWeights`. **0 frontend extensions /
0 JS-only nodes / 0 routes**; upstream's declared `./js` directory is absent.
All input names/order, required/optional placement, defaults/bounds/options,
display names, descriptions, categories, and named IMAGE outputs are preserved.

The two-reference blending algorithm remains pack-side using public
`io.ComfyNode`, `SDK_REFS=False`, and permission **raw**. No private constructors,
host paths, network, subprocess, installations, or arbitrary host imports.
Color transfer uses the already managed `color-matcher` dependency, not a new
trusted transform. All six methods are retained: mkl, hm, reinhard, mvgd,
hm-mvgd-hm, hm-mkl-hm. Auto weights retain all five easing modes, power curves,
constant/U-shape strength, first/last reference selection, singleton batches,
weight clamping, debug output, frame order, CPU float32 output and [0,1] clipping.

Manual blending retains per-frame reference batches or singleton broadcasting,
including upstream's squeeze behavior on singleton spatial/channel dimensions.
Individual `Exception` transfer failures still log and fall back to that target
frame. Unsupported method names are rejected with the same vendor error message
but normalized from its fatal `BaseException` to `ValueError`, so malformed enum
values do not bypass normal guest RPC error handling or kill a reusable worker.
Mismatched reference batch indexing errors and singleton-spatial squeeze/broadcast
errors are not silently repaired.

Resource bounds: BHWC tensors, channels 1–4, batch <=64, each spatial axis <=4096,
each tensor <=16,777,216 elements, total input work <=33,554,432 elements.
These bounds apply before CPU materialization. Empty target behavior and direct
malformed/indexing behavior inside those structural limits remain upstream-like.
The `multithread` option retains ordered parallel local computation but caps
worker count at **2** instead of exposing host CPU-count-dependent fan-out.

Runtime tested: Python 3.13, Torch 2.13.0, NumPy 2.4.6, color-matcher 0.6.0.
Exact CPU differential tests and real isolated raw guests exercise every method.
No learned models, remote services or credentials are needed. GPU-to-CPU transfer
on CUDA/MPS hardware is not directly exercised; both versions explicitly compute
on CPU and retain the same conversion calls.

Persistence disposition: **no durable pack state**. Controls belong to workflow
serialization; per-frame arrays, workers and curves are disposable render-local
computation. No endpoint/files/preset cache/global mutable state needs cloud KV.
Fresh-filesystem/fresh-worker execution verifies the same result without prior state.

Focused command:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-colormatchnodes/x6088306/Comfyui-ColorMatchNodes-HEAD/v2/tests/test_colormatchnodes_secure_conversion.py --tb=short
```

Coverage includes census/schema, all color methods and curves, reference selection,
strength and clipping, dtype/shape/frame order/input immutability, bounded thread
fan-out, fallback/error paths, resource denial, real raw-permission guest execution
and denial without raw, recreated render continuity, manifest/canonical contracts,
GPL provenance, authority audit, and exact pristine-to-V2 patch roundtrip twice.
No API/dependency/persistence gaps; shared API/runtime/docs/registry untouched.
