# Secure conversion: Redux Fine Tune

## Source and scope

Upstream: https://github.com/1038lab/ComfyUI-ReduxFineTune
Pin: `4d8ff9239bf7b86d62a9b3bc52745aeef229c18c`, release `x4d8ff92`.
The retained registry release 1.2.0 matches all ten immutable Git blob IDs and
a fresh verified-TLS codeload archive, SHA256
`6e8681ef4a00177f4b618e116dfd0a9f3655579c60be10d94e0982a77096f56c`.
Live HEAD was not substituted: its README differs. Capture preserves Git and
retained 0644 modes; codeload's 0664 file modes are recorded separately.
GPL3 LICENSE, README, update notes and publisher workflow remain byte-exact.
Root source version 1.1.0 versus project/release 1.2.0 discrepancy is preserved.
Historical retained queue priority is not modern trending or a download count.

## Exact node disposition proposal

| Exact backend ID | Disposition | Qualified evidence |
| --- | --- | --- |
| ClipVisionStyleLoader | supported | Proposed bounded Mac-local managed catalogue, crop, actual SafeTensors style parsing and typed output behavior; CLIP catalogue selection fixture returns an actual tiny canonical CPU encoder, not trained CLIP weights. Coordinator serial review required. |
| ReduxFineTune | supported | Proposed bounded local exact eleven fusion algorithms, both passes, native errors/dtypes, real canonical CPU style kernels, required guests and opaque metadata preservation. Not trained or device-profile certification. |
| ReduxFineTuneAdvanced | supported | Proposed bounded local exact resolution/regions/crop/mask/prompt/noise/SUPER math and canonical CPU vision+style controls; native nonsquare StyleAdapter failure remains. Coordinator serial review required. |

Census: three Python exports, one frontend extension, zero routes and zero
JS-only graph definitions. One extension affects the three owned IDs and the
source's external `ClipVision` appearance target; that is not a fourth export.
No partial pack count follows from draft coverage or these recommendations.

## Backend algorithms and typed boundary

All eleven fusion modes stay pack-side: Mix, Enhance, Sharpen, AdaIN, Residual,
Max, Min, Random, FrequencyMix, Multiply and AttnBias, in source order. Source
defaults/options/categories/display names, outputs and loader IMAGE-list output
are retained. Loader weight widgets use closed `/secure-nodes/models/clip_vision`
and `/secure-nodes/models/style_models` catalogues instead of host paths.
Style loading is SafeTensors-only; source arbitrary weight formats are not
restored. The public loader rejects >512MiB encoded input before its parser.

SDK_REFS is enabled on all three nodes. Basic/advanced declare raw+inspect;
loader adds models. Raw reads/publishes dense owned tensor buffers only.
Public style features return unflattened tensors; all flattening, grid resize,
FFT, unbiased standard deviations, fusion, prompt cubing/repetition and SUPER
boost/order remain source equations. No whole model, vision Output or
conditioning metadata is materialized in the guest. Public embedding handles
select only tensors; `replace_embeddings` shallow-copies each host row's
metadata, retaining identical pooled/control/HookGroup/opaque/cyclic objects.
Style/vision/image passthrough identities remain typed host references.

Exact built-in CONDITIONING lists and tuples are admitted through the published
bounded row-count descriptor, without row/metadata traversal. Both source-valid
containers are exercised in fresh required guests and the production outer
executor. Subclass containers remain opaque. Malformed IMAGE ranks outside BHWC
are refused; this is not a claim of all malformed V1 parity.

The basic second pass recomputes native features and uses the first pass's text
mean. Advanced performs two native encodes normally and three with SUPER,
including the final returned vision Output. Retry count/crop flag and native
rethrow are retained. Mask-area crops use inclusive maxima in advanced;
loader crops retain exclusive maxima and threshold 0.05, including singleton
empty crop/empty-mask center fallback. Advanced returns original IMAGE; its
mask-area result is the source-cropped mask pixels, whereas un-cropped masks
retain identity. A cropped guest buffer is independently published: V1 host
input-view storage aliasing is not restored. No mutation of graph inputs.

## Native defects and precision

Source empty-conditioning cleanup raises UnboundLocalError in basic/advanced;
it is not silently repaired. Eight-token StyleAdapter output works in basic
but is nonsquare in advanced and retains the native reshape failure. No forced
square/padding/family guess. Zero feature resolution/native channel, shape,
NumPy bfloat16-mask and CPU half-adapter errors remain separately tested.
AdaIN singleton unbiased std produces NaN; zero/negative AttnBias produces
-inf/NaN. FrequencyMix intentionally converts to float32 and retains FFT
phase/magnitude/quantization math; no finite normalization or relaxed tolerance.

## Frontend axis

Frontend converted first through public defs.extend/onCreated and NodeHandle
setColor/setBgColor/setSize. Source colors #222e40/#364254 and width340 are
preserved, with existing height or missing-size height80. V2 mutation occurs
after graph registration rather than legacy constructor timing. Host intrinsic
minimum-size policy remains authoritative. Pinned controls and actual Chromium
opaque iframe/worker bridge test all four targets, foreign-node exclusion,
reconstruction, isolation, removal and host cleanup. The production bridge uses
typed graph-handle fixtures, not an assertion of full app or Cloud rendering.

## Workload and ownership bounds

Guest publication bound128MiB; projected simultaneous ownership256MiB;
cumulative fusion work128,000,000 selected elements. Rows are capped4096.
Public shape description precedes buffer import, using a conservative16-byte
dtype upper estimate; actual dense buffer bytes refine the estimate afterward.
Snapshots, image/mask crop/resizes and nonzero/NumPy coordinates, clone,
resolution-expanded feature fields/reorder, retained rows,
SUPER repetition, FFT float32/complex64 fields, cats and transport copies enter
preflight. Schema maxima can exceed this profile and fail closed. Normal
default options are observed with actual tiny canonical CPU architectures;
canonical4096-wide/729-token default projection is analytically admitted for
single-pass Mix, not a learned-weight/hardware claim. Large SUPER/resolution/
FrequencyMix combinations may be outside the profile; no cap is raised.

Pack raw feature snapshots are explicitly deleted between passes. The typed
host feature operation separately admits canonical ReduxImageEncoder
and StyleAdapter with dense rank32 inputs/output512MiB, conservative resident,
cast and intermediate1GiB plan and128G multiply/add work before inference.
Neither this plan nor pack preflight proves a hard physical heap/kernel quota.
Allocation, device/offload, unsealed packaging and deployment remain separate
host workload requirements. No unsupported module/device escape.

## RNG, cache and persistence disposition

No authored persistent state exists. Options are workflow inputs. Original
global unseeded rand/randn becomes one invocation-local generator per device,
with exact controlled seeded draw order and the same distributions. Ambient
cross-node RNG continuation and source GPU cache-empty effects are intentionally
not preserved. Native lru caches (16/32/64/8) are replaced by render/execution
local computation: no tensor identity, stale mutated-mask cache or device
allocation survives a fresh execution. Original cache-staleness controls are
retained. There is no durable edited-data/default/KV substitution or claim of
Cloud state backing. Two freshly reconstructed roots/PIDs preserve input-driven
behavior and isolate transient state.

## Evidence and dependencies

Owned `tests/test_ned_redux_conversion.py` compares literal pristine AST
controls and registered V2 behavior, all modes/precision/passes, schema/order,
native errors, crop/alias/RNG/cache/resource/capability boundaries, two fresh
required Seatbelt roots and actual production outer execution. Synthetic
full64,503,808-parameter Redux SafeTensors exercises the actual safe parser and
canonical style loader. Tiny actual canonical SigLIP/Redux/StyleAdapter CPU
kernels are distinct from CLIP-loader recording fixtures and learned inference.
No external weights were downloaded. Python3.13, managed Torch2.13.0 and
NumPy2.4.6 are pinned, not installed at execution.

Public Python artifact SHA256
`f800a8711e554fe4221d58123cff2e30f48da4ea56499cca5ee35273d7a3b0d7`;
composite frontend artifact
`3ac9255af06288ef33356403debf2ff57fd5cbff0cf8009fa305d2c1704324c9`.
Origins and immutable API packets are in source-provenance.json. Initial
tuple-descriptor refusal and its former consumer test are preserved separately;
final gates consume the published exact-list/tuple descriptor successor without
changing public declarations or exporting metadata. Initial
frontend readiness/fixture errors, test async-generator result conversion,
wire IndexError row-count discovery, incomplete vision Output fixture and
misidentified geometry-versus-inference refusal are retained in unique logs;
no source equation/tolerance change followed those diagnostics.

Final exact commands/results, stable runtime source identities, byte/mode
inventories, two pristine→V2/ZIP roundtrips and all log hashes are bound by the
separate frozen handoff. No learned/GPU/Linux/Cloud/sealed deployment or host
non-default dtype/device equivalence is certified; no catalogue/count/commit/
push mutation is performed in this lane.
