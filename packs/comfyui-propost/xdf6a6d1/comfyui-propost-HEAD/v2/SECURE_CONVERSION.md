# ProPost — Secure Nodes V2

Upstream: <https://github.com/digitaljohn/comfyui-propost>, existing pinned commit
`df6a6d122498f57ad7195d58e07701a501c9dcb6`, release `xdf6a6d1`.
The 25 original files and tested converted code are preserved. This is an
existing-source evidence update, not a newly acquired upstream identity.

## Node scope

Five original nodes and five actual converted registrations; no upstream web
extension, browser graph node, settings or backend route.

| Node | Native comparison status | Finite purposes |
| --- | --- | --- |
| `ProPostVignette` | tested (original/default SDK) | 11: zero/nonzero intensity, one/three/four channels, offset, float32/float64 |
| `ProPostFilmGrain` | tested (original/default SDK) | 30: four stocks, grayscale/RGB, scales, repeated render, seeds, sharpening, two original errors |
| `ProPostRadialBlur` | tested (original/default SDK) | 8: float32/float64, strength, steps, center and focus spread |
| `ProPostDepthMapBlur` | tested (original/default SDK) | 8: depth channels/resize/constant values, focal range, mask blur, batch, original float64 error |
| `ProPostApplyLUT` | tested (original/default SDK) | 24: genuine colour 1D/3D LUTs, custom/default domains, strength and log branches |

The full genuine original and actual registered default-SDK packages executed
81 purposes: **78 returned results and three matching original errors**.
All **85 output tensor buffers are byte-identical**, with matching shapes and
dtypes. All 800 checks, 20 separately scoped candidate admission guards and six
coherent wrong-pixel/MASK controls passed. NaN positions were compared, allowing
NaN payload/sign-bit differences only; none of the 85 buffers needed that allowance.
The errors are the original scale-zero and gamma-zero `ZeroDivisionError` and
OpenCV's RGB float64 depth conversion error. They are not successful image renders.

## Explicit adaptations

- Zero-intensity Vignette returns a bare tensor upstream. The conversion wraps
  that same pixel result in its declared one-output container. Container identity
  is not claimed for that branch.
- Original grain reseeds global RNG and saves/reuses seed-derived temporary PNG
  masks. Converted grain uses a local `random.Random(seed)` and recomputes masks.
  Pixel and repeat-render equivalence passed. Original RNG/cache/console and
  converted unchanged RNG/no cache were recorded separately, not treated as equal
  process side effects.
- Original LUT lookup reads the physical `models/luts` catalogue. Converted LUTs
  use managed input assets through actual SDK `resolve`, `size` and `read_range`.
  Identical finite cube bytes were supplied in owned layouts; parsing and real
  colour interpolation matched. Existing LUT libraries must be admitted into the
  managed input catalogue separately. Browser selector refresh, storage migration,
  tenancy and retention are not qualified by this native comparison.
- Original package `__init__.py` exports only `NODE_CLASS_MAPPINGS`. Display
  labels were read from each original class's genuine defining `nodes.py` module;
  package-level absence and module origins were recorded, not replaced with
  candidate metadata. Explicit schema fields and declared IMAGE/MASK outputs match.

No fake colour package, `folder_paths` facade, asset provider, schema, executor
or replacement image algorithm was used. Genuine Core `folder_paths` configured
only task-owned roots. Model objects and downloads are not needed by these nodes.

## Authority and bounds

All five nodes declare `SDK_REFS=False` and `raw`; LUT additionally declares
`assets`. Floating finite CPU BHWC inputs are limited to 64 batch, 4096 per axis,
four channels and 8,388,608 elements. Projected workspace is capped at 512 MiB;
grain scale/sharpen and blur steps/kernels are checked before computation.
These are candidate bounds, not original behavior or a hard physical RAM quota.

LUT names are confined logical `.cube` names; broker reads are bounded to 8 MiB.
Parser limits include finite RGB/domain values, increasing domains, exact layout,
1D size up to 65,536 and 3D size up to 65. The 20 guard controls are candidate-only
refusals observed before the real algorithm method; they are not original parity.

## Actual evidence and limitations

One selected native attempt, `m_7185a0d2ce`, on Python 3.13.14, `comfy_api`
0.42.0, Core `44564d0279c275eef52b11750a9d76349f4e7a88`, backend
`59bd3e1acba6520bb32717ad03833f6ab2967ecc`. Actual libraries include Torch
2.13.0, NumPy 2.4.6, OpenCV 5.0.0, Pillow 12.3.0 and genuine colour-science
0.4.6. The latter was an exact cached wheel in a separately owned 737-file prefix;
no upgrade or mutation of the qualified existing site was needed.

Native work took **15.911595083 seconds**, with **540,934,144 bytes** peak sampled
aggregate RSS. This is observation, not a hard RAM/CPU quota or whole map-to-map
wall-time claim. Complete environment readbacks occurred outside the native work
clock. No automatic retry: all eight serial stages exited zero; all 16 cleanup
rows confirmed reaping and group absence. Nine groups and ten actual PIDs were
absent in two independent observations. Periodic RSS samples happened to cover
seven PIDs; actual worker ownership records identify the remaining short stages.

All 36 packet files, 141 SDK files, 1,384 Core files, 83 backend files, 84,917
installed-site files, 96 component files, 737 colour-prefix files and captured
configuration/operator maps were unchanged. Real colour and LUT import origins
were checked inside the selected job. See `validation/20261020-propost-native-r3`
for compact evidence and exact map/source hashes; raw archives and full maps stay
outside Git and are identified by their hashes.

The 32,523,946-byte evidence archive is SHA-256
`a7f54dc7e8812b52f199b04c86895af3c0b73b77cda2875b80460c8f2435381f`.
Strict independent review:
`d2ac0a34182b11ffcf35bdcb993db78c3d297cba7c6ceeb07563e74529a5ee48`.
The first local intake reader wrongly required every actual PID to appear in
periodic samples. Its failed check/source is preserved; the corrected data-only
reader derives actual PIDs from owned worker records and the observed controller
and outer process. No selected runtime predicate, evidence or expectation changed,
and no native rerun was made.

The actual normal generated manifest is retained byte for byte:
`c5fda73ba748ddb7ff1cec3cc139b15321029b642feb6e786d1a06257dac5cb9`.
Canonical pair/bundle regeneration and both pristine file-only replays preserve
all original and converted files and Unix modes. This publication changes only
this report after normal generation; neither scientific code nor the generator
is rerun. Historical pytest/Guest/outer claims in the old report were not rerun
or newly recovered as concrete historical logs. R1/R2 preparation packets remain
unselected and unrun; the R3 fixture correction did not change production code.

**Runtime/dependency-profile admission, registry adoption, actual public graph
execution, Guest/gVisor, browser UI and deployed-service acceptance remain
separate.** Testing the genuine private colour composition does not admit that
composition to a shared service. The existing source dependency-profile identity
is retained; source publication is not deployment or whole-pack certification.
