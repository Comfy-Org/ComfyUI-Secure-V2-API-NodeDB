"""torchvision 0.23.0+cu128 transforms, the PIL-image path of adjust_contrast, adjust_sharpness and Resize, copied
verbatim (BSD-3-Clause, Copyright (c) Soumith Chintala 2016). Source: the lane gate's installed torchvision
(results/gate-vendor-v1), which the original calls. ImageContrast, ImageSharpness and the resize step of
UpscaleImageByModelThenResize pass PIL images, so only those branches run.
Names bound here (not torchvision code): _log_api_usage_once is torchvision's usage-logging hook and does nothing
here. F_pil holds _functional_pil's functions (that module's get_dimensions, adjust_contrast, adjust_sharpness and
resize, renamed _pil_* in this file so they do not shadow functional's own). F_t, the tensor path, is not vendored:
a tensor input raises. F is this module, for transforms.Resize.forward.
Copied:
#   _is_pil_image: torchvision/transforms/_functional_pil.py L17-22
#   F_pil.get_dimensions: torchvision/transforms/_functional_pil.py L25-34
#   F_pil.adjust_contrast: torchvision/transforms/_functional_pil.py L80-87
#   F_pil.adjust_sharpness: torchvision/transforms/_functional_pil.py L375-382
#   F_pil.resize: torchvision/transforms/_functional_pil.py L241-253
#   InterpolationMode: torchvision/transforms/functional.py L23-36
#   _interpolation_modes_from_int: torchvision/transforms/functional.py L41-50
#   pil_modes_mapping: torchvision/transforms/functional.py L53-61
#   get_dimensions: torchvision/transforms/functional.py L66-80
#   _compute_resized_output_size: torchvision/transforms/functional.py L353-384
#   resize: torchvision/transforms/functional.py L387-479
#   adjust_contrast: torchvision/transforms/functional.py L890-909
#   adjust_sharpness: torchvision/transforms/functional.py L1451-1470
#   Resize: torchvision/transforms/transforms.py L283-358
"""
import sys
import types
import warnings
from collections.abc import Sequence
from enum import Enum
from typing import Any, Optional, Union

import torch
from PIL import Image, ImageEnhance
from torch import Tensor

accimage = None


def _log_api_usage_once(obj):
    return None


# torchvision/transforms/_functional_pil.py L17-22 (sha256 a30262323eefa9351540515b1ff78f218ecff2ce3f6ed957b271948cc8c9a276)
@torch.jit.unused
def _is_pil_image(img: Any) -> bool:
    if accimage is not None:
        return isinstance(img, (Image.Image, accimage.Image))
    else:
        return isinstance(img, Image.Image)


# torchvision/transforms/_functional_pil.py L25-34 (sha256 a30262323eefa9351540515b1ff78f218ecff2ce3f6ed957b271948cc8c9a276)
@torch.jit.unused
def _pil_get_dimensions(img: Any) -> list[int]:
    if _is_pil_image(img):
        if hasattr(img, "getbands"):
            channels = len(img.getbands())
        else:
            channels = img.channels
        width, height = img.size
        return [channels, height, width]
    raise TypeError(f"Unexpected type {type(img)}")

# torchvision/transforms/_functional_pil.py L80-87 (sha256 a30262323eefa9351540515b1ff78f218ecff2ce3f6ed957b271948cc8c9a276)
@torch.jit.unused
def _pil_adjust_contrast(img: Image.Image, contrast_factor: float) -> Image.Image:
    if not _is_pil_image(img):
        raise TypeError(f"img should be PIL Image. Got {type(img)}")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast_factor)
    return img

# torchvision/transforms/_functional_pil.py L375-382 (sha256 a30262323eefa9351540515b1ff78f218ecff2ce3f6ed957b271948cc8c9a276)
@torch.jit.unused
def _pil_adjust_sharpness(img: Image.Image, sharpness_factor: float) -> Image.Image:
    if not _is_pil_image(img):
        raise TypeError(f"img should be PIL Image. Got {type(img)}")

    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(sharpness_factor)
    return img

# torchvision/transforms/_functional_pil.py L241-253 (sha256 a30262323eefa9351540515b1ff78f218ecff2ce3f6ed957b271948cc8c9a276)
@torch.jit.unused
def _pil_resize(
    img: Image.Image,
    size: Union[list[int], int],
    interpolation: int = Image.BILINEAR,
) -> Image.Image:

    if not _is_pil_image(img):
        raise TypeError(f"img should be PIL Image. Got {type(img)}")
    if not (isinstance(size, list) and len(size) == 2):
        raise TypeError(f"Got inappropriate size arg: {size}")

    return img.resize(tuple(size[::-1]), interpolation)


# torchvision/transforms/functional.py L23-36 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
class InterpolationMode(Enum):
    """Interpolation modes
    Available interpolation methods are ``nearest``, ``nearest-exact``, ``bilinear``, ``bicubic``, ``box``, ``hamming``,
    and ``lanczos``.
    """

    NEAREST = "nearest"
    NEAREST_EXACT = "nearest-exact"
    BILINEAR = "bilinear"
    BICUBIC = "bicubic"
    # For PIL compatibility
    BOX = "box"
    HAMMING = "hamming"
    LANCZOS = "lanczos"


# torchvision/transforms/functional.py L41-50 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
def _interpolation_modes_from_int(i: int) -> InterpolationMode:
    inverse_modes_mapping = {
        0: InterpolationMode.NEAREST,
        2: InterpolationMode.BILINEAR,
        3: InterpolationMode.BICUBIC,
        4: InterpolationMode.BOX,
        5: InterpolationMode.HAMMING,
        1: InterpolationMode.LANCZOS,
    }
    return inverse_modes_mapping[i]


# torchvision/transforms/functional.py L53-61 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
pil_modes_mapping = {
    InterpolationMode.NEAREST: 0,
    InterpolationMode.BILINEAR: 2,
    InterpolationMode.BICUBIC: 3,
    InterpolationMode.NEAREST_EXACT: 0,
    InterpolationMode.BOX: 4,
    InterpolationMode.HAMMING: 5,
    InterpolationMode.LANCZOS: 1,
}


# torchvision/transforms/functional.py L66-80 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
def get_dimensions(img: Tensor) -> list[int]:
    """Returns the dimensions of an image as [channels, height, width].

    Args:
        img (PIL Image or Tensor): The image to be checked.

    Returns:
        List[int]: The image dimensions.
    """
    if not torch.jit.is_scripting() and not torch.jit.is_tracing():
        _log_api_usage_once(get_dimensions)
    if isinstance(img, torch.Tensor):
        return F_t.get_dimensions(img)

    return F_pil.get_dimensions(img)


# torchvision/transforms/functional.py L353-384 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
def _compute_resized_output_size(
    image_size: tuple[int, int],
    size: Optional[list[int]],
    max_size: Optional[int] = None,
    allow_size_none: bool = False,  # only True in v2
) -> list[int]:
    h, w = image_size
    short, long = (w, h) if w <= h else (h, w)
    if size is None:
        if not allow_size_none:
            raise ValueError("This should never happen!!")
        if not isinstance(max_size, int):
            raise ValueError(f"max_size must be an integer when size is None, but got {max_size} instead.")
        new_short, new_long = int(max_size * short / long), max_size
        new_w, new_h = (new_short, new_long) if w <= h else (new_long, new_short)
    elif len(size) == 1:  # specified size only for the smallest edge
        requested_new_short = size if isinstance(size, int) else size[0]
        new_short, new_long = requested_new_short, int(requested_new_short * long / short)

        if max_size is not None:
            if max_size <= requested_new_short:
                raise ValueError(
                    f"max_size = {max_size} must be strictly greater than the requested "
                    f"size for the smaller edge size = {size}"
                )
            if new_long > max_size:
                new_short, new_long = int(max_size * new_short / new_long), max_size

        new_w, new_h = (new_short, new_long) if w <= h else (new_long, new_short)
    else:  # specified both h and w
        new_w, new_h = size[1], size[0]
    return [new_h, new_w]


# torchvision/transforms/functional.py L387-479 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
def resize(
    img: Tensor,
    size: list[int],
    interpolation: InterpolationMode = InterpolationMode.BILINEAR,
    max_size: Optional[int] = None,
    antialias: Optional[bool] = True,
) -> Tensor:
    r"""Resize the input image to the given size.
    If the image is torch Tensor, it is expected
    to have [..., H, W] shape, where ... means an arbitrary number of leading dimensions

    Args:
        img (PIL Image or Tensor): Image to be resized.
        size (sequence or int): Desired output size. If size is a sequence like
            (h, w), the output size will be matched to this. If size is an int,
            the smaller edge of the image will be matched to this number maintaining
            the aspect ratio. i.e, if height > width, then image will be rescaled to
            :math:`\left(\text{size} \times \frac{\text{height}}{\text{width}}, \text{size}\right)`.

            .. note::
                In torchscript mode size as single int is not supported, use a sequence of length 1: ``[size, ]``.
        interpolation (InterpolationMode): Desired interpolation enum defined by
            :class:`torchvision.transforms.InterpolationMode`.
            Default is ``InterpolationMode.BILINEAR``. If input is Tensor, only ``InterpolationMode.NEAREST``,
            ``InterpolationMode.NEAREST_EXACT``, ``InterpolationMode.BILINEAR`` and ``InterpolationMode.BICUBIC`` are
            supported.
            The corresponding Pillow integer constants, e.g. ``PIL.Image.BILINEAR`` are accepted as well.
        max_size (int, optional): The maximum allowed for the longer edge of
            the resized image. If the longer edge of the image is greater
            than ``max_size`` after being resized according to ``size``,
            ``size`` will be overruled so that the longer edge is equal to
            ``max_size``.
            As a result, the smaller edge may be shorter than ``size``. This
            is only supported if ``size`` is an int (or a sequence of length
            1 in torchscript mode).
        antialias (bool, optional): Whether to apply antialiasing.
            It only affects **tensors** with bilinear or bicubic modes and it is
            ignored otherwise: on PIL images, antialiasing is always applied on
            bilinear or bicubic modes; on other modes (for PIL images and
            tensors), antialiasing makes no sense and this parameter is ignored.
            Possible values are:

            - ``True`` (default): will apply antialiasing for bilinear or bicubic modes.
              Other mode aren't affected. This is probably what you want to use.
            - ``False``: will not apply antialiasing for tensors on any mode. PIL
              images are still antialiased on bilinear or bicubic modes, because
              PIL doesn't support no antialias.
            - ``None``: equivalent to ``False`` for tensors and ``True`` for
              PIL images. This value exists for legacy reasons and you probably
              don't want to use it unless you really know what you are doing.

            The default value changed from ``None`` to ``True`` in
            v0.17, for the PIL and Tensor backends to be consistent.

    Returns:
        PIL Image or Tensor: Resized image.
    """
    if not torch.jit.is_scripting() and not torch.jit.is_tracing():
        _log_api_usage_once(resize)

    if isinstance(interpolation, int):
        interpolation = _interpolation_modes_from_int(interpolation)
    elif not isinstance(interpolation, InterpolationMode):
        raise TypeError(
            "Argument interpolation should be a InterpolationMode or a corresponding Pillow integer constant"
        )

    if isinstance(size, (list, tuple)):
        if len(size) not in [1, 2]:
            raise ValueError(
                f"Size must be an int or a 1 or 2 element tuple/list, not a {len(size)} element tuple/list"
            )
        if max_size is not None and len(size) != 1:
            raise ValueError(
                "max_size should only be passed if size specifies the length of the smaller edge, "
                "i.e. size should be an int or a sequence of length 1 in torchscript mode."
            )

    _, image_height, image_width = get_dimensions(img)
    if isinstance(size, int):
        size = [size]
    output_size = _compute_resized_output_size((image_height, image_width), size, max_size)

    if [image_height, image_width] == output_size:
        return img

    if not isinstance(img, torch.Tensor):
        if antialias is False:
            warnings.warn("Anti-alias option is always applied for PIL Image input. Argument antialias is ignored.")
        pil_interpolation = pil_modes_mapping[interpolation]
        return F_pil.resize(img, size=output_size, interpolation=pil_interpolation)

    return F_t.resize(img, size=output_size, interpolation=interpolation.value, antialias=antialias)


# torchvision/transforms/functional.py L890-909 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
def adjust_contrast(img: Tensor, contrast_factor: float) -> Tensor:
    """Adjust contrast of an image.

    Args:
        img (PIL Image or Tensor): Image to be adjusted.
            If img is torch Tensor, it is expected to be in [..., 1 or 3, H, W] format,
            where ... means it can have an arbitrary number of leading dimensions.
        contrast_factor (float): How much to adjust the contrast. Can be any
            non-negative number. 0 gives a solid gray image, 1 gives the
            original image while 2 increases the contrast by a factor of 2.

    Returns:
        PIL Image or Tensor: Contrast adjusted image.
    """
    if not torch.jit.is_scripting() and not torch.jit.is_tracing():
        _log_api_usage_once(adjust_contrast)
    if not isinstance(img, torch.Tensor):
        return F_pil.adjust_contrast(img, contrast_factor)

    return F_t.adjust_contrast(img, contrast_factor)


# torchvision/transforms/functional.py L1451-1470 (sha256 0b2fdf8e6764f4be0113acd95b58d3b14158c13fa2374ed93fbbe1f4b8730ded)
def adjust_sharpness(img: Tensor, sharpness_factor: float) -> Tensor:
    """Adjust the sharpness of an image.

    Args:
        img (PIL Image or Tensor): Image to be adjusted.
            If img is torch Tensor, it is expected to be in [..., 1 or 3, H, W] format,
            where ... means it can have an arbitrary number of leading dimensions.
        sharpness_factor (float):  How much to adjust the sharpness. Can be
            any non-negative number. 0 gives a blurred image, 1 gives the
            original image while 2 increases the sharpness by a factor of 2.

    Returns:
        PIL Image or Tensor: Sharpness adjusted image.
    """
    if not torch.jit.is_scripting() and not torch.jit.is_tracing():
        _log_api_usage_once(adjust_sharpness)
    if not isinstance(img, torch.Tensor):
        return F_pil.adjust_sharpness(img, sharpness_factor)

    return F_t.adjust_sharpness(img, sharpness_factor)


# torchvision/transforms/transforms.py L283-358 (sha256 b0d9742f64140b4f40a23e343ef28734c32f0fc38bc4d153403bc9d6ac553402)
class Resize(torch.nn.Module):
    """Resize the input image to the given size.
    If the image is torch Tensor, it is expected
    to have [..., H, W] shape, where ... means a maximum of two leading dimensions

    Args:
        size (sequence or int): Desired output size. If size is a sequence like
            (h, w), output size will be matched to this. If size is an int,
            smaller edge of the image will be matched to this number.
            i.e, if height > width, then image will be rescaled to
            (size * height / width, size).

            .. note::
                In torchscript mode size as single int is not supported, use a sequence of length 1: ``[size, ]``.
        interpolation (InterpolationMode): Desired interpolation enum defined by
            :class:`torchvision.transforms.InterpolationMode`. Default is ``InterpolationMode.BILINEAR``.
            If input is Tensor, only ``InterpolationMode.NEAREST``, ``InterpolationMode.NEAREST_EXACT``,
            ``InterpolationMode.BILINEAR`` and ``InterpolationMode.BICUBIC`` are supported.
            The corresponding Pillow integer constants, e.g. ``PIL.Image.BILINEAR`` are accepted as well.
        max_size (int, optional): The maximum allowed for the longer edge of
            the resized image. If the longer edge of the image is greater
            than ``max_size`` after being resized according to ``size``,
            ``size`` will be overruled so that the longer edge is equal to
            ``max_size``.
            As a result, the smaller edge may be shorter than ``size``. This
            is only supported if ``size`` is an int (or a sequence of length
            1 in torchscript mode).
        antialias (bool, optional): Whether to apply antialiasing.
            It only affects **tensors** with bilinear or bicubic modes and it is
            ignored otherwise: on PIL images, antialiasing is always applied on
            bilinear or bicubic modes; on other modes (for PIL images and
            tensors), antialiasing makes no sense and this parameter is ignored.
            Possible values are:

            - ``True`` (default): will apply antialiasing for bilinear or bicubic modes.
              Other mode aren't affected. This is probably what you want to use.
            - ``False``: will not apply antialiasing for tensors on any mode. PIL
              images are still antialiased on bilinear or bicubic modes, because
              PIL doesn't support no antialias.
            - ``None``: equivalent to ``False`` for tensors and ``True`` for
              PIL images. This value exists for legacy reasons and you probably
              don't want to use it unless you really know what you are doing.

            The default value changed from ``None`` to ``True`` in
            v0.17, for the PIL and Tensor backends to be consistent.
    """

    def __init__(self, size, interpolation=InterpolationMode.BILINEAR, max_size=None, antialias=True):
        super().__init__()
        _log_api_usage_once(self)
        if not isinstance(size, (int, Sequence)):
            raise TypeError(f"Size should be int or sequence. Got {type(size)}")
        if isinstance(size, Sequence) and len(size) not in (1, 2):
            raise ValueError("If size is a sequence, it should have 1 or 2 values")
        self.size = size
        self.max_size = max_size

        if isinstance(interpolation, int):
            interpolation = _interpolation_modes_from_int(interpolation)

        self.interpolation = interpolation
        self.antialias = antialias

    def forward(self, img):
        """
        Args:
            img (PIL Image or Tensor): Image to be scaled.

        Returns:
            PIL Image or Tensor: Rescaled image.
        """
        return F.resize(img, self.size, self.interpolation, self.max_size, self.antialias)

    def __repr__(self) -> str:
        detail = f"(size={self.size}, interpolation={self.interpolation.value}, max_size={self.max_size}, antialias={self.antialias})"
        return f"{self.__class__.__name__}{detail}"



F_pil = types.SimpleNamespace(_is_pil_image=_is_pil_image, get_dimensions=_pil_get_dimensions,
                              adjust_contrast=_pil_adjust_contrast, adjust_sharpness=_pil_adjust_sharpness,
                              resize=_pil_resize)


class _NoTensorPath:
    def __getattr__(self, name):
        raise TypeError(f"the tensor path of torchvision.transforms.functional.{name} is not vendored here")


F_t = _NoTensorPath()
F = sys.modules[__name__]
