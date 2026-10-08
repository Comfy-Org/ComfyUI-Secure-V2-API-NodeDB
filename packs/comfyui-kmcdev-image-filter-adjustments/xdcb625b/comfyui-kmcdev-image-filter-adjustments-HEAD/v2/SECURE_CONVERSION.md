<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-kmcdev-image-filter-adjustments

## Provenance

- Upstream: https://github.com/kevinmcmahondev/comfyui-kmcdev-image-filter-adjustments
- Pinned commit: `dcb625b4f9b5b8501016eea8319bfbb02502e99c`.
- Release key: `xdcb625b`; snapshot: `comfyui-kmcdev-image-filter-adjustments-HEAD`.
- Historical Aug 4, 2026 registry: 3,224 downloads, ordinal rank 1,374/4,998.
  This is download-ranking evidence, not a current-trending claim.
- Registry SHA-256: `a0f27ea0f7b4ae1b26f2cf84b72ab3b2ad06eb4eb1f3aed7a338a4a2b1d47408`.
- Starting central catalog SHA-256: `cee2cbc4d5af77549dac4b9d180720e9f3595025428ae24ad77af79d1012f6f9`.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Evidence basis |
| --- | --- | --- | --- |
| `ImageFilterAdjustments` | supported | yes | Exact control/batch/dtype pixels and actual guest/outer IMAGE observed. |
| `ImageBlankAlpha` | supported | yes | Rounded RGBA geometry/pixels, bounds denial and actual guest/outer IMAGE observed. |
| `ImageBlendMask` | supported | yes | IMAGE-mask inversion/resize/rounding and second-image geometry parity; actual guest/outer IMAGE observed. |
| `ImageMixColorByMask` | supported | yes | MASK broadcasting/dtype/native failures, input isolation and actual guest/outer IMAGE observed. |

Totals: 4 supported / 0 rejected / 0 pending / 0 unknown. Registration/schema
alone never establish support. Dispositions remain bounded evidence declarations.

## Frontend and ancillary scope

Actual pinned package loader: 4 Python registrations, 0 frontend extensions,
0 JS-only nodes and 0 routes. No WEB_DIRECTORY or JavaScript surface exists.

## Verification results

Focused test source: `v2/tests/test_moe_oct6_kmcdev_filter_adjustments_pack_conversion.py`.
Tests retain class-method ASTs byte-equivalent, helper bytes, schema choices/defaults/
bounds/categories/IDs, filter/no-op and batch pathways, RGBA floor-to-eight
generation, inverted IMAGE-mask rounding, MASK blending and native malformed shape
errors. Projected output/aggregate/workspace limits precede algorithm allocations.
Each node is exercised in a real raw guest from original and fresh pack roots,
with raw denial, bounds denial and actual outer IMAGE result typing.

Observed complete gate: **129 passed** (7.64s), before this final ledger update.
121 warnings are retained: one external pynvml deprecation and 120 NumPy/Torch
interop deprecations from unchanged algorithms. Final-byte repeat results are in
the accompanying moe-oct6 handoff logs/evidence. SDK refs/ops are in-process providers supporting
real isolated guest execution; no algorithm double. Direct upstream runs use real
installed Torch, torchvision, NumPy and Pillow. No cloud deployment, full workflow,
model inference or GPU/MPS hardware path is certified.

## Release integrity

Canonical approved declarations copied from coordinator-owned KJ composite:
`packs/comfyui-kjnodes/x3f20054/ComfyUI-KJNodes-HEAD/v2`.

- d.ts: `4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3`.
- pyi: `50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78`.
- Pinned pristine identity, manifest and exact patch reconstruction are different
  checks; final per-file and pair hashes accompany the handoff.

## Authority and assets

Every node requests only `raw` through public value-mode `SDK_REFS=False`.
Algorithms stay in the pack. No storage, files, graph, models, network, routes,
subprocesses, downloads, globals mutation, runtime install or private constructor.
Unused imports of torch_utils/torchvision are removed; all actual algorithms and
tensor/Pillow quantization are retained. Uses managed common Torch/NumPy/Pillow,
declared in pyproject and requirements. Local installed execution is not a claim
that a fresh cloud runtime image was provisioned. No weights needed.
LICENSE and third-party NOTICE retained exactly.

Preserves no-op single-batch input aliasing; default multi-batch concatenation;
quantized PIL vs unquantized arithmetic; mask socket types; RGBA rounding to eight;
inverted/composited blend behavior, second-image output geometry for mismatched
blend sizes, and native safe channel/shape failures.

Safety narrowings: finite floating image/mask inputs, BHWC IMAGE and 2D/3D MASK,
batch≤64, axes≤8192, image channels1–4, each input/output≤16,777,216 elements,
aggregate≤33,554,432, conservative projected workspace≤67,108,864. Control ranges
match schema, including integer/color bounds. Large nominally schema-valid blank
images are denied before allocation when output exceeds bounds. No repair of safe
native failed combinations or hidden replacement interpolation is claimed.

## Persistence and limitations

Persistence disposition: **no durable state**; inputs are workflow-owned, all
compute is scratch per execution. Same inputs tested after new pack filesystem
and independent guest process; no per-user library or cloud durability claim.
CPU parity is proven only by observed tests; GPU/MPS paths not hardware-tested.
No coordinator integration or daily-count promotion before independent review.
