# comfy-image-saver (giriss): Secure Nodes V2 conversion

**Status: converted 9 of 9 declared nodes; 0 refused.** Five saver behaviours that V2 cannot reproduce exactly are refused
with named errors (see Known differences). This is the 2026-11-02 repair of the 2026-10-26 conversion.

- **Upstream:** giriss/comfy-image-saver @ `65e6903eff274a50f8b5cd768f0f96baf37baea1` (MIT).
- **Minimum SDK base 0cd9adec.** The saver uses `png_text`, `a1111_parameters` and `graph.execution_metadata()`, none of
  which exist in 0b86765f.

## Node ids
These are the original `NODE_CLASS_MAPPINGS` keys (`nodes.py:269-279`), unchanged and in order:
"Checkpoint Selector", "Save Image w/Metadata", "Sampler Selector", "Scheduler Selector", "Seed Generator",
"String Literal", "Width/Height Literal", "Cfg Literal", "Int Literal".

The original has no display-name mappings, so each display name is the id. The 2026-10-26 conversion registered
sanitized, hash-suffixed ids instead of these; this repair restores the originals.

## How the nodes run
- **Seed Generator and the four literals:** pure values. No permissions.
- **Sampler Selector and Scheduler Selector:** the same choices as the original, from core's lists at ComfyUI 6257422b
  (`_catalogues.py`).
- **Checkpoint Selector:** `assets`. `web/catalogues.js` fills the menu from the host checkpoint catalogue, and
  `validate_inputs` checks membership at queue time.
- **Save Image w/Metadata:** `assets`, `output` and `graph.metadata`.
  - `assets` resolves the checkpoint and gives its sha256 for "Model hash".
  - `output` is the SDK image writer.
  - `graph.metadata` reads prompt/extra_pnginfo. These are declared as hidden inputs, as in the original
    (`nodes.py:199-202`), and read with `ctx.graph.execution_metadata()`, which returns the same original prompt and
    extra_pnginfo.
  - The filename, path and comment code is the original's, unchanged (`_saver.py`).

## Tests (`tests/`, run in the gate container)
- **`test_comfy_image_saver_parity.py`** compares the original in-process with V2 in a real guest process, over 216 cases.
  - **All 9 nodes are EXACT:** values (type-strict, float bits), schemas, queue-time validation, and the filename algorithm
    under a frozen clock.
  - **PNG output is byte-identical**, including UI payloads and colon names.
  - **WebP output is identical after decoding** (see below).
  - Five behaviours are refused as designed (JPEG, overwrite, duplicate key, path escape, backslash), and a negative
    control turns the comparator red.
- **`encode_manifest.py`** shows that `secure-nodes.json` is the live encoder's output, and that the real loader registers
  the nine original ids.
- **`combo45_link_check.py`** is labelled evidence for selector-output links on two cores (see 7 below). It is not part of
  tier-1.

## Known differences
1. **JPEG is refused**, with a named error. The original saves with Pillow's default 4:2:0 chroma subsampling, but the V2
   writer always uses 4:4:4 and has no subsampling option. (API ask.)
2. **Existing file:** the original overwrites it. The V2 writer never overwrites, so V2 raises
   `FileExistsError: comfy-image-saver/Save Image w/Metadata: <names> already exists. The original overwrites it, but the
   V2 image writer never overwrites files; use %time or %counter in the filename.` (API ask: explicit overwrite for exact
   names.)
3. **Duplicate PNG text keys** (extra_pnginfo containing "parameters" or "prompt") are refused with a named error. The
   original writes duplicate chunks; the writer's `png_text` is a dict.
4. **Output names** follow the writer's rules, each refused with a node-prefixed named error:
   - absolute paths, a drive prefix (`C:` or `C:/…`) and `..` segments leave the output folder (the original writes
     outside it);
   - a backslash is refused because the writer treats it as a path separator, while the original writes it literally;
   - a mid-name `:` (e.g. `%H:%M:%S`) works exactly as in the original.
5. **WebP:** pixels, EXIF UserComment and every image chunk are byte-identical. Only the EXIF chunk differs: 420 bytes from
   Pillow vs 416 from piexif. Pillow writes the Exif sub-IFD's TIFF-required 4-byte next-IFD offset, and piexif omits it,
   so UserComment sits at 0x2c vs 0x28. The tags and payload are the same, and the files are not byte-identical.
6. **Writer bounds** that the original lacks raise named SDK errors:
   - PNG text: at most 1 MiB, with Latin-1 keywords of at most 79 bytes;
   - WebP UserComment: at most 60 KiB.
7. **Selector outputs (Combo.Output, partial).** The original returns its choice list as the output type, so its
   outputs link into KSampler and CheckpointLoaderSimple inputs.
   - On core 6257422b the V2 outputs are typed COMBO, and core refuses those links (`return_type_mismatch`).
   - Core 45c05a86 and later accept the Sampler and Scheduler Selector links, because their options are declared. That
     change is not yet adopted by the runtime.
   - Checkpoint Selector declares no options and stays partial.
8. **The sampler and scheduler choice lists are static** (core 6257422b order). The original reads them live, so names
   that other packs add at runtime are not offered.
9. **A non-catalogue checkpoint name** is refused at queue time by both, but V2's message is the pack's own ("Checkpoint is
   not in the current checkpoints catalogue"), not core's "Value not in list".

## Dependencies
- The guest has none (`pyproject.toml` dependencies = []).
- `piexif` 1.1.3 is used only by the original, inside the parity test. So `requirements.txt` (piexif) is the one pristine
  file not copied into v2. LICENSE, README.md, example-workflow.json and .gitignore are unchanged copies.
