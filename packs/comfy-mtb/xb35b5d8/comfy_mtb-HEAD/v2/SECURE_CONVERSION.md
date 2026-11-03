# comfy_mtb: Secure Nodes V2 conversion

**Status: 10 of the 113 ids the original registers are converted. The other 103 are registered with the original's
schema and refuse with `comfy-mtb/<id> is not yet converted to Secure Nodes V2` (plus a reason where there is one).**

Source: melMass/comfy_mtb at b35b5d8a17c0d59e80a8b3627b679c2c1003d04f (version 0.5.4).

Converted:
- Any To String
- String Replace
- Int To Number
- Pick From Batch
- Color Correct
- Image Compare
- Sharpen
- Uncrop
- Vae Decode
- Load Image Sequence

Load Image From Url is refused because it downloads from a URL at run time, and V2 nodes have no network access.

## Layout
- **`__init__.py`** (new). The original's `__init__.py` imports every module in `nodes/` at load. Those reach Core,
  `folder_paths`, `server`, OpenCV, scikit-image, onnxruntime, tensorflow, requests and more. It also registers server
  routes and static folders, and builds each id from its class name. This entry does none of that. It registers all 113
  ids in the original's order, with `WEB_DIRECTORY = "./web"` as before.
- **Schemas.**
  - `_frozen_schemas.json` holds every node's schema, frozen in the lane gate from the original classes.
  - It is read by `_frozen_schema.py`, a copy of the manifest decoder.
  - V1 option keys that the V1-to-V3 rule does not map (here, `widgetType` on 10 colour inputs) are kept in each
    input's `extra_dict`.
  - An all-node check compares every V1 option (113 nodes, 452 inputs, 688 option keys) with what the V2 schema
    serves; nothing is missing or changed.
- **`_secure_unconverted.py`** (generated) holds the 103 refusals.
  - Each validator names the node's inputs, so Core hands them over instead of rejecting a value first.
  - `execute` raises the same message if validation is bypassed.
- **`_secure_used.py`** holds the 10 converted nodes, and **`_mtb_upstream.py`** holds the original code they run:
  - 16 segments of `utils.py` and `nodes/*.py`, copied verbatim;
  - the one edit: Uncrop's progress bar (Core's `comfy.utils`) is a no-op.
- **`_vendored.py`** holds two library functions the guest does not have, both BSD-3-Clause:
  - torchvision 0.23.0 `gaussian_blur` (tensor path), used by Uncrop;
  - scikit-image 0.25.2 `compare_images`, used by Image Compare's checkerboard.
  - The parity test runs the originals with the real libraries.
- **`log.py`** and the rest of the original files stay byte-identical. Only `log.py` is imported.
- **`pyproject.toml`**: `requires-python` is `>=3.13,<3.14`.

## How each converted node runs
- **Plain values** (inputs and outputs cross as data; the original's method runs in the guest): Any To String,
  String Replace, Int To Number, Pick From Batch, Color Correct, Image Compare, Sharpen, Uncrop.
- **Vae Decode.** The VAE stays on the host.
  - Plain decode is the host's `vae.decode`, which is the original's call.
  - The tiling decoder is the host's tiled decode (Core's VAEDecodeTiled) with `tile_size` and overlap 128 pixels.
    For an 8x image VAE and `tile_size` ≥ 512, that is exactly the original's `decode_tiled(tile_x=tile_size // 8,
    tile_y=tile_size // 8)` with Core's default overlap.
- **Load Image Sequence.** It reads the frame's bytes through the SDK's assets from ComfyUI's input folder. The
  original's `[output]` / `[input]` / `[temp]` suffixes pick that folder. The original's decode then runs on those
  bytes.
  - Its fingerprint is the frame's sha256 (or `"NONE"`), as the original's `IS_CHANGED`.
- **Masks.** Pick From Batch's and Load Image Sequence's MASK outputs are made in the guest.
  - The runtime publishes a plain-values MASK output only as `[B,H,W]` or `[B,1,H,W]`.
  - The original's single-frame loader returns `[H,W]`, and a picked mask keeps its input's shape.
  - This SDK base has no public MASK constructor, so the mask crosses as a VALUE (`ValueRef.from_value`). The host
    stores exactly the original's tensor, whatever its shape.

## Known differences (each tested)
- **Any To String.** A live host object (model, VAE, CLIP, …) cannot cross to the guest as a value; the runtime
  refuses it. The original prints the object.
- **Pick From Batch.** A pick with no images (e.g. count 0 from the start) is refused by name. The original returns
  an empty IMAGE batch, which V2 cannot pass on.
- **Vae Decode.**
  - `seamless_model` is refused: the original switches the shared host VAE to circular padding in place.
  - The tiling decoder is refused for `tile_size` below 512 (the host narrows the overlap there) and for VAEs other
    than 8x image VAEs (the original divides by 8 for every VAE).
- **Load Image Sequence.**
  - Loading all frames (`current_frame` −1) or a `range` is refused by name: the original globs the server's file
    system relative to its working folder.
  - Paths outside the managed folders are refused by name; Core refuses absolute paths in the original too.
- **Uncrop** reports no progress. Its blending runs in the guest on CPU, where the original uses CUDA when it is
  available.
- **Server routes and static folders.** The `/mtb/...` endpoints and `/mtb_async` assets are not served. The
  frontend features that call them do not work: Note Plus's markdown and editor assets, sidebar actions and server
  info. Note Plus itself is a frontend-only node and never runs on the server.

## Parity (tests/, run in the gate)
- **`test_comfy_mtb_parity.py`.** The pristine node modules (with scikit-image from the test's own dependency folder)
  run against the V2 proxies, with every node body in a real guest process.
  - **Cases: 101 EXACT** (tensors byte-exact; errors equal in type and message). Any To String 10, String Replace 7,
    Int To Number 4, Pick From Batch 9, Color Correct 21, Image Compare 10, Sharpen 8, Uncrop 18, Vae Decode 4 (on a
    seeded SD-architecture VAE), Load Image Sequence 10.
  - **Known differences: 7**, each checked to differ exactly as listed.
  - **Schemas.** The converted nodes' inputs, options and outputs equal the original's.
  - **Negative control.** A one-element change in a V2 output is caught.
- **`test_comfy_mtb_production_load.py`.**
  - **Static audit.** Every import, function-local ones included, is stdlib, numpy, Pillow, torch or the SDK.
  - **Guest load.** On both guest SDK bases, with Core and the original's other libraries blocked, every row loads the
    way the guest loads it (no `__init__.py`) and matches its manifest row.
- **`encode_manifest.py`.** `secure-nodes.json` is the live encoder's output (`--check`).

## Dependencies
None beyond the guest's standard library, torch, numpy, Pillow and the SDK.
