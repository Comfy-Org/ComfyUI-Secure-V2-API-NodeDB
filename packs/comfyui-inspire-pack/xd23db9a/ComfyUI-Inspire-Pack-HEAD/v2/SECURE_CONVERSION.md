# Secure conversion report: ComfyUI-Inspire-Pack

- Pinned commit: `d23db9aa544de9a6d4c609cb7005fa9e0d42031d` (version 1.23)
- Status, round 1: **3 nodes converted**, with their original ids, schemas and display names:
  - `LoadImagesFromDir //Inspire` (Load Image Batch From Dir)
  - `LoadImageListFromDir //Inspire` (Load Image List From Dir)
  - `ChangeImageBatchSize //Inspire`
- **The pack's other declared nodes are not registered in this round.** Refusal stubs will follow in a later round. Several of their modules need the Impact Pack and ComfyUI host modules at import time.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Every symbol used is also in 0b86765f, so no minimum base applies.
- Frontend: none served. The pack's `js/` extensions belong to nodes not converted in this round. Routes: none.

## How it runs
- `__init__.py` registers only `secure_inspire.py`. The original imported all thirteen `inspire/` modules.
- `_sn_image.py` holds the three nodes. Their value-handling lines are the original's (`inspire/image_util.py`), in the original order. Each change is marked `V2:` in the code:
  - **Listing:** the folder is listed through the SDK (`ctx.assets.list`; `_sn_dir.py`), not `os.listdir`.
  - **Reading:** each image's bytes are read through the SDK (`ctx.assets.resolve` + `read_bytes`) and opened by the pack's own PIL lines.
  - **Resizing:** `comfy.utils.common_upscale` is a line-for-line copy (`_sn_comfy_utils.py`), because a guest cannot import ComfyUI.
- Permissions: `assets` for the two folder loaders; none for ChangeImageBatchSize.
- `pyproject.toml` declares `requires-python = ">=3.13,<3.14"`. Its `dependencies` are empty: the converted nodes import neither matplotlib nor cachetools.

## Folders
The original reads any folder on the host. Secure Nodes V2 reads only ComfyUI's managed folders:
- `input/<folder>`, `output/<folder>` or `temp/<folder>` select that folder. The original resolves these relative to the ComfyUI folder too.
- Any other relative path, e.g. `my_frames` or `my_frames/day1`, is a folder inside the input folder.
- Absolute paths (`C:\...`, `/...`, `\\server\...`) and `..` are refused by name, at validation and at execute.

## Parity (tier 1, CPU gate)
`tests/test_comfyui-inspire-pack_parity.py` runs the original node and v2 on synthetic image folders:
- RGB and RGBA images of mixed sizes, an EXIF-rotated JPEG, upper-case extensions, non-image files and a sub-folder.
- The original reads them by absolute path; v2 reads them through the SDK. Outputs are compared exactly.
- Covered: every sort method v2 offers, start_index (including -1), image_load_cap, the output folder, folders with no images, the original's error messages, and `IS_CHANGED` vs `fingerprint_inputs`.
- The schemas are checked through the guest class and the host proxy; ChangeImageBatchSize is checked for growing and shrinking batches.

`tests/test_comfyui-inspire-pack_guest.py` runs the nodes through the host proxy in a real guest process.

## Known differences
1. **Folders:** only folders inside ComfyUI's input, output or temp folder are read (see above). File paths from LoadImageListFromDir are the folder as entered, joined with the file name.
2. **"None" sort, or no sort saved:** files come in name order. The original used the order the host filesystem lists them in, which differs between systems.
3. **Datetime (ASC/DESC) sorts are refused:** the SDK does not expose file modification times.
4. **Edge cases:**
   - Sub-folders are not listed. The original raised an AttributeError for a sub-folder named like an image.
   - An existing but empty folder reports "cannot be found" instead of "No files in directory".
   - A folder can list at most 4096 files, and an image can be at most 64 MiB.
   - No image left after filtering, start_index and the cap: not a difference. The original returns nothing, which ComfyUI rejects with `TypeError: object of type 'NoneType' has no len()`. A V3 node returning nothing would finish without outputs, so v2 raises that same error.
5. **pillow-jxl:** if it is installed, the original also accepts files ending in `.`, `j`, `x` or `l`, because of how it extends its extension list. A guest has no pillow-jxl.
6. **Errors:** an error raised while a node executes in the guest reaches ComfyUI as a transport error (`WireError`), whose text is the original exception type and message.
7. `/object_info` `python_module` is the secure mount path.
