"""WAS Node Suite as Secure Nodes V2 classes: the converted nodes, and every other declared node registered with
its real schema and a refusal (SECURE_CONVERSION.md).

Each id gets its own class (no concrete parent class), built from the original's declaration (schema_v3.py).
Pure value nodes call the original's method from originals.py (copied verbatim from WAS_Node_Suite.py by the
build); nodes that touch models, tensors or files go through the guest SDK.
"""
import hashlib
import json
import os
import posixpath
import re
import sys

from comfy_api.latest import io, sdk

from . import originals
from .refusals import (IMAGE_SAVE_HISTORY, IMAGE_SAVE_JPEG, IMAGE_SAVE_LISTING, IMAGE_SAVE_OVERWRITE,
                       IMAGE_SAVE_PATH, IMAGE_SAVE_PREFIX, IMAGE_SAVE_WEBP_EMBED, SecureConversionRefusal,
                       not_converted)
from .schema_v3 import ROWS, build_schema
from .tokens import TextTokens


def _node_output(result):
    """A V1 FUNCTION result as a NodeOutput: a tuple of outputs, or {"ui": ..., "result": ...}."""
    if isinstance(result, dict) and ("result" in result or "ui" in result):
        return io.NodeOutput(*tuple(result.get("result", ())), ui=result.get("ui"))
    return io.NodeOutput(*tuple(result))


# ---- pure value nodes: the original method, called with the inputs the executor passed it
_PURE = {
    "Text to String": ("WAS_Text_To_String", "text_to_string"),
    "Text to Number": ("WAS_Text_To_Number", "text_to_number"),
    "String to Text": ("WAS_String_To_Text", "string_to_text"),
    "Number to Int": ("WAS_Number_To_Int", "number_to_int"),
    "Text Concatenate": ("WAS_Text_Concatenate", "text_concatenate"),
    "Text Find and Replace": ("WAS_Search_and_Replace", "text_search_and_replace"),
    "Text Multiline": ("WAS_Text_Multiline", "text_multiline"),
}


def _pure_execute(class_name, function):
    def execute(cls, **kwargs):
        return _node_output(getattr(getattr(originals, class_name)(), function)(**kwargs))
    return execute


async def _text_to_conditioning(cls, clip, text):
    # The original called nodes.CLIPTextEncode().encode(clip, text) (core nodes.py:74-78) and returned
    # (conditioning, {"ui": ...}) for its one output; the second value was never an output.
    if clip is None:
        raise RuntimeError("ERROR: clip input is invalid: None\n\nIf the clip is from a checkpoint loader node your checkpoint does not contain a valid clip or text encoder model.")
    tokens = await clip.tokenize(text)
    return io.NodeOutput(await clip.encode_from_tokens_scheduled(tokens))


async def _image_filters(cls, image, **kwargs):
    tensor = await image.raw()
    result = originals.WAS_Image_Filters().image_filters(tensor, **kwargs)
    return io.NodeOutput(await sdk.ImageRef.from_value(result[0]))


async def _latent_noise(cls, samples, noise_std):
    value = await samples.value()
    result = originals.WAS_Latent_Noise().inject_noise(value, noise_std)
    return io.NodeOutput(await sdk.LatentRef.from_value(result[0]))


# ---- model menus: the original listed a model folder when its INPUT_TYPES ran (WAS_Node_Suite.py:13796-13819,
# 13859-13862, 13901-13904, 13986-13989); V2 declares the host's catalogue route for the same folder, and the host fills
# the menu from it.
_MODEL_MENUS = {
    ("Checkpoint Loader", "config_name"): "configs",
    ("Checkpoint Loader", "ckpt_name"): "checkpoints",
    ("Checkpoint Loader (Simple)", "ckpt_name"): "checkpoints",
    ("unCLIP Checkpoint Loader", "ckpt_name"): "checkpoints",
    ("Upscale Model Loader", "model_name"): "upscale_models",
}


def _model_menu_input(name, folder):
    def make():
        return io.Combo.Input(name, options=[], remote=io.RemoteOptions(
            route=f"/models/{folder}", refresh_button=True, control_after_refresh="first"))
    return make


# ---- Load Lora / Lora Loader (WAS_Lora_Loader)
def _lora_name_input():
    # The original listed ["None"] + folder_paths.get_filename_list("loras") when the schema was built; V2 lists
    # the host's LoRA catalogue in the browser and checks the value in validate_inputs, as core's menu check did.
    return io.Combo.Input("lora_name", options=["None"], remote=io.RemoteOptions(
        route="/models/loras", refresh_button=True, control_after_refresh="first"))


async def _lora_validate(cls, lora_name):
    if lora_name == "None":
        return True
    catalogue = list(await sdk.ctx().assets.list("loras"))
    if lora_name in catalogue:
        return True
    return f"Value not in list: lora_name: '{lora_name}' not in {['None', *catalogue]}"


async def _lora_execute(cls, model, clip, lora_name, strength_model, strength_clip):
    if strength_model == 0 and strength_clip == 0:
        return io.NodeOutput(model, clip)  # the original returned these two values for its three outputs
    name = posixpath.relpath(posixpath.join("/", lora_name), "/")
    if not await sdk.ctx().assets.exists("loras", name):
        lora_path = None
        lora_path.lower()  # the original: comfy.utils.load_torch_file(None) raised this AttributeError
    asset = await sdk.ctx().assets.resolve("loras", name)
    model_lora, clip_lora = await model.apply_lora(
        asset, clip, strength_model, strength_clip if clip is not None else 0.0)
    return io.NodeOutput(model_lora, clip_lora, os.path.splitext(os.path.basename(lora_name))[0])


# ---- Image Save (WAS_Image_Save.was_save_images)
async def _image_save(cls, images, output_path='', filename_prefix="ComfyUI", filename_delimiter='_',
                      extension='png', dpi=96, quality=100, optimize_image="true", lossless_webp="false",
                      overwrite_mode='false', filename_number_padding=4, filename_number_start='false',
                      show_history='false', show_history_by_prefix="true", embed_workflow="true",
                      show_previews="true"):
    prompt = cls.hidden.prompt
    extra_pnginfo = cls.hidden.extra_pnginfo
    delimiter = filename_delimiter
    number_padding = filename_number_padding
    lossless_webp = (lossless_webp == "true")
    optimize_image = (optimize_image == "true")
    if extension in ("jpg", "jpeg"):
        raise SecureConversionRefusal(IMAGE_SAVE_JPEG.format(ext=extension))
    if extension == "webp" and embed_workflow == "true":
        raise SecureConversionRefusal(IMAGE_SAVE_WEBP_EMBED)
    if show_history == "true" and show_previews == "true":
        raise SecureConversionRefusal(IMAGE_SAVE_HISTORY)

    # Define token system
    tokens = TextTokens()

    # Parse prefix tokens
    filename_prefix = tokens.parseTokens(filename_prefix)

    # Setup output path (a folder relative to the output root)
    if output_path in [None, '', "none", "."]:
        folder = ""
    else:
        output_path = tokens.parseTokens(output_path)
        if "\\" in output_path or os.path.isabs(output_path) or re.match(r"^[A-Za-z]:", output_path):
            raise SecureConversionRefusal(IMAGE_SAVE_PATH.format(path=output_path))
        folder = posixpath.normpath(output_path)
        if folder == ".":
            folder = ""
        if folder == ".." or folder.startswith("../"):
            raise SecureConversionRefusal(IMAGE_SAVE_PATH.format(path=output_path))
    if "/" in filename_prefix or "\\" in filename_prefix:
        raise SecureConversionRefusal(IMAGE_SAVE_PREFIX.format(prefix=filename_prefix))

    # Find existing counter values (the original listed the folder with os.listdir)
    if filename_number_start == 'true':
        pattern = f"(\\d+){re.escape(delimiter)}{re.escape(filename_prefix)}"
    else:
        pattern = f"{re.escape(filename_prefix)}{re.escape(delimiter)}(\\d+)"
    try:
        listed = await sdk.ctx().assets.list("output", prefix=folder, recursive=False)
    except ValueError as error:
        raise SecureConversionRefusal(IMAGE_SAVE_LISTING.format(path=folder or "output")) from error
    existing_counters = [
        int(re.search(pattern, filename).group(1))
        for filename in (posixpath.basename(name) for name in listed)
        if re.match(pattern, os.path.basename(filename))
    ]
    existing_counters.sort(reverse=True)

    # Set initial counter value
    if existing_counters:
        counter = existing_counters[0] + 1
    else:
        counter = 1

    # Set Extension
    file_extension = '.' + extension

    results = list()
    output_files = list()
    for index in range(int(await images.batch_size())):
        image = await images.select_batch([index])

        # Delegate metadata/pnginfo
        png_text = {}
        if embed_workflow == 'true':
            if prompt is not None:
                png_text["prompt"] = json.dumps(prompt)
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    png_text[x] = json.dumps(extra_pnginfo[x])

        # Delegate the filename stuffs
        if overwrite_mode == 'prefix_as_filename':
            file = f"{filename_prefix}{file_extension}"
        else:
            if filename_number_start == 'true':
                file = f"{counter:0{number_padding}}{delimiter}{filename_prefix}{file_extension}"
            else:
                file = f"{filename_prefix}{delimiter}{counter:0{number_padding}}{file_extension}"
        logical = posixpath.join(folder, file) if folder else file
        if await sdk.ctx().assets.exists("output", logical):
            raise SecureConversionRefusal(IMAGE_SAVE_OVERWRITE.format(name=logical))

        # Save the images (the original printed and skipped an image whose save failed)
        try:
            if extension == 'png':
                # Pillow's PNG writer compresses at level 9 when optimize is set, else at zlib's default (6).
                options = {"png_text": png_text, "optimize": optimize_image,
                           "compress_level": 9 if optimize_image else 6}
            elif extension == 'webp':
                options = {"quality": quality, "lossless": lossless_webp, "save_metadata": False}
            elif extension in ('tiff', 'gif'):
                options = {"optimize": optimize_image, "save_metadata": False}
            else:
                options = {"save_metadata": False}
            await sdk.ctx().output.save_images(image, filenames=[logical], image_format=extension, **options)
            output_files.append(logical)

            if show_history != 'true' and show_previews == 'true':
                results.append({
                    "filename": file,
                    "subfolder": folder,
                    "type": "output"
                })
        except SecureConversionRefusal:
            raise
        except Exception as e:
            print(f'Unable to save file due to the to the following error: {e}')

        if overwrite_mode == 'false':
            counter += 1

    if show_previews == 'true':
        return io.NodeOutput(images, output_files, ui={"images": results, "files": output_files})
    else:
        return io.NodeOutput(images, output_files, ui={"images": []})


# ---- registry
_CONVERTED = {}
for _node_id, (_class_name, _function) in _PURE.items():
    _CONVERTED[_node_id] = {"execute": classmethod(_pure_execute(_class_name, _function))}
_CONVERTED["Text to Conditioning"] = {"execute": classmethod(_text_to_conditioning), "SDK_REFS": True}
_CONVERTED["Image Filter Adjustments"] = {"execute": classmethod(_image_filters), "SDK_REFS": True,
                                          "SDK_PERMISSIONS": ("raw",)}
_CONVERTED["Latent Noise Injection"] = {"execute": classmethod(_latent_noise), "SDK_REFS": True,
                                        "SDK_PERMISSIONS": ("raw",)}
for _node_id in ("Load Lora", "Lora Loader"):
    _CONVERTED[_node_id] = {"execute": classmethod(_lora_execute), "validate_inputs": classmethod(_lora_validate),
                            "SDK_REFS": True, "SDK_PERMISSIONS": ("assets",),
                            "_overrides": {"lora_name": _lora_name_input}}
_CONVERTED["Image Save"] = {"execute": classmethod(_image_save), "SDK_REFS": True,
                            "SDK_PERMISSIONS": ("assets", "output")}


def _class_name_for(node_id):
    return "WAS_V2_" + re.sub(r"\W+", "_", node_id).strip("_") + "_" + hashlib.sha1(node_id.encode()).hexdigest()[:8]


def _make_class(node_id):
    spec = dict(_CONVERTED.get(node_id) or {})
    factories = {name: _model_menu_input(name, folder) for (menu_node, name), folder in _MODEL_MENUS.items()
                 if menu_node == node_id}
    factories.update(spec.pop("_overrides", {}))

    def define_schema(cls):
        return build_schema(node_id, {name: make() for name, make in factories.items()})

    attrs = {"__module__": __name__, "define_schema": classmethod(define_schema)}
    if node_id in _CONVERTED:
        attrs.update(spec)
    else:
        message = not_converted(node_id)

        def validate_inputs(cls, **kwargs):
            return message

        def execute(cls, **kwargs):
            raise SecureConversionRefusal(message)

        attrs["validate_inputs"] = classmethod(validate_inputs)
        attrs["execute"] = classmethod(execute)
    generated = type(_class_name_for(node_id), (io.ComfyNode,), attrs)
    setattr(sys.modules[__name__], generated.__name__, generated)
    return generated


NODE_CLASS_MAPPINGS = {node_id: _make_class(node_id) for node_id in ROWS}
CONVERTED_IDS = sorted(_CONVERTED)
