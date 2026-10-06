# Image Expand Nodes — Secure Nodes V2

Upstream: https://github.com/tuki0918/comfyui-image-expand-nodes
Pinned commit: `3e28a97d804cf9e6ab246e3bfebe69f404209827` (`x3e28a97`).

Census: **3 Python supported, 0 rejected, 0 pending; 0 frontend/JS-only/routes**:
ImageExpandNoiser, ImageExpandMerger, ImageExpandOption. Names, category,
socket order/types/option order, percentage default/range/step, and optional
mask are preserved. The custom EXPAND_OPTION value remains an ordinary closed
schema socket carrying direction/mode data between the option and image nodes.

The original noiser/merger method bodies remain in `algorithms.py`; V2 wrappers
declare public value-mode raw compute on those two nodes, and zero permissions
on the scalar option node. No private ref constructor, host model, filesystem,
network, subprocess, installation, browser, or shared API is used.

All four directions and outside/inside modes retain shifts, ceil rounding,
mask nearest interpolation/batch broadcast, RGB/RGBA promotion, mask-derived
merge slicing, and output order. In particular, zero expansion retains the
original bottom/right `-0:` slice behavior (including native inside-noiser
assignment errors). Invalid option keys/rank/shape/percentage cases retain
native errors where safe; the intentionally out-of-contract rank-4 merger mask
is rejected before its unbounded rank-5 broadcast. Unknown option values keep
the original fallback behavior rather than being silently corrected.

Noise is still unseeded `torch.rand` on the input device/dtype with the original
draw shapes/consumption. The pack never sets a process-global RNG seed. Tests
temporarily fork/seed/restore RNG only to compare every generated pixel to
upstream. Real independent guests test noise distribution, draw independence,
exact non-noise pixels, exact masks, and no mutation/aliasing of inputs.

Resource bounds are enforced before algorithm allocations: batch 1..64,
spatial axes 1..4096, image channels 1..4; each input <=16,777,216 elements,
aggregate input <=33,554,432; projected noise and merged output <=16,777,216,
projected workspace <=67,108,864. Merger projection includes worst-case slicing,
RGBA promotion, device copies and broadcast/composite intermediates; noiser
projection includes mask interpolation/broadcast and noise. Rank/channel/size
resource rejections are deliberate fail-closed compatibility boundaries.

Persistence disposition: **no durable pack state**. Options and images/masks
belong to the workflow/execution. There are no presets, editable libraries,
counters, endpoints, cache files, or state carried across renders. Fresh pack
filesystems/guest processes are tested; no cloud storage backend claim is made.

MIT LICENSE retained byte-for-byte. Torch is a declared managed dependency.
CPU float16/bfloat16/float32/float64 and batch/mask/channel paths are exercised.
CUDA/MPS device-transfer paths are retained but not directly hardware-tested;
there are no weights, credentials, or external integrations. Public outer
executor tests verify declared IMAGE/MASK outputs, not an interim guest ref
kind inference. Exact patch/manifest/contract tests must pass twice on final
bytes; handoff records the precise gate command and results.

The focused module contains 112 tests; the combined gate adds 33 shared
manifest/patch tests. Real guest execution includes 64 successful option/noise/
merge calls across independent original/fresh pack roots, 32 raw-capability
denials, two overlimit guest rejections, and one public outer-executor run.
Stochastic repeat calls must produce distinct noise without changing host RNG.

From the isolated pack-db worktree, run the final-byte combined gate twice:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-image-expand-nodes/x3e28a97/comfyui-image-expand-nodes-HEAD/v2/tests/test_image_expand_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py --tb=short
```
