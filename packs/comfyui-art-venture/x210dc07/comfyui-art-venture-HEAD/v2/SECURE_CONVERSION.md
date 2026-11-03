# Secure Nodes V2 conversion

Pinned upstream commit: `210dc072b1f103f91be18a33bdeb13ab315aaae5`
Upstream: `https://github.com/sipherxyz/comfyui-art-venture`

## Census and terminal status

- Every node id the original registers on its own is registered here with its
  original schema, frozen from the original (`_frozen_nodes.json`). That
  means without the optional packs it integrates with (Impact Pack,
  IPAdapter, AnimateDiff, VideoHelperSuite, efficiency nodes, ControlNet
  auxiliaries). The served node info equals the original's
  (`tests/test_artv_schemas.py`).
- Converted (`utility_nodes.py`):
  - `StringToInt`, `BooleanPrimitive`, `SeedSelector`;
  - `SDXLAspectRatioSelector`, `AspectRatioSelector`;
  - `ImageScaleDownBy`, `ImageScaleDownToSize`, `ImageScaleToMegapixels`;
  - `ImageGaussianBlur`, `ImageApplyChannel`;
  - `CheckpointNameSelector`, `RandomInt`, `RandomFloat`.
- Converted (`loader_nodes.py`): `AV_LoraLoader`, `AV_VAELoader`.
- Every other id is refused by name at queue time ("not converted to Secure
  Nodes V2 yet"), and again at run time. Nothing is approximated. These are
  refused with their own reason:
  - `MergeModels`: it merges two models' weights, and the guest SDK has no
    model-merge operation;
  - `Fooocus_KSampler` and `Fooocus_KSamplerAdvanced`: they patch Core's UNet
    forward and SDXL conditioning for the whole process while they sample;
  - `AV_ControlNetPreprocessor`: its preprocessors are another pack's code
    (comfyui_controlnet_aux). Without that pack the original fails too;
  - `LaMaInpaint` and `LoadLaMaModel`: the LaMa model is a TorchScript
    archive, which V2 does not load.
- Not registered: the nodes the original adds only when an optional pack is
  installed (for example `AV_FaceDetailer`, `AV_IPAdapter`).
- Frontend extensions (`web/`): not served (not converted).

## What runs where

- Every converted node runs in the guest with the original's own code: the
  same conversions (`modules/utils.py`), the same Pillow resampling and blur,
  and the same torch operations.
- Images and masks arrive as tensor refs and are read exactly.
- `ImageScaleToMegapixels` upscales below 1.2x, or without an upscale model,
  with the bicubic interpolation that core's `common_upscale` uses. With a
  connected upscale model, from 1.2x up, the host runs the model the way
  Core's "Upscale Image (using Model)" does: colour channels only, 512-pixel
  tiles with a 32-pixel overlap, clamped. The original's centre-crop scale-down
  then runs on the result in the guest.
- `AV_LoraLoader` and `AV_VAELoader` keep the original's enable and override
  logic in the guest. The override name is checked against the host's own
  catalogue, and the same warning is printed when it is missing. Loading and
  applying run on the host's LoRA and VAE loaders, which are Core's
  `LoraLoader` and `VAELoader`. Zero strengths return the inputs unchanged;
  strengths linked from other nodes pass through, as in the original. An
  override check against a catalogue of more than 4096 names is refused by
  name.
- Model menus are filled by the host from its own model folders, never by
  the pack. The menu's static entries come first, as in the original.
- `CheckpointNameSelector` passes the chosen name on unchanged. Like the
  original, it counts as changed on every run.
- `RandomInt` and `RandomFloat` draw from torch's global random generator,
  which upstream leaves unseeded. The value differs from run to run in both
  versions. Given the same generator state, the two return the same value.

## Known differences

- A model-folder list output, `CheckpointNameSelector`'s first output, cannot
  be declared statically. It serves as a generic COMBO, so linking it into a
  list-typed input (such as a checkpoint loader's menu) is refused at queue
  time. Its STRING output is unaffected.
- The host appends folder names after a menu's static entries. Where the
  original lists the folder first (core's VAE menu puts `pixel_space` last),
  the entries match but their order differs. The original's extra
  `taesd` entries for VAE menus are not offered.
- The Pillow-based nodes are exact when the guest's Pillow matches the host's,
  as it does in the test environment.
- `AV_VAELoader`: a VAE file with audio (vocoder) weights is converted the way
  the host's loader converts it, which differs from Core's plain `VAELoader`.
  Image VAEs are unaffected.

## Verification

All tests run on CPU without weights, on synthetic, seeded images and values.

- `tests/test_artv_parity.py` compares every converted utility node, original
  against V2 in a real guest, bitwise and type-strict. That includes
  `ImageScaleToMegapixels` with a small seeded upscale model, loaded through
  Core's own upscale-model loader. The random nodes are compared with both
  sides' generator seeded identically before the call. Includes a negative
  control.
- `tests/test_artv_loaders.py` compares `AV_LoraLoader` and `AV_VAELoader`,
  original against V2 in a real guest, on a seeded tiny UNet and text
  encoder, LoRA files built from Core's own LoRA key maps, and TAESD-format
  VAE files. It compares the returned model and text-encoder patches and the
  returned VAEs (state, settings, a decode) bitwise, plus the override
  warnings and errors. It includes a negative control and a guard against
  empty patch sets.
- `tests/test_artv_schemas.py`: every node's node info, in process and as
  served from the manifest, against the original's.
- `tests/encode_manifest.py`: manifest regeneration and loader check.
- `tests/test_production_load.py`: every manifest row resolved the way the
  guest resolves it: only the row's module is imported, without the pack's
  `__init__.py`, and the class is looked up by its manifest name. Checked in
  process and through a real guest.
- `tests/freeze_artv.py`: how the frozen schemas were captured from the
  original. Its import stubs (`tests/import_stubs.py`) stand in only for
  heavy dependencies that no converted node uses, and raise if used.
