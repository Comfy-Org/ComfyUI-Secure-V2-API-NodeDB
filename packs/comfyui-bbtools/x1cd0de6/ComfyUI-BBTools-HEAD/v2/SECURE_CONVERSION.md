<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-bbtools

## Provenance

Upstream https://github.com/bbaudio-2025/ComfyUI-BBTools at exact Git commit `1cd0de69099bde98df3c46f817409f75b259a196`, release `x1cd0de6`. Complete retained registry release0.0.2 archive SHA `fa5d65ae73d482ea5942672255f1c980042762b4e784154dadd7bd92c0b5f70a` matches all six paths and Git blobs of that entire immutable tree, including hidden workflow. This is a verified archive-to-Git correspondence, not an archive hash labelled commit or substitution with a newer version. Read-only commit/tag/tree probes and source SHA256s are recorded in `source-provenance.json` and external correspondence evidence. Pristine CRLF Python bytes remain unchanged.

Queue49 historical downloads796 is a retained corpus measure, not current trending. Actual GPLv3 LICENSE is preserved; source pyproject refers to missing LICENSE.txt. V2 packaging refers to the existing LICENSE without inventing a grant or resolving all distribution duties.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `EmptyImageBBTools` | supported | yes | bounded CPU RGB/MASK/RGBA allocation | Source defaults/color math/three typed output slots, native allocation controls and real guest+outer MASK. |
| `ReplaceColorBBTools` | supported | yes | bounded native Pillow pixel transform | Strict threshold, quantization/squeeze/native mode behavior, exact source controls and guest+outer. |
| `VideosConcatWithCrossFadeBBTools` | supported | yes | exact positive math plus approved zero repair | Canonical public resize, frame order/dtypes, original zero-cat failure, explicit concat0 control and guest+outer. |
| `VideosConcatWithCrossFadeLoopbackBBTools` | supported | yes | exact positive math plus approved empty-transition repair | Both positive transitions/rotation, asymmetric0/N,N/0,0/0, defaults, source failures and guest+outer. |

Four complete registered Python algorithms in this admitted local scope; no partial-pack count. These are bounded behavior proposals for coordinator review, not Linux/cloud/runtime deployment or catalogue promotion.

## Frontend and ancillary census

Zero frontend extensions, JS-only graph node definitions, routes, mutable files, network calls, subprocesses, weights or learned inference. No missing frontend conversion. Preserve all six pristine files; full V2 sibling includes immutable README/LICENSE/workflow resources and unique tests.

## Exact computation and deliberate repairs

Seven pure source helpers retain normalized AST-exact bodies. EmptyImage retains CPU float32 channel values RGB color/255, alpha directly in both RGBA and MASK; output order RGB,MASK,RGBA. Source dimensions/schema defaults/maxima/steps are not narrowed in the socket schema, while supported execution bounds are explicit below.

ReplaceColor preserves clip(255*image.cpu().numpy().squeeze(),0,255)->uint8 Pillow construction, RGB Euclidean distance divided by255*sqrt(3), strict less-than threshold, replacement tuple and original Pillow mode, and per-frame float32/255 with source squeeze/stack behavior. Threshold0 replaces no colors. Do not silently fix source alpha/channel/singleton/BF16 behavior.

Videos retain source two-input order, last/head transition slices and alpha(i+1)/(N+1), multiplication/addition order, native dtype promotion, loopback rotation and length/sum failures. Different canvases use the existing public ImageRef.resize(width,height,method='bilinear',crop='center'), which invokes canonical common_upscale just as source. Bounded pack-side blending uses explicitly permissioned raw pixels and public TensorRef.from_value for typed guest-wire publication; no private constructors or host objects.

Coordinator approved a narrow default-usability repair after preserving original source controls: plain count0 concatenates the two input batches after existing source shape/length checks. Loopback omits only a zero-length transition;0/0 concatenates, N/0 keeps the first transition,0/N retains the second wrap transition before central frames. Positive branches remain unchanged. This admitted Torch build raises native **ValueError** on torch.cat([]), not RuntimeError; historical initial fixture error and original zero source outcomes remain evidence, not called successful source behavior. Zero-frame repair does not change sockets/category/display/return types. Plain empty input retains its first-frame IndexError; loopback0/0 has no first-frame check in source and can concatenate an empty admitted batch.

## Bounds and native limitations

Preflight dense4D BHWC, batch<=64, spatial dimensions<=4096, channels<=8 and aggregate logical/backing input<=64MiB. Video projected whole concatenated output<=64MiB and conservative input+resized+4*output<=192MiB precede resize/blending. ReplaceColor output<=64MiB and input+320*pixel-count<=192MiB bound its Python pixel-list workload before Pillow. EmptyImage sums all three output buffers under64MiB and estimated peak under192MiB before allocation. Declared defaults512x512 are admitted and exercised. Scalars are finite nonboolean numeric values/integers with explicit direct-call bounds; malformed oversized workloads fail closed without changing UI maxima.

These are admitted workload/preallocation estimates, not hard physical memory/parser/profile guarantees or source maxima. Source BF16-to-NumPy errors, channel-mode errors, singleton squeeze behavior, negative native allocations/counts and ordinary length failures remain controls. Typed image resize has its existing closed channel/nonempty admission; arbitrary malformed ranks/channels/zero-size mismatched canvases are not claimed legacy parity. No global/default-device/dtype mutation; local CPU evidence does not attest accelerator placement or --gpu-only behavior.

## Evidence and repeatable verification

`tests/test_ned_bbtools_conversion.py` covers exact actual root census/schema options/display names/output order/helper AST identity, color/dimension/default cases, five video dtypes, Pillow native modes/quantization/threshold boundaries, positive loopback combinations and canvas resize, asymmetric repaired zeros, input identity, noncontiguous/channel controls, negative/empty cases and backing/projected allocation refusal.

Two freshly reconstructed V2 trees execute all four entries in distinct required macOS Seatbelt guest PIDs through production outer IMAGE/MASK boundaries. Default empty image512, default zero transitions, source-positive transitions, asymmetric repairs, five video dtypes, native BF16 Pillow/length failures, budget refusal and recovery are exercised. Test-only publisher proves no-raw denial and is not a registered production node. In-process resize doubles are identified separately; real guest also invokes the actual broker.

Exact secure manifest/proxy registrations, current used stub hashes, immutable resources/pristine identity/cache hygiene, two pristine-to-V2 normal/ZIP byte roundtrips and wrong-pristine refusal are part of the whole focused gate. Selected preliminary totals and retained fixture failures are not whole passes. Final observed matching logs/handoff are external artifacts so they do not self-modify the exact pair.

Run from `v2/tests`:

```sh
PYTHONDONTWRITEBYTECODE=1 COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONPATH=/Users/ben/comfy/ComfyUI-secure-nodes:/Users/ben/comfy/ComfyUI_secure_nodes/backend /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -p no:cacheprovider test_ned_bbtools_conversion.py -q
```

Historical failures: missing generated manifest before proxy fixture; native zero error-class assumption corrected to measured ValueError; raw tensor returned by typed video class corrected to public tensor publication. Exact pixel/frame/error controls are not weakened. No shared implementation/stub generator or schema authority change.

## Dependencies and state disposition

Python>=3.13,<3.14 with managed Torch/NumPy/Pillow. Canonical core explicitly `/Users/ben/comfy/ComfyUI-secure-nodes`. Pyi origin `many-oct7-font-catalogue-comfy-api.pyi` SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`; checked composite d.ts SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Unused declarations do not grant capabilities.

No durable state: only explicit input buffers/options and per-call intermediate arrays/Pillow objects. Fresh renders recreate the pack/guest and retain deterministic computation; no KV/cloud persistence requirement is inferred. Runtime provisioning, Linux/cloud deployment, accelerator/device parity and hard profile enforcement remain separate unproved deployment scope. No shared/catalogue write, commit/push or daily count in this lane.
