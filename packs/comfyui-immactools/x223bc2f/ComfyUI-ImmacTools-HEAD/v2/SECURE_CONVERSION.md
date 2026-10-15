# Secure conversion: ImmacTools

## Pinned source and whole scope

Upstream https://github.com/Immac/ComfyUI-ImmacTools, exact commit
`223bc2ff027280a28ab309081e4e5344f40b3488` / `x223bc2f`.
All22 retained registry0.1.0 paths/bytes match the complete recursive Git blob
tree, with no omitted or added Git source paths; regular100644 modes agree
with retained0644. Retained release ZIP SHA256
`f43ac9b0be4340e0e68fb862582a84d4a10a290221ee7cf1f9bb001bc8d680f3`.
This establishes historical release correspondence, not a newer-source
substitution. MIT license/resources/readme/test metadata are preserved.
Historical retained queue126 recorded475 downloads; not current trending.

## Exact node dispositions

| Backend ID | Disposition | Evidence scope |
| --- | --- | --- |
| ConcatenateSigmasImmacTools | supported | Source boundary comparison/dedup, scalar/empty/dtype/native errors, bounded CPU tensor publication. |
| SpliceSigmasAtImmacTools | supported | Source masks/prefix/suffix/boundary insertion, clamp/rounding/options and native errors. |
| ResampleSigmasImmacTools | supported | Source scalar and multi-point interpolation/default10; singleton repeat error remains native. |
| SkipEveryNthImagesImmacTools | supported | Ordered tensor/list filtering and removed indices, n<=0/empty/fallback and typed buffer output. |
| MatchContrastImmacTools | supported | Exact NumPy uint16 CDF/LUT and RGB/LAB math, batch reference-last selection, blend/dtype/native errors. |
| SwitchImmacTools | supported | Zero-cap selected ANY identity without traversing unselected opaque objects. |
| ForwardAnyImmacTools | supported | Zero-cap structured/opaque/model/tensor passthrough identity. |
| ForwardConditioningImmacTools | supported | Host conditioning identity including cyclic/opaque row metadata, no export. |
| ForwardModelImmacTools | supported | Actual canonical tiny ModelPatcher identity, no inference/load/raw. |

These are bounded Mac-local release proposals pending coordinator intake.
Nine backend IDs, one extension `immac.switch_node`, zero JS-only IDs/routes.
Schemas, IDs, defaults, category/display/output ordering and source lazy[]
are exact. Source root display mapping versus V3 schema spelling differences
are retained, not silently harmonized. Source algorithms in
`src/immac_tools/nodes.py` and `forwarding_nodes.py` remain byte-identical.

## Frontend and persistence axes

The sole extension is supported in a real opaque iframe/worker V2 bridge:
public defs created/configured/removed hooks, widget change subscription and
input collection add/remove replace prototype/global app access. Source1..20
input order, tail removal, surviving link identity, widget restoration,
reopening, growth/shrink, instance isolation and disposal are tested against
literal pristine controls. Public minimum-size/resize clamping replaces
computeSize. Browser graph/widget/slot handles are labelled host facades; this
is production bridge execution, not full app/Cloud rendering certification.

State is workflow-serialized num_inputs/index/one_indexed and input links.
No authored persistent documents, routes, filesystem, cache, service or RNG.
Per-worker event subscriptions are disposable; no tenant+pack storage needed.

## Authority, resource and native behavior

Only five compute nodes declare raw+inspect; switch/three forwarding nodes
declare no capabilities. Typed model/conditioning handles are never recovered.
Tensor description projects shape and a bounded public diagnostic dtype
string, unknown summaries reserve16 bytes. Before raw re-admission/read,
plans cover input snapshots, casts, masks/index arrays/interpolation fields,
all output siblings, histogram/LAB/NumPy temporaries, stacked frame lists and
publication copies:64MiB output,128MiB projected ownership,8,388,608 dense
elements,67,108,864 work units and4096 sequence items. Unknown/malformed
non-tensor structured numeric inputs are explicitly bounded admission,
not arbitrary source object compatibility. Source dimension/rank errors are
not replaced by reshape or forced channel normalization.

Normal sigma default10 and256x256 RGB/luminance workloads are exact and usable.
Common512 image workload exceeds the conservative local ownership profile
and refuses before raw; schema/source maxima are not promised. This is not
a hard physical heap/kernel profile or a budget increase. Genuine host meta
tensor refusals and pack pre-raw sentinels prove ordering without allocation.

Source T==1 Resample unsqueeze/repeat cardinality error, empty index/stack,
multidimensional truth ambiguity, BF16 NumPy conversion error, float16
histogram overflow/NaNs and reference-last selection remain source-native
outcomes (the source comment says first-frame reuse, but code uses last).
No repair, finite clamp, precision cast, error smoothing or tolerance change.
Exact contiguous bits include NaNs; dtype/device/shape and scalar/list outer
types are separately checked.

## Reproducible evidence and boundaries

Python tests: `tests/test_ned_immactools.py`.
Browser: `node tests/ned_immac_browser.mjs`.
Canonical detached roots core f5e175a / overlay2aff983 / frontend60e1387;
worker/host bridge belongs to overlay2aff. No dirty provider adoption.
Use COMFY_CORE_ROOT explicitly, required Seatbelt, bytecode/cache disabled:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-many-oct8-author-provider \
NED_OVERLAY_ROOT=/Users/ben/comfy/ComfyUI_secure_nodes-many-oct8-owner-provider \
COMFY_SECURE_SANDBOX_MODE=required PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/Users/ben/comfy/ComfyUI-many-oct8-author-provider:/Users/ben/comfy/ComfyUI_secure_nodes-many-oct8-owner-provider/backend \
/Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -q --noconftest \
-c tests/ned_pytest.ini -p no:cacheprovider tests/test_ned_immactools.py
```

Unchanged final Python/browser bytes are run twice; manifest, pristine hashes,
permissions, exact diff/JSON/ZIP and two byte+mode reconstruction gates cover
all files. Logs and source/runtime hashes are frozen in the handoff.
Torch/NumPy/typing_extensions are provisioned, not installed by this lane.
Current pyi f800a871 (tested style composite, tensor re-admission/publication
already included), d.ts3ac9255 (tested additive composite) are copied only to
this new pack and their origins/hashes are recorded.

Native errors are deliberate evidence, not all-input functionality. No trained
model inference is needed for these tensor/forward algorithms; canonical
ModelPatcher fixtures attest identity only. CPU/Mac local tensor math and
actual local CloudExecutionBackend transport are tested, not Linux/Cloud
activation, GPU placement, sealed dependencies, hostile heap enforcement or
full deployment. No catalogue/count/shared edits/commit/push in owner lane.

Initial artifact generation refused upstream Python>=3.10 before pair
publication; V2 explicitly declares provisioned >=3.13,<3.14. Pristine is
unchanged. A diagnostic excerpt, not full stderr, is retained. --noconftest
isolates owned tests from upstream test bootstrap; no dependency install.

First expanded artifact gate retained467 positives/one harness failure:
the reconstruction fixture passed a pack root rather than required snapshot
parent to packpatch.apply. Only fixture layout was corrected; source/algorithm
assertions and byte/mode equality were not relaxed.
The second retained fixture failure found the API also validates slug/release
directory names; temporary paths now reproduce exact comfyui-immactools/
x223bc2f topology. Both native refusal diagnostics remain preserved.
