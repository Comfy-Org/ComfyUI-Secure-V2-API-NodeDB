<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-emptyhunyuanlatent

## Provenance

Upstream https://github.com/ShmuelRonen/ComfyUI-EmptyHunyuanLatent, exact Git commit `3930b0f322cbc68bdb23cd0fa52d6ea3e84f635a`, release `x3930b0f`. All eight paths/blobs in the complete retained archive matched the immutable Git tree; `source-provenance.json` records exact SHA-256s and actual loader census. Current central URL/exact-ID exclusion was negative before capture. No live substitution, archive-as-commit or popularity/trending claim; retained download field is zero/unavailable.

README declares MIT, but the complete source has no LICENSE file despite its pyproject reference to LICENSE. Both original facts are preserved; no missing license file or distribution permission is invented.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `EmptyHunyuanLatentForImage` | supported | yes | bounded local CPU behavior; approved allocation normalization | All42 ordered choices, exact C4/T1 five-dimensional zeros/defaults/rounding, actual fresh guest/outer LATENT. |
| `EmptyHunyuanLatentForVideo` | supported | yes | bounded local CPU behavior; approved allocation normalization | All42 choices/default25, C16 temporal floor boundaries, batch/empty axes, actual fresh guest/outer LATENT. |

Two Python nodes, zero pending implementations/rejected intents within the explicitly reviewed local CPU scope. No count/deployment/user verification promotion by this report.

## Frontend, ancillary and resource census

Zero frontend extensions, JS-only definitions and routes. Complete original workflows, README, pyproject and publishing metadata are captured; workflow examples are source resources, not executed downstream model certifications. No weights, model objects, services, credentials, file/network/process behavior or editable durable data. No legacy bridge.

## Algorithm, allocation policy and authority

Public value-mode `io.ComfyNode`, declared `raw`, pack-side Torch tensor construction only. All42 resolution choices/order, ID/category/input attributes, source batch default1, video length default25/step4/max16384 and one LATENT output remain exact. Parse first space-delimited dimensions, floor each to16, then spatial cells divide by8. Image layout remains `[B,4,1,H/8,W/8]`; video remains `[B,16,((length-1)//4)+1,H/8,W/8]`. No silent change to the source's image-channel4/video-channel16 mismatch or README's inconsistent frame claims. Outputs remain a dict with only samples.

Coordinator explicitly approved guest-local CPU zero allocation followed by existing typed LATENT publication as a deliberate allocation/lifetime normalization. The original host intermediate_device call is not recovered; closed16384 replaces the equivalent current core constant. Source math AST is normalized-exact except those declared host bindings/imports. Default CPU source/draft shape,dtype,device and all zero values are compared exactly. Source Torch default dtype is not changed by pack code; trusted in-process float64 controls are retained. A fresh guest has its own default dtype, so custom host-default-dtype continuation and `--gpu-only`/intermediate-device GPU placement are unproved deployment scope, not claimed native GPU parity. No new5D shared constructor, host module or device escape.

## Workload and native boundaries

Bounded resolution text1024UTF8 bytes; strict integer batch0..4096 and video length0..16384 (zero direct-call cases preserve empty source tensors). Projected floored dimensions at most16384; negative dimensions refuse before allocation. Before Torch construction, whole5D sample size is estimated at eight bytes per cell, conservatively covering admitted float32/default and float64 controls. Output projection at most64MiB, with three copies at most192MiB for construction/publication/transport. This limits complete batch/channels/temporal/spatial allocation, not merely nominal resolution. These are explicit supported workloads, not upstream maxima, hard physical memory/host quota enforcement or accelerator grants. Output64MiB accounting is conservative: default float32 actual buffers may be smaller.

Native malformed string parse failures retain their error types; floor16 zero dimensions and length0 frames remain allowed. Negative/bool/noninteger/oversized batch or length, oversized text and large complete sample workloads deliberately fail closed before source allocation. No unrestricted malformed-input parity claim. A dimension16385 correctly floors to16384 and is not rejected solely for its pre-floor size; the bound applies to projected dimensions.

## Verification

`tests/test_ned_hunyuanempty_conversion.py` proves actual two-node schema/proxy, all42 choices per ID, exact zeros/5D shapes,42 temporal/batch controls, floor16/empty axes/native parse controls, normalized source math AST, trusted local float64/default policy, full allocation bound before Torch work, complete resources/source/stub/cache identity, two reconstructed pack filesystems and required fresh raw guests, all84 node/choice combinations in each real production outer execution, native errors, budgets, raw refusal/recovery and exact pair+ZIP reconstruction twice/wrong-pristine refusal.

Without raw, registered value-mode output tensors are not published handles and the guest wire refuses them before any tensor buffer can be marshalled; an explicit public raw publisher is separately denied in each disposable guest. This test-only probe is not a third released node. Initial RED fixtures are retained:16385 pre-floor dimension was wrongly expected to fail; broad import scan falsely matched relative nodes_hunyuan; no-raw value-mode wire refusal differs from explicit permission error. Tests were corrected to discriminate the actual boundaries without weakening shape/value assertions or allocation limits.

Run from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_hunyuanempty_conversion.py -q
```

The external frozen handoff records matching final-byte full results and hashed logs. No actual Hunyuan trained-model sampling or GPU execution occurs.

## Runtime, integrity and persistence

Python `>=3.13,<3.14`, observed local3.13/Torch2.13.0. No runtime installations/downloads. Retained pyproject license reference remains, missing-file caveat explicit. Composite origins are coordinator-tested `many-oct7-font-catalogue-comfy-api.pyi` SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada` and checked frontend SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`; unused APIs confer no grants. No shared/catalog edit.

No durable state: explicit scalar controls and deterministic empty tensors only. Fresh render pack filesystems and guest PIDs reproduce outputs; no pack-file/global/Cloud KV continuity needed. Guest allocations do not mutate source inputs or host device/global dtype policy.

Required macOS sandbox/CPU and production outer LATENT transport proved, not Linux/Cloud provisioning, GPU/intermediate placement, custom host-default dtype continuation, full downstream Hunyuan model compatibility or user verification. Those deployment/inference/provenance boundaries are separate from tested local zero-tensor behavior. Coordinator owns integration/count/release review.
