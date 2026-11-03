"""Secure Nodes V2 classes for ComfyUI_Mira's converted node types (pin dfb1c847, a V3-native pack).

Every schema is the original class's own V3 schema, encoded in the lane gate (_frozen_schema.py). Each class is a new
io.ComfyNode (never a subclass of an original class) whose execute calls the original class's execute:
  - Arithmetic.py, Numeral.py and Text.py import only comfy_api and v3schema.py, so v2 imports them as they are;
  - Util.py's classes come from _mira_util.py and the English character selector from _mira_wai.py (verbatim copies:
    those modules import cv2, comfy, folder_paths, requests or torchvision at module level);
  - image inputs arrive as tensors (public values mode, "raw"), as the original received them.
UpscaleImageByModelThenResize is ported line for line: the engine runs the upscale model
(UpscaleModelRef.upscale(images, tile_size=512), the original's upscale() step for step), and the resize is the
original's code on the original's (vendored) torchvision PIL path.
Image Color Transfer's Lab and Pdf+Regrain methods need OpenCV, which a guest does not have: they are refused by name
(MERVYN m_b621de7da8); Mean and Pdf run the original's code.
"""
import torch
from comfy_api.latest import io, sdk

from . import _mira_util as util
from . import _mira_wai as wai
from . import _vendor_torchvision as T
from .Arithmetic import IntToFloatMultiplication as _IntToFloatMultiplication
from .Numeral import NumeralToString as _NumeralToString
from .Numeral import StepsAndCfg as _StepsAndCfg
from .Text import TextBox as _TextBox
from .Text import TextCombinerSix as _TextCombinerSix
from .Text import TextCombinerTwo as _TextCombinerTwo
from ._frozen_schema import schema_for

PACK = "comfyui_mira"


class SecureConversionRefusal(RuntimeError):
    """A behaviour of the original that this Secure Nodes V2 conversion refuses by name."""


def _output(result):
    # io.ComfyNode.EXECUTE_NORMALIZED's rule for the original's return value: a tuple becomes the node's outputs.
    return result if isinstance(result, io.NodeOutput) else io.NodeOutput(*result)


def _node(node_id, cls_name, original, permissions=(), refs=False, before=None):
    def define_schema(cls):
        return schema_for(node_id)

    def execute(cls, **kwargs):
        if before is not None:
            before(**kwargs)
        return _output(original.execute(**kwargs))

    return type(cls_name, (io.ComfyNode,), {
        "SDK_REFS": refs,
        "SDK_PERMISSIONS": tuple(permissions),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
        "__module__": __name__,
        "__qualname__": cls_name,
    })


OPENCV_METHODS = {"Lab": "cv2.cvtColor (BGR to Lab and back)", "Pdf+Regrain": "cv2.resize (the regrain pyramid)"}


def _color_transfer_refusal(src_image=None, ref_image=None, method=None):
    if method in OPENCV_METHODS:
        raise SecureConversionRefusal(
            f"{PACK}/ImageColorTransferMira: method {method!r} is not available on Secure Nodes V2. The original computes "
            f"it with OpenCV ({OPENCV_METHODS[method]}), which the guest runtime does not provide. Use 'Mean' or 'Pdf'.")


CanvasCreatorAdvanced = _node("CanvasCreatorAdvanced", "CanvasCreatorAdvanced", util.CanvasCreatorAdvanced)
CanvasCreatorSimple = _node("CanvasCreatorSimple", "CanvasCreatorSimple", util.CanvasCreatorSimple)
SeedGeneratorMira = _node("SeedGeneratorMira", "SeedGeneratorMira", util.SeedGenerator)
ImageContrast = _node("ImageContrast", "ImageContrast", util.ImageContrast, permissions=("raw",))
ImageSharpness = _node("ImageSharpness", "ImageSharpness", util.ImageSharpness, permissions=("raw",))
ImageColorTransferMira = _node("ImageColorTransferMira", "ImageColorTransferMira", util.ImageColorTransfer,
                               permissions=("raw",), before=_color_transfer_refusal)
IntToFloatMultiplication = _node("IntToFloatMultiplication", "IntToFloatMultiplication", _IntToFloatMultiplication)
NumeralToString = _node("NumeralToString", "NumeralToString", _NumeralToString)
StepsAndCfg = _node("StepsAndCfg", "StepsAndCfg", _StepsAndCfg)
TextBoxMira = _node("TextBoxMira", "TextBoxMira", _TextBox)
TextCombinerSix = _node("TextCombinerSix", "TextCombinerSix", _TextCombinerSix)
TextCombinerTwo = _node("TextCombinerTwo", "TextCombinerTwo", _TextCombinerTwo)
illustrious_character_select_en = _node("illustrious_character_select_en", "illustrious_character_select_en",
                                        wai.illustrious_character_select_en)


class UpscaleImageByModelThenResize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("UpscaleImageByModelThenResize")

    @classmethod
    async def execute(cls, upscale_model, image, resize_scale, resize_method):
        # Util.py UpscaleImageByModelThenResize.execute (L1153-1233), line for line; DecodeImage, EncodeImage and
        # Fixeight are the original's (_mira_util), T is the original's torchvision.transforms (its PIL path, vendored).
        def resize_torch_image(img, size, interpolation_mode):
            transform = T.Resize(size, interpolation=interpolation_mode, antialias=True)
            resized_img = transform(util.DecodeImage(img))
            result = util.EncodeImage(resized_img)  # [1, C, H, W]
            return result

        interpolation_mode = T.InterpolationMode.NEAREST
        if resize_method == 'nearest-exact':
            interpolation_mode = T.InterpolationMode.NEAREST_EXACT
        elif resize_method == 'bilinear':
            interpolation_mode = T.InterpolationMode.BILINEAR
        elif resize_method == 'bicubic':
            interpolation_mode = T.InterpolationMode.BICUBIC
        elif resize_method == 'lanczos':
            interpolation_mode = T.InterpolationMode.LANCZOS
        elif resize_method == 'box':
            interpolation_mode = T.InterpolationMode.BOX
        elif resize_method == 'hamming':
            interpolation_mode = T.InterpolationMode.HAMMING

        pixels = await image.raw()
        if pixels.shape[3] == 3:  # [B, H, W, C]
            width = pixels.shape[2]
            height = pixels.shape[1]
        else:   # [B, C, H, W]
            width = pixels.shape[3]
            height = pixels.shape[2]

        new_width = util.Fixeight(width*resize_scale)
        new_height = util.Fixeight(height*resize_scale)
        size = (new_height, new_width)

        # upscale() (L1160-1186) is core's ImageUpscaleWithModel: tiled_scale with 512 tiles, 32 overlap, halving the
        # tile on OOM, then clamp; the engine's UpscaleModelRef.upscale(images, tile_size=512) does the same steps.
        new_img = await (await upscale_model.upscale(image, tile_size=512)).raw()

        batch_size = new_img.shape[0]
        out_imgs = []
        if batch_size == 1:
            result = resize_torch_image(new_img, size, interpolation_mode)  # [1, C, H, W]
            out_imgs.append(result)
        else:
            for i in range(batch_size):
                img_i = new_img[i]  # [H, W, C]
                result = resize_torch_image(img_i.unsqueeze(0), size, interpolation_mode)  # [1, C, H, W]
                out_imgs.append(result)

        out_imgs_tensor = torch.cat(out_imgs, dim=0)  # [B, C, H, W]
        if out_imgs_tensor.ndim == 3:
            out_imgs_tensor = out_imgs_tensor.unsqueeze(0)
        return io.NodeOutput(await sdk.ImageRef.from_value(out_imgs_tensor))


NODE_CLASS_MAPPINGS = {
    "CanvasCreatorAdvanced": CanvasCreatorAdvanced,
    "CanvasCreatorSimple": CanvasCreatorSimple,
    "ImageColorTransferMira": ImageColorTransferMira,
    "ImageContrast": ImageContrast,
    "ImageSharpness": ImageSharpness,
    "IntToFloatMultiplication": IntToFloatMultiplication,
    "NumeralToString": NumeralToString,
    "SeedGeneratorMira": SeedGeneratorMira,
    "StepsAndCfg": StepsAndCfg,
    "TextBoxMira": TextBoxMira,
    "TextCombinerSix": TextCombinerSix,
    "TextCombinerTwo": TextCombinerTwo,
    "UpscaleImageByModelThenResize": UpscaleImageByModelThenResize,
    "illustrious_character_select_en": illustrious_character_select_en,
}
