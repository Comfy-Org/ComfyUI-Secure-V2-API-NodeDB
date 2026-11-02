# Secure Nodes V2 conversion: comfyui_image_metadata_extension

**Status: converted 2 of 2 declared nodes** (`SaveImageWithMetaData`, `CreateExtraMetaData`); 0 nodes refused.
`SaveImageWithMetaData` refuses four behaviours by name (`modules/_v2_refusals.py`). **Minimum guest SDK base:
0cd9adec** (comfy_api 0.37.0): it uses `graph.execution_metadata` and the image writer's `png_text` /
`a1111_parameters`, which base 0b86765f lacks.

Upstream: https://github.com/edelvarden/comfyui_image_metadata_extension @ `0fbd59eed23268d46ac43c110246a7dcaa09295b`
(v1.3.4, GPL-3.0). Node ids, display names, categories, inputs, tooltips, defaults and outputs are the original's.

## What changed (boundary only)
- `modules/__init__.py`, `modules/hook.py`: the executor monkeypatches (`PromptExecutor.execute`,
  `execution.get_input_data`) are gone. The save node asks the broker for the running prompt and its observed node
  inputs and outputs (`ctx.graph.execution_metadata(include_observations=True)`, permission `graph.metadata`);
  `modules/_v2_capture.py` rebuilds the `get_input_data` view the capture code reads. `capture.py`, `trace.py` and
  `defs/` keep the published algorithms (three import lines in `capture.py` changed).
- `modules/defs/formatters.py`, `modules/utils/hash.py`, `modules/utils/embedding.py`: model and embedding names are
  looked up in the asset catalogue instead of `folder_paths`; hashes come from `assets.digest` (same first 10 hex
  digits of SHA-256, same in-memory cache keyed by file name).
- `modules/config.py`: no `.cache` folder is created in the (read-only) pack folder.
- `modules/nodes/node.py`: V3 `io.ComfyNode` schemas; the save loop is the original's, writing through
  `ctx.output.save_images` (PNG `png_text`, WebP `a1111_parameters`) and `ctx.output.write_text` (workflow JSON).
  Hidden `prompt` and `extra_pnginfo` are declared and read through the schema (`cls.hidden`).

## Parity (tier 1, gate `run_in_gate.sh`, core 6257422b executor)
`tests/test_comfyui_image_metadata_extension_parity.py` runs every case through the real executor three times: the
unmodified original, the original plus a harness-only cache adapter (the reference), and V2. Each case declares its
expected outcome. On core 6257422b the pinned original cannot capture: `OutputCacheCompat` (`modules/capture.py`)
falls back to the output cache's `get()`, which is async there (`comfy_execution/caching.py:384`), so
`execution.get_input_data` (`execution.py:294`) receives a coroutine and every capturing save fails with
`AttributeError: 'coroutine' object has no attribute 'outputs'` (upstream issue). The reference restores the
synchronous accessor of the ComfyUI releases the original targets (`HierarchicalCache.get_cache = get_local`,
`tests/edelvarden_parity_worker.py`, `ADAPTER`).

## Known differences
Named refusals (`SecureConversionRefusal`):
1. `output_format` `jpg` / `jpg_with_json`: the writer encodes JPEG 4:4:4 with its own EXIF; the original used
   Pillow's default subsampling plus piexif.
2. A `subdirectory_name` leaving the output folder (`..`, absolute): the original joined it to the output folder
   without a check and wrote there; V2 writes only inside the output folder.
3. A backslash in `subdirectory_name` or `filename_prefix`: on a Linux host the original kept it as a name
   character; the writer treats it as a folder separator.
4. `filename_prefix` with a folder part while `subdirectory_name` is set: the original created only the subdirectory
   and wrote into `<subdirectory>/<prefix folder>/` only if that folder already existed (otherwise
   `FileNotFoundError`); the writer would create it.

Documented behaviour differences (each shown by a gate case):
5. UI records: the original reported the absolute host folder as `subfolder`; V2 reports the folder relative to the
   output root. Both point at the same file.
6. A `filename_prefix` leaving the output folder: both raise `Exception("**** ERROR: Saving image outside the output
   folder is not allowed. ...")`; the original's message names host paths, V2's names relative paths.
7. PNG batches: the original reused one `PngInfo` for the whole batch, so images 2+ repeat every text keyword; V2
   writes each keyword once with the last value, at its first position. Readers keeping the last value (Pillow, the
   ComfyUI frontend) see the same text; a reader of the first chunk saw the first image's parameters in the original.
8. WebP: image chunks (VP8/VP8L) and decoded EXIF are identical; the EXIF chunk is written by Pillow instead of
   `piexif.insert`, so its bytes differ.

Not shown by a gate case:
9. Model-hash disk cache: the original also kept `.cache/model_hash_cache.json` in its pack folder (keyed by file
   name and modification time) and created that folder at import; V2 keeps the in-memory cache only and hashes the
   current file.
10. Limits the original did not have: the execution metadata snapshot (prompt, workflow, observations) must stay under
    1 MiB (`comfy_api/latest/_execution_metadata.py`); PNG text keywords 1-79 Latin-1 bytes and 1 MiB total; the
    WebP A1111 payload at most 60 KiB.
11. With several embeddings folders, the original probed each folder in turn; the catalogue answers for all of them
    at once (the first folder holding the file wins in both).
12. Local-time placeholders (`%date:...%`, `%year%`...) use the guest's clock and time zone, the host's unless the
    runtime gives guests another time zone (unverified).

## Dependencies
None for V2. The parity test's original side needs piexif 1.1.3 (pinned wheel, mounted read-only in the gate).
