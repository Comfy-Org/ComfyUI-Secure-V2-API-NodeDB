# Secure conversion: Dimensional Latent Perlin

## Source and scope

Upstream: https://github.com/NeuralSamurAI/ComfyUI-Dimensional-Latent-Perlin
Pinned commit: `72cf9c1aeac606c44d812b104bfdce9b0e73ed8d` (`x72cf9c1`).
Five pristine files correspond byte-for-byte to the verified-TLS commit archive
SHA256 `084c4dd13a47030a4f1f83efab707e3f18824a3fd5d072fc1cbc9af387acb923`.
Independent Git-tree metadata was not observed; this is pinned archive
correspondence, not an assertion of an observed Git tree. MIT license, README,
and screenshot are preserved. No weights, downloads, routes or frontend code.
Retained queue download metric was unavailable/zero; no modern popularity claim.

## Node disposition

| Exact backend ID | Disposition | Qualified evidence |
| --- | --- | --- |
| NoisyLatentPerlinD | supported | Proposed bounded Mac-local conversion; exact CPU seeded/source math and canonical channel query, required fresh guests and production outer behavior. Coordinator serial release review still required. |

Backend census: one registered Python node. Frontend extension, JS-only graph
node, route censuses: zero. Schemas, ordering, defaults, ID, display name,
category and LATENT output are unchanged. `SDK_REFS=True` admits opaque MODEL
and LATENT handles. Permissions are `raw` and `inspect`: raw only computes and
publishes owned tensor data; inspect describes optional LATENT sample shape.
No model object or private constructor is accessed by pack code.

## Computation and deliberate lifetime normalization

The original Perlin grid, fade, trigonometric gradients, nested interpolation,
million/remainder transform, erfinv/detail multiplier and clamp remain pack
code. Batch/channel draw order is unchanged. An invocation-local CPU Torch
generator replaces global `torch.manual_seed`; ambient cross-node/global RNG
continuation is intentionally not preserved. Output is source explicit CPU
float32; operations respect the admitted runtime's floating default. Source
default 1024 creates `(1,4,128,128)` finite output. Non-default fp16 arithmetic
can overflow and produce native NaNs; exact bit controls retain those outcomes,
not finite normalization or relaxed numerical tolerances.

`await model.latent_channels()` follows canonical `get_model_object('latent_format')`
object patch/backup/base precedence. Public contract admits exact built-in
integers 1..4096; source zero-channel empty success and divide-by-zero repeat
controls remain separate historical/native evidence, not claimed admitted
zero-channel model parity. Model weights/inference are never read or executed.

Optional latent input is only a target **shape**, as in the original. Public
`describe()` gives its exact sample shape without materializing any buffers or
unrelated opaque metadata. A pack-local shape carrier drives the unchanged
source helper. Channels repeat or trim using exact canonical repeat/narrow
math, including rounded-up backing storage. Batch and spatial dimensions only
slice; larger targets are not expanded. Five-dimensional comparison/indexing
quirks and dropping all original metadata are preserved. Malformed non-tensor
sample descriptions and ranks outside admitted 4D/5D are refused; arbitrary
malformed legacy input parity is not claimed. Zero projected spatial cells
retain native division failure.

## Resource policy

Before algorithm allocation, preflight enforces scalar schema domains, source
floor grid, maximum 4096 target channels, 64 MiB output/repeat backing, 128 MiB
projected simultaneous ownership, and 16,777,216 cumulative pixel/draw work.
Projection covers original output, rounded-up repeated backing, three copies
for publication/transport and 64 floating planes plus fixed temporary allowance.
Shape-only input means zero input tensor snapshots. Defaults remain usable;
schema maxima may exceed bounds and fail closed before allocation. These are
local workload estimates and admission policy, not a hard physical-heap,
kernel, model compute-profile or sealed deployment attestation. No cap lift.

## Evidence and reproducibility

Unique owned tests: `tests/test_ned_perlin_conversion.py`; test-only probes are
not registered nodes. Tests compare exact contiguous bytes (including NaN
payload and signed zero), full schemas/census, seeded draw order and unchanged
global RNG, canonical tiny ModelPatcher object patches, channel repeat/slicing,
native errors, pre-allocation refusal, fresh required Seatbelt guest roots/PIDs,
real outer LATENT types, permission denial/recovery, unrelated opaque metadata
identity, live duplicate exclusion, resources/stub hashes and exact pair/ZIP
roundtrips. Canonical model fixtures are CPU metadata objects, not trained
inference. Frontend/browser harness is inapplicable because census is zero.

Test command from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes \
COMFY_SECURE_SANDBOX_MODE=required PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/Users/ben/comfy/ComfyUI-secure-nodes:/Users/ben/comfy/ComfyUI_secure_nodes/backend \
/Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -q -c pytest.ini \
-p no:cacheprovider --tb=short test_ned_perlin_conversion.py
```

Observed early gate: 95 passed. Expanded gate: 120 passed / one comparator
failure, preserved in `ned-oct8-perlin-expanded-1.log`: `torch.equal` rejects
native fp16 NaNs even against themselves. Comparator changed to **exact bits**,
not tolerance. Initial missing-PYTHONPATH collection error and the actual
whole-latent-materialization/opaque-metadata refusal are retained separately;
the latter is not a missing API because the existing shape-description service
suffices. Final matching gates and artifact hashes are bound in the handoff,
not inferred from earlier totals. Bytecode and pytest caches are disabled.

Additional retained pre-final diagnostics: missing V2 runtime declaration
prevented the first artifact-generation attempt; a Python 3.13 declaration
with the observed Torch 2.13.0 / NumPy 2.4.6 versions was then added. Empty
transported tensors have zero strides, so an empty byte comparison is vacuous
after exact shape/dtype/device checks rather than requiring a dtype view.
The pinned Python files use CRLF; diff comparisons read exact bytes rather
than universal-newline-normalizing text. No source pixel/math change follows
from any of these harness/packaging corrections.

Canonical Python stub: `355778b6cc0d44c9cae46b4fca001a2593934b791afec5f864b2f31f8a598fb3`,
from coordinator tested latent-channel handoff `dfda81358a336014c263272dfd96663dec3c131eff858d2ee7338aa2e8a9d578`.
Composite TypeScript stub: `3ac9255af06288ef33356403debf2ff57fd5cbff0cf8009fa305d2c1704324c9`;
no frontend features consumed. Source provenance names exact artifact origins.

## Persistence and limitations

No durable state or cache. Seeds/options live in workflow inputs; generators,
temporary arrays and results are invocation-owned. Fresh pack/guest recreation
preserves deterministic input-driven behavior, not a persistent service.
No model/weights, trained/GPU inference, Linux/Cloud deployment, sealed runtime,
physical memory profile or non-default host-device equivalence is certified.
No registry/status/count/commit/push/deploy mutation is authorized in this lane.
