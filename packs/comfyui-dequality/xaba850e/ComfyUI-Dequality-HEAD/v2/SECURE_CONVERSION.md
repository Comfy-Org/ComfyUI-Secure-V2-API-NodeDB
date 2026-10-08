<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-dequality

## Provenance

Upstream https://github.com/Tr1dae/ComfyUI-Dequality at exact Git commit `aba850e3c339914fdc470a9345a64844da2f51e0`, release `xaba850e`. Complete four-file retained source is verified with TLS against exact immutable Git paths/blob IDs/modes. No live revision substitution. `source-provenance.json` records source SHA-256s, actual root loader census, dependencies and then-current210 catalogue URL/pin/exact-ID negative screen.

Retained queue139 has zero/unavailable historical downloads; no current trending/rank claim. Complete source has no LICENSE or explicit grant. This local conversion is authorized; publication/distribution permission remains a separate unresolved provenance requirement.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `Dequality` | supported | yes | bounded local pixel/codec behavior, approved RNG lifetime normalization | Exact seeded enhancements, controlled unseeded noise, actual JPEG bytes/pixels, admitted native errors, two fresh required guests and production outer IMAGE. |

One Python node, no rejected or pending implementation in this bounded local scope. Coordinator release/integration/count and deployment are separate.

## Frontend and ancillary census

Zero frontend extensions, JS-only definitions and routes. No downloads, model weights, ambient host imports, network, backend route, device/module escape, output saver or filesystem authority. README and all four pristine Git blobs remain unchanged. The complete V2 sibling replaces scratch-only temporary JPEG files with in-memory bytes.

## Algorithm fidelity and deliberate normalization

Preserve exact ID, display name/category, ordered IMAGE/six INT input schema, signed seed bounds/defaults/steps and one IMAGE output. Quantization remains clip(255*pixels.cpu().numpy().squeeze(0),0,255)->uint8. RGBA converts to RGB; other Pillow modes retain native behavior. Brightness then color then contrast each consume the same `default_rng(abs(seed)).uniform(.9,1.1)` draws only when its adjustment equals1.

The source seed does **not** seed noise. Preserve the two Gaussian draws followed by uniform variation mask >.95, 1000-based scaling, clipping and uint8 conversion. Coordinator approved a per-execution legacy `RandomState()` rather than consuming the process-global NumPy RNG. Controlled-state source oracles require identical pixels/draw order; real sampled guests prove admitted output shape/range/finite values and stochastic variation. This is a deliberate isolation/lifetime normalization, not seed-controlled noise or source cross-node/global RNG continuation.

JPEG quality<100 invokes Pillow JPEG with only the source quality option; quality>=100 skips it. File-backed versus BytesIO encoded JPEG bytes and decoded pixels are exact in the controlled tests, including RGBA conversion and noise. No host file import/write is retained.

## Native errors and supported workload

Preserve BF16 NumPy native TypeError, native LA-JPEG mode refusal, one-channel/unsupported Pillow modes, batch>1/squeeze, empty axes/batches, nonfinite quantization, noncontiguous input and native direct HWC squeeze outcomes for admitted workloads. No silent dtype cast, batching expansion or JPEG-mode repair.

Preflight dense HWC/BHWC, batch<=64/spatial axes<=4096/channels<=8, aggregate logical **and backing** input<=64MiB, projected float32 output<=64MiB and conservative array/PIL/noise/codec work estimate<=384MiB. Bounds happen before NumPy/Pillow work. Scalars must be nonbool ints; absolute seed<=1125899906842624 and bounded direct noise/quality/adjustment magnitudes<=10000. Schema remains unchanged. These are supported workload limits, not source maxima, exact parser peak-memory or host-enforced physical/profile grants. Source-valid1024 RGB and source-default512 are admitted by these formulae; the actual tested representative workload is512.

## Verification and evidence tiers

`tests/test_ned_dequality_conversion.py` exercises ordered enhancement flags and JPEG qualities, RGBA/LA/channel boundaries, seven dtypes, both seed signs/endpoints, controlled noise levels/draw seeds, file-versus-memory JPEG byte identity, native malformed/squeeze/BF16/nonfinite controls, input and global RNG preservation, sampled noise, source-default512 and refusal before computation.

Two fresh required macOS Seatbelt guest PIDs reconstruct the entire V2 tree and execute the production outer IMAGE boundary with dtype/quality controls, representative512 RGBA, sampled noise, native refusals, workspace denial and recovery. A disposable test-only public tensor publisher confirms no-raw refusal. It is not a second registered node. No trained model/inference evidence is necessary for this pure image algorithm.

Exact manifests/proxy schemas, dependencies/current used stubs, complete pristine hashes, no cache litter, stored patch plus ZIP pristine-to-V2 reconstruction twice and wrong-source refusal are included. Final unchanged-byte observed logs and handoff are external; selected preliminary results are not called whole passes.

Run from `v2/tests`:

```sh
PYTHONDONTWRITEBYTECODE=1 COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONPATH=/Users/ben/comfy/ComfyUI-secure-nodes:/Users/ben/comfy/ComfyUI_secure_nodes/backend /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -p no:cacheprovider test_ned_dequality_conversion.py -q
```

Historical fixture diagnostics remain separate: initial pyproject lacked the required upper Python minor bound and therefore no manifest existed; an overbroad source-text 'open(' ban misclassified Pillow `Image.open(BytesIO)`. It is replaced by an AST authority assertion forbidding built-in filesystem open/ambient imports and admitting only the named BytesIO stream at Pillow decode. No algorithm oracle/tolerance/native-error assertion was relaxed.

## Runtime and state lifetime

Python>=3.13,<3.14, managed Torch/NumPy/Pillow. Remove unused torchvision import; no runtime installs. Tested pyi artifact origin `many-oct7-font-catalogue-comfy-api.pyi`, SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`; checked composite d.ts SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Unused declarations do not grant authority.

No durable state: explicit pixels/options, local per-call RNG and disposable in-memory JPEG buffers. Fresh workers/filesystems retain deterministic seeded/no-noise behavior; unseeded noise intentionally remains stochastic. No user KV or cloud persistence claim. Linux dependency provisioning, GPU/intermediate-device parity, hard physical memory/profile enforcement, cloud deployment and publication permission are outside the observed local evidence.

