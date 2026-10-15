<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-imgmask2png

## Provenance

Upstream https://github.com/freelifehacker/ComfyUI-ImgMask2PNG, exact Git commit `a7ae08c135c13e254cfbb3bee194990e970bb6ae`, release `xa7ae08c`. Complete three-path retained capture was verified against immutable Git blob hashes and path/mode metadata, not substituted live HEAD. `source-provenance.json` records source SHA-256s, actual root import/census, dependencies and current central URL/exact-ID negative screen. Retained popularity field is zero/unavailable, not asserted modern/trending.

The complete Git tree has no license file or declared grant. Local conversion is explicitly authorized; distribution permission remains a separate unresolved provenance requirement. No license text is invented.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `ImageMask2PNG` | supported | yes | bounded local tensor/Pillow behavior | Byte-exact source pixel algorithm, unequal batches/resize/modes/quantization/native errors, two required fresh guests and production outer IMAGE. |

One Python node, zero rejected or pending implementations in this bounded local scope. Coordinator review/integration and user verification are separate; no local count/deployment promotion.

## Frontend and ancillary census

Zero frontend extensions, JS-only graph definitions and routes. Original three files are preserved with a complete V2 sibling. Despite PNG in the name, the node returns an in-memory RGBA IMAGE, not a saved file; no file service, models, secrets, downloads, runtime installation, host modules or legacy bridge are involved.

## Behavior and authority

Value-mode public `io.ComfyNode`, declared `raw` for pack-side tensor NumPy/Pillow computation. Original `imgmask2png.py` remains byte-exact. Preserve ID, display/category `🌊ImageMask2PNG`, required MASK then IMAGE sockets and one IMAGE named image. Float inputs are clipped/quantized to uint8 exactly as source, mask resizing uses Pillow Lanczos, image converts RGBA, mask converts L, and `paste` blends both RGB and alpha onto a zero RGBA image. This is not an alpha-only attachment. Output conversion is float32 divided by255 and concatenates frames in source order.

Unequal mask/image batches retain source `zip` truncation; no implicit broadcast or mismatch rejection is introduced. Existing RGBA alpha is blended along with RGB. Source singleton squeeze/PIL mode behavior and empty-list Torch concatenation errors are retained in admitted shape/workload controls. BF16 source NumPy conversion error is not silently cast away. Representative connected512 images with resized256 masks are tested, not merely an import or tiny-fixture claim.

## Supported workload and malformed boundaries

Admit dense BHWC IMAGE and BHW MASK, at most64 batch elements and4096 spatial axes. Aggregate input logical bytes at most32MiB, projected min(batch) full RGBA float32 output at most64MiB. Before Pillow conversion, estimate clipping/multiply intermediates, PIL copies, all retained output frames and final concatenation; projected aggregate work at most192MiB. These are explicit supported workload limits, not upstream maxima, hard native parser/process/profile enforcement or a host allocation grant. Noncontiguous tensors retain source values. Rank-mismatched direct inputs deliberately refuse; unrestricted malformed-input legacy parity is not claimed.

## Verification

`tests/test_ned_imgmask_conversion.py` compares exact source pixels across unequal batches, same/upsampled/downsampled masks, four source image modes, seven dtypes, eighty deterministic random vectors, noncontiguous tensors, native empty/squeeze/nonfinite controls, input identity, representative512 workloads and admission-before-compute negatives. A discriminating fixture checks RGB and existing-alpha scaling; exact equality is required without tolerance relaxation.

Two fresh required macOS guest processes reconstruct the entire V2 filesystem. Real production outer execution supplies declared MASK/IMAGE input hints and returns declared IMAGE with exact source shape/dtype/pixels. Native errors, workload refusal, recovery and no-raw refusal are tested. A separate public tensor-publisher permission probe exists only in disposable test copies, not as a second released node. Without raw, unresolved typed handles are rejected by pack tensor admission; raw is not an ambient model/device/path grant.

Resource gates verify complete pristine identity, byte-exact algorithm/README, actual proxy schema/census, exact manifest/runtime declarations, canonical stub hashes, no interpreter cache litter and stored pair plus ZIP pristine-to-V2 reconstruction twice; wrong pristine bytes fail before V2 writes.

Run from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_imgmask_conversion.py -q
```

The frozen external handoff records matching final-byte observed runs, commands and hashed logs. No full Linux/Cloud provisioning, GPU placement or user-workflow certification is inferred.

## Runtime and persistence

Python >=3.13,<3.14, local Torch2.13.0/NumPy2.4.6/Pillow12.3.0 observed. No dependency install/download during conversion or node execution. Tested composite pyi origin `many-oct7-font-catalogue-comfy-api.pyi` SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`; checked frontend composite SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Unused APIs confer no grants.

No durable state: explicit image/mask inputs, no mutable pack files, cache, routes or globals. Recreated filesystems/PIDs reproduce output; host input tensors remain unchanged. No Cloud KV continuity is needed. GPU source tensors, cross-platform dependency availability, hard physical memory/profile enforcement and publication permission remain unproved deployment/provenance scope.
