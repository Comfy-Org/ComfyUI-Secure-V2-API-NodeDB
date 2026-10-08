<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-apply-style-model-adjust

## Provenance

https://github.com/ShmuelRonen/ComfyUI-Apply_Style_Model_Adjust at exact Git `21d3b35bfb5d7922b0b2656a1d4626ecd7de5121`, release `x21d3b35`. Six complete retained paths/Git blobs and modes verified with TLS, full README/examples/source preserved, no live substitution. `source-provenance.json` records SHA-256s and actual root census. Queue96 downloads0/unavailable is not trending or verified popularity.

Complete source has no LICENSE. Local conversion is authorized; publication permission remains a separate unresolved provenance requirement.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `ApplyStyleModelAdjust` | supported | yes | bounded local typed math and tiny canonical model behavior | Four dtypes/eight strengths/native controls, real tiny Redux, canonical ControlNet identity in zero-capability guests and outer CONDITIONING. |

One Python node, no rejected/pending implementations in the bounded tested local scope. No count or release promotion by this lane.

## Frontend and ancillary census

Zero frontend extensions/routes/JS-only nodes. Exact source ID/schema/display/category and one CONDITIONING output. No durable state, host module/model/device recovery, network, secrets, weight download/runtime installs, callbacks, side effects or legacy bridge.

## Behavior and resolved API boundary

Source style get_cond is flattened(0,1) and unsqueezed(0). Original conditioning embeddings scale by `3.0-2.0*strength`, style embeddings by `strength*0.7`, concatenate on sequence axis1 and shallow-copy metadata. These coefficients remain pack-side. Public StyleModelRef.apply owns canonical get_cond/flatten/style multiply/cat; public `await conditioning.scale_embeddings(3.0-2.0*strength)` scales only embeddings while shallow-copying host metadata. No raw/inspect/model-management grant is needed. Existing pooled tensors and actual canonical ControlNet objects retain exact identity.

Zero strength still triples text and appends zero style tokens, not identity. Empty rows and empty/multi-batch style tokens preserve source behavior. `nodes.py` remains byte-exact source/schema oracle. Host inputs and global RNG remain unchanged.

## Historical RED and successor

The initial raw conditioning draft matched data-only math but CondRef.value could not export legitimate ControlBase/ControlNet metadata. Both RED diagnostics and the complete raw predecessor V2 are preserved externally. No metadata deletion, private cast or host-object export was introduced.

The coordinator published the generalized typed scale operation. The unchanged original ControlNet identity/math assertions then passed in the real guest; the obsolete final no-raw-refusal expectation became DID NOT RAISE, retained in a transition log. Successor node dispatches have zero capabilities; a disposable raw-value probe verifies that raw is still denied and normal execution recovers. No math/identity/tolerance oracle was weakened.

Shared operation evidence `outputs/many-oct7-cond-scale-evidence.json` SHA `e88a4c4f5089b0badeb561fb27f23cfaa58a7ed345c748535bf94e22dbfaae29`; frozen SDK after SHA `8bcd1654a3e79a759f0a95c760fba1ad32f6af88ae4917572bffa77d33776457`. Root127x2 checks are separate dependency evidence, not added to pack totals.

## Workload and proof boundary

Finite nonboolean numeric strength with absolute direct limit1000000, unchanged source UI0..1/default1/step.01. Shared scale validates at most4096 closed tensor+dict rows and total16,777,216 embedding elements BEFORE multiplying. These are logical bounds, not physical RAM/VRAM/profile enforcement or full-width model allocation guarantees. No fabricated device/shape budget is imposed pack-side.

Exact CPU controls use FP16/FP32/FP64/BF16, strengths0/.1/.25/.5/.7/1/-2/2, rows0/1/3, style batch/token order and empty branches, metadata scalar/tensor/control values, input/RNG immutability and native concat mismatch. Canonical ReduxImageEncoder has actual executable Torch modules with deterministic synthetic tiny weights; not a recording-model mock, but NOT trained/default-width vision/style inference or accelerator placement proof.

## Verification

`tests/test_ned_styleadjust_conversion.py` covers exact behavior/schema/proxy/census, malformed/pre-work refusals, manifests/current consumed stubs/resources/pristine/cache hygiene, two fresh required macOS Seatbelt guest PIDs with recreated V2 filesystems, production outer CONDITIONING/ControlNet identity, zero-capability dispatch plus raw denial/recovery, stored patch+ZIP two byte-exact pristine-to-V2 reconstructions and wrong-source refusal.

Run from `v2/tests`:

```sh
PYTHONDONTWRITEBYTECODE=1 COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONPATH=/Users/ben/comfy/ComfyUI-secure-nodes:/Users/ben/comfy/ComfyUI_secure_nodes/backend /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -p no:cacheprovider test_ned_styleadjust_conversion.py -q
```

Frozen external handoff records matching unchanged-byte whole runs/hashed logs. Historical104 narrowed pass, both metadata REDs, transition and2PASS/104deselected scoped successor remain separate from whole result.

## Runtime and persistence disposition

Python>=3.13,<3.14, managed Torch2.13.0. Tested public composite pyi origin `many-oct7-cond-scale-comfy-api.pyi` SHA `66f96a76ea39af855af448d1e6b77ae43d20f09ada9aefd221ba9edef9c8a553`; checked d.ts SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Unused declarations grant no authority.

No durable state: explicit typed input/output refs, no authored pack files/cache/global state. Fresh executions retain math and metadata identity; no cloud KV continuity needed. Full trained/default-width checkpoints, GPU/intermediate-device semantics, hard model/resource-profile enforcement, Linux/cloud provisioning, publication permission and user-workflow validation remain unproved deployment/provenance scope. Coordinator owns integration and counts.
