# Secure Nodes V2 conversion: ComfyUI_Mira

- Upstream: mirabarukaso/ComfyUI_Mira at `dfb1c847097cf1f69055c46c24b723a5a55f2e09` (version 0.6.0.1). The pack is
  V3-native: it registers 82 io.ComfyNode classes through comfy_entrypoint().
- Status:
  - 14 of the 82 nodes are converted.
  - The other 68 keep their original schemas and refuse at queue time with "comfyui_mira/<node id> is not yet
    converted to Secure Nodes V2".
  - Image Color Transfer refuses its two OpenCV methods by name (below).
- The pristine tree and v2/ omit the upstream media under examples/ (screenshots and two videos), per the lane's
  omission policy. The json/ data files stay.
- No Python dependencies. The converted code uses torch, numpy and Pillow from the guest base. The torchvision and
  color-transfer code it needs is vendored.

## Converted nodes
| Node id | V2 |
|---|---|
| CanvasCreatorAdvanced, CanvasCreatorSimple, SeedGeneratorMira | Util.py's classes, verbatim |
| IntToFloatMultiplication, NumeralToString, StepsAndCfg | Arithmetic.py and Numeral.py's classes, imported as they are |
| TextBoxMira, TextCombinerSix, TextCombinerTwo | Text.py's classes, imported as they are |
| illustrious_character_select_en | the original class, verbatim, on the pack's character list (json/) |
| ImageContrast, ImageSharpness | Util.py's classes, verbatim, on the image tensor (values mode) |
| ImageColorTransferMira | Util.py's class, verbatim; Mean and Pdf run, Lab and Pdf+Regrain are refused |
| UpscaleImageByModelThenResize | ported line for line: the engine runs the upscale model, the resize is the original's |

## How it runs
- `v2/__init__.py` imports none of the original modules that reach host code. Util.py, Tagger.py, Lora.py, Mask.py,
  Logic.py and image_saver/ import cv2, onnxruntime, comfy, folder_paths, requests, piexif or torchvision when they
  load.
  - All original files stay in v2/ byte-identical.
  - v2 imports Arithmetic.py, Numeral.py, Text.py and v3schema.py as they are, since they need only comfy_api.
- Every schema is the original class's own V3 schema, frozen in the lane gate by encoding each class's GET_SCHEMA()
  (`_frozen_schemas.json`, read by `_frozen_schema.py`).
- Each converted node is a new io.ComfyNode class whose execute calls the original class's execute. No V2 class
  subclasses an original class.
- Verbatim copies, each block with its line range and the file's sha256:
  - `_mira_util.py`: Util.py's helpers and classes.
  - `_mira_color_transfer.py`: color_transfer.py.
  - `_mira_wai.py`: the English character selector, plus main()'s character-list loading for the shipped CSV, without
    the download.
- `_vendor_torchvision.py`: the PIL-image path of torchvision 0.23.0's adjust_contrast, adjust_sharpness and Resize,
  copied verbatim (BSD-3-Clause) from the lane gate's installed torchvision. ImageContrast, ImageSharpness and the
  resize pass PIL images.
- UpscaleImageByModelThenResize:
  - The original's upscale() is core's ImageUpscaleWithModel. The engine's UpscaleModelRef.upscale(images,
    tile_size=512) runs the same steps: tiled_scale with 512 tiles and 32 overlap, the tile halved on OOM, then clamp.
  - Everything else is the original's code, on the tensors.
  - The output image is created with ImageRef.from_value, so the minimum guest base is 0cd9adec.

## Refused
- **Image Color Transfer, methods Lab and Pdf+Regrain.** The original computes them with OpenCV (cv2.cvtColor; the
  regrain pyramid's cv2.resize), and the guest runtime has no OpenCV. The node's first method, Mean, is unaffected,
  and so is Pdf.
- **The other 68 nodes**, by name, at queue time.

## Known differences
1. **Character list.** The selector reads the pack's shipped json/waiIllustriousSDXL_v160_characters.csv. When that
   file is missing, the original downloads it from GitHub at import; a guest has no network.
2. **Engine step.** The upscale model runs in the engine (Core's own code). The parity test covers it only through
   identical stand-ins.

## Parity
`tests/test_comfyui_mira_parity.py` runs in the lane gate.
- Both sides run every converted node on generated cases: the pristine pack under Core, and these classes behind a
  guest import guard that stays installed while the cases run.
- Compared exactly: tensors (dtype, shape and bytes), numbers, strings, and errors (type and message).
- For all 82 ids, the encoded V3 schema and the V1 projection (INPUT_TYPES) equal the original's.
- Every refusal is checked by name, and the manifest is compared with the real encoder's output.
- A mutant run must turn red.
`tests/test_comfyui_mira_production_load.py` loads every manifest row the way a guest does, on both guest bases, with
Core, OpenCV, torchvision, requests, onnxruntime, piexif and tqdm blocked.
