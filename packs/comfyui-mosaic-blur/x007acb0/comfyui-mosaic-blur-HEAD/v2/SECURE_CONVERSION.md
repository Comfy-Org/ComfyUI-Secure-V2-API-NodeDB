<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-mosaic-blur

## Provenance

- Upstream: https://github.com/fuselayer/comfyui-mosaic-blur
- Pinned upstream commit: `007acb074a77b8472bd837704442e4056d9de7e7`.
- Release key: `x007acb0`; snapshot: `comfyui-mosaic-blur-HEAD`.
- Selection: historical Aug 4, 2026 registry download snapshot, 4,318 downloads,
  descending ordinal rank 1,107 of 4,998. Not current trending evidence.
- Snapshot source: local pinned Git clone; every tracked blob tested against pin.
- Registry snapshot SHA-256: `a0f27ea0f7b4ae1b26f2cf84b72ab3b2ad06eb4eb1f3aed7a338a4a2b1d47408`.
- Base central catalog SHA-256: `cee2cbc4d5af77549dac4b9d180720e9f3595025428ae24ad77af79d1012f6f9`.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Evidence basis |
| --- | --- | --- | --- |
| `ImageMosaic` | supported | yes | Exact pixels/quirks, two fresh isolated guests, raw denial, outer IMAGE and exact artifact reconstruction observed. |

Registration or schema parity alone does not establish support.
Current terminal totals: 1 supported / 0 rejected / 0 pending / 0 unknown.

## Frontend and ancillary scope

Actual pinned loader exports 1 Python node, 0 frontend extensions, 0 JS-only graph
nodes and 0 routes. There is no WEB_DIRECTORY or JavaScript source. These are
separate censuses, not inferred from missing Python manifest entries.

## Verification results

Focused selector: `v2/tests/test_moe_oct6_mosaic_blur_pack_conversion.py`.
Tests preserve algorithm ASTs and compare both Pillow/OpenCV pixel output at
float16/32/64, RGB/RGBA, noncontiguous batches and several block sizes. Native
tiny-grid, squeezed-axis and grayscale failures are compared, not made into
fabricated successful output. Finite-control/input and projected work limits are
checked before pixel compute. Real isolated raw guests run both methods and
channels from original and recreated pack roots; raw denial, host input isolation,
separate PIDs and actual outer IMAGE executor result typing are tested.

Observed complete gate: **66 passed**, one external pynvml deprecation warning
(7.99s), before this final ledger update. Final-byte repeat results are preserved
in the unique moe-oct6 handoff logs/evidence packet. No model inference, deployed
cloud workflow or GPU/MPS transfer path is certified. Guest broker refs/ops are
in-process providers; the pack algorithm itself executes in a separate guest,
not a recording algorithm double. The direct upstream loader uses real installed
dependencies; folder_paths is unused legacy import removed in V2.

## Release integrity

Canonical declarations copied from coordinator-owned
`packs/comfyui-kjnodes/x3f20054/ComfyUI-KJNodes-HEAD/v2`, not an arbitrary
historical conversion.

- d.ts SHA-256: `4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3`.
- pyi SHA-256: `50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78`.
- Manifest and exact pristine→V2 reconstruction are tested separately from pinned
  Git-blob provenance and behavior; final hashes in accompanying handoff.

## Authority and assets

Only `raw`, public value-mode `SDK_REFS=False`. No files, storage, model,
network, graph, backend routes, subprocess or host-global mutation. No weights or
assets required. Uses installed Torch, Pillow, NumPy and OpenCV; declared in
pyproject/requirements. No downloads/install performed by pack or this conversion.
Actual cloud runtime provisioning is separate from observed local guest execution.

Pillow always returns RGBA, including RGB input, and keeps out-of-bounds edge crop
padding. OpenCV floor-downsamples then nearest-resizes, with original alpha
preserved. Both retain clipped uint8 conversion and CPU float32 output.

Safety narrowings: batch≤64; axes≤8192; floating BHWC with 1–4 channels;
finite input; input/output≤16,777,216 elements; projected blocks≤1,048,576;
method restricted to schema choices and integer block_size 1–100. Native safe
errors within these limits remain errors. Pillow global image policy untouched.

Upstream metadata declares MIT License but no LICENSE file is present at the
pin. This missing-license provenance is retained; no license text/terms invented.

## Persistence and limitations

Persistence disposition: **no durable state**. All inputs are workflow-owned;
compute is scratch-only. Fresh pack filesystem and independent guest processes
test continuity using the same inputs. No userdata/cloud storage claim is needed
or made. GPU/MPS-specific conversion is untested; original CPU conversion retained.
All dispositions are bounded test-supported declarations, not full workflow or
production certification. No coordinator integration/count promotion yet.
