# Secure conversion status

Pinned upstream commit: `58e077a7435631301cf7443412515cf958e7f3d1`.

All 207 frozen upstream backend node mappings are supported by concrete Secure
Nodes 2.0 handlers. No node mapping is rejected and no mapping is left on an
unsupported fallback.

The conversion keeps loader, pipe, prompt, XY-plot, adapter, inpaint, sampling,
detailer, image, loop, and wildcard orchestration pack-side. Core is used for
typed model operations and confined asset, output, graph, interaction, UI, and
sampling primitives.

Additional models are declared as pinned Hugging Face weights with hashes.
Downloads are brokered into the managed model catalogue and reused after the
first verified download; a node does not download a weight on every execution.

`secure-nodes.json` is the authoritative sealed schema/permission census. The
operational classification and representative real-guest behavior are enforced
by `backend/tests/test_popular_pack_conversions.py`, including an explicit
`207 supported / 0 rejected` assertion.

## Repair round r1: `easy showAnything`, `easy indexAnything`

`easy showAnything` (and `easy showAnythingLazy`, which shares the handler) formats each input value the way the
original does (`py/nodes/logic.py:1329-1358`):
- Nothing connected, or only `None` values, shows `[]` and returns `[]`.
- Strings are shown as they are. Numbers and booleans go through `str()`.
- A list of up to 30 items replaces the shown values.
- Anything else is shown as `json.dumps(indent=4, ensure_ascii=False)`, or as `str()` when that fails. Tensors and
  LATENT dicts are read through `raw` so they print exactly like the original.

`easy indexAnything` picks items the way the original does (`py/nodes/logic.py:1193-1221`), with the same index
clamping. For an IMAGE batch it returns the selected image as an IMAGE ref, through `ImageRef.batch_size` and
`ImageRef.select_batch`, because a raw tensor cannot cross the guest wire.

Known differences:
- `showAnything` shows engine objects (MODEL, CLIP, VAE, CONDITIONING, ...) as `<KIND ref>`. The original shows their
  Python repr, which contains a memory address.
- The original also writes the shown values into the workflow's `widgets_values` inside `extra_pnginfo`. A later
  image save in the same run then embeds them. A guest receives `extra_pnginfo` as a copy, so V2 does not change the
  embedded workflow.
- `indexAnything` refuses by name, instead of returning an item, when the single input is:
  - a MASK or other non-IMAGE tensor batch, or
  - a CONDITIONING or another engine object.
  Those items cannot be returned across the guest wire.
- `indexAnything` cannot see whether the upstream output is a list output. The original returns a one-item list
  output whole. V2 indexes into that single item, the same way the original treats a single value.

## Repair round r2: `easy hiresFix`

`easy hiresFix` now runs the selected upscale model, as the original does (`py/nodes/fix.py:61-149`). The previous
handler resized the input image and never used the model.

How it runs:
- `models.load_upscale_model` loads the model and `UpscaleModelRef.upscale` runs it, host-side.
- Tiling matches the original's `comfy.utils.tiled_scale` call: 192-px tiles, 8-px overlap, and the same
  feathering and normalisation.
- The result is clamped to [0, 1].
- The rescale is optional. It uses the original's sizes: multiples of 8 from `enforce_mul_of_64`, the
  `MAX_RESOLUTION` cap, and the widget width/height for "to Width/Height".
- The pixels are cropped to multiples of 8 and their RGB channels VAE-encoded.
- The node declares the `models` permission so that it can load the upscale model.

Known differences:
- The original's "Preview" saves temp files named `easyPreview_temp_…`. V2 previews through the platform preview,
  which names them differently. The pixels are the same.
- "Sender" and "Sender&Save" save the image like the original, but do not send the frontend `img-send` event.

## Repair round r3: `easy loraPromptApply`, `easy imageColorMatch`

`easy loraPromptApply` handles prompts the way the original does (`py/libs/wildcards.py:279-308`,
`py/libs/loader.py:326-426`):
- Each prompt first goes through the wildcard pass. Text without `{options}` or `__wildcards__` is unchanged. Other
  text uses the pack's wildcard port with an unseeded choice, as the original's `seed=None` does.
- Every `<lora:name[:model[:clip]]>` tag is applied in order: first the positive prompt's tags, then the negative's.
  - The model and clip strengths each default to 1.0.
  - A name repeated within one prompt applies once.
- Tags are removed with the surrounding spaces kept. An unconnected negative returns `""`.
- Names resolve like the original's `resolve_lora_name`:
  - ".safetensors" is appended. The original's extension test always appends it, so a full file name ends in a doubled
    extension and is not found.
  - The name resolves to the first LoRA in the catalogue (sorted) whose path ends with it. A file stem resolves; a full
    file name does not.
  - A LoRA that isn't found is skipped, as in the original, instead of failing the node.
- LoRAs are applied through `ModelRef.apply_lora` with the native loader's behaviour: `skip_zero=False`,
  `allow_extended_strengths=True`. On a runtime base whose `apply_lora` lacks those keywords (0b86765f), the
  platform instead skips zero-strength LoRAs and refuses strengths outside [-100, 100].

`easy imageColorMatch` now runs the selected method. The previous handler applied one mean/std transfer whatever the
method.
- "wavelet" and "adain" use the pack's own colour-fix functions (`py/libs/colorfix.py`), copied verbatim. torchvision's
  `ToTensor`/`ToPILImage` conversions are reproduced exactly.
- The other methods use color-matcher 0.6.0, the package the original installs. It is vendored in `_color_matcher/`
  and uses numpy only. It is GPL-3.0, the same as this pack. The files are verbatim except that three package
  imports in `top_level.py` are relative.
- "Hide", "Preview", "Save" and "Hide/Save" behave as the original's `easySave`. The node declares `output` and `ui`
  for that.

Known differences:
- loraPromptApply refuses by name for a LoRA block-weight tag (`LBW=`). The original hands those to another pack's
  block-weight loader.
- loraPromptApply skips the original's local-path lookup (`os.path.exists(name)`, relative to the server's working
  directory).
- loraPromptApply searches a LoRA catalogue larger than the listing cap (4096 names) by exact name only.
- When a LoRA file carries metadata, the platform loader attaches it to the patched model as `lora_metadata`. The
  original's loader call passes no metadata.
- color-matcher modifies the original's input images in place: zero pixels become 1/255. A guest works on copies, so a
  later node that reads those same inputs sees unmodified pixels.
- imageColorMatch "Preview" temp-file names differ from the original's `easyPreview_temp_…`. The pixels are the same.
