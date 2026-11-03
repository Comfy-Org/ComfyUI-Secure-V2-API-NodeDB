# Secure Nodes V2 conversion: ComfyUI_JPS-Nodes

- Upstream: JPS-GER/ComfyUI_JPS-Nodes at `0e2a9aca02b17dde91577bfe4b65861df622dcaf` (no version file).
- Status:
  - 15 of the 72 declared nodes are converted.
  - The other 57 keep their original schemas and refuse at queue time with "comfyui_jps-nodes/<node id> is not yet
    converted to Secure Nodes V2".
- The pristine tree and v2/ are the whole upstream tree. It has no media, example workflows or model files; the
  styles/*.json files are the prompt styler's data.
- No Python dependencies. The converted code uses the standard library; tensors and model references come from the
  host.

## Converted nodes
| Node id | V2 |
|---|---|
| SDXL Resolutions, Resolution Multiply, Largest Int, Multiply Int Float | the original methods |
| Text Prompt, Text Prompt Combo, SDXL Prompt Handling, Text Concatenate | the original methods |
| Get Date Time String | the original method; its change fingerprint is the original IS_CHANGED (the formatted time) |
| Sampler Scheduler Settings | the original method; the two outputs are COMBO outputs with the original's choices |
| Integer Switch | the original method |
| Model Switch, Latent Switch | the original methods; the selected reference passes through |
| Get Image Size | the original method on the IMAGE tensor |
| Lora Loader | ported line for line; the engine loads the LoRA file and patches MODEL and CLIP |

All node ids end in " (JPS)".

## How it runs
- `v2/__init__.py` imports no original module.
  - The original jps_nodes.py imports comfy.sd, folder_paths, comfy.cli_args, PIL and numpy at import.
  - It stays in v2/ byte-identical and is never imported.
- `_jps_upstream.py` holds the 14 original node classes the converted nodes run, copied verbatim as AST source
  segments, with line ranges and the file's sha256.
  - Its one stand-in: `comfy.samplers.KSampler.SAMPLERS / SCHEDULERS` are empty lists. Only Sampler Scheduler
    Settings' class attributes read them, and its V2 schema is the frozen original schema.
- Every schema is the original's, frozen in the lane gate (`_frozen_schemas.json`, read by `_frozen_schema.py`).
  - V1 list-valued RETURN_TYPES are COMBO outputs carrying the original's choices.
- Lora Loader (`_secure_used.py`) keeps the original's two early returns. Then it resolves the LoRA from the host's
  `loras` catalogue and applies it with `ModelRef.apply_lora` (Core's `load_lora_for_models`).
  - Its menu is the host's catalogue (`/models/loras`), after the original's "None".
  - Where apply_lora accepts `skip_zero` and `allow_extended_strengths` (base 0cd9adec), it passes `skip_zero=False`
    and `allow_extended_strengths=True`, so the native loader runs as in the original. This is the corpus'
    comfyui-easy-use pattern.

## Refused
- **The other 57 declared nodes**, by name, at queue time.

## Known differences
1. **LoRA strengths outside [-100, 100]**, or not finite, can arrive only through a link; the widgets allow
   [-10, 10].
   - Base 0cd9adec applies them as the original does.
   - Base 0b86765f's apply_lora refuses them by name ("strength_model must be finite and in [-100, 100]").
2. **No CLIP.** When the CLIP input is None, the original ignores strength_clip; V2 passes zero (the SDK requires it).
   - The outputs are the same.
   - On base 0b86765f, if strength_model is also zero, the input MODEL comes back. The original returns a
     zero-strength clone, which computes the same values.
3. **LoRA cache.** The original keeps the last LoRA's tensors on the node instance. The engine reads the file on each
   run.
4. **Frozen choices.** Sampler Scheduler Settings offers the sampler and scheduler names frozen from Core 6257422b.
   - The original lists the running Core's names.
   - Linking its COMBO outputs to Core sampler inputs depends on the platform's COMBO-output support, a known
     platform gap.
5. **Clock.** Get Date Time String reads the guest's clock. The original reads the ComfyUI process's clock.
6. **Engine steps.** Loading and applying the LoRA are the engine's (Core's own code). The parity test covers them
   only through identical stand-ins.

## Parity
`tests/test_jps_nodes_parity.py` runs in the lane gate.
- Both sides run every converted node on generated cases: the pristine jps_nodes.py under Core, and these classes
  with a fake SDK context.
- The LoRA files are synthetic safetensors fixtures, and the images are synthetic tensors.
- The clock is frozen at the same instant on both sides.
- Strings, numbers, outputs, change fingerprints, errors (type and message) and the manifest (against the real
  encoder) are compared exactly.
- The apply_lora stand-in repeats the trusted argument checks of both bases. A second run with base 0b86765f's
  signature must differ only in the cases listed above.
- Each of the 57 refusals is checked by name.
- A mutant run must turn the comparison red.
