# calcuis-gguf: platform requests r2 (review H1, H2, M3; re-review N3, N5)

From NED, for MERVYN to route. This is a second request file; GERALD_REQUEST.md (d4ddc2de) is unchanged.
Line numbers refer to the a2 base used for the tests: core d1a9259 (deployed 6257422 plus GGML SDK files) and backend a1 894ead3.

## 1. GGUF mapping limit (GERALD/JERRY), review H1

- `COMFY_SECURE_MAX_GGUF_MAPPING_BYTES` defaults to "0" and is read on every call (backend `transport/host.py:1407-1409`).
  Any GGUF larger than the limit is refused with "GGUF mapping exceeds the selected operator byte limit".
  With the default, every GGUF load fails.
- Affected nodes:
  - LoaderGGUF, LoaderGGUFAdvanced, and the four GGUF CLIP loaders, for any `.gguf` input;
  - VaeGGUF and AudioEncoderLoaderGGUF, for `.gguf` files.
- The original reads the file in process, with no such limit.
- Ask: what value should JERRY's runtime set, and who owns the setting? Or should the backend ship a non-zero default?

## 2. SafeTensors text encoders cross to the guest and back (GERALD), review H1

- The GGML text path needs one state dict per file. For a SafeTensors encoder the guest calls `assets.load_state_dict`, then
  `ValueRef.from_value`, then `models.ggml_text_encoders_from_state_dicts`, so the tensors make a round trip through the guest.
- `COMFY_SECURE_MAX_STORE_BYTES` (default 2 GiB, backend `transport/host.py:736-739`) caps that round trip.
  - `t5xxl_fp16.safetensors` (about 9.5 GB) cannot pass.
  - Inside the cap, the state is held about three times at peak: host cache, guest copy, and the copy back.
- Affected nodes:
  - DualClipLoaderGGUF, TripleClipLoaderGGUF and QuadrupleClipLoaderGGUF;
  - ClipLoaderGGUF, for every name that is neither `.gguf` nor lower-case `.safetensors` (`.sft`, upper-case SafeTensors,
    and Torch containers, which the host loads with `comfy.utils.load_torch_file(safe_load=True)` as pig.py does).
- The original loads the file in place (`comfy.utils.load_torch_file`).
- Ask: let `ggml_text_encoders_from_state_dicts` take an AssetRef for a SafeTensors file, or add a host-side
  SafeTensors-to-state verb, so the tensors stay on the host.

## 3. GGUF names in the dropdowns (MIKE/GERALD), review H2

- The combos use `/models/{folder}`, which returns `folder_paths.get_filename_list(folder)` (core `server.py:414-419`).
  For `diffusion_models`, `text_encoders`, `vae` and `audio_encoders`, that list holds `supported_pt_extensions` only,
  so no `.gguf` name is ever offered.
- The original registers `model_gguf`, `clip_gguf`, `vae_gguf` and `encoder_gguf` folders with `{'.gguf'}` and lists them.
- Host `assets.exists` and `assets.resolve` have no extension filter. A `.gguf` name sent through the API, or saved in a
  workflow, works. Only the listing is missing.
- Ask: a host route, or a folder registration, that lists `.gguf` files under those four folders for converted packs.
  `/models/gguf/choices` exists, but it depends on City96's `unet_gguf`.

## 4. Provider parity (GERALD), review M3

- Missing Linear weight:
  - The provider raises NotImplementedError (core `comfy_api/latest/_ggml.py:130-135`); pig.py zero-fills (`pig.py:166-170`).
  - Example: an SD1.5 CLIP-L GGUF has no `text_projection`. Core declares it as a Linear and treats its absence as
    normal. The original loads the file; the port refuses it.
- Ask: zero-fill parity, or confirm the refusal as policy, in which case it becomes a recorded difference.
- Also recorded. These need no ask unless you want one:
  - dynamic patchers are refused (`_ggml_patcher.py:20-21`);
  - the tensor table allows 1..4096 tensors, at most 512 KiB of JSON, and 1..8 positive dimensions (`_gguf_tensor.py:99-115`).

## 5. Binary output limit (GERALD/JERRY), re-review N3

- `COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES` defaults to "0" (backend `transport/host.py:1781-1783`), so `output.save_binary`
  is refused with "binary output exceeds the selected operator byte limit" until an operator selects a cap.
- Affected nodes: GGUFSave and GGUFRun (their converted GGUF files are published through `save_binary`).
- Ask: the same decision as item 1: a bounded default or a documented operator setting, and who sets it live.

## 6. Torch requirement for weights-only loading (platform), re-review N5

- The host loads user Torch containers with `comfy.utils.load_torch_file(path, safe_load=True)` (backend
  `model_cache.py:192-199`), i.e. `torch.load(weights_only=True)`. That is a safety boundary only on torch >= 2.6
  (CVE-2025-32434).
- Affected: the GGUF CLIP loaders (Torch containers in the GGML text path, r5) and AudioEncoderLoaderGGUF (since rev 2).
- Ask: state torch >= 2.6 as a host requirement and check it at startup. Test runs record the torch version.

All six are recorded per node in the test r4 records: items 1-5 as "missing", item 6 as a requirement.
