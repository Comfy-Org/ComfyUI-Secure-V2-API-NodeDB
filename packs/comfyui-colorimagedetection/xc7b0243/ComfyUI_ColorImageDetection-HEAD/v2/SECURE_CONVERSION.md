# Color Image Detection — Secure Nodes V2

Source: https://github.com/DrMWeigand/ComfyUI_ColorImageDetection
Pinned commit: `c7b02434e908d6133c0acb94e031640689165abf` (`xc7b0243`).

Actual imported census: **2 Python supported, 0 rejected, 0 pending**;
**0 frontend extensions, 0 JS-only nodes, 0 routes**. The catalogue's count of
three is superseded by actual registration of `RGBColorDetection` and
`LABColorDetection` only. Both preserve category `Image Analysis`, ordered
inputs/defaults, custom `BOOL` (not `BOOLEAN`) plus `FLOAT` outputs, and exact
output names. The upstream RGB display-name entry uses the unmatched key
`ColorDetection`; that mapping is preserved without inventing a corrected
registered-node label. The LAB label remains `LAB Color Detection`.

## Algorithms and compatibility quirks

The original NumPy/OpenCV/Torch algorithms remain in the pack. RGB analysis
casts to float32, performs the original BGR-to-RGB operation, flattens absolute
channel deviations, sorts them and averages the selected tail. The percentage
is divided by 100 exactly as upstream (the default is 0.1 percent). When the
integer selected-count is zero, `[-0:]` means the entire vector; this behavior
is deliberately retained. LAB analysis retains BGR-to-LAB and mean absolute
A-minus-B scoring. Both analyze every batch member but return only the final
member's result, not a batch average/list. Strict greater-than threshold
comparison is retained, including equality returning false.

NumPy boolean/float32 scalars are converted to Python bool/float for wire
transport without changing their values. The real outer executor test checks
the declared custom BOOL and FLOAT outputs emerge as native Python scalars.
No private SDK constructor or output-type workaround is used.

The unused legacy `comfy.model_management.get_torch_device()` assignment is
removed; it never placed or modified the input. Execution is public value mode
(`SDK_REFS=False`) with the explicit `raw` capability, solely for bounded
tensor compute. No host services, models, paths, files, network, routes, subprocess,
runtime installation or global RNG mutation are requested. NumPy, Torch and
OpenCV are declared managed dependencies, not installed during execution.

## Bounds and malformed direct inputs

Inputs must be nonempty finite floating-point CPU RGB tensors with shape
`[batch, height, width, channels]`: at most 32 images, 8192 per spatial axis,
4,194,304 total pixels, and 128 MiB source tensor bytes. Scalar parameters must
be finite nonboolean real numbers with absolute value at most 1,000,000.
Existing widgets have no added min/max; these are direct execution safety
bounds. Finite extended percentages (including some negative values and values
over 100) retain the native slicing semantics. An empty selected slice producing
NaN fails closed rather than attempting invalid nonfinite JSON transport.
Malformed dimensions/types/nonfinite values and oversized inputs fail closed.

The original algorithm calls Tensor.numpy() directly and supports CPU data only;
this conversion does not silently transfer unsupported GPU inputs or claim GPU
execution. Native dtype conversion/failure behavior is retained, including
OpenCV float32 conversion and unsupported NumPy bfloat16 inputs. Float16,
float32, float64 and noncontiguous CPU inputs are differentially exercised.
Both nodes accept RGB/RGBA and retain native alpha-discarding color conversion.
RGB also accepts one-channel images; LAB retains its native OpenCV rejection
of one-channel input. These paths are explicitly tested, including real guest
and outer execution of RGBA and one-channel RGB.

## Persistence disposition

**No durable state.** There are no authored presets, routes, endpoint files,
browser stores or user caches. The only instance field was unused `self.device`.
Thresholds and percentages are workflow inputs; analysis variables are
dispatch-local. Tests recreate both pack filesystems and guests across user A,
user B, then user A and verify identical scores. No cloud persistence backend
is required or claimed.

## Repeatable verification

`v2/tests/test_color_image_detection_secure_conversion.py` checks exact census,
schemas and legacy mappings; byte-exact source hashes; upstream numeric
differentials across batches/dtypes/strides/thresholds and percentages; last-batch
and zero-slice quirks; bounds, malformed and nonfinite outcomes; input/RNG
immutability; actual guest outputs and raw denial; real outer-executor BOOL/FLOAT
normalization; fresh-render isolation; current manifest/stub hashes; cache
hygiene; and byte-exact pristine-to-V2 patch roundtrip.

Run with `PYTHONDONTWRITEBYTECODE=1`,
`COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes`, and
`/Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -p no:cacheprovider`, plus
the focused file, backend `test_packpatch.py`, and `test_packdb_manifest.py`.

Canonical d.ts SHA-256:
`4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3`;
pyi `50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78`.
No shared/API changes or pending gaps. Real guest verification uses macOS
seatbelt; Linux deployment is not directly exercised here. Numerical parity is
verified with the installed managed OpenCV/NumPy versions; independently changing
those versions can change native vendor math, as for the pristine pack.
