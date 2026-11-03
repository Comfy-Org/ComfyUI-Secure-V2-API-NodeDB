# Secure Nodes V2 conversion: mikey_nodes

- Upstream: bash-j/mikey_nodes at `a5aa9cf637c4aa83fb369230e1cd728f4f56a8de` (version 1.0.5).
- Status:
  - 16 of the 73 declared nodes are converted.
  - Batch Load Images is refused by name.
  - The other 56 keep their original schemas and refuse at queue time with "mikey_nodes/<node id> is not yet
    converted to Secure Nodes V2".
- The pristine tree and v2/ omit upstream media, example workflows and bundled model files: HaldCLUT/*.png,
  noise.png, noise_bw.png, haar_cascade_models/*.xml and six workflow JSONs. The nodes that use them are not converted.
- No Python dependencies. The converted code uses numpy, PIL and torch from the guest base.

## Converted nodes
| Node id | V2 |
|---|---|
| Int to String, Range Integer, Seed String, TextConcat, RemoveTextBetween | the original methods |
| FileNamePrefix, FileNamePrefixDateDirFirst | the original methods (date, `%date:...%` and `%Node name.widget%` replacement) |
| Upscale Tile Calculator, Resize Image for SDXL | the original methods; the resize is Core's `common_upscale` |
| Empty Latent Ratio Select SDXL | the original method on the pack's ratios.json |
| Wildcard Processor, WildcardOobaPrompt | the original methods, reading wildcard files from the `mikey_wildcards` asset kind |
| Checkpoint Loader Simple Mikey | the engine loads the checkpoint; `ckpt_hash` is the file's sha256, first 10 hex digits |
| MikeySamplerTiledAdvancedBaseOnly | the original steps; the engine samples, encodes, decodes and runs the upscale model |
| Save Images Mikey, Save Images No Display | the original file naming and counters, written by the SDK image writer |

## How it runs
- `v2/__init__.py` imports no original module.
  - The original mikey_nodes.py imports folder_paths, nodes, comfy, latent_preview, spandrel and requests at import.
  - It stays in v2/ byte-identical and is never imported.
- `_mikey_upstream.py` holds the original helpers and node classes, copied verbatim as AST source segments, with
  line ranges and the file's sha256. Its stand-ins:
  - the user directory does not exist in the guest;
  - Core's `common_upscale` and `ImageScale` are copied verbatim from ComfyUI (GPL-3.0) in `_core_upscale.py`.
- `_mikey_wildcards.py` holds the original `find_and_replace_wildcards`, verbatim.
  - It reads a read-only in-memory tree of the `mikey_wildcards` asset kind, loaded through the SDK before each run.
  - The original read `<user directory>/wildcards`.
- MikeySamplerTiledAdvancedBaseOnly and the save nodes are ported line for line (`_secure_used.py`).
  - Their host steps go through the SDK: sampling, VAE, upscale model, output listing, and writing.
  - Tiling, stitching and file naming are the original code.
- The save nodes write PNG text chunks in the original's order: prompt, each extra_pnginfo key, extra_metadata.
- Hidden inputs (prompt, extra_pnginfo, unique_id) are declared and read through the V2 schema.
- The two model menus are the host's catalogues, `/models/checkpoints` and `/models/upscale_models`.

## Refused
- **Batch Load Images.** It loads every image in a directory path typed into the node, anywhere on the host's file
  system. A guest can read only the host's catalogued folders.
- **WildcardOobaPrompt with `<llm:...>`.** That text is sent to a text-generation server over the network, and a
  guest has no network. Prompts without it run.
- **The other 56 declared nodes**, by name, at queue time.

## Known differences
1. **Wildcards.** The host must provide the `mikey_wildcards` asset kind. The original uses the user directory's
   wildcards folder, or ComfyUI's wildcards folder when that is missing.
   - Without the kind, a prompt that names a wildcard fails with `WildcardsUnavailableError`.
   - A prompt without wildcards runs unchanged.
2. **User ratios.** Empty Latent Ratio Select SDXL offers the pack's ratios only. The original also adds the user
   directory's `user_ratios.json`.
3. **Range Integer.** Its INT output is a Python int with the same value. The original returns numpy's int64, which
   cannot cross the guest wire.
4. **Shared prompt data.** In the original, WildcardOobaPrompt writes its result into the shared prompt data, and
   other nodes' edits to extra_pnginfo reach the save nodes' metadata. In V2 each node receives its own copy.
5. **Checkpoint hash.** It is always the file's sha256. The original caches hashes by file base name in the temp
   folder, so it can return a stale or same-name entry.
6. **Save nodes.**
   - They never overwrite a file. The original overwrites an existing name when counter_type is none; V2 raises a
     named FileExistsError instead.
   - Counters read the sub-directory's files in sorted order. The original's directory listing also includes folders,
     in file-system order; this matters only when a name that cannot be parsed stops its counter scan.
   - An absolute sub_directory is refused, and the writer refuses `..`, file names with no elements, and PNG text
     over 1 MiB.
   - A repeated PNG text key is refused: an extra_pnginfo key named "prompt" or "extra_metadata". The original writes
     the duplicate chunk.
7. **Unseeded randomness.** WildcardOobaPrompt's `{a|b}` choice uses the guest's own random stream.
8. **Engine steps.** Sampling, the VAE, the upscale model and checkpoint loading are the engine's (Core's own code).
   The parity test covers them only through identical stand-ins.

## Parity
`tests/test_mikey_nodes_parity.py` runs in the lane gate.
- Both sides run every converted node on generated cases: the pristine mikey_nodes.py under Core, and these classes
  with a fake SDK context.
- Fixtures are synthetic: images, wildcard files, a small checkpoint file and a synthetic workflow.
- The clock is frozen at the same instant on both sides.
- Strings, numbers, tensors, saved PNG files (bytes, names, folders), errors (type and message) and the manifest
  (against the real encoder) are compared exactly.
