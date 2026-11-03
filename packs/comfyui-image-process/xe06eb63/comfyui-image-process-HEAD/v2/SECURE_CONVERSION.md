# comfyui-image-process: Secure Nodes V2 conversion

**Status: 1 of 18 registered nodes converted (SaveImageBMP). The other 17 are registered with the original's schema and
refused by name. SaveImageJPG's body is ready behind a one-line switch until the SDK's JPEG writer can write what the
original writes.**

Source: wakaura-asaho/comfyui-image-process at e06eb63e502efd7c1bc8e1128df349d75058835f.

## Layout
- **`_secure_nodes.py`** holds all 18 classes.
  - Each docstring and `define_schema` is the original's from `image_process.py`, copied verbatim; the only edit is
    LoadICCProfile's profile list (below).
  - `ImageSaveHelperExt.resolve_filename_prefix` is copied verbatim from `image_helper.py`.
  - The module imports only the standard library, numpy, Pillow, the SDK and `define.py`. It never imports
    `image_process.py` or `image_helper.py`, which import scipy, scikit-image, piexif and ComfyUI's `folder_paths`.
- **`__init__.py`** is the original, with two edits:
  - it imports the classes from `_secure_nodes`;
  - it no longer creates and registers `models/icc_profiles` at import. LoadICCProfile, the only node that used that
    folder, is refused.
- **`pyproject.toml`** declares `requires-python`, and scipy is dropped from its dependencies.
- **Unchanged:**
  - `image_process.py`, `image_helper.py`, `define.py`, `web/image_process.js` and the rest stay byte-identical;
  - no manifest row reaches `image_process.py` or `image_helper.py`;
  - the frontend file has no server routes and is served as before (`web_directory`).

## Converted: SaveImageBMP
The original resolves its own filename tokens:
- `%date:yyyy-MM-dd%`-style dates;
- `%year%` … `%second%`;
- `%width%`, `%height%`.

It then calls Core's `get_save_image_path` and saves each image as `<name>_<counter:05>_.bmp` (with `%batch_num%`
replaced). The image is `Image.fromarray(np.clip(255 * image, 0, 255).astype(np.uint8)).convert("RGB")`, saved with
`dpi=(72, 72)`.

V2 resolves the same tokens with the same code in the guest. The SDK's image writer then runs Core's
`get_save_image_path`, applies the same naming and quantizes the same way.
- Pillow decides what `convert("RGB")` does with the channel count, as in the original. The node reads the batch's
  shape with `describe()`, so no pixels move to the guest.
  - 3 channels go to the writer unchanged.
  - RGBA images go as their first three channels (`rgb()`, host-side); `convert` drops alpha.
  - Channel counts Pillow can't read raise Pillow's own TypeError, as in the original.
- Permissions: `inspect` for `describe()`, `output` for the writer.

## Refused, by name
Validation fails, and so does execution, with
`comfyui-image-process/<id> is not yet converted to Secure Nodes V2: <reason>`. The reasons:
- **SaveImageJPG.** The SDK's JPEG writer always uses 4:4:4 chroma subsampling and has no dpi option. The original
  saves with Pillow's default 4:2:0 at 72 dpi, so the decoded pixels differ (up to 53/255 on test images).
  - The body is written and gated by `_JPEG_WRITER_OPTIONS`.
  - Once the writer declares the options, setting them there turns the node on.
- **Colour tools.** ColorPatchFlatten (scikit-image), ColorPatchMerge (scipy, scikit-image, OpenCV) and
  AchromaticStabilizer (scipy) need libraries the V2 guest does not have; no dependency profile is declared.
- **LoadICCProfile.** It reads profile files from `models/icc_profiles`, for which V2 has no catalogue.
  - Its schema's profile list is `[]`. The original lists the readable profiles there, which is `[]` on a fresh
    install.
- **SaveImageAdvancedCustom, SaveImageAdvancedJPG, SaveImageAdvancedBMP, SaveImageAdvancedTIFF,
  SaveImageAdvancedAVIF.** Their ICC profiles, dpi, compression, EXIF/TIFF metadata, alpha masks and saving into the
  input folder need image-writer options the SDK does not declare.
- **SaveImageTIFF.** It joins alpha masks and shows temporary PNG previews, and the SDK's TIFF writer has no dpi
  option.
- **SaveImageAVIF.** The SDK's AVIF writer has no speed or dpi option.
- **SaveImageTGA, SaveImageAdvancedTGA, SaveImageICO, SaveImageAdvancedICO.** The SDK has no TGA or ICO writer.
- **ICOPacker.** It only prepares SaveImageAdvancedICO's input.

## Known differences (SaveImageBMP)
- **Resolution field.** The BMP header records 96 dpi (Pillow's default; the SDK writer has no dpi option), where the
  original records 72 dpi. These are the two 4-byte resolution fields. Every other byte, and so every pixel, is the
  original's.
- **2-channel (grey + alpha) IMAGE.** The original saves the grey channel as RGB. V2 refuses it by name, because the
  writer has no grey-to-RGB conversion.
- **Prefix outside the output folder.** Both refuse; the message is the SDK writer's, not Core's.
- **No overwriting.** The SDK writer never overwrites a file; the original does. With the counter this only matters
  for names the counter can't see: a `%batch_num%` prefix reuses its names on a second run, which the original
  overwrites and V2 refuses ("output image already exists").
- **Clock.** Filename date and time tokens use the guest's clock and time zone.

## Parity (tests/, run in the gate)
- `test_comfyui_image_process_parity.py`:
  - **Setup.** The original classes are defined from the pristine source. The V2 side is the manifest proxies, with
    every node body in a real guest process. Both run the same prompts through Core's PromptExecutor.
  - **Schemas.** All 18 encode exactly as the original's.
  - **SaveImageBMP.** 13 cases. EXACT in 10 (file names, UI, decoded pixels, and every byte except the resolution
    fields): defaults; a batch of 3 with a subfolder and `%batch_num%`; clipping; RGBA; exact and half-step 8-bit
    levels; the pack's tokens; 1x1; the counter on a second run; 1- and 5-channel errors. The other 3 are the known
    differences above (2 channels, a prefix outside the output folder, a `%batch_num%` prefix run twice), each checked
    to differ in exactly that way.
  - **Refusals.** All 17 refused nodes are REFUSED-AS-DESIGNED, at validation and at execution.
  - **Negative control.** A one-byte change in a V2 output is caught.
- `test_comfyui_image_process_production_load.py`:
  - **Static audit.** Every import in the modules the rows reach, function-local ones included, is stdlib, numpy,
    Pillow or the SDK.
  - **Guest load.** On both guest SDK bases, with Core, scipy, scikit-image, OpenCV and piexif blocked, each row loads
    the way the guest loads it (no `__init__.py`) and matches its manifest row.
- `encode_manifest.py`: `secure-nodes.json` is the live encoder's output (`--check`).

## Dependencies
None beyond the guest's standard library, numpy, Pillow and the SDK.

## API asks
Either of these turns SaveImageJPG on exactly:
- (a) JPEG subsampling and dpi options on the image writer;
- (b) a bounded raw-bytes output writer, so the guest encodes with Pillow as the original does.

(b) would also cover the TGA, ICO, AVIF, TIFF and BMP options above.
