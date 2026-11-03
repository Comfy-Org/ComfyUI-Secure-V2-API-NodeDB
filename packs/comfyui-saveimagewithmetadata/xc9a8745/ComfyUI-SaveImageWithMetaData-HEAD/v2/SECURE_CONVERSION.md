# Secure Nodes V2 conversion: ComfyUI-SaveImageWithMetaData (nkchocoai)

**Status: converted 2 of 2 declared nodes** (`SaveImageWithMetaData`, `CreateExtraMetaData`); 0 nodes refused.
`SaveImageWithMetaData` refuses six behaviours by name (`py/_v2_refusals.py`). **Minimum guest SDK base: 0cd9adec**
(comfy_api 0.37.0): it uses `graph.execution_metadata` and the image writer's `png_text` / `a1111_parameters`, which
base 0b86765f lacks.

Upstream: https://github.com/nkchocoai/ComfyUI-SaveImageWithMetaData @ `c9a87453bc4257614c87d28a64a5be9c4fdccba9`
(GPL-3.0). Node ids, display names, categories, inputs, defaults and outputs are the original's.

## What changed (boundary only)
- `py/__init__.py`, `py/hook.py`: the executor monkeypatches (`PromptExecutor.execute`, `execution.get_input_data`) are
  gone. The save node asks the broker for the running prompt and its observed node inputs and outputs
  (`ctx.graph.execution_metadata(include_observations=True)`, permission `graph.metadata`); `py/_v2_capture.py`
  rebuilds the `get_input_data` view the capture code reads. `capture.py`, `trace.py` and `defs/` keep the published
  algorithms (three import lines in `capture.py` changed; `defs/__init__.py` imports `ext/` relatively).
- `py/defs/formatters.py`: model names are looked up in the asset catalogue (`assets.exists`) instead of
  `folder_paths.get_full_path`; hashes come from `assets.digest` (`py/utils/hash.py`), same first 10 hex digits of SHA-256.
  The prompt parser helpers are vendored verbatim from core 6257422b `comfy/sd1_clip.py:320-376` (`py/_v2_clip.py`).
- `py/utils/embedding.py`: embeddings are searched in the embeddings catalogue (root, then subfolders).
- `py/nodes/node.py`: V3 `io.ComfyNode` schemas; the save loop is the original's, writing through
  `ctx.output.save_images` (PNG `png_text`, WebP `a1111_parameters`) and `ctx.output.write_text` (workflow JSON).
  With `add_counter_to_filename` on, the writer runs core `folder_paths.get_save_image_path` for the prefix, so names
  and counters are the original's (`<name>_00001_.png`).
- Hidden `prompt` and `extra_pnginfo` are declared and read through the schema (`cls.hidden`).

## Parity (tier 1, gate `run_in_gate.sh`, core 6257422b executor)
`tests/test_comfyui_saveimagewithmetadata_parity.py` runs 52 prompts through the real executor three times: the
unmodified original, the original plus a harness-only cache adapter (the reference), and V2. Each case declares its
expected outcome. The pinned original cannot capture on core 6257422b at all: `py/capture.py:19-27` passes the
executor's output cache to `execution.get_input_data`, which now calls `execution_list.get_cache()` (core
`execution.py:294`); `HierarchicalCache` has no such method and its `get` is async (`comfy_execution/caching.py:384`).
Every unmodified save fails with `AttributeError: 'HierarchicalCache' object has no attribute 'get_cache'`
(upstream issue). The reference restores the synchronous accessor of the ComfyUI releases the original targets
(`HierarchicalCache.get_cache = get_local`, `tests/nk_parity_worker.py`, `ADAPTER`).

## Known differences
Named refusals (`SecureConversionRefusal`):
1. `file_format` `jpeg`: the writer encodes JPEG 4:4:4 with its own EXIF; the original used Pillow's 4:2:0 + piexif.
2. `add_counter_to_filename` off when the target file exists, or with a batch of 2+: the original overwrote the file;
   the writer never overwrites. (A new name is written exactly as the original did.)
3. `%batch_num%` in the prefix: the original kept it literally; the writer would substitute it.
4. A prefix naming no file (empty, `.`, `..`): the original wrote `._00001_.png`; the writer rejects the name.
5. An embedding not at the embeddings root while the embeddings catalogue lists more than 4096 files.
6. A backslash in the (formatted) prefix: on a Linux host the original kept it as part of the file name; the writer
   treats it as a folder separator.

Documented behaviour differences (each shown by a gate case):
6. Prefixes leaving the output folder: both raise `Exception("**** ERROR: Saving image outside the output folder is not
   allowed. ...")`; the original's message names host paths and it first creates the escaping folder (upstream
   `py/nodes/node.py:118-120`); V2's message names relative paths and nothing is created.
7. A prefix whose folder part holds `%year%`-style variables: the original also creates an empty folder named with the
   unsubstituted text (e.g. `run_%year%%month%/`); V2 creates no empty folders. Image files are identical.
8. `save_workflow_image` off with a workflow: the original writes the `workflow` text chunk twice (the workflow, then
   `""`); V2 writes it once, `""`, at the first position. Readers keeping the last value (Pillow, the ComfyUI
   frontend) see the same text; a reader of the first chunk saw the workflow in the original. Pixels identical.
9. WebP: image chunks (VP8/VP8L) and decoded EXIF are identical; the EXIF chunk is written by Pillow instead of
   `piexif.insert`, so its bytes differ (e.g. 748 vs 752 bytes).
10. Host started with `--disable-metadata`: the original wrote no PNG text and an empty WebP UserComment; a guest
    cannot read host flags, so V2 writes the metadata (explicit `png_text`/`a1111_parameters` bypass the switch).
11. CLIP inputs: the original inspected the live tokenizer (upstream `py/defs/formatters.py:74-83`); a guest sees an
    opaque reference, so V2 treats every CLIP input as an SD-family tokenizer (identifier `embedding:`, the embeddings
    folders). The original raised `AttributeError` for SD1Tokenizer subclasses with another clip name (no `clip_l`,
    e.g. newer text encoders) and, for a prompt with an `embedding:` word, for non-SD tokenizers; V2 writes the fields.
12. An embedding name found in several embeddings subfolders: the original's choice followed set iteration order
    (`comfy.sd1_clip.expand_directory_list`); V2 searches the root, then subfolders by depth and name. Only subfolders
    holding catalogued files are searched.
13. Limits the original did not have: the execution metadata snapshot (prompt, workflow, observations) must stay
    under 1 MiB (`comfy_api/latest/_execution_metadata.py`); PNG text keywords 1-79 Latin-1 bytes and 1 MiB total;
    the WebP A1111 payload at most 60 KiB.
14. `CreateExtraMetaData` keeps the original's shared default dict, so keys still accumulate across executions in
    one process; in V2 that process is the guest worker. Chained nodes still mutate the upstream dict in-process; when
    values cross a process boundary, other consumers of the upstream output do not see the downstream keys.
15. Local-time placeholders (`%date:...%`, `%year%`...) use the guest's clock and time zone, the host's unless the
    runtime gives guests another time zone (unverified).

## Dependencies
None for V2. The parity test's original side needs piexif 1.1.3 (pinned wheel, mounted read-only in the gate).
