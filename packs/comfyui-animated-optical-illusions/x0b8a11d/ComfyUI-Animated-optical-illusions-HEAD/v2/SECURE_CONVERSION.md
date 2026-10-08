<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-animated-optical-illusions

## Provenance

Upstream https://github.com/ZHO-ZHO-ZHO/ComfyUI-Animated-optical-illusions, exact Git commit `0b8a11dca5d2bef97863cfe2aa073a172e6cd686`, release `x0b8a11d`. All four paths/blobs in the complete retained snapshot match the immutable Git tree. SHA-256s and actual root import census are recorded in `source-provenance.json`; current central URL/exact-ID exclusion was negative before materialization. No live-source substitution or archive-as-Git identity. Retained corpus popularity field is zero/unavailable; no current trending/high-download assertion. Original complete GPL3 license is retained, without independent distribution/legal certification.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `AOI_Processing_Zho` | supported | yes | bounded image-batch behavior; coordinator review | Byte-exact source, exact strip/frame order/quantization/alpha, native malformed cases, default512, actual confined guest and outer IMAGE/IMAGE, work refusal before source allocation. |

One Python node, zero pending implementations/rejected intents within admitted workloads. Declaration is not central integration, user verification or deployment certification.

## Frontend and ancillary census

Zero frontend extensions, JS-only nodes and routes. No model, weights, credentials, service, network, file or process behavior. Pillow font imports in the original are unused; no font catalogue or new resource authority is needed. No legacy bridge.

## Algorithm and authority

The entire original `Animated_optical_illusions_Zho.py`, including its CRLF bytes, remains unchanged. Public `io.ComfyNode` uses `SDK_REFS=False` and only declared `raw` for tensor-only computation. No private constructors, host objects, paths, device access or global mutation. IDs, display name, category, required images/width(default1,min1,max100), return names and two IMAGE outputs are preserved. The second output is an RGBA IMAGE called mask, not a MASK socket.

Source frame conversion remains clip(255*image) to uint8, including dtype-dependent quantization and squeeze. The original chunk selection and zip truncation remain exact: some incomplete frame groups drop trailing strips, not pad/resample. At three frames,13columns,width4, output is12columns with first frame63/255, second127/255 and third1; white first-frame mask stripes have alpha0 and black stripes alpha1. Native empty batches, unavailable strip groups and unsuitable shape/channel inputs retain their original admitted outcomes/errors. No batch/order/trailing-width or alpha repair. Original tensors remain unchanged. Admitted default width1 with three512px frames produces510 output columns exactly as source.

## Bounds and workload

Strict integer width1..100; dense BHWC input, at most64frames,4096each spatial dimension,32MiB logical input,1,048,576 candidate output pixels and192MiB projected aggregate workspace. Input dimensions and bytes are checked before source conversion. The conservative estimate includes all frame clip/conversion arrays plus output arrays/tensor copies and the original per-pixel RGBA Python tuple list. Since zip can truncate, output width never exceeds candidate input width; no large render is needed to estimate work. These are supported workload limits, not source maxima or a hard process/native allocator/backing-storage quota. The aggregate estimate can refuse cases below the independent pixel ceiling. Empty/singleton malformed inputs within these bounds are not silently normalized; direct rank3 is refused rather than claiming unrestricted malformed-input parity.

## Verification

`tests/test_ned_aoi_conversion.py` covers full source/schema/proxy;96 frame/width/column combinations,16 channel/dtype modes, exact quantization/transparent alpha and discriminating partial-stripe behavior,60 seeded image controls, noncontiguous input/no mutation/repeated reconstruction, native empty/squeeze/channel errors, all workload gates before source invocation, default512, two fresh required sandbox PIDs/recreated pack filesystems and real production outer two IMAGE results, no-raw refusal and explicit public publisher denial, guest recovery, full source/GPL/resources/stub/cache identity, exact pair+ZIP reconstruction twice and wrong-pristine refusal.

Value mode without raw leaves typed image handles unresolved; registered compute refuses those handles. The explicit raw publisher denial uses a test-only probe in disposable guest source, not a second released node. Original source warnings remain visible. Initial negative-limit fixture RED is preserved: a float32 pixel-limit fixture hit logical input bytes first; changing only its dtype to uint8 observes the pixel gate, with no math/budget/tolerance relaxation.

Run from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_aoi_conversion.py -q
```

Final unchanged-byte repeated results/log hashes are recorded in the external frozen handoff. Aggregate totals do not imply new nodes, trained inference or deployment.

## Dependencies, release integrity and persistence

Python `>=3.13,<3.14`, local3.13; observed Torch2.13.0, NumPy2.4.6 and Pillow12.3.0. Dependencies are declared but not installed/provisioned by this conversion. Original Pillow Image.getdata emits a deprecation warning in this environment; removal in a future Pillow version is not certified by these tests. No runtime install/download/weights.

Tested composite origins: coordinator's frozen `many-oct7-font-catalogue-comfy-api.pyi` SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`, checked frontend SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Unused signatures do not grant authority. Shared/catalog files are untouched.

No durable state: explicit width and image batch only, no caches, files, browser or process globals. Two fresh render pack filesystems/PIDs preserve behavior; no Cloud storage continuity is required or claimed.

Actual required macOS sandbox and CPU Pillow/NumPy pixel transport through the production outer executor are proved. Linux/Cloud dependency provisioning, full end-user workflows/user verification and deployment are unproved. Bounded malformed behavior and future dependency availability remain qualified. Coordinator owns final serial integration/release/count.
