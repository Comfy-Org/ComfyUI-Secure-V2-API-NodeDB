# Secure Nodes V2 conversion: weilin-comfyui-tools (WeiLin-Comfyui-Tools)

**Status: converted 3 of 3 declared nodes** (`WeiLinPromptUI`, `WeiLinPromptUIWithoutLora`,
`WeiLinPromptUIOnlyLoraStack`); 0 nodes refused. One behaviour is refused by name (`_v2_refusals.py`).
Guest SDK: `ClipRef.tokenize` / `encode_from_tokens_scheduled`, `ModelRef.apply_lora` (defined in both guest bases'
runtime `_sdk.py`) and the asset catalogue (`assets.exists` / `resolve` / `read_range`).

Upstream: https://github.com/weilin9999/WeiLin-Comfyui-Tools @ `5b0b8730193d498432e2fc43549b42edcb498c63`
(v0.0.80, GPL-2.0). Node ids, inputs, defaults and outputs are the original's.

## What changed (boundary only)
- `__init__.py`: the original pip-installed its requirements at import (`install_request.py`), registered the
  `js_node` web directory, and imported `app/server` (HTTP routes for its prompt editor, a local database, a
  tag-image worker). None of that runs in V2; the three nodes are in `_v2_nodes.py`. The original chose Chinese or
  English strings (category, placeholders, display names) from the host locale; V2 uses the English ones.
- LoRAs: the original resolved the file with `folder_paths.get_full_path("loras", ...)`, loaded it with
  `comfy.utils.load_torch_file(..., safe_load=True)` and patched MODEL and CLIP with its own copy of
  `load_lora_for_models` (`__init__.py:808-835`). V2 resolves the same name in the asset catalogue and applies it with
  `ModelRef.apply_lora` (core `comfy.sd.load_lora_for_models`), keeping the original's zero-strength cloning
  (`skip_zero=False`) and unchecked strengths (`allow_extended_strengths=True`); with no CLIP, the CLIP strength is
  ignored as before.
- Prompt encoding: the original built `[[cond, pooled]]` from `encode_from_tokens(..., return_pooled=True,
  return_dict=True)` (WeiLinPromptUI) or called `encode_from_tokens_scheduled` (WeiLinPromptUIWithoutLora); V2 calls
  `encode_from_tokens_scheduled`, which returns the same structure when the CLIP carries no hooks
  (core `comfy/sd.py:340-350`). Encoding errors still yield an empty CONDITIONING output, as before.
- Trigger words (`_v2_trigger_words.py`): the original's order (`app/server/prompt_api/trigger_words.py`) without
  its first step (see Known differences): safetensors `ss_tag_frequency` by training count with non-generic tags
  first, then `ss_output_name`, then the file name; the header is read through `assets.read_range`.

## Parity (tier 1, gate `run_in_gate.sh`, core 6257422b executor)
`tests/test_weilin_comfyui_tools_parity.py` runs every case through the real executor on both sides. MODEL and CLIP
are weightless stand-ins: the CLIP is a `comfy.sd.CLIP` with the real SD1 tokenizer and core's real
`encode_from_tokens_scheduled`; both stand-ins record every LoRA patch `comfy.lora.load_lora` builds (key, strength,
tensors). The original loads with harness stand-ins for its two import-time side effects only (its pip installer and
its web-editor server module; `tests/weilin_parity_worker.py`, `HARNESS_STUBS`).

## Known differences
Named refusal (`SecureConversionRefusal`):
1. `auto_random` with a non-empty `random_template`: the original drew tags from template files and a database that
   its web editor keeps in the pack folder; neither is part of the V2 pack. (Without such a file the original failed
   with `TypeError` when indexing the empty result of its lookup.)

Documented behaviour differences (each shown by a gate case):
2. LoRA application goes through core's `comfy.sd.load_lora_for_models`, which also attaches the LoRA file's
   metadata to the patched MODEL/CLIP (`lora_metadata`) and first passes the state dict through
   `comfy.lora_convert.convert_lora`, which rewrites only BFL Flux-control, Wan Fun and USO LoRA files
   (`comfy/lora_convert.py:36-43`); the original's copy did neither. Patches and strengths are identical for all
   other LoRA files.
3. Trigger words: the original first asked Civitai's API (network) by the file's SHA-256 and cached the answer in
   `./loras_tags.json` in the host's working directory (also when the request failed). V2 has no network at runtime
   and no host working directory: it gives the original's offline result for a LoRA with no cache entry.

Not shown by a gate case:
4. The prompt-editor web UI (`js_node`, `dist/`, `app/server` routes) is not served by V2; the nodes show their plain
   text widgets, whose values workflows already carry.
5. A CLIP input carrying hook keyframes: WeiLinPromptUI encoded unscheduled in the original; V2 uses the scheduled
   encoder for both prompt nodes.
6. Category, placeholders and display names are the English strings on every host (the original showed Chinese ones
   on a zh_CN host).

## Dependencies
None for V2 (the original's `uuid7` and `aiosqlite` served `app/server`).
