<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-cs-customnodes

## Provenance

Upstream https://github.com/claussteinmassl/ComfyUI-CS-CustomNodes, exact Git commit `87cea44c877f203ae5de0782bc6f42c7ec76fd1b`, release `x87cea44`. All three paths and blobs in the retained source match the complete immutable Git tree; `source-provenance.json` records SHA-256s, actual import census and current central duplicate exclusion. No live substitution, archive-as-commit or current popularity claim. The retained ranking field is zero/unavailable.

**NO LICENSE:** the complete pinned tree contains no license file or explicit grant. This explicitly authorized local conversion does not establish any later publication/distribution permission. No license is invented and no security rejection is inferred from its absence.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `CS Transform` | supported | yes | bounded tensor behavior; coordinator review, separate distribution permission caveat | Byte-exact original OpenCV algorithm, image/mask exact pixels, optional outputs, default canvas, real confined guests/outer, preallocation refusal. |

One Python node, zero pending implementations or rejected intents within the documented workload. This is a local bounded conversion declaration, not catalogue integration, user verification or deployment certification.

## Frontend and ancillary scope

No frontend extension, JS-only node or route exists in the complete source. Inputs are ordinary native widgets; no frontend shim or bridge is added. No model, weights, network, filesystem, subprocess or service behavior exists. Original display-name metadata is retained exactly, including its `CSTransform` key which differs from the registered `CS Transform` ID; it is not silently repaired.

## Algorithm and authority

The entire `nodes/transform.py` is byte-exact. Value-mode `io.ComfyNode` admission uses only public APIs with declared `raw`, keeping NumPy/OpenCV/Torch computation pack-side. No private constructors or ambient host object recovery. Original defaults, min/max, optional IMAGE/MASK/canvas, category, return names and two output slots are retained.

Three sequential OpenCV warps remain scale, rotation, translation; interpolation, border defaults, integer corner rounding, expansion centering, pivot offset, circle channel values and Torch/NumPy squeeze behavior are unchanged. A provided canvas determines dimensions but its pixels are not composited, exactly as upstream. The mask is transformed independently. Missing image/mask outputs remain None in their original positions. Small admitted malformed batch/shape/dtype inputs retain native errors; no batch repair or new shape semantics is inferred. Missing required controls fail admission rather than inventing defaults. The source's squeeze can produce unusual one-channel or singleton-axis shapes; tests preserve these outcomes/errors rather than claim conventional IMAGE normalization.

## Workload and bounds

Finite numeric controls must have the original declared bounds; booleans and integer controls are strict. Logical aggregate inputs are limited to32MiB and rank4. Before source canvas/warp allocation, the identical four-corner source calculation predicts each output size. Expanded dimensions exceeding10000 are refused. A192MiB conservative aggregate projection accounts for logical inputs plus eight copies of each target image/mask buffer (expansion, warp intermediates, tensor copy/publication and retained arrays). Both outputs count together. These are explicit supported workload limits, not upstream maxima, backend heap grants, or a hard guarantee on OpenCV/native process overhead/backing storage. Out-of-budget malformed inputs may be refused before their source-native error. Admitted default1024 RGBA+mask works and is pixel-exact; large nominal dimensions cannot bypass preflight.

## Verification

`tests/test_ned_cstransform_conversion.py` covers actual source/V2 registration, full schema and proxy, unchanged algorithm,80 parameter grids,120 seeded differentials, dtype/channel/squeeze/canvas precedence, optional branches, default1024, input identity, native errors, malformed controls, aggregate/dimension/input bounds before original allocation, two reconstructed pack filesystems and required fresh sandbox guests, actual production outer IMAGE/MASK pixels/order, guest refusal and recovery, manifest/source/stubs/cache hygiene, exact patch and ZIP reconstruction twice and wrong-pristine refusal before writes.

Without raw, value-mode inputs remain typed handles, not recoverable tensors, and the registered node refuses them. A separate test-only public tensor publisher is permission-denied in each disposable guest; that probe is not a second released node. Initial fixture RED logs are preserved: omitted manifest/runtime declaration, unwrapped tensor wire fixture, a malformed default canvas outside the workload budget, and the distinction between unresolved-handle refusal and explicit raw permission denial. No pixel tolerance or budget was relaxed.

Run from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_cstransform_conversion.py -q
```

The frozen external handoff records matching final-byte run results and hashes. Test totals are not hardware/deployment or full workflow certification.

## Dependencies and integrity

Python `>=3.13,<3.14`, local3.13; observed Torch2.13.0, NumPy2.4.6 and OpenCV5.0.0. Dependency declarations do not install or provision a Cloud profile. Existing macOS OpenCV/PyAV duplicate AVF class warnings are retained; these tests do not exercise video/device capture. Runtime has no model/download requirements. Complete source README/resources are retained.

Tested composite origins are the coordinator's frozen `many-oct7-font-catalogue-comfy-api.pyi` SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada` and checked frontend composite SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`; unused newer APIs do not imply grants. Shared files were not edited.

## Persistence and remaining boundaries

No durable state: every transform is determined by explicit workflow controls and tensor inputs. Fresh pack filesystems/PIDs preserve output and original inputs stay unchanged; no process globals, pack-local file or cloud KV is used.

Actual required macOS sandbox, CPU OpenCV and production outer outputs are proved. Linux/Cloud dependency provisioning, full downstream workflow/user verification and publication/distribution permission are not established. Native malformed-input parity is limited to admitted tested cases; bounds and no-raw refusal are deliberate secure adaptations. Coordinator owns final integration and release review.
