> **STATUS: IN PROGRESS — UNVERIFIED.** Publication r4 candidate prepared on 2026-10-21; earlier revisions were published for evaluation at the user's request. Whole-pack acceptance remains open.
> Nodes: 13 of 13 upstream converted; 7 tested (scoped), 6 converted but untested/partly tested,
> 0 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> (Revision 4. Ten nodes need SDK verbs the deployed host does not have yet. The six GGUF loaders need the GGML verbs; GGUFSave, GGUFRun, VaeGGUF (`.gguf` branch) and AudioEncoderLoaderGGUF need the Phase-1 verbs, as in revision 2. On the current runtime those nodes fail closed. Operators must set COMFY_SECURE_MAX_GGUF_MAPPING_BYTES and COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES; the default 0 refuses. Revision 4 is kept out of the registry until the SDK and the limits ship.)

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — calcuis GGUF (`calcuis-gguf`), revision 4

Revision 4 widens the GGUF text-encoder path of the four CLIP loaders. qwen2/qwen3 GGUFs with fewer than 65,536 token rows now load as a key rename with the shipped map. cat GGUFs load unchanged when no tokenizer file sits beside them. Revision 3 ported the six GGUF model/CLIP loaders onto the GGML SDK verbs and added queue validators to all 13 nodes. The loaders were compared with the original pig.py on the "a2 base": deployed core 6257422 plus the undeployed GGML SDK (core d1a9259, backend 894ead3). For the loaders this is construction-call evidence, not a real model load.

## Provenance

Upstream https://github.com/calcuis/gguf at commit `cb433968a4d42c59fc344d659ad94200b6c16689` (key `xcb43396`). The pristine tree beside `v2/` is byte-exact at that commit (89 tracked files; SHA-256 values pinned in `v2/tests/pristine_sha256.json`). This is a different pack from City96 `comfyui-gguf`; City96 code is never substituted for Calcuis behaviour.

Revision 4 = revision 3 plus loader port r6 (listed under *Revision 4 changes*); revision 3 = revision 2 plus loader port r5. The production files are byte-identical to the tested tree; only this report changed after testing. Evidence: `validation/20261021-calcuis-gguf-a2base-r5` (revision 4: every tier re-run on the revision-4 bytes) and `validation/20261020-calcuis-gguf-a2base-r4` (revision 3).

## Runtime requirement (read first)

- **GGML SDK verbs** (`assets.gguf_tensor_state`, `models.ggml_diffusion_from_state_dict`, `models.ggml_text_encoders_from_state_dicts`): the six loaders. They are not in the deployed SDK, so the loaders fail closed until it ships.
- **Phase-1 SDK verbs** (`output.save_binary`, `models.vae_from_state_dict`, `models.audio_encoder_from_state_dict`): GGUFSave, GGUFRun, VaeGGUF (`.gguf` branch) and AudioEncoderLoaderGGUF, unchanged from revision 2.
- **Operator limits.** `COMFY_SECURE_MAX_GGUF_MAPPING_BYTES` gates every GGUF load (the six loaders, and VaeGGUF/AudioEncoderLoaderGGUF `.gguf`); `COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES` gates GGUFSave/GGUFRun. The default 0 refuses both. The revision-3 and revision-4 tests set the mapping limit to 42,991,616 bytes (41 MiB, their largest fixture rounded up) and showed the documented refusal one byte below a file's size.
- **Store cap.** `COMFY_SECURE_MAX_STORE_BYTES` (default 2 GiB) limits every state that crosses the guest: TENSORBoost, TENSORCut and GGUFUndo results, AudioEncoderLoaderGGUF's non-GGUF branch, and non-`.gguf` text encoders in the GGML text path (a T5-XXL fp16 SafeTensors does not fit).
- **Host torch >= 2.6.** Torch containers are loaded host-side with `weights_only` (`comfy.utils.load_torch_file(safe_load=True)`), which is a safety boundary only from torch 2.6 (CVE-2025-32434). The tested image had torch 2.8.0.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode). Revision-4 evidence: one selected attempt each of Tier A (in process), Tier B (construction calls through the real secure Guest path) and Tier Q (core queue validation through the shipped-manifest proxies) on the a2 base, CPU, network none, as an unprivileged container user, with every mount checked against bound pins (`validation/20261021-calcuis-gguf-a2base-r5`; revision 3: `validation/20261020-calcuis-gguf-a2base-r4`). The Guest path ran with the sandbox off, so it is protocol and provider evidence, not sandbox evidence. Revision-2 evidence still applies where a node's code is unchanged (see *Revision 3 changes*).

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| `TENSORBoost` | TENSOR Booster | tested (scoped) | Revision-2 evidence applies: the node code is unchanged except the name check, which now accepts any-case `.safetensors` as the original's list does (that path is verified by reading only). Output tensor bytes/dtypes equal the original native files (real Torch 2.8 + SafeTensors); real guest subprocesses ran it through installed SDK assets and managed output. A 2.13 GB SD1.5 checkpoint (1145 tensors) was verified under a 12 GiB fixture. Queue validator equal to the original list (revision-3 Tier A A8, Tier Q). Results above the 2 GiB store cap are refused. |
| `GGUFUndo` | GGUF Convertor (Reverse) | tested (scoped) | Revision-2 evidence applies: the node code is unchanged except the name check, which now accepts any-case `.gguf` as the original's list does (verified by reading only). Real guest subprocesses passed native dtypes/bytes, reverse metadata, empty outputs, collision-free counters, and raw/assets/output permission denials. Queue validator equal to the original list. Results above the 2 GiB store cap are refused. |
| `TENSORCut` | TENSOR Cutter (Beta) | converted, partly tested | The r3 fixture verified real CUDA math and exact native saved bytes, including the native empty-input error. The production guest output path on a CUDA worker is not qualified. Revision 3 changes only the any-case name check and adds the queue validator (equal to the original list). |
| `GGUFSave` | GGUF Convertor (Alpha) | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | Revision-2 evidence applies: the node code is unchanged except the any-case `.safetensors` name check (verified by reading only). Complete `.gguf` bytes equal the original pig.py output, in-process and through an ordinary GuestSession (MOE alpha fixture). Evidence: `tests/gguf-phase1-r2-writers-inprocess-and-guest-vs-original-r1`. Queue validator equal to the original list. Needs `COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES` > 0 (default 0); fails closed without the Phase-1 SDK. |
| `GGUFRun` | GGUF Convertor (Zero) | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | As GGUFSave: complete `.gguf` bytes equal the original for the zero fixture, a mixed bf16/f16/f32/int32-scalar/empty state and a 167,325,504-byte SD1.5 VAE. Queue validator equal to the original list. Needs `COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES` > 0; fails closed without the Phase-1 SDK. |
| `LoaderGGUF` | GGUF Loader | tested (scoped: a2 base, undeployed GGML SDK) | Construction-call parity through the real Guest path for the 20 provider-supported GGML types, every `load_gguf_sd` rule (prefix, architecture, `orig_shape`, sdxl squeeze, non-2-D BF16, largest weight) and the metadata; bit-exact dequantization against the original for every type, dtype and dequant dtype (800 cells); queue validation equal to the original list. No real model load or forward. Q4_0, Q4_1, Q5_0, Q5_1, Q2_K and Q3_K are refused by the provider (missing). Needs the GGML SDK deployment and the GGUF mapping limit. |
| `LoaderGGUFAdvanced` | GGUF Loader (Advanced) | converted, partly tested | As LoaderGGUF, plus all 51 dequant/patch/`patch_on_device` combinations compared as values through the provider's own precision table, and `dequant_dtype` at function level. `patch_dtype` and `patch_on_device` only act when patches (LoRA) are applied, which was not exercised. Per-load dtype settings are a final accepted difference (the original shares them across all loads). |
| `ClipLoaderGGUF` | GGUF CLIP Loader | converted, partly tested | Construction-call parity (a2 base) for identity GGUF text encoders, the t5 T5/B5 maps, qwen2/qwen3 GGUFs below 65,536 token rows (key rename with the shipped map; revision 4), cat GGUFs without a tokenizer file beside them (revision 4), the typed `.safetensors` branch, `.sft` and Torch containers. Exact named refusals where the original changes tensor data or merges files (missing): qwen2/qwen3 with 65,536 or more token rows, cat with a `*tokenizer*.safetensors` file beside it (the original merges it), the 256384-row t5 tokenizer, and llama, mistral3, gemma2, gemma3, qwen2vl, qwen3vl, ideogram, ideogram4, cow and dog. A cat GGUF is also refused when such a file sits in the same folder under another text-encoder root, or when the folder cannot be listed (fail closed). Real construction is not exercised: there a missing Linear weight (for example an SD1.5 CLIP-L without `text_projection`) is refused by the provider where the original zero-fills it (missing). One declared output (final accepted difference). |
| `DualClipLoaderGGUF` | GGUF DualCLIP Loader | converted, partly tested | As ClipLoaderGGUF for two files, including construction-only SDXL CLIP-G (layers 0 and 30) and CLIP-L fixtures. The revision-4 qwen/cat rows ran through ClipLoaderGGUF only; this node uses the same text path. Two SafeTensors with an explicit device refuse by name (missing two-file typed loader). Full encode blocked: encoder not local. |
| `TripleClipLoaderGGUF` | GGUF TripleCLIP Loader | converted, partly tested | Construction-call parity on shape-only SafeTensors (real names and shapes). Full-model test blocked: encoder not local (T5-XXL). A T5-XXL fp16 SafeTensors exceeds the 2 GiB store cap (missing). The revision-4 qwen/cat rows ran through ClipLoaderGGUF only; this node uses the same text path. |
| `QuadrupleClipLoaderGGUF` | GGUF QuadrupleCLIP Loader | converted, partly tested | As TripleClipLoaderGGUF. A llama GGUF is refused (transforms missing) and a Llama-class SafeTensors exceeds the store cap. Full-model test blocked: encoder not local. |
| `VaeGGUF` | GGUF VAE Loader | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | Revision-2 evidence applies: the node code is unchanged, and the `.gguf` table builder was refactored into shared helpers with statement-for-statement identical code (checked); those helpers are exercised on revision-3 bytes. The `.gguf` and `.safetensors` branches: constructed VAE state (248 tensors), a decode and an encode are bit-exact vs the original, in-process and guest (`tests/gguf-phase1-r3-vaegguf-inprocess-and-guest-vs-original-r1`). Queue validator equal to the original list, including TAESD presets. The `.gguf` branch needs the GGUF mapping limit. |
| `AudioEncoderLoaderGGUF` | GGUF AudioEncoder Loader | tested (Phase-1 SDK branch core 844d7d60 / backend 7f73734e; pending SDK deployment) | Revision-2 evidence applies, as for VaeGGUF: `.gguf` and `.safetensors` branches with chinese-wav2vec2-base (fp16), encoder state (211 tensors) and `encode_audio` bit-exact vs the original, in-process and guest (`tests/gguf-phase1-r4-audioencoderloadergguf-inprocess-and-guest-vs-original-r1`). Queue validator equal to the original list. The `.gguf` branch needs the mapping limit; the non-GGUF branch is limited by the store cap; Torch containers need host torch >= 2.6. |

## Revision 4 changes

| File | Change |
| --- | --- |
| `gguf_state.py` | `build_text_table`: qwen2/qwen3 GGUFs whose `token_embd` is absent or has fewer than 65,536 rows are renamed with the shipped L3 map (a copy taken at import, applied with `str.replace` in map order, as pig.py does). At 65,536 rows or more they stay refused, with their own reason. A cat GGUF loads unchanged only when the caller reports that no tokenizer file is beside it; otherwise it is refused, with its own reason. |
| `nodes.py` | `tokenizer_pair_absent` lists the GGUF's folder with `assets.list('text_encoders', prefix=..., recursive=False)`. Any `*tokenizer*.safetensors` sibling (in any case), an unexpected entry or a listing error counts as a tokenizer file. The GGML text path asks only for cat GGUFs. |
| `SECURE_CONVERSION.md` | This report (the only change made after testing). |

Unchanged in revision 4: `secure-nodes.json` (byte-identical, so no permission or schema change), every other production file, the diffusion and VAE/audio table builders, and the t5 branch.

## Revision 3 changes

| File | Change |
| --- | --- |
| `nodes.py` | The six loaders on the GGML verbs. Queue validators on all 13 nodes: membership in the original's lists (folder, extension set compared case-insensitively, canonical spellings only; a linked input passes), declared on each class. Any-case suffixes accepted where the original lists them. The GGML text path loads non-`.gguf` encoders like pig.py `load_data`. |
| `gguf_state.py` | Diffusion and text table builders with the `load_gguf_sd` / `load_gguf_clip` rules (including the t5 maps) and the metadata. The VAE/audio table builder is refactored into shared helpers with identical statements. |
| `clip_types.py`, `catalogue_pins.py` (new) | CLIPType names and `supported_pt_extensions` pinned to the run core 6257422. Core 708e6c01 adds `flux3` and `moss_image`; they are recorded, not offered. |
| `secure-nodes.json` | `validate_inputs` true and `validation_inputs` for all 13 nodes; the six loaders' permissions (`models`, `assets`; CLIP loaders also `raw`). Re-encoding with the backend's own manifest encoders gives the same rows. |
| `tests/test_clip_types_pinned.py`, `tests/test_core_pins.py`, `tests/test_manifest_rows.py` (new) | Drift tests for the pins and a static check of the manifest validator rows. |
| `SECURE_CONVERSION.md` | The revision-3 report (the only change made after testing). |

## Deliberate differences (final)

- **Per-load dtype settings.** The original sets `dequant_dtype`/`patch_dtype` on a shared class, so the last GGUF load sets them for every loaded GGUF model's Linear layers. The conversion keeps each load's own settings. Outputs differ only when one workflow holds two or more GGUF loads with different dtype options; a single load matches exactly.
- **One declared output** for the GGUF CLIP branches. The original returns `(clip, device options)`; only the declared first output is linkable (core keeps both elements; a link to the second is rejected at queue time).
- **The shipped key map on every load.** In the original, loading a gemma3 GGUF writes the G3 names into the shared L3 key map (pig.py:507-509). Later llama, qwen2, qwen3, qwen2vl, qwen3vl, mistral3 and dog loads in the same process then rename `ffn_norm` to `pre_feedforward_layernorm` instead of `post_attention_layernorm`. The conversion always uses the shipped map, which gives the original's result in a fresh process (revision-4 Tier A A10, Tier B B9).
- The model-detection failure message omits the host path. Non-`.gguf` LoaderGGUF names are also rejected at execute. The host refuses a weights container whose content is not a flat tensor dict.
- Names the host cannot address are not accepted: a listed name containing a backslash, and files whose real path leaves the folder root (platform policy).

## Refused techniques (never-do) and their public replacements

No user-visible node or feature is refused. Only these techniques are:

1. **Reading model files by absolute host path** (upstream `folder_paths.get_full_path` in `pig.py`). *Replacement:* logical asset names through published, confined asset ranges (TENSORBoost, TENSORCut, GGUFUndo, GGUFSave, GGUFRun); for the loaders, VaeGGUF and AudioEncoderLoaderGGUF a guest-built tensor table over host-owned read-only GGUF storage (`assets.gguf_tensor_state`) and the typed constructors.
2. **Writing outputs straight into the host output directory** (upstream `get_output_directory()` with `save_file` / `GGUFWriter`). *Replacement:* managed publication — SafeTensors via `output.save_state_dict`; GGUF bytes via bounded `output.save_binary`.
3. **Network downloads and file writes from the bundled CLI tools** (`gguf_connector`). *Replacement:* the tools stay pristine-only (v2 never imports them); models come from the managed catalogue.
4. **Installing packages at runtime** (upstream README: `pip install gguf-node`). *Replacement:* the locked runtime base (Python >=3.13,<3.14) and declared dependencies.

## Missing capabilities (not yet supported)

- GGML provider: Q4_0, Q4_1, Q5_0, Q5_1, Q2_K and Q3_K tensors.
- Text-encoder transforms: llama, mistral3, gemma2 and gemma3; qwen2/qwen3 with 65,536 or more token rows (float16 token embedding); qwen2vl/qwen3vl (mmproj pairs); the 256384-row t5 tokenizer; ideogram; cat tokenizer files (merge); cow and dog. The concrete asks are in `validation/20261021-calcuis-gguf-a2base-r5/GERALD_REQUEST_SECTION2_R2.md`.
- A two-file typed text-encoder loader with an explicit device (DualClipLoaderGGUF).
- Zero-fill of missing Linear weights at construction; dynamic patchers; tensor tables above 4096 tensors or 512 KiB.
- Host GGUF catalogue listing: the `/models/<folder>` routes list no `.gguf` names, so GGUF files can be chosen only by name through the API or a saved workflow.
- Operator limits: non-zero defaults (or a documented setting) for the GGUF mapping and binary-output limits; a host-side path for SafeTensors text encoders larger than the store cap.

## Open test gates

- Real model and text-encoder construction, load and forward for the six loaders, and LoRA patching with `patch_dtype`/`patch_on_device` (planned with local SD1.5 UNet, LoRA and CLIP-L; needs a separate GO).
- Full Dual/Triple/Quad encodes: encoder not local.
- Re-run the Phase-1 differentials on the deployed SDK once it ships (they then count as live-tested).
- TENSORCut's production guest output on a CUDA worker.
- Normal gVisor admission (the revision-3 and revision-4 Guest tests ran with the sandbox off).
- Quantized (Q*) and BF16 VAE/audio GGUFs; big-endian GGUF.
- Whole-pack acceptance review and registry admission (kept out of every registry slot until the GGML and Phase-1 SDK and the operator limits ship).

## Authority and permissions

| Permissions | Nodes |
| --- | --- |
| `models`, `assets` | LoaderGGUF, LoaderGGUFAdvanced, VaeGGUF |
| `models`, `assets`, `raw` | ClipLoaderGGUF, DualClipLoaderGGUF, TripleClipLoaderGGUF, QuadrupleClipLoaderGGUF, AudioEncoderLoaderGGUF |
| `raw`, `assets`, `output` | GGUFRun, GGUFSave, GGUFUndo, TENSORBoost, TENSORCut |

`raw` on the CLIP loaders and AudioEncoderLoaderGGUF: a non-`.gguf` encoder's state is loaded with `assets.load_state_dict` and passed to the constructor as a `ValueRef` (`ValueRef.from_value` is runtime-public but not yet declared in the SDK stub; a stub fix is requested). No network, host filesystem paths or subprocesses. Runtime: Python >=3.13,<3.14.

## Assets and weights

No weights are committed. Users supply GGUF/SafeTensors models through the managed model catalogue (`unet`/`diffusion_models`, `clip`/`text_encoders`, `vae`, `audio_encoders`). Upstream points to example models at https://huggingface.co/calcuis; they are not bundled. The revision-3 and revision-4 tests used only small synthetic fixtures written by the original pack's own GGUF writer and quantizer (revision 4 adds a two-tensor SafeTensors tokenizer file written by the test); no model weights.

---

## Revision 2 report (retained; superseded above)

(The revision-2 status banner and report marker are omitted here; the rest is verbatim.)

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
