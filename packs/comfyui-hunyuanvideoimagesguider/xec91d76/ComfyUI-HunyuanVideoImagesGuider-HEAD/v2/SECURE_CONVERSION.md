# Secure Nodes V2 conversion

## Identity and scope

Pinned upstream: https://github.com/benjiyaya/ComfyUI-HunyuanVideoImagesGuider at `ec91d767ee2ce82a67d4a498eb036f193100d261`. Complete pristine capture: 11 files, exact Git blob bytes and modes independently checked. See `source-provenance.json`. Retained queue position 176; downloads unavailable/zero, not a current popularity or trending claim.

Actual pinned entrypoint census: 1 Python registration, 0 frontend extensions, 0 JS-only nodes, 0 routes. V2 has the same exact ID, ordered schema, defaults, category, and one IMAGE output.

| Node ID | Disposition | Evidence and bounded scope |
| --- | --- | --- |
| Hunyuan Video Image To Guider | supported | Pack-side source pixel algorithm retained; differential motion/zoom/resize/crop/dtype controls, required confined guests and actual outer IMAGE boundary. CPU-local workload described below, not GPU/cloud certification. |

## Backend behavior and deliberate boundaries

The source algorithm is AST-exact after removing two unused ambient imports (`nodes`, `folder_paths`). The V3 wrapper explicitly uses public value-mode raw tensor compute (`SDK_REFS=False`, `raw` permission), with no model, filesystem, network, process, device-selection or private-constructor authority.

Preserved details: source processes only input batch index 0, returns `frame_num` frames rather than multiplying by input batch, truncates keep-ratio height, uses bilinear resize/zoom, optional center square crop, and creates CPU default-floating canvases. Partial wrap copies leave black remainder regions; the README's seamless-tiling description is not substituted for actual pixels. Empty/malformed native tensor branches remain errors within admitted bounds; no silent clamp, minimum-size repair, or batch expansion.

Admission preflights the complete input and projected resize/output work before source execution: dense BHWC; batch <=64; axes <=4096; channels 1..4; input logical bytes <=32 MiB; finite closed motion/zoom controls; original frame/target ranges; projected output accounting <=64 MiB; conservative aggregate workspace estimate <=192 MiB. Default connected 512x512 RGB, 10 frames, zero motion/zoom executes and is tested in fresh confined guests. Larger source-valid workloads can be refused deliberately. The estimate is pack-side allocation preflight, not proof of a host hard RSS ceiling or deployment compute profile.

Local controls cover fp16/fp32/fp64/BF16 and trusted local float64 default dtype. Confined guest results use its existing CPU default dtype. GPU input continuation, host intermediate-device placement, arbitrary host default-dtype inheritance, Linux sandbox, cloud deployment and production workload scheduling are not certified.

## Frontend and persistence disposition

Frontend axis: not applicable; no JavaScript or mounted UI in the pinned pack. Ordinary schema widgets are host-owned.

No authored state, route, file cache or cross-render mutable global is used. Image/frame work is render-local; parameters remain ordinary workflow inputs. Two independently recreated pack roots and guest PIDs prove identical execution, denial recovery and no required pack-local durable state. No cloud storage service is needed or claimed.

## Dependencies, resources and provenance

Python 3.13 runtime declaration; existing admitted Torch tensor/interpolation dependency, no runtime install or downloaded model/code. MIT LICENSE retained byte-exact, as are all bundled images and workflow resources. Pristine resource hashes, upstream commit and complete tree correspondence are recorded in `source-provenance.json`; source snapshots are not regenerated from live HEAD.

Tested public composite declarations are copied byte-for-byte:
- `comfy-api.pyi`: SHA-256 `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`, coordinator artifact `many-oct7-font-catalogue-comfy-api.pyi`.
- `comfy-api.d.ts`: SHA-256 `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`, coordinator artifact `many-oct6-model-catalogue-checked-comfy-api.d.ts`.

## Verification and qualifications

Unique suite: `v2/tests/test_amy_imagesguider_conversion.py`. Run with explicit `COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes`, `PYTHONDONTWRITEBYTECODE=1`, Python `-B`, pytest `-c pytest.ini -p no:cacheprovider`.

Tests cover exact census/schema/proxy, normalized algorithm AST, 504 exact-pixel option/dtype combinations, input immutability, first-batch/black-remainder behavior, native empty/error paths, noncontiguous input, declared default usability, bounded malformed and projected workloads, two required Seatbelt guests and production outer IMAGE shape/dtype/pixels, absent-raw denial/recovery, resources/license/stub hashes/cache hygiene, and byte-exact stored pair plus ZIP and wrong-pristine refusal. No model double or trained model inference is involved in this pure tensor algorithm.

The initial 526-pass/1-failure run reached a missing manifest during normal artifact generation; that log is preserved separately, not labelled a complete gate. Final unchanged-byte gate results are recorded in the external AMY handoff and observed logs, not inferred from registration or this report. The matching pair reconstructs the entire V2 tree; no backend/frontend legacy bridge is used.

Release recommendation is bounded local conversion support, subject to coordinator artifact review and serial catalogue integration. Passing local tests is not automatic cloud, Linux, GPU or end-user workflow certification.
