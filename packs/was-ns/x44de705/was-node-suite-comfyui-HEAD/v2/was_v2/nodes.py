"""WAS Node Suite as Secure Nodes V2 classes: the converted nodes, and every other declared node registered with
its real schema and a refusal (SECURE_CONVERSION.md).

Each id gets its own class (no concrete parent class), built from the original's declaration (schema_v3.py).
Pure value nodes call the original's method from originals.py (copied verbatim from WAS_Node_Suite.py by the
build); nodes that touch models, tensors or files go through the guest SDK.
"""
import codecs
import glob
import hashlib
import io as io_bytes
import json
import os
import posixpath
import random
import re
import sys

from PIL import Image, ImageOps

from comfy_api.latest import io, sdk

from . import originals
from .refusals import (CLIPSEG_WEIGHTS, IMAGE_SAVE_HISTORY, IMAGE_SAVE_JPEG, IMAGE_SAVE_LISTING,
                       IMAGE_SAVE_OVERWRITE, IMAGE_SAVE_PATH, IMAGE_SAVE_PREFIX, IMAGE_SAVE_WEBP_EMBED,
                       LOAD_BATCH_LISTING, LOAD_BATCH_PATH, LOAD_BATCH_PATTERN, NEEDS_OPENCV, NEEDS_PILGRAM,
                       NEEDS_SCIPY, NO_NETWORK, NSP_SOURCES, SAVE_TEXT_ENCODING, SAVE_TEXT_LISTING, SAVE_TEXT_NAME,
                       SAVE_TEXT_PATH, TEXT_FILE_LISTING, TEXT_FILE_PATH, SecureConversionRefusal, not_converted)
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
    # phase B batch 1 (r2)
    "Seed": ("WAS_Seed", "seed"),
    "Constant Number": ("WAS_Constant_Number", "return_constant_number"),
    "Number Operation": ("WAS_Number_Operation", "math_operations"),
    "Latent Input Switch": ("WAS_Latent_Input_Switch", "latent_input_switch"),
    "Lora Input Switch": ("WAS_Lora_Input_Switch", "lora_input_switch"),
    "VAE Input Switch": ("WAS_VAE_Input_Switch", "vae_switch"),
    "Text Input Switch": ("WAS_Text_Input_Switch", "text_input_switch"),
    "Model Input Switch": ("WAS_Model_Input_Switch", "model_switch"),
    "Conditioning Input Switch": ("WAS_Conditioning_Input_Switch", "conditioning_input_switch"),
    "Text List": ("WAS_Text_List", "text_as_list"),
    "Text List to Text": ("WAS_Text_List_to_Text", "text_list_to_text"),
    "Text List Concatenate": ("WAS_Text_List_Concatenate", "text_concatenate_list"),
    "Text String": ("WAS_Text_String", "text_string"),
    "Text Multiline (Code Compatible)": ("WAS_Text_Multiline_Raw", "text_multiline"),
    "Text Parse Tokens": ("WAS_Text_Parse_Tokens", "text_parse_tokens"),
    "Number to String": ("WAS_Number_To_String", "number_to_string"),
    "Number to Float": ("WAS_Number_To_Float", "number_to_float"),
    "Number to Text": ("WAS_Number_To_Text", "number_to_text"),
    "Logic Boolean": ("WAS_Boolean", "return_boolean"),
    "Text Compare": ("WAS_Text_Compare", "text_compare"),
    "Text String Truncate": ("WAS_Text_String_Truncate", "truncate_string"),
    "Text Random Line": ("WAS_Text_Random_Line", "text_random_line"),
    # phase B batch 2 (r3): tensors arrive and leave as raw values (the guest's values mode)
    "Image Size to Number": ("WAS_Image_Size_To_Number", "image_width_height"),
    "Latent Size to Number": ("WAS_Latent_Size_To_Number", "latent_width_height"),
    "Create Grid Image from Batch": ("WAS_Image_Grid_Image_Batch", "smart_grid_image"),
    "Image Batch": ("WAS_Image_Batch", "image_batch"),
    "Images to RGB": ("WAS_Images_To_RGB", "image_to_rgb"),
    "Tensor Batch to Image": ("WAS_Tensor_Batch_to_Image", "tensor_batch_to_image"),
    "Convert Masks to Images": ("WAS_Mask_To_Image", "mask_to_image"),
    "Masks Combine Batch": ("WAS_Mask_Combine_Batch", "combine_masks"),
    "Image to Seed": ("WAS_Image_To_Seed", "image_to_seed"),
    "Image Blank": ("WAS_Image_Blank", "blank_image"),
    # phase B batch 3 (r4)
    "Image Blend": ("WAS_Image_Blend", "image_blend"),
    "Image Bloom Filter": ("WAS_Image_Bloom_Filter", "image_bloom"),
    "Image Bounds": ("WAS_Image_Bounds", "image_bounds"),
    "Image Chromatic Aberration": ("WAS_Image_Chromatic_Aberration", "image_chromatic_aberration"),
    "Image Crop Location": ("WAS_Image_Crop_Location", "image_crop_location"),
    "Image Levels Adjustment": ("WAS_Image_Levels", "apply_image_levels"),
    "Image Paste Crop": ("WAS_Image_Paste_Crop", "image_paste_crop"),
    "Image Resize": ("WAS_Image_Rescale", "image_rescale"),
    "Image Rotate": ("WAS_Image_Rotate", "image_rotate"),
    "Image Select Color": ("WAS_Image_Select_Color", "select_color"),
    "Bounded Image Blend with Mask": ("WAS_Bounded_Image_Blend_With_Mask", "bounded_image_blend_with_mask"),
    "Bounded Image Crop with Mask": ("WAS_Bounded_Image_Crop_With_Mask", "bounded_image_crop_with_mask"),
    "Masks Subtract": ("WAS_Mask_Subtract", "subtract_masks"),
    "Text Find and Replace Input": ("WAS_Search_and_Replace_Input", "text_search_and_replace"),
    "Bus Node": ("WAS_Bus", "bus_fn"),
    "Blend Latents": ("WAS_Blend_Latents", "latent_blend"),
    "Image Film Grain": ("WAS_Film_Grain", "film_grain"),
    # phase B batch 4 (r5)
    "Random Number": ("WAS_Random_Number", "return_randm_number"),
    "Image Stitch": ("WAS_Image_Stitch", "image_stitching"),
    "Mask Gaussian Region": ("WAS_Mask_Gaussian_Region", "gaussian_region"),
    # phase B batch 6 (r6)
    "Image Transpose": ("WAS_Image_Transpose", "image_transpose"),
    "Mask Invert": ("WAS_Mask_Invert", "add_masks"),
    "Image Flip": ("WAS_Image_Flip", "image_flip"),
    # phase B batch 8
    "Image Monitor Effects Filter": ("WAS_Image_Monitor_Distortion_Filter", "image_monitor_filters"),
}
# WAS_Mask_Combine_Batch.__init__ only builds a WAS_Tools_Class (WAS_Node_Suite.py:1022-2456, the pack's large filter
# toolbox), which combine_masks never uses; V2 creates the instance without running __init__.
_SKIP_INIT = {"Masks Combine Batch"}
# Refused by name until the pack's guest runtime provides their dependency (SECURE_CONVERSION.md).
_NAMED_REFUSALS = {
    "Image Lucy Sharpen": NEEDS_SCIPY.format(node="Image Lucy Sharpen", use="scipy.signal.convolve2d"),
    "Mask Fill Holes": NEEDS_SCIPY.format(node="Mask Fill Holes", use="scipy.ndimage.binary_fill_holes"),
    "Text Random Prompt": NO_NETWORK.format(node="Text Random Prompt"),
    # WAS_Tools_Class.shadows_and_highlights / dragan_filter and WAS_Image_Style_Filter (WAS_Node_Suite.py:1700-1793,
    # 3063-3067) import pilgram when they run
    "Image Shadows and Highlights": NEEDS_PILGRAM.format(node="Image Shadows and Highlights",
                                                         use="pilgram.css.blending.color"),
    "Image Dragan Photography Filter": NEEDS_PILGRAM.format(node="Image Dragan Photography Filter",
                                                            use="pilgram.css.blending.overlay and color"),
    "Image Style Filter": NEEDS_PILGRAM.format(node="Image Style Filter", use="its photo filters"),
    # phase B batch 9: WAS_Image_Crop_Face and WAS_Tools_Class.VideoWriter import cv2 (WAS_Node_Suite.py:3139-3276,
    # 1268-1473); WAS_CLIPSeg downloads its model (11628-11629); nsp_parse fetches the NSP pantry (528-535)
    "Image Crop Face": NEEDS_OPENCV.format(node="Image Crop Face", use="cv2 cascade classifiers"),
    "Create Video from Path": NEEDS_OPENCV.format(node="Create Video from Path", use="cv2 video writing"),
    "Video Dump Frames": NEEDS_OPENCV.format(node="Video Dump Frames", use="cv2 video reading"),
    "CLIPSeg Masking": CLIPSEG_WEIGHTS,
    "CLIPTextEncode (NSP)": NSP_SOURCES,
}
# The original's IS_CHANGED, as V2 fingerprint_inputs (WAS_Node_Suite.py:11030-11032: always changed)
# Random Number's IS_CHANGED raises (hashlib's update on an int, WAS_Node_Suite.py:12552-12556); core turns that into
# NaN, so it too re-runs on every prompt.
_ALWAYS_CHANGED = {"Text Parse Tokens", "Text Find and Replace Input", "Random Number"}


def _pure_execute(class_name, function, construct=True):
    def execute(cls, **kwargs):
        original = getattr(originals, class_name)
        instance = original() if construct else original.__new__(original)
        return _node_output(getattr(instance, function)(**kwargs))
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


# ---- model loaders (phase B batch 4, r5): the same core loaders the original called, through the host's catalogue
def _catalogue_validate(folder, input_name):
    async def validate(cls, **kwargs):
        # Core's menu check on the original's INPUT_TYPES list (execution.py "Value not in list"); V2's menu is the
        # host catalogue route, so the check runs here.
        value = kwargs.get(input_name)
        catalogue = list(await sdk.ctx().assets.list(folder))
        if value in catalogue:
            return True
        return f"Value not in list: {input_name}: '{value}' not in {catalogue}"
    return validate


def _combine_validators(*validators):
    async def validate(cls, **kwargs):
        for check in validators:
            result = await check(cls, **kwargs)
            if result is not True:
                return result
        return True
    return validate


def _model_label(name):
    return os.path.splitext(os.path.basename(name))[0]


async def _checkpoint_loader_simple(cls, ckpt_name):
    # WAS_Node_Suite.py:13868-13871: comfy.sd.load_checkpoint_guess_config, then the file name without its extension.
    model, clip, vae = await sdk.ctx().models.load_checkpoint(ckpt_name)
    return io.NodeOutput(model, clip, vae, _model_label(ckpt_name))


async def _checkpoint_loader(cls, config_name, ckpt_name):
    # WAS_Node_Suite.py:13822-13826: comfy.sd.load_checkpoint with the chosen config.
    model, clip, vae = await sdk.ctx().models.load_checkpoint(ckpt_name, config_name=config_name)
    return io.NodeOutput(model, clip, vae, _model_label(ckpt_name))


async def _upscale_model_loader(cls, model_name):
    # WAS_Node_Suite.py:13995-13999: comfy.utils.load_torch_file and the spandrel model loader.
    return io.NodeOutput(await sdk.ctx().models.load_upscale_model(model_name), model_name)


# ---- Load Image Batch (WAS_Load_Image_Batch, WAS_Node_Suite.py:5313-5437), phase B batch 7
# Folder reads go through the SDK as in the converted directory loaders of other packs: ctx.assets.list over the input
# folder, then ctx.assets.resolve and read_bytes for each file. In the guest a host-side error reaches the pack as a
# transport error rather than as its builtin type, so no branch here depends on an exception's type.
# ALLOWED_EXT (WAS_Node_Suite.py:162-163)
_IMAGE_EXTENSIONS = ('.jpeg', '.jpg', '.png', '.tiff', '.gif', '.bmp', '.webp')
_DRIVE = re.compile(r"^[A-Za-z]:")


def _batch_folder(path):
    """The input-folder subfolder that the original's `path` names. The original globbed `path` on the host, relative
    to ComfyUI's working directory, where `input` is the input folder; a V2 node reads only that folder. Backslashes
    count as separators, as on a Windows host."""
    text = path.replace("\\", "/")
    if text.startswith("/") or _DRIVE.match(text):
        raise SecureConversionRefusal(LOAD_BATCH_PATH.format(path=path))
    normalized = posixpath.normpath(text)
    if normalized == "input":
        return ""
    if normalized.startswith("input/"):
        return normalized[len("input/"):]
    raise SecureConversionRefusal(LOAD_BATCH_PATH.format(path=path))


def _batch_pattern(pattern):
    """The original's pattern relative to the folder (glob.glob(os.path.join(glob.escape(path), pattern),
    recursive=True), WAS_Node_Suite.py:5395-5399), and whether it reaches into subfolders. A '.' part or a doubled
    separator names the same files for glob and is dropped; the last part is kept as it is (a trailing separator
    matches only folders). An absolute pattern or a '..' part reads outside the folder and is refused."""
    text = pattern.replace("\\", "/")
    parts = text.split("/")
    if text.startswith("/") or _DRIVE.match(text) or ".." in parts:
        raise SecureConversionRefusal(LOAD_BATCH_PATTERN.format(pattern=pattern))
    kept = [part for part in parts[:-1] if part not in ("", ".")] + parts[-1:]
    return "/".join(kept), len(kept) > 1 or kept == ["**"]


def _listing_refusal(folder, error):
    return SecureConversionRefusal(LOAD_BATCH_LISTING.format(path=posixpath.join("input", folder), reason=error))


async def _batch_paths(folder, pattern):
    """BatchImageLoader.load_images (WAS_Node_Suite.py:5395-5399): glob.glob(os.path.join(glob.escape(path), pattern),
    recursive=True), image extensions only, then sorted by absolute path, which within one folder is the order of the
    names. Returns (whether the original's os.path.exists(path) held, as far as the SDK can tell, the batch)."""
    pattern, recursive = _batch_pattern(pattern)
    assets = sdk.ctx().assets
    try:
        if folder and await assets.exists("input", folder):
            return True, []  # path names a file: the original's glob inside it found nothing
        listed = list(await assets.list("input", prefix=folder, recursive=recursive))
    except Exception as error:  # the host's listing limit (4096 names) or a folder it cannot confine to the input
        raise _listing_refusal(folder, error) from error
    exists = bool(listed)
    if not exists and not recursive:
        # Files only in subfolders: the folder exists for os.path.exists. The SDK lists files, not folders.
        try:
            exists = bool(await assets.list("input", prefix=folder, recursive=True))
        except Exception:
            exists = True  # more files below than the host lists at once
    matcher = re.compile(glob.translate(pattern, recursive=True, include_hidden=False))
    batch = []
    for name in listed:
        relative = name[len(folder) + 1:] if folder else name
        if matcher.match(relative) and relative.lower().endswith(_IMAGE_EXTENSIONS):
            batch.append(name)
    return exists, sorted(batch)


def _batch_key(label):
    return "load-image-batch:" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:40]


async def _batch_state(label, path, pattern):
    """BatchImageLoader.__init__ (WAS_Node_Suite.py:5379-5393): the label's counter, reset to 0 (and stored with the
    new path and pattern) when the label's stored path or pattern differ. The original kept these in its database in
    the pack folder; V2 keeps them in the pack's host storage."""
    storage = sdk.ctx().storage
    stored = await storage.get(_batch_key(label))
    state = json.loads(stored) if stored else {}
    if state.get("path") != path or state.get("pattern") != pattern:
        state = {"label": label, "path": path, "pattern": pattern, "counter": 0}
        await storage.set(_batch_key(label), json.dumps(state))
    return state


async def _batch_open(name):
    data = await sdk.ctx().assets.read_bytes(await sdk.ctx().assets.resolve("input", name))
    image = Image.open(io_bytes.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    return (image, posixpath.basename(name))


async def _batch_by_id(names, image_id):
    # get_image_by_id (WAS_Node_Suite.py:5401-5407): an invalid index prints and returns None
    if image_id < 0 or image_id >= len(names):
        originals.cstr(f"Invalid image index `{image_id}`").error.print()
        return
    return await _batch_open(names[image_id])


async def _load_image_batch(cls, path, pattern='*', index=0, mode="single_image", seed=0, label='Batch 001',
                            allow_RGBA_output='false', filename_text_extension='true'):
    allow_RGBA_output = (allow_RGBA_output == 'true')
    if not path:
        return io.NodeOutput(None)  # os.path.exists('') is False: the original returned (None, )
    folder = _batch_folder(path)
    exists, names = await _batch_paths(folder, pattern)
    if not exists:
        return io.NodeOutput(None)  # no such folder in the input folder: the original returned (None, )
    state = await _batch_state(label, path, pattern)
    if mode == 'single_image':
        image, filename = await _batch_by_id(names, index)
    elif mode == 'incremental_image':
        # get_next_image (WAS_Node_Suite.py:5409-5420)
        counter = state["counter"]
        if counter >= len(names):
            counter = 0
        name = names[counter]
        counter += 1
        if counter == len(names):
            counter = 0
        originals.cstr(f'{originals.cstr.color.YELLOW}{label}{originals.cstr.color.END} Index: {counter}').msg.print()
        state["counter"] = counter
        await sdk.ctx().storage.set(_batch_key(label), json.dumps(state))
        image, filename = await _batch_open(name)
    else:
        random.seed(seed)
        newindex = int(random.random() * len(names))
        image, filename = await _batch_by_id(names, newindex)
    if not allow_RGBA_output:
        image = image.convert("RGB")
    if filename_text_extension == "false":
        filename = os.path.splitext(filename)[0]
    return io.NodeOutput(originals.pil2tensor(image), filename)


async def _load_image_batch_fingerprint(cls, **kwargs):
    # IS_CHANGED (WAS_Node_Suite.py:5428-5437): always changed in the incremental and random modes. For a single image,
    # the sha256 of os.path.join(path, <base name of the file at the label's stored counter>). Whatever fails there (an
    # empty batch, a file in a subfolder, which that join misses) makes core count the node as changed, as it did for
    # the original.
    if kwargs['mode'] != 'single_image':
        return float("NaN")
    path, pattern, label = kwargs['path'], kwargs['pattern'], kwargs['label']
    folder = _batch_folder(path)
    _exists, names = await _batch_paths(folder, pattern)
    state = await _batch_state(label, path, pattern)
    counter = state["counter"] if state["counter"] < len(names) else 0
    assets = sdk.ctx().assets
    target = posixpath.join(folder, posixpath.basename(names[counter]))
    return await assets.digest(await assets.resolve("input", target), "sha256")


async def _load_image_batch_validate(cls, path=None, pattern=None):
    # A path or pattern that leaves the input folder is refused before the prompt runs; linked values are checked when
    # the node runs.
    try:
        if isinstance(path, str) and path:
            _batch_folder(path)
        if isinstance(pattern, str):
            _batch_pattern(pattern)
    except SecureConversionRefusal as refusal:
        return str(refusal)
    return True


# ---- text files (phase B batch 9): Load Text File, Text Load Line From File, Save Text File
# The originals resolved a file path against ComfyUI's working directory, where input, output and temp are ComfyUI's
# folders. V2 reads only inside those three folders (ctx.assets) and writes only inside output or temp
# (ctx.output.write_text). The original also recorded every file it read or wrote in its history database; V2 keeps
# no such history.
_TEXT_FOLDERS = ("input", "output", "temp")
_TEXT_WRITE_FOLDERS = ("output", "temp")
# The extensions the managed text writer accepts (comfy_api output.write_text)
_TEXT_WRITE_EXTENSIONS = (".txt", ".caption", ".json", ".yaml", ".yml", ".md", ".csv", ".tsv", ".xml", ".log", ".ini",
                          ".toml")
_TEXT_WRITE_LIMIT = 960 * 1024  # below the guest wire's 1 MiB frame, which carries the text to the writer


def _text_location(node, path, folders=_TEXT_FOLDERS, refusal=TEXT_FILE_PATH):
    """(folder, logical name) for a path inside one of ComfyUI's folders, else a named refusal. Backslashes count as
    separators, as on a Windows host."""
    text = path.replace("\\", "/")
    if text.startswith("/") or _DRIVE.match(text):
        raise SecureConversionRefusal(refusal.format(node=node, path=path))
    head, _, rest = posixpath.normpath(text).partition("/")
    if head in folders:
        return head, rest
    raise SecureConversionRefusal(refusal.format(node=node, path=path))


async def _text_kind(node, folder, name, path):
    """What os.path.exists(path) found: "file", "folder" or None. The SDK lists files, so a folder that holds no files
    reads as missing."""
    if not name:
        return "folder"
    assets = sdk.ctx().assets
    try:
        if await assets.exists(folder, name):
            return "file"
        below = await assets.list(folder, prefix=name, recursive=True)
    except Exception as error:  # in a guest a host error arrives as a transport error
        raise SecureConversionRefusal(TEXT_FILE_LISTING.format(node=node, path=path, reason=error)) from error
    return "folder" if below else None


async def _text_open(folder, name, kind, path):
    """open(path, 'r', encoding="utf-8", newline='\\n') on the asset's bytes; for a folder, the IsADirectoryError that
    open() raised."""
    if kind == "folder":
        raise IsADirectoryError(21, "Is a directory", path)
    assets = sdk.ctx().assets
    data = await assets.read_bytes(await assets.resolve(folder, name))
    return io_bytes.TextIOWrapper(io_bytes.BytesIO(data), encoding="utf-8", newline="\n")


def _text_validate(node):
    async def validate(cls, file_path=None):
        # A path outside ComfyUI's folders is refused before the prompt runs; a linked path when the node runs.
        if isinstance(file_path, str) and file_path:
            try:
                _text_location(node, file_path)
            except SecureConversionRefusal as refusal:
                return str(refusal)
        return True
    return validate


async def _load_text_file(cls, file_path='', dictionary_name='[filename]]'):
    # WAS_Text_Load_From_File.load_file (WAS_Node_Suite.py:11210-11232)
    filename = (os.path.basename(file_path).split('.', 1)[0]
                if '.' in os.path.basename(file_path) else os.path.basename(file_path))
    if dictionary_name != '[filename]':
        filename = dictionary_name
    kind = None
    if file_path:  # os.path.exists('') is False
        folder, name = _text_location("Load Text File", file_path)
        kind = await _text_kind("Load Text File", folder, name, file_path)
    if kind is None:
        originals.cstr(f"The path `{file_path}` specified cannot be found.").error.print()
        return io.NodeOutput('', {filename: []})
    with await _text_open(folder, name, kind, file_path) as file:
        text = file.read()

    lines = []
    for line in io_bytes.StringIO(text):
        if not line.strip().startswith('#'):
            lines.append(line.replace("\n", '').replace("\r", ''))
    dictionary = {filename: lines}

    return io.NodeOutput("\n".join(lines), dictionary)


def _text_batch_index(position):
    color = originals.cstr.color
    originals.cstr(f'{color.YELLOW}TextBatch{color.END} Index: {position}').msg.print()


def _text_batch_key(kind, label):
    return f"text-load-line:{kind}:" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:40]


async def _text_load_line(cls, file_path='', dictionary_name='[filename]', label='TextBatch', mode='automatic',
                          index=0, multiline_text=None):
    # WAS_Text_Load_Line_From_File.load_file and TextFileLoader (WAS_Node_Suite.py:11274-11363). The original kept the
    # file mode's counter and path per label in its settings database and the multiline mode's counter per label in
    # its history database; V2 keeps both in the pack's host storage, under separate keys.
    storage = sdk.ctx().storage
    if multiline_text is not None:
        lines = multiline_text.strip().split('\n')
        if mode == 'index':
            if index < 0 or index >= len(lines):
                originals.cstr(f"Invalid line index `{index}`").error.print()
                return io.NodeOutput('', {dictionary_name: []})
            line = lines[index]
        else:
            key = _text_batch_key("multiline", label)
            stored = await storage.get(key)
            line_index = json.loads(stored) if stored is not None else None
            if line_index is None:
                line_index = 0
            line = lines[line_index % len(lines)]
            await storage.set(key, json.dumps(line_index + 1))
        return io.NodeOutput(line, {dictionary_name: lines})

    if file_path == '':
        originals.cstr("No file path specified.").error.print()
        return io.NodeOutput('', {dictionary_name: []})

    folder, name = _text_location("Text Load Line From File", file_path)
    kind = await _text_kind("Text Load Line From File", folder, name, file_path)
    if kind is None:
        originals.cstr(f"The path `{file_path}` specified cannot be found.").error.print()
        return io.NodeOutput('', {dictionary_name: []})

    # TextFileLoader.load_file: the label's counter, reset to 0 (with the new path) when its stored path differs,
    # before the file is opened
    key = _text_batch_key("file", label)
    stored = await storage.get(key)
    state = json.loads(stored) if stored else {}
    if state.get("path") != file_path:
        state = {"label": label, "path": file_path, "counter": 0}
        await storage.set(key, json.dumps(state))
    position = state["counter"]
    with await _text_open(folder, name, kind, file_path) as file:
        lines = [line.strip() for line in file]

    line, found_lines = None, []
    if mode == 'automatic':
        # get_next_line
        if position >= len(lines):
            position = 0
        line = lines[position]
        position += 1
        if position == len(lines):
            position = 0
        _text_batch_index(position)
        found_lines = lines
    elif mode == 'index':
        if index >= len(lines):
            index = index % len(lines)
        # get_line_by_index
        if index < 0 or index >= len(lines):
            originals.cstr(f"Invalid line index `{index}`").error.print()
        else:
            position = index
            line = lines[position]
            _text_batch_index(position)
            found_lines = lines
    if line is None:
        originals.cstr("No valid line was found. The file may be empty or all lines have been read.").error.print()
        return io.NodeOutput('', {dictionary_name: []})
    state["counter"] = position  # store_index
    await storage.set(key, json.dumps(state))

    return io.NodeOutput(line, {dictionary_name: found_lines})


async def _text_load_line_fingerprint(cls, **kwargs):
    # IS_CHANGED (WAS_Node_Suite.py:11255-11266): always changed in automatic mode; in index mode the sha256 of the
    # file, or False when there is no such file.
    if kwargs['mode'] != 'index':
        return float("NaN")
    file_path = kwargs['file_path']
    if file_path == '':
        return False
    folder, name = _text_location("Text Load Line From File", file_path)
    kind = await _text_kind("Text Load Line From File", folder, name, file_path)
    if kind is None:
        return False
    if kind == "folder":  # the original's open(path, 'rb') raised; core then counts the node as changed
        raise IsADirectoryError(21, "Is a directory", file_path)
    assets = sdk.ctx().assets
    return await assets.digest(await assets.resolve(folder, name), "sha256")


def _save_text_checks(path, encoding, filename_prefix, filename_suffix, file_extension):
    folder, sub = _text_location("Save Text File", path, _TEXT_WRITE_FOLDERS, SAVE_TEXT_PATH)
    if codecs.lookup(encoding).name != 'utf-8':  # an unknown name raises the LookupError the original's open() raised
        raise SecureConversionRefusal(SAVE_TEXT_ENCODING.format(encoding=encoding))
    for part in (filename_prefix, filename_suffix, file_extension):
        if "/" in part or "\\" in part:
            raise SecureConversionRefusal(SAVE_TEXT_NAME.format(
                name=f"{filename_prefix}{filename_suffix}{file_extension}", why="it holds a folder separator"))
    if file_extension.lower() not in _TEXT_WRITE_EXTENSIONS:
        raise SecureConversionRefusal(SAVE_TEXT_NAME.format(
            name=f"{filename_prefix}{filename_suffix}{file_extension}",
            why="the managed text writer accepts only " + ", ".join(_TEXT_WRITE_EXTENSIONS)))
    return folder, sub


async def _save_text_file(cls, text, path, filename_prefix='ComfyUI', filename_delimiter='_',
                          filename_number_padding=4, file_extension='.txt', encoding='utf-8', filename_suffix=''):
    # WAS_Text_Save.save_text_file, generate_filename and write_text_file (WAS_Node_Suite.py:10848-10916)
    tokens = TextTokens()
    path = tokens.parseTokens(path)
    filename_prefix = tokens.parseTokens(filename_prefix)
    folder, sub = _save_text_checks(path, encoding, filename_prefix, filename_suffix, file_extension)
    size = len(text.encode("utf-8"))
    if size > _TEXT_WRITE_LIMIT:
        raise SecureConversionRefusal(SAVE_TEXT_NAME.format(
            name=f"{filename_prefix}{filename_suffix}{file_extension}",
            why=f"the text takes {size} bytes, more than a Secure Nodes V2 node can write at once"))

    if text.strip() == '':
        originals.cstr("There is no text specified to save! Text is empty.").error.print()

    delimiter = filename_delimiter
    number_padding = int(filename_number_padding)
    prefix, suffix, extension = filename_prefix, filename_suffix, file_extension
    assets = sdk.ctx().assets
    if number_padding == 0:
        # If number_padding is 0, don't use a numerical suffix
        filename = f"{prefix}{suffix}{extension}"
    else:
        if delimiter:
            pattern = f"{re.escape(prefix)}{re.escape(delimiter)}(\\d{{{number_padding}}}){re.escape(suffix)}{re.escape(extension)}"
        else:
            pattern = f"{re.escape(prefix)}(\\d{{{number_padding}}}){re.escape(suffix)}{re.escape(extension)}"
        try:  # os.listdir(path)
            listed = [posixpath.basename(name) for name in await assets.list(folder, prefix=sub, recursive=False)]
        except Exception as error:  # in a guest a host error arrives as a transport error
            where = posixpath.join(folder, sub)
            raise SecureConversionRefusal(SAVE_TEXT_LISTING.format(path=where, reason=error)) from error
        existing_counters = [
            int(re.search(pattern, filename).group(1))
            for filename in listed
            if re.match(pattern, filename) and filename.endswith(extension)
        ]
        existing_counters.sort()
        if existing_counters:
            counter = existing_counters[-1] + 1
        else:
            counter = 1
        if delimiter:
            filename = f"{prefix}{delimiter}{counter:0{number_padding}}{suffix}{extension}"
        else:
            filename = f"{prefix}{counter:0{number_padding}}{suffix}{extension}"

        while await assets.exists(folder, posixpath.join(sub, filename) if sub else filename):
            counter += 1
            if delimiter:
                filename = f"{prefix}{delimiter}{counter:0{number_padding}}{suffix}{extension}"
            else:
                filename = f"{prefix}{counter:0{number_padding}}{suffix}{extension}"

    logical = posixpath.join(sub, filename) if sub else filename
    await sdk.ctx().output.write_text(text, filename=logical, folder=folder, mode="overwrite")
    return io.NodeOutput()


async def _save_text_validate(cls, path=None, encoding=None, filename_prefix=None, filename_suffix=None,
                              file_extension=None):
    # The path, encoding and file name checks of _save_text_file, before the prompt runs (widget values only)
    values = (path, encoding, filename_prefix, filename_suffix, file_extension)
    if all(isinstance(value, str) for value in values):
        try:
            tokens = TextTokens()
            _save_text_checks(tokens.parseTokens(path), encoding, tokens.parseTokens(filename_prefix),
                              filename_suffix, file_extension)
        except SecureConversionRefusal as refusal:
            return str(refusal)
        except LookupError:  # an unknown encoding fails when the node runs, as the original's open() did
            pass
    return True


# ---- Number Counter (WAS_Number_Counter.increment_number, WAS_Node_Suite.py:12706-12730), phase B batch 9
async def _number_counter(cls, number_type, mode, start, stop, step, reset_bool=0):
    # The original kept each node's counter on the node object, keyed by the node id, for as long as ComfyUI kept
    # that object. V2 keeps it in the pack's host storage under the node id and runs the original method on it.
    unique_id = cls.hidden.unique_id
    key = "number-counter:" + hashlib.sha256(str(unique_id).encode("utf-8")).hexdigest()[:40]
    storage = sdk.ctx().storage
    node = originals.WAS_Number_Counter()
    stored = await storage.get(key)
    if stored is not None:
        node.counters[unique_id] = json.loads(stored)
    result = node.increment_number(number_type, mode, start, stop, step, unique_id, reset_bool=reset_bool)
    await storage.set(key, json.dumps(node.counters[unique_id]))
    return io.NodeOutput(*result)


# ---- Prompt Styles Selector (WAS_Prompt_Styles_Selector.load_style, WAS_Node_Suite.py:9825-9841), phase B batch 9
def _prompt_styles_selector(cls, style):
    # The original read styles.json from its configuration folder. With the default configuration there is no such
    # file (its menu then holds only "None"), and V2 ships none either, so the styles are empty, as there.
    originals.cstr("The styles file does not exist. Unable to load styles! Have you imported your AUTOMATIC1111 "
                   "WebUI styles?").error.print()
    styles = {}
    if styles and style != None or style != 'None':  # noqa: E711 (the original's test)
        prompt = styles[style]['prompt']
        negative_prompt = styles[style]['negative_prompt']
    else:
        prompt = ''
        negative_prompt = ''
    return io.NodeOutput(prompt, negative_prompt)


# ---- Image Save (WAS_Image_Save.was_save_images)
_WEBP_EMBED_LIMIT = 960 * 1024  # below the guest wire's 1 MiB frame, which carries this metadata to the writer


def _webp_embed_metadata(prompt, extra_pnginfo):
    """WAS_Node_Suite.py:7452-7464 (webp with embed_workflow): EXIF 0x010F holds "Prompt:" + json.dumps(prompt) and
    0x010E holds "Workflow:" + the json.dumps of every extra_pnginfo value, joined. Given save_metadata=False and
    extra_metadata, the managed writer stores "<key>:" + json.dumps(value) in 0x010F, 0x010E, ... in key order
    (ImageSaveHelper._create_webp_metadata), so the two agree when the prompt has exactly one extra_pnginfo entry."""
    if prompt is None:
        why = "there is no prompt, so the original writes the Workflow tag alone"
    elif not isinstance(extra_pnginfo, dict) or len(extra_pnginfo) != 1:
        count = len(extra_pnginfo) if isinstance(extra_pnginfo, dict) else 0
        why = f"the prompt has {count} workflow entries"
    else:
        metadata = {"Prompt": prompt, "Workflow": next(iter(extra_pnginfo.values()))}
        try:
            size = len(json.dumps(metadata, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError):
            why = "the prompt or workflow holds values that are not plain JSON, such as NaN or Infinity"
        else:
            if size <= _WEBP_EMBED_LIMIT:
                return metadata
            why = f"the prompt and workflow take {size} bytes"
    raise SecureConversionRefusal(IMAGE_SAVE_WEBP_EMBED.format(why=why))


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
    webp_metadata = None
    if extension == "webp" and embed_workflow == "true":
        webp_metadata = _webp_embed_metadata(prompt, extra_pnginfo)
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
    except Exception as error:  # the host's listing limit; in a guest it arrives as a transport error
        raise SecureConversionRefusal(IMAGE_SAVE_LISTING.format(path=folder or "output", reason=error)) from error
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
                if webp_metadata is not None:
                    options["extra_metadata"] = webp_metadata
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
def _always_changed(cls, **kwargs):
    return float("NaN")


# Switches between engine objects: they take handles (SDK_REFS) and return the chosen one unchanged, as the original
# returned the chosen object. Without handles the guest would have to materialize a MODEL, CLIP or VAE.
_PASS_THROUGH_REFS = {"Latent Input Switch", "Lora Input Switch", "VAE Input Switch", "Model Input Switch",
                      "Conditioning Input Switch", "Bus Node"}

_CONVERTED = {}
for _node_id, (_class_name, _function) in _PURE.items():
    _CONVERTED[_node_id] = {"execute": classmethod(_pure_execute(_class_name, _function,
                                                                 construct=_node_id not in _SKIP_INIT))}
    if _node_id in _ALWAYS_CHANGED:
        _CONVERTED[_node_id]["fingerprint_inputs"] = classmethod(_always_changed)
    if _node_id in _PASS_THROUGH_REFS:
        _CONVERTED[_node_id]["SDK_REFS"] = True
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
_CONVERTED["Checkpoint Loader (Simple)"] = {
    "execute": classmethod(_checkpoint_loader_simple), "SDK_REFS": True, "SDK_PERMISSIONS": ("assets", "models"),
    "validate_inputs": classmethod(_catalogue_validate("checkpoints", "ckpt_name"))}
_CONVERTED["Checkpoint Loader"] = {
    "execute": classmethod(_checkpoint_loader), "SDK_REFS": True, "SDK_PERMISSIONS": ("assets", "models"),
    "validate_inputs": classmethod(_combine_validators(_catalogue_validate("configs", "config_name"),
                                                       _catalogue_validate("checkpoints", "ckpt_name")))}
_CONVERTED["Load Image Batch"] = {
    "execute": classmethod(_load_image_batch), "fingerprint_inputs": classmethod(_load_image_batch_fingerprint),
    "validate_inputs": classmethod(_load_image_batch_validate), "SDK_PERMISSIONS": ("assets", "storage")}
_CONVERTED["Load Text File"] = {
    "execute": classmethod(_load_text_file), "validate_inputs": classmethod(_text_validate("Load Text File")),
    "SDK_PERMISSIONS": ("assets",)}
# No validate_inputs: with multiline_text connected the original ignores file_path, so a path is refused only when
# the file mode runs.
_CONVERTED["Text Load Line From File"] = {
    "execute": classmethod(_text_load_line), "fingerprint_inputs": classmethod(_text_load_line_fingerprint),
    "SDK_PERMISSIONS": ("assets", "storage")}
_CONVERTED["Save Text File"] = {
    "execute": classmethod(_save_text_file), "validate_inputs": classmethod(_save_text_validate),
    "SDK_PERMISSIONS": ("assets", "output")}
# IS_CHANGED returns NaN (WAS_Node_Suite.py:12696-12698)
_CONVERTED["Number Counter"] = {
    "execute": classmethod(_number_counter), "fingerprint_inputs": classmethod(_always_changed),
    "SDK_PERMISSIONS": ("storage",)}
_CONVERTED["Prompt Styles Selector"] = {"execute": classmethod(_prompt_styles_selector)}
_CONVERTED["Upscale Model Loader"] = {
    "execute": classmethod(_upscale_model_loader), "SDK_REFS": True, "SDK_PERMISSIONS": ("assets", "models"),
    "validate_inputs": classmethod(_catalogue_validate("upscale_models", "model_name"))}


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
        message = _NAMED_REFUSALS.get(node_id) or not_converted(node_id)

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
