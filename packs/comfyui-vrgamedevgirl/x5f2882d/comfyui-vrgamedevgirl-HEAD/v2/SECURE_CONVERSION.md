# comfyui-vrgamedevgirl: Secure Nodes V2 conversion (partial)

Upstream: https://github.com/vrgamegirl19/comfyui-vrgamedevgirl at `5f2882d835bfa616feed7b73ab102775ab8de64d`
(v9.1.1, 2026-09-26), key `x5f2882d`. UNRUN-IN-GUEST: tier-1 parity ran in the lane gate, not in a guest or browser.

**Status:** converted 6 of 264 registered nodes. 258 are refused as unconverted. One declared
node is not registered, the same as in the original without its dependency pack (see below).

## Why this commit
This revision converts six types: FastFilmGrain, ColorMatchToReference, FastUnsharpSharpen,
FastLaplacianSharpen, VRGDG_LUTS and VRGDG_MultiStringConcat.
- `8e595af` (2026-09-28, "Reorganize pack into feature packages for 2.0") moved the root `nodes.py` into
  `optional_nodes/general_utilities/`, which its README says "are not loaded by the main pack".
- `f90cad3` (2026-11-02, "Remove standalone optional node packs") deleted them. At today's HEAD only
  VRGDG_MultiStringConcat remains.
- `5f2882d8` is the parent of `8e595af`, the last commit whose `__init__` registers all six.

## What v2 contains
- `__init__.py` is replaced by a safe entry. The original imports 59 submodules (folder_paths, server, aiohttp,
  librosa, torchaudio, cv2, transformers, ...) and writes placeholder files under the output folder at import. The
  safe entry registers `_secure_used.py` and `_secure_unconverted.py` only, and serves no frontend files.
- `_vrgdg_used_original.py` holds the six classes copied verbatim: AST segments of `nodes.py` L172-443,
  `VRGDG_IV_Adjustments.py` L7-36 and L140-361, and `VRGDG_GeneralNodes2.py` L2149-2191, with the line ranges and file
  hashes in its header. Boundary edits:
  - `comfy.model_management` is a local stand-in answering the CPU device, so the original device lines stay
    byte-identical;
  - `kornia` points to `_vendor_kornia_color.py`;
  - VRGDG_LUTS parses the bytes of its asset instead of opening a file in the pack folder (3 asserted edits).
- `_secure_used.py` defines the V2 classes; each `execute` calls the original method.
  - The four image nodes use public value mode (`SDK_REFS = False`, "raw"; precedent: comfyui-advanced-photo-grain v2).
  - VRGDG_LUTS gets its `.cube` file from the `vrgdg_luts` asset kind (`asset_directories`). This follows
    comfyui_essentials v2 (`image.py:1793`, "essentials_luts"); the host registers the kind. A name the host does
    not have is a named refusal at queue time.
  - The original's folder-mtime `IS_CHANGED` becomes a content-digest fingerprint.
- `_vendor_kornia_color.py`: kornia 0.8.3's RGB<->Lab path, copied verbatim from
  `kornia-0.8.3-py3-none-any.whl` (sha256 `0b15f5d3…`, the hash pinned in the guest's expanded-base lock), under
  Apache-2.0. The sealed guest base (`guest_common.lock`, 41 pins) has no kornia.
- `_secure_unconverted.py` holds one generated class per unconverted node, built from `_frozen_schemas.json`.
  - The schemas were frozen in the gate from the original classes: `freeze_v1.py` plus the backend's
    `generate_pack_schema_data.py`, decoded by `_frozen_schema.py`, a copy of the manifest decoder.
  - Each node's `validate_inputs` names its inputs and returns `"comfyui-vrgamedevgirl/<node> is not yet converted to
    Secure Nodes V2"`; `execute` raises the same message.
  - A V1 node's description is its `DESCRIPTION` attribute (Core's rule), not the class docstring the generator uses.
  - V1 option keys that have no V3 parameter are kept in the input's `extra_dict`, so the frontend gets the
    original's options. There are 12 such inputs on 6 nodes: `label` (7), `password` (1, VRGDG_VideoPromptReconstructor
    `api_key`), `precision` (2) and `dynamic` (2). The generator had dropped them for INT, FLOAT, STRING and BOOLEAN
    inputs.
- `pyproject.toml`: Python `>=3.13,<3.14` and no dependencies. `secure-nodes.json` comes from the real encoder. The two
  API stubs are byte copies of the published pair. `tests/` holds the parity test.

## Parity (tier 1, gate)
`tests/test_vrgamedevgirl_parity.py` compares originals against v2 on seeded fixtures. Tensors are compared with
`torch.equal` (dtype, shape and bytes), strings by equality, and errors by type and message.

| Node | Verdict | Cases |
|---|---|---|
| FastFilmGrain | EXACT | 240 |
| ColorMatchToReference | EXACT | 36 |
| FastUnsharpSharpen | EXACT | 64 |
| FastLaplacianSharpen | EXACT | 64 |
| VRGDG_LUTS | EXACT | 330 |
| VRGDG_MultiStringConcat | EXACT | 400 |
| 258 unconverted | REFUSED-AS-DESIGNED | 258 |

- FastFilmGrain draws unseeded noise upstream, so both sides run after the same `torch.manual_seed`.
- For ColorMatchToReference, the original runs kornia 0.8.3 from the gate image and v2 runs the vendored copy.
- The VRGDG_LUTS cases use fixture LUTs: 3D sizes 2-17, DOMAIN, CRLF, malformed and 1D files.
- Every schema round-trips to its frozen form, and `secure-nodes.json` equals the encoder's output.
- The negative control turns red.
- An import guard is installed before v2 loads and stays for the whole run. Every import that v2 code executes,
  function-local ones included, must come from the standard library, the sealed guest base (`guest_common.lock`, 41
  pins) or v2 itself. None is blocked. The guard's own check blocks kornia, which the gate has and a guest lacks.

## Known differences
- **Not registered:** `VRGDG_LTXVLoopingSamplerAdvanced` (module `VRGDG_LTXLoopingSampler`). It subclasses a class
  from the separate ComfyUI-LTXVideo pack, so its schema cannot be frozen. The original also fails to import it when
  that pack is absent.
- **Device:** computation runs on the guest's CPU device. On a CUDA host the original ran these nodes on the GPU, so
  float results can differ in the last bits. FastFilmGrain's noise is random in both versions. Tier 2 covers this.
- **LUT error text:** VRGDG_LUTS error messages name the LUT instead of a host path.
- **VRGDG_MultiStringConcat:** the original's frontend script that hid the unused string boxes is not served; all 20
  boxes show. The values and the output are unchanged.
- **Frontend:** no original frontend file is served. The 258 unconverted nodes refuse, so their custom widgets do not
  matter for running.
