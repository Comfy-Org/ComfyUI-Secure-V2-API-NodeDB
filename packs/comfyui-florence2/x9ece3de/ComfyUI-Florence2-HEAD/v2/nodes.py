import torch
import torchvision.transforms.functional as F
import io as bytes_io
import gc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image, ImageDraw, ImageColor, ImageFont
import random
import numpy as np
import re

from comfy_api.latest import io, sdk

from . import _florence2_catalog as catalog
from .model import _ops

# Florence-2 is built, loaded and run inside this pack.  The host brokers two
# things and nothing else: it installs the declared weight files, and it hands
# over their tensors.  Architecture, tokenizer, prompt construction, the
# generation loop and every line of the parsing below stay here, which is why
# no core model loader has to learn about this one model family.


_MODEL_DESCRIPTOR_KEYS = frozenset({
    "secure_kind", "repo_id", "folder", "weight", "dtype",
    "extra_special_tokens", "lora",
})
_LORA_DESCRIPTOR_KEYS = frozenset({
    "secure_kind", "repo_id", "folder", "weight", "alpha",
})


def _safe_catalogue_name(value, *, label):
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or "\\" in value
        or "\0" in value
        or ".." in value.split("/")
    ):
        raise ValueError(f"invalid Florence2 {label} {value!r}")
    return value


def _validated_lora_descriptor(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _LORA_DESCRIPTOR_KEYS:
        raise ValueError("invalid Florence2 LoRA descriptor")
    if value.get("secure_kind") != "florence2.lora":
        raise ValueError("invalid Florence2 LoRA descriptor kind")

    repo_id = value.get("repo_id")
    declared = catalog.LORA_WEIGHTS.get(repo_id)
    if declared is None:
        raise ValueError("Florence2 LoRA is not in the declared catalogue")
    if (
        value.get("folder") != declared.folder
        or value.get("weight") != declared.catalogue_name
        or value.get("alpha") != catalog.LORA_ALPHA[repo_id]
    ):
        raise ValueError("Florence2 LoRA descriptor does not match its declaration")
    return value


def _validated_model_descriptor(value):
    if not isinstance(value, dict) or set(value) != _MODEL_DESCRIPTOR_KEYS:
        raise ValueError("invalid Florence2 model descriptor")
    if value.get("secure_kind") != "florence2.model":
        raise ValueError("invalid Florence2 model descriptor kind")
    if value.get("dtype") not in {"bf16", "fp16", "fp32"}:
        raise ValueError("invalid Florence2 model precision")

    repo_id = value.get("repo_id")
    extras = value.get("extra_special_tokens")
    if not isinstance(extras, list) or not all(
        isinstance(token, str) for token in extras
    ):
        raise ValueError("invalid Florence2 tokenizer extension")

    if repo_id is None:
        if value.get("folder") != "text_encoders" or extras:
            raise ValueError("invalid local Florence2 model descriptor")
        _safe_catalogue_name(value.get("weight"), label="model name")
    else:
        declared = catalog.MODEL_WEIGHTS.get(repo_id)
        expected_extras = list(catalog.EXTRA_SPECIAL_TOKENS.get(repo_id, ()))
        if declared is None:
            raise ValueError("Florence2 model is not in the declared catalogue")
        if (
            value.get("folder") != declared.folder
            or value.get("weight") != declared.catalogue_name
            or extras != expected_extras
        ):
            raise ValueError(
                "Florence2 model descriptor does not match its declaration"
            )

    _validated_lora_descriptor(value.get("lora"))
    return value


def apply_florence2_lora(model, lora_sd, lora_alpha, strength=1.0):
    """Apply a peft-style LoRA adapter to a Florence2 model in place.

    Upstream built a ``comfy.lora`` patch set and handed it to a ModelPatcher.
    There is no ModelPatcher here, so the same arithmetic is done directly on
    the parameters: ComfyUI's LoRA adapter computes
    ``weight += strength * (alpha / rank) * (up @ down)`` in float32, and that
    is reproduced exactly, including reading the rank from the adapter's own
    ``lora_down`` shape rather than from its config.
    """
    # Convert peft keys (base_model.model.X.lora_A/B.weight) to comfy lora format (X.lora_down/up.weight)
    converted = {}
    for k, v in lora_sd.items():
        k = k.replace("base_model.model.", "")
        k = k.replace("lora_A", "lora_down").replace("lora_B", "lora_up")
        converted[k] = v

    # Build key map: lora prefix -> model weight key
    model_sd = model.state_dict()
    key_map = {}
    for k in model_sd:
        lora_prefix = k.replace(".weight", "")
        if f"{lora_prefix}.lora_down.weight" in converted:
            key_map[lora_prefix] = k

    for lora_prefix, weight_key in key_map.items():
        up = converted[f"{lora_prefix}.lora_up.weight"]
        down = converted[f"{lora_prefix}.lora_down.weight"]
        weight = model_sd[weight_key]
        alpha = lora_alpha / down.shape[0]
        diff = torch.mm(
            up.to(weight.device, torch.float32).flatten(start_dim=1),
            down.to(weight.device, torch.float32).flatten(start_dim=1),
        ).reshape(weight.shape)
        with torch.no_grad():
            weight += ((strength * alpha) * diff).type(weight.dtype)
    return model


async def load_florence2(descriptor):
    """Build Florence-2 from a declared weight, inside the guest.

    Upstream read a directory that ``snapshot_download`` had filled and
    preferred ``config.json``, falling back to deriving the architecture from
    the checkpoint.  Only the fallback survives: the shapes in the weights are
    self-describing, so no repository config file is needed, and none is
    fetched.
    """
    descriptor = _validated_model_descriptor(descriptor)

    from .model.config import Florence2Config
    from .model.model import Florence2
    from .model.processing import Processor

    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[descriptor["dtype"]]

    ctx = sdk.ctx()
    asset = await ctx.assets.resolve(descriptor["folder"], descriptor["weight"])
    sd = await ctx.assets.load_state_dict(asset)

    config = Florence2Config.from_state_dict(sd)

    model = Florence2(config, dtype=dtype, device="cpu", operations=_ops.manual_cast)

    for key in ["language_model.model.encoder.embed_tokens.weight",
                "language_model.model.decoder.embed_tokens.weight"]:
        if key in sd and "language_model.model.shared.weight" in sd:
            sd.pop(key, None)

    m, u = model.load_state_dict(sd, strict=False)
    if m:
        print(f"Florence2 missing keys: {m}")
    if u:
        print(f"Florence2 unexpected keys: {u}")
    del sd

    lora = descriptor.get("lora")
    if lora is not None:
        lora_asset = await ctx.assets.resolve(lora["folder"], lora["weight"])
        lora_sd = await ctx.assets.load_state_dict(lora_asset)
        apply_florence2_lora(model, lora_sd, lora["alpha"])
        del lora_sd

    model.language_model.tie_weights()
    model = model.eval()

    processor = Processor(extra_special_tokens=tuple(descriptor.get("extra_special_tokens", ())))
    return model, processor, dtype


async def _install(weight):
    """Install one declared weight and return its logical catalogue name."""
    installed = await sdk.ctx().models.download_huggingface_weights(
        repo_id=weight.repo_id,
        filename=weight.filename,
        folder=weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    if installed != weight.catalogue_name:
        raise RuntimeError("the Florence2 weight provider returned the wrong asset")
    return installed


class _Progress:
    """Node-level progress over the brokered channel."""

    def __init__(self, total):
        self.total = int(total)
        self.current = 0

    async def update(self, value=1):
        self.current += int(value)
        await sdk.ctx().progress.update(self.current, self.total)


# The catalogue in `_florence2_catalog` is the single source of truth for what
# this pack may fetch; the combo shows exactly that set, in upstream's order.
model_list = catalog.MODEL_LIST


class DownloadAndLoadFlorence2Model(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.download",)
    SDK_REQUIRED_WEIGHTS = tuple(catalog.MODEL_WEIGHTS.values())

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DownloadAndLoadFlorence2Model",
            display_name="DownloadAndLoadFlorence2Model",
            category="Florence2",
            inputs=[
                io.Combo.Input("model", options=list(catalog.MODEL_LIST), default='microsoft/Florence-2-base'),
                io.Combo.Input("precision", options=['fp16', 'bf16', 'fp32'], default='fp16'),
                io.Custom("PEFTLORA").Input("lora", optional=True),
                io.Boolean.Input("convert_to_safetensors", default=False, optional=True, tooltip="Some of the older model weights are not saved in .safetensors format, which seem to cause longer loading times, this option converts the .bin weights to .safetensors"),
            ],
            outputs=[io.Custom("FL2MODEL").Output(display_name="florence2_model")],
        )

    @classmethod
    async def execute(cls, model, precision, lora=None, convert_to_safetensors=False) -> io.NodeOutput:
        # Selecting a model that is not declared is refused here, before any
        # request reaches the host -- which refuses it a second time.
        weight = catalog.model_weight(model)

        # `convert_to_safetensors` existed because a snapshot could contain a
        # pickle.  Every declared weight is already SafeTensors and the host
        # parses it structurally before storing it, so the request is already
        # satisfied whichever way this is set.

        lora = _validated_lora_descriptor(lora)
        installed = await _install(weight)

        florence2_model = {
            'secure_kind': 'florence2.model',
            'repo_id': weight.repo_id,
            'folder': weight.folder,
            'weight': installed,
            'dtype': precision,
            'extra_special_tokens': list(catalog.EXTRA_SPECIAL_TOKENS.get(model, ())),
            'lora': lora,
        }

        return io.NodeOutput(florence2_model)


class DownloadAndLoadFlorence2Lora(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.download",)
    SDK_REQUIRED_WEIGHTS = tuple(catalog.LORA_WEIGHTS.values())

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DownloadAndLoadFlorence2Lora",
            display_name="DownloadAndLoadFlorence2Lora",
            category="Florence2",
            inputs=[
                io.Combo.Input("model", options=['NikshepShetty/Florence-2-pixelprose']),
            ],
            outputs=[io.Custom("PEFTLORA").Output(display_name="lora")],
        )

    @classmethod
    async def execute(cls, model) -> io.NodeOutput:
        weight = catalog.lora_weight(model)
        installed = await _install(weight)
        # Upstream handed the next node a filesystem path.  A logical
        # catalogue name carries the same meaning and is not a path.
        return io.NodeOutput({
            'secure_kind': 'florence2.lora',
            'repo_id': weight.repo_id,
            'folder': weight.folder,
            'weight': installed,
            'alpha': catalog.LORA_ALPHA[model],
        })


class Florence2ModelLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        # Upstream listed `models/LLM` from inside INPUT_TYPES, which runs in
        # the host process.  The options are served by the host's own model
        # route instead, and the selection is resolved through the asset
        # broker at execution -- the node never builds a path.
        return io.Schema(
            node_id="Florence2ModelLoader",
            display_name="Florence2ModelLoader",
            category="Florence2",
            inputs=[
                io.Combo.Input("model", options=[], remote=io.RemoteOptions(route="/models/text_encoders", refresh_button=True), tooltip="models are expected to be in Comfyui/models/LLM folder"),
                io.Combo.Input("precision", options=['fp16', 'bf16', 'fp32']),
                io.Custom("PEFTLORA").Input("lora", optional=True),
                io.Boolean.Input("convert_to_safetensors", default=False, optional=True, tooltip="Some of the older model weights are not saved in .safetensors format, which seem to cause longer loading times, this option converts the .bin weights to .safetensors"),
            ],
            outputs=[io.Custom("FL2MODEL").Output(display_name="florence2_model")],
        )

    @classmethod
    def validate_inputs(cls, model=None, **kwargs):
        # Host-side check only: a selection must be a plain catalogue name.
        # Existence and containment remain the broker's answer, not ours, and
        # this must never turn the name into a path.
        if not isinstance(model, str) or not model:
            return "Florence2ModelLoader needs a model selection"
        if model.startswith("/") or "\\" in model or ".." in model.split("/"):
            return f"invalid model name {model!r}"
        return True

    @classmethod
    async def execute(cls, model, precision, lora=None, convert_to_safetensors=False) -> io.NodeOutput:
        print(f"Loading model from {model}")
        # Resolving now is the existence and containment check; the ref is not
        # carried onward, because the descriptor crosses as plain data.
        model = _safe_catalogue_name(model, label="model name")
        lora = _validated_lora_descriptor(lora)
        await sdk.ctx().assets.resolve("text_encoders", model)

        florence2_model = {
            'secure_kind': 'florence2.model',
            'repo_id': None,
            'folder': "text_encoders",
            'weight': model,
            'dtype': precision,
            'extra_special_tokens': [],
            'lora': lora,
        }

        return io.NodeOutput(florence2_model)


class Florence2Run(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Florence2Run",
            display_name="Florence2Run",
            category="Florence2",
            inputs=[
                io.Image.Input("image"),
                io.Custom("FL2MODEL").Input("florence2_model"),
                io.String.Input("text_input", default="", multiline=True),
                io.Combo.Input("task", options=[
                    'region_caption',
                    'dense_region_caption',
                    'region_proposal',
                    'caption',
                    'detailed_caption',
                    'more_detailed_caption',
                    'caption_to_phrase_grounding',
                    'referring_expression_segmentation',
                    'ocr',
                    'ocr_with_region',
                    'docvqa',
                    'prompt_gen_tags',
                    'prompt_gen_mixed_caption',
                    'prompt_gen_analyze',
                    'prompt_gen_mixed_caption_plus',
                ]),
                io.Boolean.Input("fill_mask", default=True),
                io.Boolean.Input("keep_model_loaded", default=False, optional=True),
                io.Int.Input("max_new_tokens", default=1024, min=1, max=4096, optional=True),
                io.Int.Input("num_beams", default=3, min=1, max=64, optional=True),
                io.Boolean.Input("do_sample", default=True, optional=True),
                io.String.Input("output_mask_select", default="", optional=True),
                io.Int.Input("seed", default=1, min=1, max=0xffffffffffffffff, optional=True),
            ],
            outputs=[
                io.Image.Output(display_name="image"),
                io.Mask.Output(display_name="mask"),
                io.String.Output(display_name="caption"),
                io.Custom("JSON").Output(display_name="data"),
            ],
        )

    @classmethod
    def hash_seed(cls, seed):
        import hashlib
        # Convert the seed to a string and then to bytes
        seed_bytes = str(seed).encode('utf-8')
        # Create a SHA-256 hash of the seed bytes
        hash_object = hashlib.sha256(seed_bytes)
        # Convert the hash to an integer
        hashed_seed = int(hash_object.hexdigest(), 16)
        # Ensure the hashed seed is within the acceptable range for set_seed
        return hashed_seed % (2**32)

    @classmethod
    async def execute(cls, image, text_input, florence2_model, task, fill_mask, keep_model_loaded=False,
            num_beams=3, max_new_tokens=1024, do_sample=True, output_mask_select="", seed=None) -> io.NodeOutput:
        image = await image.raw()
        _, height, width, _ = image.shape
        annotated_image_tensor = None
        mask_tensor = None
        model, processor, dtype = await load_florence2(florence2_model)
        # The weights arrive on the negotiated device; keep the model with them.
        load_device = next(model.parameters()).device

        if seed:
            torch.manual_seed(cls.hash_seed(seed))

        colormap = ['blue','orange','green','purple','brown','pink','olive','cyan','red',
                    'lime','indigo','violet','aqua','magenta','gold','tan','skyblue']

        prompts = {
            'region_caption': '<OD>',
            'dense_region_caption': '<DENSE_REGION_CAPTION>',
            'region_proposal': '<REGION_PROPOSAL>',
            'caption': '<CAPTION>',
            'detailed_caption': '<DETAILED_CAPTION>',
            'more_detailed_caption': '<MORE_DETAILED_CAPTION>',
            'caption_to_phrase_grounding': '<CAPTION_TO_PHRASE_GROUNDING>',
            'referring_expression_segmentation': '<REFERRING_EXPRESSION_SEGMENTATION>',
            'ocr': '<OCR>',
            'ocr_with_region': '<OCR_WITH_REGION>',
            'docvqa': '<DocVQA>',
            'prompt_gen_tags': '<GENERATE_TAGS>',
            'prompt_gen_mixed_caption': '<MIXED_CAPTION>',
            'prompt_gen_analyze': '<ANALYZE>',
            'prompt_gen_mixed_caption_plus': '<MIXED_CAPTION_PLUS>',
        }
        task_prompt = prompts.get(task, '<OD>')

        if (task not in ['referring_expression_segmentation', 'caption_to_phrase_grounding', 'docvqa']) and text_input:
            raise ValueError("Text input (prompt) is only supported for 'referring_expression_segmentation', 'caption_to_phrase_grounding', and 'docvqa'")

        if text_input != "":
            prompt = task_prompt + " " + text_input
        else:
            prompt = task_prompt

        image = image.permute(0, 3, 1, 2)

        out = []
        out_masks = []
        out_results = []
        out_data = []
        pbar = _Progress(len(image))
        for img in image:
            image_pil = F.to_pil_image(img)
            inputs = processor(text=prompt, images=img.unsqueeze(0))

            generated_ids = model.generate(
                input_ids=inputs["input_ids"].to(load_device),
                pixel_values=inputs["pixel_values"].to(dtype=dtype, device=load_device),
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                num_beams=num_beams,
            )

            results = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            print(results)
            # cleanup the special tokens from the final list
            if task == 'ocr_with_region':
                clean_results = str(results)
                cleaned_string = re.sub(r'</?s>|<[^>]*>', '\n',  clean_results)
                clean_results = re.sub(r'\n+', '\n', cleaned_string)
            else:
                clean_results = str(results)
                clean_results = clean_results.replace('</s>', '')
                clean_results = clean_results.replace('<s>', '')

             #return single string if only one image for compatibility with nodes that can't handle string lists
            if len(image) == 1:
                out_results = clean_results
            else:
                out_results.append(clean_results)

            W, H = image_pil.size

            parsed_answer = processor.post_process_generation(results, task=task_prompt, image_size=(W, H))

            if task == 'region_caption' or task == 'dense_region_caption' or task == 'caption_to_phrase_grounding' or task == 'region_proposal':
                fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
                fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
                ax.imshow(image_pil)
                bboxes = parsed_answer[task_prompt]['bboxes']
                labels = parsed_answer[task_prompt]['labels']

                mask_indexes = []
                # Determine mask indexes outside the loop
                if output_mask_select != "":
                    mask_indexes = [n for n in output_mask_select.split(",")]
                    print(mask_indexes)
                else:
                    mask_indexes = [str(i) for i in range(len(bboxes))]

                # Initialize mask_layer only if needed
                if fill_mask:
                    mask_layer = Image.new('RGB', image_pil.size, (0, 0, 0))
                    mask_draw = ImageDraw.Draw(mask_layer)

                for index, (bbox, label) in enumerate(zip(bboxes, labels)):
                    # Modify the label to include the index
                    indexed_label = f"{index}.{label}"

                    if fill_mask:
                        # Ensure y1 is greater than or equal to y0 for mask drawing
                        x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
                        if y1 < y0:
                            y0, y1 = y1, y0
                        if x1 < x0:
                            x0, x1 = x1, x0

                        if str(index) in mask_indexes:
                            print("match index:", str(index), "in mask_indexes:", mask_indexes)
                            mask_draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
                        if label in mask_indexes:
                            print("match label")
                            mask_draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))

                    # Create a Rectangle patch
                    # Ensure y1 is greater than or equal to y0
                    y0, y1 = bbox[1], bbox[3]
                    if y1 < y0:
                        y0, y1 = y1, y0

                    rect = patches.Rectangle(
                        (bbox[0], y0),  # (x,y) - lower left corner
                        bbox[2] - bbox[0],   # Width
                        y1 - y0,   # Height
                        linewidth=1,
                        edgecolor='r',
                        facecolor='none',
                        label=indexed_label
                    )
                     # Calculate text width with a rough estimation
                    text_width = len(label) * 6  # Adjust multiplier based on your font size
                    text_height = 12  # Adjust based on your font size

                    # Get corrected coordinates
                    x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
                    if y1 < y0:
                        y0, y1 = y1, y0
                    if x1 < x0:
                        x0, x1 = x1, x0

                    # Initial text position
                    text_x = x0
                    text_y = y0 - text_height  # Position text above the top-left of the bbox

                    # Adjust text_x if text is going off the left or right edge
                    if text_x < 0:
                        text_x = 0
                    elif text_x + text_width > W:
                        text_x = W - text_width

                    # Adjust text_y if text is going off the top edge
                    if text_y < 0:
                        text_y = y1  # Move text below the bottom-left of the bbox if it doesn't overlap with bbox

                    # Add the rectangle to the plot
                    ax.add_patch(rect)
                    facecolor = random.choice(colormap) if len(image) == 1 else 'red'
                    # Add the label
                    plt.text(
                        text_x,
                        text_y,
                        indexed_label,
                        color='white',
                        fontsize=12,
                        bbox=dict(facecolor=facecolor, alpha=0.5)
                    )
                if fill_mask:
                    mask_tensor = F.to_tensor(mask_layer)
                    mask_tensor = mask_tensor.unsqueeze(0).permute(0, 2, 3, 1).cpu().float()
                    mask_tensor = mask_tensor.mean(dim=0, keepdim=True)
                    mask_tensor = mask_tensor.repeat(1, 1, 1, 3)
                    mask_tensor = mask_tensor[:, :, :, 0]
                    out_masks.append(mask_tensor)

                # Remove axis and padding around the image
                ax.axis('off')
                ax.margins(0,0)
                ax.get_xaxis().set_major_locator(plt.NullLocator())
                ax.get_yaxis().set_major_locator(plt.NullLocator())
                fig.canvas.draw()
                buf = bytes_io.BytesIO()
                plt.savefig(buf, format='png', pad_inches=0)
                buf.seek(0)
                annotated_image_pil = Image.open(buf)

                annotated_image_tensor = F.to_tensor(annotated_image_pil)
                out_tensor = annotated_image_tensor[:3, :, :].unsqueeze(0).permute(0, 2, 3, 1).cpu().float()
                out.append(out_tensor)

                if task == 'caption_to_phrase_grounding':
                    out_data.append(parsed_answer[task_prompt])
                else:
                    out_data.append(bboxes)


                await pbar.update(1)

                plt.close(fig)

            elif task == 'referring_expression_segmentation':
                # Create a new black image
                mask_image = Image.new('RGB', (W, H), 'black')
                mask_draw = ImageDraw.Draw(mask_image)

                predictions = parsed_answer[task_prompt]

                # Iterate over polygons and labels
                for polygons, label in zip(predictions['polygons'], predictions['labels']):
                    color = random.choice(colormap)
                    for _polygon in polygons:
                        _polygon = np.array(_polygon).reshape(-1, 2)
                        # Clamp polygon points to image boundaries
                        _polygon = np.clip(_polygon, [0, 0], [W - 1, H - 1])
                        if len(_polygon) < 3:
                            print('Invalid polygon:', _polygon)
                            continue

                        _polygon = _polygon.reshape(-1).tolist()

                        # Draw the polygon
                        if fill_mask:
                            overlay = Image.new('RGBA', image_pil.size, (255, 255, 255, 0))
                            image_pil = image_pil.convert('RGBA')
                            draw = ImageDraw.Draw(overlay)
                            color_with_opacity = ImageColor.getrgb(color) + (180,)
                            draw.polygon(_polygon, outline=color, fill=color_with_opacity, width=3)
                            image_pil = Image.alpha_composite(image_pil, overlay)
                        else:
                            draw = ImageDraw.Draw(image_pil)
                            draw.polygon(_polygon, outline=color, width=3)

                        #draw mask
                        mask_draw.polygon(_polygon, outline="white", fill="white")

                image_tensor = F.to_tensor(image_pil)
                image_tensor = image_tensor[:3, :, :].unsqueeze(0).permute(0, 2, 3, 1).cpu().float()
                out.append(image_tensor)

                mask_tensor = F.to_tensor(mask_image)
                mask_tensor = mask_tensor.unsqueeze(0).permute(0, 2, 3, 1).cpu().float()
                mask_tensor = mask_tensor.mean(dim=0, keepdim=True)
                mask_tensor = mask_tensor.repeat(1, 1, 1, 3)
                mask_tensor = mask_tensor[:, :, :, 0]
                out_masks.append(mask_tensor)
                await pbar.update(1)

            elif task == 'ocr_with_region':
                try:
                    font = ImageFont.load_default().font_variant(size=24)
                except:
                    font = ImageFont.load_default()
                predictions = parsed_answer[task_prompt]
                scale = 1
                image_pil = image_pil.convert('RGBA')
                overlay = Image.new('RGBA', image_pil.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)
                bboxes, labels = predictions['quad_boxes'], predictions['labels']

                # Create a new black image for the mask
                mask_image = Image.new('RGB', (W, H), 'black')
                mask_draw = ImageDraw.Draw(mask_image)

                for box, label in zip(bboxes, labels):
                    scaled_box = [v / (width if idx % 2 == 0 else height) for idx, v in enumerate(box)]
                    out_data.append({"label": label, "box": scaled_box})

                    color = random.choice(colormap)
                    new_box = (np.array(box) * scale).tolist()

                    # Ensure polygon coordinates are valid
                    # For polygons, we need to make sure the points form a valid shape
                    # This is a simple check to ensure the polygon has at least 3 points
                    if len(new_box) >= 6:  # At least 3 points (x,y pairs)
                        if fill_mask:
                            color_with_opacity = ImageColor.getrgb(color) + (180,)
                            draw.polygon(new_box, outline=color, fill=color_with_opacity, width=3)
                        else:
                            draw.polygon(new_box, outline=color, width=3)

                        # Get the first point for text positioning
                        text_x, text_y = new_box[0]+8, new_box[1]+2

                        draw.text((text_x, text_y),
                                  "{}".format(label),
                                  align="right",
                                  font=font,
                                  fill=color)

                        # Draw the mask
                        mask_draw.polygon(new_box, outline="white", fill="white")

                image_pil = Image.alpha_composite(image_pil, overlay)
                image_pil = image_pil.convert('RGB')

                image_tensor = F.to_tensor(image_pil)
                image_tensor = image_tensor[:3, :, :].unsqueeze(0).permute(0, 2, 3, 1).cpu().float()
                out.append(image_tensor)

                # Process the mask
                mask_tensor = F.to_tensor(mask_image)
                mask_tensor = mask_tensor.unsqueeze(0).permute(0, 2, 3, 1).cpu().float()
                mask_tensor = mask_tensor.mean(dim=0, keepdim=True)
                mask_tensor = mask_tensor.repeat(1, 1, 1, 3)
                mask_tensor = mask_tensor[:, :, :, 0]
                out_masks.append(mask_tensor)

                await pbar.update(1)

            elif task == 'docvqa':
                if text_input == "":
                    raise ValueError("Text input (prompt) is required for 'docvqa'")
                prompt = "<DocVQA> " + text_input

                inputs = processor(text=prompt, images=img.unsqueeze(0))
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"].to(load_device),
                    pixel_values=inputs["pixel_values"].to(dtype=dtype, device=load_device),
                    max_new_tokens=max_new_tokens,
                    do_sample=do_sample,
                    num_beams=num_beams,
                )

                results = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
                clean_results = results.replace('</s>', '').replace('<s>', '')

                if len(image) == 1:
                    out_results = clean_results
                else:
                    out_results.append(clean_results)

                out.append(F.to_tensor(image_pil).unsqueeze(0).permute(0, 2, 3, 1).cpu().float())

                await pbar.update(1)

        if len(out) > 0:
            out_tensor = torch.cat(out, dim=0)
        else:
            out_tensor = torch.zeros((1, 64,64, 3), dtype=torch.float32, device="cpu")
        if len(out_masks) > 0:
            out_mask_tensor = torch.cat(out_masks, dim=0)
        else:
            out_mask_tensor = torch.zeros((1,64,64), dtype=torch.float32, device="cpu")

        if not keep_model_loaded:
            # Upstream evicted this model from the host's global cache.  The
            # model here was built for this call and belongs to the guest, so
            # dropping it now is the same request, confined to this process.
            # Either way the host's warm weight cache keeps the tensors, so a
            # later run does not re-read them from disk.
            del model, processor
            gc.collect()

        return io.NodeOutput(
            await sdk.ImageRef._from_raw(out_tensor),
            await sdk.MaskRef._from_raw(out_mask_tensor),
            out_results,
            out_data,
        )

NODE_CLASS_MAPPINGS = {
    "DownloadAndLoadFlorence2Model": DownloadAndLoadFlorence2Model,
    "DownloadAndLoadFlorence2Lora": DownloadAndLoadFlorence2Lora,
    "Florence2ModelLoader": Florence2ModelLoader,
    "Florence2Run": Florence2Run,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DownloadAndLoadFlorence2Model": "DownloadAndLoadFlorence2Model",
    "DownloadAndLoadFlorence2Lora": "DownloadAndLoadFlorence2Lora",
    "Florence2ModelLoader": "Florence2ModelLoader",
    "Florence2Run": "Florence2Run",
}
