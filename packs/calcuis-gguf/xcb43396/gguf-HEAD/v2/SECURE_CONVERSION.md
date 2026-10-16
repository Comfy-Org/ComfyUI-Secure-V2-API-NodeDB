> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-16 at the user's request.
> Nodes: 13 of 13 upstream converted; 6 tested (scoped), 1 converted but untested/partly tested,
> 6 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> (Revision 2. 4 of the 6 tested nodes — GGUFSave, GGUFRun, VaeGGUF, AudioEncoderLoaderGGUF — are tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment). On the CURRENT runtime they fail closed until the Phase-1 SDK ships; VaeGGUF's ordinary non-GGUF branch is unchanged from revision 1. Operators must set COMFY_SECURE_MAX_GGUF_MAPPING_BYTES and COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES: tested with 256 MiB each; the default 0 refuses.)

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — calcuis GGUF (`calcuis-gguf`), revision 2

The 6 model/CLIP loaders that remain "pending capability" are registered with their original IDs and schemas but fail closed with an explicit message until the host capability they need exists (see *Pending capabilities*).

## Provenance

Upstream https://github.com/calcuis/gguf at commit `cb433968a4d42c59fc344d659ad94200b6c16689` (key `xcb43396`). The pristine tree beside `v2/` is byte-exact at that commit (89 tracked files; SHA-256 values pinned in `v2/tests/pristine_sha256.json`). This is a different pack from City96 `comfyui-gguf`; City96 code is never substituted for Calcuis behaviour.

Revision 2 = the committed revision-1 tree plus the Phase-1 pack differential (listed under *Revision 2 changes*). No test-only approvals are included; production admission stays closed.

## Runtime requirement (read first)

- GGUFSave, GGUFRun, VaeGGUF (`.gguf` branch) and AudioEncoderLoaderGGUF call SDK verbs that exist only in the Phase-1 SDK (draft core #17072 at 844d7d60, backend #31 at 7f73734e): `output.save_binary`, `assets.gguf_tensor_state`, `models.vae_from_state_dict`, `models.audio_encoder_from_state_dict`.
- On the CURRENT runtime (any SDK without those verbs) these nodes fail closed: the missing SDK call raises before any output is published or any model object is returned. GGUFSave/GGUFRun read and encode their input, then stop at `output.save_binary`; no file is written. The pack still imports and registers all 13 nodes.
- Operators must set `COMFY_SECURE_MAX_GGUF_MAPPING_BYTES` (guest `assets.gguf_tensor_state`) and `COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES` (guest `output.save_binary`). The default 0 refuses both verbs on the guest route. The differential used 268,435,456 bytes (256 MiB) for each.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode). Revision-2 evidence: each node ran in-process (registered node, SDK in-process runtime) and through an ordinary GuestSession, and each output was compared bit-exact with the genuine original pig.py on identical inputs (CPU, 1 thread, capped container, network none; guest sandbox kind none, not gVisor admission).

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| `TENSORBoost` | TENSOR Booster | tested (scoped) | Output tensor bytes/dtypes equal the original native files (real Torch 2.8 + SafeTensors); real guest subprocesses ran it through installed SDK assets and managed output. A 2.13 GB SD1.5 checkpoint (1145 tensors) was verified under a 12 GiB fixture. The r5 helpers pass in actual gVisor. |
| `GGUFUndo` | GGUF Convertor (Reverse) | tested (scoped) | Real guest subprocesses passed native dtypes/bytes, reverse metadata, empty outputs, collision-free counters, and raw/assets/output permission denials. |
| `TENSORCut` | TENSOR Cutter (Beta) | converted, partly tested | The r3 fixture verified real CUDA math and exact native saved bytes, including the native empty-input error. The production guest output path on a CUDA worker is not qualified. |
| `GGUFSave` | GGUF Convertor (Alpha) | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | Complete `.gguf` bytes equal the original pig.py output, in-process and through an ordinary GuestSession (MOE alpha fixture). On a non-diffusion state (SD1.5 VAE) all three refuse with the same `AssertionError: Unknown model architecture detected!` and publish nothing. The guest denial without `assets` named `assets`. The managed name `calcuis-gguf/<native stem>_<counter>_.gguf` replaces the legacy overwrite prompt. Evidence: `tests/gguf-phase1-r2-writers-inprocess-and-guest-vs-original-r1`. On runtimes without the Phase-1 SDK it fails closed at the missing SDK call. |
| `GGUFRun` | GGUF Convertor (Zero) | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | Complete `.gguf` bytes equal the original pig.py output, in-process and guest, for the zero fixture, a mixed bf16/f16/f32/int32-scalar/empty state and a 167,325,504-byte SD1.5 VAE (also equal to an earlier original run: deterministic). The guest denial without `output` named `output` and published nothing. Evidence: `tests/gguf-phase1-r2-writers-inprocess-and-guest-vs-original-r1`. On runtimes without the Phase-1 SDK it fails closed at the missing SDK call. |
| `LoaderGGUF` | GGUF Loader | pending capability | Needs an opaque `ModelRef` constructor that selects the retained Calcuis implementation (`calcuis-diffusion`). |
| `LoaderGGUFAdvanced` | GGUF Loader (Advanced) | pending capability | `calcuis-diffusion`, including the dequant/patch dtype and `patch_on_device` semantics. |
| `ClipLoaderGGUF` | GGUF CLIP Loader | pending capability | The GGUF branch needs Calcuis `ClipRef` construction (`calcuis-text`). The single-SafeTensors branch uses the existing typed service but has no trained-model evidence. |
| `DualClipLoaderGGUF` | GGUF DualCLIP Loader | pending capability | `calcuis-text` (ordered assets, native device and type handling). |
| `TripleClipLoaderGGUF` | GGUF TripleCLIP Loader | pending capability | `calcuis-text`. |
| `QuadrupleClipLoaderGGUF` | GGUF QuadrupleCLIP Loader | pending capability | `calcuis-text`. |
| `VaeGGUF` | GGUF VAE Loader | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | `.gguf` branch (an F16 GGUF made by the original GGUFRun) and the ordinary `.safetensors` branch: the constructed VAE state (248 tensors), a decode and an encode are bit-exact vs the original (`load_gguf_clip` / `load_torch_file` + `comfy.sd.VAE`), in-process and guest. Evidence: `tests/gguf-phase1-r3-vaegguf-inprocess-and-guest-vs-original-r1`. On runtimes without the Phase-1 SDK the `.gguf` branch fails closed at the missing SDK call; the ordinary branch is unchanged from revision 1 (`models.load_vae`). |
| `AudioEncoderLoaderGGUF` | GGUF AudioEncoder Loader | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | `.gguf` and `.safetensors` branches with chinese-wav2vec2-base (fp16): the encoder state (211 tensors) and `encode_audio` of a fixed 1 s / 16 kHz waveform (every layer) are bit-exact vs the original (`load_gguf_clip` / `load_torch_file` + `load_audio_encoder_from_sd`), in-process and guest. Evidence: `tests/gguf-phase1-r4-audioencoderloadergguf-inprocess-and-guest-vs-original-r1`. On runtimes without the Phase-1 SDK it fails closed at the missing SDK call. |

## Revision 2 changes

| File | Change |
| --- | --- |
| `gguf_state.py` (new) | Calcuis `load_gguf_sd` + `load_gguf_clip` rules (prefix, architecture, `comfy.gguf.orig_shape`, sdxl squeeze, storage shapes) as a guest-built tensor table for host-owned GGUF storage; text-encoder architectures whose branch transforms keys or data refuse with a named scope error. Byte-exact re-chunking for `output.save_binary`. |
| `nodes.py` | The four node bodies on the Phase-1 SDK verbs; permissions VaeGGUF `models, assets`, AudioEncoderLoaderGGUF `models, assets, raw`. The 6 model/CLIP loaders are unchanged. |
| `secure-nodes.json` | Regenerated by the SDK codec (backend 7f73734 packmanifest) from this tree; the only drift vs revision 1 is the two permission rows above. |
| `tests/test_pack_math.py` | The four nodes left the "pending branch fails closed" test (they are no longer pending). The 6 loaders stay in it. |
| `tests/wire_control.py`, `tests/test_model_boundary_probe.py` | Removed the probe asserting that `output.save_binary` is absent: the pack now depends on that verb. The other probes are unchanged. |
| `README.md` | Revision-2 status paragraph. |
| `SECURE_CONVERSION.md` | This report. |

## Refused techniques (never-do) and their public replacements

No user-visible node or feature is refused. Only these techniques are:

1. **Reading model files by absolute host path** (upstream `folder_paths.get_full_path` in `pig.py`). *Replacement:* logical asset names through published, confined asset ranges (TENSORBoost, TENSORCut, GGUFUndo, GGUFSave, GGUFRun); for VaeGGUF and AudioEncoderLoaderGGUF a guest-parsed tensor table, host-owned read-only GGUF storage (`assets.gguf_tensor_state`) and the typed constructors. Model/CLIP loaders: not yet.
2. **Writing outputs straight into the host output directory** (upstream `get_output_directory()` with `save_file` / `GGUFWriter`). *Replacement:* managed publication — SafeTensors via `output.save_state_dict`; GGUF bytes via bounded `output.save_binary` (1 MiB chunks, atomic counter-suffixed names, no overwrite prompt).
3. **Network downloads and file writes from the bundled CLI tools** (`gguf_connector`). *Replacement:* the tools stay pristine-only (v2 never imports them); models come from the managed catalogue.
4. **Installing packages at runtime** (upstream README: `pip install gguf-node`). *Replacement:* the locked runtime base (Python >=3.13,<3.14) and declared dependencies.

## Pending capabilities (not yet supported — nodes fail closed)

- `calcuis-diffusion` — LoaderGGUF, LoaderGGUFAdvanced: not yet supported — needs an opaque `ModelRef` selecting the Calcuis loader (Phase-2 a1 is in preparation).
- `calcuis-text` — ClipLoaderGGUF, DualClipLoaderGGUF, TripleClipLoaderGGUF, QuadrupleClipLoaderGGUF: not yet supported — needs Calcuis `ClipRef` construction.
- Phase-1 SDK deployment — GGUFSave, GGUFRun, VaeGGUF (`.gguf` branch), AudioEncoderLoaderGGUF: converted and tested on the Phase-1 SDK branch; on the current runtime they fail closed until it ships.

## Open test gates

- Re-run the four Phase-1 differentials on the deployed SDK once it ships (they then count as live-tested).
- Quantized (Q*) and BF16 VAE/audio GGUFs: the fixtures were F16; the non-2-D BF16 dequantization branch is source-checked only.
- Normal gVisor admission for the revision-2 guest routes (the differential used sandbox kind none).
- A model-capable normal-renderer TEST route with real GGUF assets, for the 6 loaders.
- TENSORCut's production guest output on a CUDA worker.
- Big-endian GGUF.
- Whole-pack acceptance review and registry admission (kept out of every registry slot until the Phase-1 SDK is deployed).

## Authority and permissions

| Permissions | Nodes |
| --- | --- |
| `models` | ClipLoaderGGUF, DualClipLoaderGGUF, LoaderGGUF, LoaderGGUFAdvanced, QuadrupleClipLoaderGGUF, TripleClipLoaderGGUF |
| `raw`, `assets`, `output` | GGUFRun, GGUFSave, GGUFUndo, TENSORBoost, TENSORCut |
| `models`, `assets` | VaeGGUF |
| `models`, `assets`, `raw` | AudioEncoderLoaderGGUF |

`raw` on AudioEncoderLoaderGGUF: its ordinary branch turns the restricted `assets.load_state_dict` result into a `ValueRef` for the constructor. No network, host filesystem paths or subprocesses. Runtime: Python >=3.13,<3.14. Operator byte caps: see *Runtime requirement*.

## Assets and weights

No weights are committed. Users supply GGUF/SafeTensors models through the managed model catalogue (`unet`, `clip`, `vae`, `audio_encoders`, `diffusion_models`). Upstream points to example models at https://huggingface.co/calcuis; they are not bundled.

Weights used by the revision-2 differential (never committed): SD1.5 VAE `moe-zimage-sd15-vae-0c324912599f.safetensors` (167,333,134 bytes, sha256 0c324912599f…b804) and `wav2vec2-chinese-base_fp16.safetensors` from Kijai/wav2vec2_safetensors@87847d3b (190,115,368 bytes, sha256 000813e44102…05b4); the GGUF fixtures were made from them by the original GGUFRun.

---

## Revision 1 report (retained; superseded above)

(The revision-1 status banner and report marker are omitted here; the rest is verbatim.)

# Secure Nodes V2 conversion report — calcuis GGUF (`calcuis-gguf`)

The 10 "partial" nodes are registered with their original IDs and schemas but fail closed with an
explicit message until the host capability they need exists (see *Pending capabilities*).

## Provenance

Upstream https://github.com/calcuis/gguf at commit `cb433968a4d42c59fc344d659ad94200b6c16689`
(key `xcb43396`). The pristine tree beside `v2/` is byte-exact at that commit (89 tracked files).
Their SHA-256 values are pinned in `v2/tests/pristine_sha256.json`. This is a different pack from City96 `comfyui-gguf`;
City96 code is never substituted for Calcuis behaviour.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode).

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| `TENSORBoost` | TENSOR Booster | tested (scoped) | Output tensor bytes/dtypes equal the original native files (real Torch 2.8 + SafeTensors); real guest subprocesses ran it through installed SDK assets and managed output. A 2.13 GB SD1.5 checkpoint (1145 tensors) was verified under a 12 GiB fixture. The r5 helpers pass in actual gVisor. |
| `GGUFUndo` | GGUF Convertor (Reverse) | tested (scoped) | Real guest subprocesses passed native dtypes/bytes, reverse metadata, empty outputs, collision-free counters, and raw/assets/output permission denials. |
| `TENSORCut` | TENSOR Cutter (Beta) | converted, partly tested | The r3 fixture verified real CUDA math and exact native saved bytes, including the native empty-input error. The production guest output path on a CUDA worker is not qualified. |
| `GGUFSave` | GGUF Convertor (Alpha) | pending capability | Alpha writer bytes equal the native writer across float32, float16, bfloat16 and float8_e4m3fn (actual gVisor). Publishing the `.gguf` output needs bounded binary output, so the node fails closed. |
| `GGUFRun` | GGUF Convertor (Zero) | pending capability | Zero writer: same evidence and the same missing capability as GGUFSave. |
| `LoaderGGUF` | GGUF Loader | pending capability | Needs an opaque `ModelRef` constructor that selects the retained Calcuis implementation (`calcuis-diffusion`). |
| `LoaderGGUFAdvanced` | GGUF Loader (Advanced) | pending capability | `calcuis-diffusion`, including the dequant/patch dtype and `patch_on_device` semantics. |
| `ClipLoaderGGUF` | GGUF CLIP Loader | pending capability | The GGUF branch needs Calcuis `ClipRef` construction (`calcuis-text`). The single-SafeTensors branch uses the existing typed service but has no trained-model evidence. |
| `DualClipLoaderGGUF` | GGUF DualCLIP Loader | pending capability | `calcuis-text` (ordered assets, native device and type handling). |
| `TripleClipLoaderGGUF` | GGUF TripleCLIP Loader | pending capability | `calcuis-text`. |
| `QuadrupleClipLoaderGGUF` | GGUF QuadrupleCLIP Loader | pending capability | `calcuis-text`. |
| `VaeGGUF` | GGUF VAE Loader | pending capability | The native GGUF VAE needs an opaque `VaeRef` constructor with Calcuis decoding (`calcuis-native-vae`). The ordinary VAE branch uses the existing `load_vae` but is untested with trained models. |
| `AudioEncoderLoaderGGUF` | GGUF AudioEncoder Loader | pending capability | Needs a typed `AudioEncoderRef` constructor (`calcuis-audio`). |

## Refused techniques (never-do) and their public replacements

No user-visible node or feature is refused. Only these techniques are:

1. **Reading model files by absolute host path.** Upstream does this with `folder_paths.get_full_path` in `pig.py` lines 571–1129. It
   exposes the host's layout and allows unconfined reads. *Replacement:* logical asset names read
   through published, confined asset ranges (TENSORBoost, TENSORCut, GGUFUndo, GGUFSave and GGUFRun).
   Loaders: not yet, pending the typed model constructors below.
2. **Writing outputs straight into the host output directory.** Upstream combines `get_output_directory()` with `save_file` or
   `GGUFWriter` in `pig.py` lines 827–1004. This bypasses ownership, conflict and quota rules. *Replacement:*
   managed output publication for SafeTensors. GGUF bytes: not yet, pending bounded binary output.
3. **Network downloads and file writes from the bundled CLI tools.** In `gguf_connector`, b1.py and b2.py call
   `huggingface_hub.snapshot_download`; d.py, d2.py and e.py write into the working directory; data.json holds model URLs.
   This is unaudited network access plus arbitrary host writes. *Replacement:* the tools stay pristine-only (v2 never imports them),
   and models come from the managed catalogue.
4. **Installing packages at runtime** (upstream README: `pip install gguf-node`). This mutates a shared environment.
   *Replacement:* the locked runtime base (Python >=3.13,<3.14) and declared dependencies.

## Pending capabilities (not yet supported — nodes fail closed)

- `calcuis-diffusion` — LoaderGGUF, LoaderGGUFAdvanced: an opaque `ModelRef` selecting the Calcuis loader.
- `calcuis-text` — ClipLoaderGGUF, DualClipLoaderGGUF, TripleClipLoaderGGUF, QuadrupleClipLoaderGGUF.
- `calcuis-native-vae` — VaeGGUF.
- `calcuis-audio` — AudioEncoderLoaderGGUF.
- `gguf-binary-output` — GGUFSave, GGUFRun: bounded managed binary output with an opaque receipt,
  never host paths.

## Open test gates

- A model-capable normal-renderer TEST route with real GGUF assets, for loader and inference parity.
- TENSORCut's production guest output on a CUDA worker.
- Managed binary publication for GGUFSave and GGUFRun, once that capability exists.
- Big-endian GGUF, plus the BF16 and one-dimensional state-transport limits recorded in the notes below.
- Whole-pack acceptance review and registry admission.

## Authority and permissions

- Loaders (8 nodes): `models`.
- Converters and tensor tools (5 nodes): `raw`, `assets`, `output`.
- No network, host filesystem paths or subprocesses. Runtime: Python >=3.13,<3.14.

## Assets and weights

No weights are committed. Users supply GGUF/SafeTensors models through the managed model catalogue
(`unet`, `clip`, `vae`/`vae_gguf`, `audio_encoders`/`encoder_gguf`, `select_safetensors`, `select_gguf`).
Upstream points to example models at https://huggingface.co/calcuis; they are not bundled.

## Conversion notes (retained r5 report)

### Calcuis GGUF pack correction r5

Pin: cb433968a4d42c59fc344d659ad94200b6c16689.
This is a pack source successor to the sealed r1 asset-range draft. All13
registrations and node bodies are retained; this is not whole-pack acceptance.
The r2 SDK/runtime experiment is excluded and unapplied.

SafeTensors input now validates the complete header, exact shape/dtype spans,
metadata, contiguous coverage and absence of overlap before reading payloads.
Each tensor is decoded separately by the installed SafeTensors decoder. Stored
BF16, scalar and empty shapes stay exact. Header and payload reads are64KiB.
The header format limit is the installed native parser's100,000,000 bytes;
the SDK's16MiB per-request ceiling does not cap the complete header.
Removed conversion-invented1GiB state/output and aggregate element limits,
and the arbitrary state/SafeTensors rank8 cap. Resource admission remains the
host's responsibility. Empty states and keys, long keys, more than65,536
tensors and writer rank9 are accepted. Parser bounds derive from file spans
instead of arbitrary string, count, metadata or rank ceilings. Logical names
retain published asset confinement; each SDK domain and host filesystem owns
its additional rules. There is no full unrestricted native-parity claim.
The binary writer still enforces explicit caller limits when supplied.

Focused native tests use the original package and original nodes, real Torch
2.8.0+cu128, CUDA and SafeTensors. Boost and Cut output tensor bytes/dtypes
match original native files. Cut empty input produces the native error.
Alpha/Zero complete GGUF files match original native writer files for the
focused matrix fixture. These checks supersede the old arbitrary-cap tests.

The actual SD1.5 checkpoint is2,132,696,762 bytes and1145 tensors. All stored
tensor bytes/dtypes and every saved nativeF32 cast were verified. Saved output
is4,265,145,968 bytes. The12GiB isolated fixture passed with peakRSS9,108,456KiB;
the earlier8GiB fixture was OOM-killed and remains in the ledger. Removing a
pack cap does not qualify that model for a smaller production worker grant.

Four fresh real guest subprocesses exercised exported TENSORBoost/GGUFUndo
through unchanged installed GuestSession/SDK assets and managed state output.
Native dtypes/bytes, reverse metadata, empty outputs, collision-free counters,
and raw/assets/output permission denials passed. These guests used sandbox
kind none inside constrained owned Docker units, not normal gVisor admission.
Historical r1 actual public gVisor receipts remain sealed; they were not rerun.

Full loader/provider/device/inference and managed GGUF binary-output seams
remain separate work; City96 is not substituted for Calcuis. No shared or
isolated SDK/broker/runtime integration was changed in this successor.
This pack directory is the V2 overlay only; pristine original sources are
retained in the canonical base and the hash-pinned test fixture package.

#### Focused r5 evidence

Fourteen new regressions passed against actual installed SafeTensors and the
pinned native GGUF writer/reader, locally and in actual gVisor. The six reviewed
failures now pass: empty state, empty and4097-byte keys,65537 empty tensors,
writer rank9 and an empty GGUF tensor name. Complete native GGUF bytes, reader
values and metadata agree for the writer cases. A header above16MiB assembles
in64KiB chunks; the100,000,000-byte native boundary is independently checked.
The real existing SDK asset reader passed the large-header fixture locally.
The gVisor test uses genuine encoded bytes and pure production helpers; it
does not claim asset RPC or empty-state managed output publication.

Positive job `143fa96fb7ab730c01a8165e03fe70dd`; expected assertion-negative `19a9c2e22e2a169bbb121cc58aaf1286`.
Both use the same source draft and actual gVisor. Positive PID1 is recorded;
the negative receipt omits PID. All13 production nodes remain release-pending.
The local frozen service has no located model-capable TEST registration;
capability of the intended Bens Linux registry route is not established.
Big-endian GGUF, provider/inference and managed binary publication remain
outside these focused checks. No SDK, runtime or service code was changed.
