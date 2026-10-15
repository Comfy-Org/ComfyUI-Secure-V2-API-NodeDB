# Secure Nodes V2 conversion

## Identity, census and declaration

Pinned upstream https://github.com/ShmuelRonen/ComfyUI-HunyuanVideoSamplerSave at `12da6f230aae1427c74e96dd3d34735d5b8bd390`. Complete nine-file pristine Git capture; exact blobs/modes and source hashes recorded in `source-provenance.json`. Retained queue position 178, downloads unavailable/zero; no popularity/trending claim.

Actual pinned registration: four Python nodes; zero frontend extensions, JS-only nodes or routes. Original IDs, display names, categories, defaults, ordered choices and output contracts retained. Sampler uint64 seed maximum remains the exact integer 18446744073709551615, not a JavaScript-rounded number. A decimal string in schema-data is converted back to that integer before schema construction.

| Node ID | Disposition | Scope and positive evidence |
| --- | --- | --- |
| HunyuanVideoSamplerSave | supported | Public typed sample operation; real native ComfyUI FLOW loop with tiny CPU BaseModel/ModelPatcher and synthetic diffusion kernel, required confined guest and actual outer 5D LATENT. Not trained Hunyuan generation certification. |
| ResizeImageForHunyuan | supported | Typed canonical resize, all 36 ordered presets, all four source methods/crops/floating dtypes, exact source pixels and LA two-channel admission; inspect-only whole-batch preflight. |
| EmptyVideoLatentForHunyuan | supported | All 36 presets, floor-to-16 spatial and temporal-ceiling math, CPU zero allocation, exact source CPU defaults and typed outer LATENT publication within workload bounds. |
| ImageMotionInfluance | supported | AST-exact retained pack-side motion class, mirrored wrap/zoom/first-batch frame order, native errors and raw-denied confined-guest controls. |

These are bounded local conversion recommendations; coordinator review/serial integration owns declaration promotion and counts. Hardware/cloud deployment is a separate unproved axis.

## Registered intent versus unused code

The released sampler calls `nodes.common_ksampler` on the whole latent dictionary. The substantial `MotionGuidedSampler` helper is unregistered and is never called by any of the four exported nodes. No per-frame consistency algorithm, cache clearing or motion-guided sampling is fabricated from that unused helper or README descriptions. Its original source remains pristine.

The converted sampler passes opaque MODEL/CONDITIONING/LATENT refs to `ctx.sample`, with only sample authority. Models, modules, weights and placement are never recovered in the pack. Source-unused get_torch_device and tensor-shape debug print are not restored via raw/inspect grants. Native seed/noise, denoise, scheduler and sampler behavior is owned by the canonical host loop, not a copied sampler.

Source-order sampler/scheduler menus are captured from the observed canonical catalogue at conversion; live broker admission uses canonical installed names. Host/provider changes after this pinned manifest snapshot require owner schema refresh; no promise of automatic UI discovery of future providers.

## Exact algorithms and scoped adaptations

Resize uses source size parsing and the public common_upscale-backed operation, preserving crop/interpolation and output order. It reads only public `image.describe()` structured shape, then `spatial_shape()` for the original dimension log. Inspect permission is necessary for batch/channel preflight, not raw pixels. Dtype summary text is not parsed. A conservative 16-byte scalar reserve covers dense Torch scalar storage through native unsupported-type errors.

Empty allocation retains source floor division, 16 channels, shape [batch,16,((length-1)//4)+1,height//8,width//8], zeros and default floating dtype. Coordinator approved CPU-local allocation followed by typed LATENT publication instead of pack device access. Same-process source CPU/default-float32 and float64 controls are exact; guest default float32 is verified. Source intermediate_device/gpu-only placement and host-default-dtype inheritance are unproved deployment scope, not claimed GPU parity. Zero spatial cells from directly supplied small/zero dimensions retain admitted source tensor behavior; malformed parsing controls remain native errors.

Motion retains the exact original ImageMotionInfluance class under Torch-only pack compute. It uses only input batch index zero, mirrored horizontal wrap, source integer pixel steps/start offsets, bilinear zoom and default CPU floating canvas. Whole input batch is nevertheless accounted before work. Input tensors remain unchanged.

## Bounds, authority and state

- Sampler: only sample permission; canonical host validates steps/seed/finite cfg/denoise/catalogue and owns model/device/lifetime. Source ratio metadata is forwarded and consumed through the tested shared correction. No extra raw/model inspection.
- Resize: only inspect permission. Dense BHWC dimensions: batch 1..64, axes <=4096, channels 1..4. Input reserve <=32 MiB, output reserve <=64 MiB, input plus three output reserves <=192 MiB, preflight before resize allocation. Declared presets remain usable; larger direct workloads may be refused.
- Empty: explicit value mode/raw permission for local zero construction. Original length/batch ranges retained in schema; projected allocation <=64 MiB using eight-byte conservative default-floating reserve, axes <=4096, before zeros.
- Motion: value-mode raw permission. Dense BHWC, batch <=64, axes <=4096/channels 1..4, source closed motion/frame/zoom controls; input <=32 MiB/output reserve <=64 MiB/work estimate <=192 MiB before source work.

These are workload admission estimates, not proofs of host hard aggregate RSS/VRAM/physical compute-profile enforcement. Native parser/tiny/empty errors are tested separately from deliberate resource refusals. No arbitrary filesystem/network/subprocess/runtime-install authority, private ref constructor, cross-user module mutation or new shared grant is introduced.

No authored file/cache/global state, frontend local store or durable cross-render requirement exists in the registered pack. Workflow inputs own settings; outputs/scratch tensors are render-local. Two recreated pack roots and guest PIDs test all four IDs, different tenant identities, missing-capability denial and recovery. Model/context remains host-selected; trained weight provisioning and cloud user identity are not certified.

## Tested shared dependencies and resources

Sample correction packet `outputs/many-oct7-sample-latent-metadata-evidence.json`, SHA `84130cdc9f233f20bad25caf98854426db0c69e11a1f8d02468ebd08aad6d1e4`; host source `513cb99c5783dadb8f35a9dc3135970b0b79c4cb599a16316eaaadcfc8560572`. Canonical ratio/channel/temporal normalization, consumed ratio removal and original metadata retention remain shared, not pack workarounds.

LA2 reader/resize packet `outputs/many-oct7-image-resize-la-evidence.json`, SHA `8bcc0228b73445c5ade5c4effa681ddce688064c3bfc4acae2d1302523238e49`; SDK source `00ded186c106d39bbb6dcb18f330c4b8959862598e93f80bdd93e20e1f76edf1`. Only LA channel admission changed; native common_upscale math is unchanged. Old LA RED/source controls and the earlier in-process sample-placeholder harness failure are preserved in external logs.

Python 3.13 and existing admitted Torch dependency; no trained model download or runtime install. MIT LICENSE, README and bundled workflows retained byte-exact; complete pinned resources captured. Public composites:
- Python `many-oct7-image-mask-comfy-api.pyi`, SHA `4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183`.
- Frontend `many-oct6-model-catalogue-checked-comfy-api.d.ts`, SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`.

## Verification and limitations

Unique suite `v2/tests/test_amy_samplersave_conversion.py`; explicit core root, bytecode disabled, pytest no-cache. Tests include actual source census/schema/proxy/AST, full ordered presets and exact tensor controls, malformed/native branches, source-connected defaults, true canonical tiny FLOW sampling across denoise/seed extremes and denoise-zero host tensor identity, ratio metadata, fresh required guests and production outer IMAGE/LATENT, all permissions denied/recovered, allocation preflight, immutable resources/stubs/cache hygiene, exact stored pair/ZIP reconstruction twice and wrong-pristine refusal. External frozen handoff/logs record observed final runs and source fingerprints.

Frontend axis not applicable. Sampling uses a real canonical engine with a synthetic deterministic CPU diffusion kernel, not a recording sampling stub; no trained Hunyuan weights or learned video-quality evidence. GPU placement, Linux/Cloud deployment, hard compute quotas, new providers after captured choices and end-user generation workflows remain unproved. None is silently converted to a security rejection or full deployment certification.
