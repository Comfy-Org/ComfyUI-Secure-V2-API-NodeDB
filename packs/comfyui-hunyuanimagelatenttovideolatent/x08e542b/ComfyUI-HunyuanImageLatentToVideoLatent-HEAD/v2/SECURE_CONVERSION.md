<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-hunyuanimagelatenttovideolatent

## Provenance and census

Upstream https://github.com/philiprodriguez/ComfyUI-HunyuanImageLatentToVideoLatent, exact Git commit `08e542b0da1e422f3c32a1fd73b0a0c772539ff3`, release `x08e542b`. Complete four-path retained tree matches immutable Git blobs/paths/modes; MIT LICENSE is preserved. Root source census, schemas, hashes, dependencies and negative central URL/exact-ID screen are in `source-provenance.json`. No live substitution or trending/download rank claim; retained popularity is unavailable/zero.

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `HunyuanImageLatentToVideoLatent` | supported | yes | bounded CPU-local tensor behavior | Byte-exact source temporal block concatenation/logistic masks, schema/default49, actual fresh raw guest/production outer LATENT and refusal/recovery controls. |

One Python node, zero frontend extensions, JS-only definitions or routes; zero pending/rejected implementations within this tested local scope. Coordinator integration and user verification remain separate from this proposal. No model weights, host modules, service, runtime install or device escape is used.

## Behavior and authority

Public io.ComfyNode value-mode with declared `raw` admits tensor computation pack-side. `source_algorithm.py` is byte-exact pristine root code. Preserve all six input schemas/defaults/tooltips, display/category/description and one LATENT output. Copies are `((length-1)//4)+1`; concatenate the entire original samples block on time axis2, not individual frame repetition or first-frame substitution. Return a new samples dictionary, dropping source-ignored metadata/old noise_mask exactly as upstream.

When enabled, the logistic noise curve, draw order and printed intensities are unchanged. Source torch.ones is CPU default floating dtype regardless of sample dtype: do not cast mask to sampled FP16/BF16/integer dtype. Trusted in-process float64-default controls and fresh default-float32 guest controls are tested separately. No ambient RNG or state is involved. Host GPU placement and cross-process host-default-dtype continuation are not inferred from CPU-local fidelity.

Native length0 empty concatenation remains an error. An initially incorrect host RuntimeError matcher is retained as RED evidence. A disposable test-only oracle runs the byte-exact pristine algorithm in each of two actual confined guests: pristine and converted both report `ValueError: torch.cat(): expected a non-empty list of Tensors` on Torch2.13.0. Host pristine/converted in-process controls both retain RuntimeError. The test now discriminates exact same-guest class/message; no production exception coercion, pixel/tolerance/dtype change or invented success. Oracle is not registered in the released manifest.

## Supported workload

Admit dense five-dimensional samples, batch<=64, remaining axes<=4096 and source-declared finite numeric controls. Length0 is retained for native-error testing; negative/noninteger/bool/over40000 refuse. Bound the entire ignored-metadata tree as well as samples: depth8,4096 nodes,64KiB string leaves, plain string-keyed containers and dense tensors,32MiB aggregate logical input. Account all temporal samples, all default-floating masks, retained chunks and final concatenation before algorithm entry:64MiB output and192MiB projected aggregate workspace. Bounds apply to empty/noncontiguous tensors and extreme copies; an expanded ignored tensor cannot bypass input accounting.

These are explicit supported workloads, not unrestricted upstream maxima, hard transport/parser/process physical enforcement or a compute-profile grant. Malformed arbitrary metadata/ranks are refused; unrestricted malformed-input parity is not claimed.

## Verification

`tests/test_ned_hunyuanconvert_conversion.py` compares source/converted across170 length/mask/dtype combinations,12 empty-axis/multiple-input-time cases, six curve extremes, noncontiguous blocks, exact metadata dropping/no mutation, local float64 default restoration, real default49 connected512-spatial latent, scalar admission and whole-input/output/workspace refusal before algorithm entry. Two fresh required Seatbelt guests reconstruct V2 and exercise the registered production outer LATENT for FP16/BF16/integer/default/empty/multiple-time cases, same-guest native oracle, budget errors, no-raw refusal and recovery. Every positive shape/dtype/device/value assertion is exact.

Manifest/proxy schema/census, complete pristine identity, MIT resources, byte-exact source algorithm, canonical stubs, interpreter cache hygiene, stored pair and ZIP pristine-to-V2 reconstruction twice and wrong-source refusal close the artifact gate. Matching final-byte observed runs and hashed logs are in the external frozen handoff, not inferred from parameter-count totals.

Run from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_hunyuanconvert_conversion.py -q
```

## Runtime and persistence

Observed Python3.13/Torch2.13.0. Tested composite pyi origin `many-oct7-font-catalogue-comfy-api.pyi` SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`; checked d.ts SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. No unused shared declaration churn.

No durable state: explicit LATENT/numeric inputs and reconstructed guest/filesystem identity; original inputs remain unchanged. No mutable files, caches or Cloud KV are needed. Linux/cloud provisioning, GPU/intermediate-device behavior, host-default-dtype continuation, trained downstream video inference and hard physical memory/profile enforcement remain unproved deployment scope. This is not full-model or user-workflow certification.
