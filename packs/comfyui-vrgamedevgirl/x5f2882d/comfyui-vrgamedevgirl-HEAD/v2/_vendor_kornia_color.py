# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright 2018 Kornia Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# Vendored for the comfyui-vrgamedevgirl Secure Nodes V2 conversion: ColorMatchToReference calls
# kornia.color.rgb_to_lab / lab_to_rgb, and the sealed guest base (guest_common.lock, 41 pins) has no
# kornia. Every definition below is a verbatim copy from kornia-0.8.3-py3-none-any.whl (sha256
# 0b15f5d359aeafd7ff54ea631ed1943a3eb295c4a6dae3f745ddeada25e33289), Apache License 2.0 (header above).
# Copied definitions:
#   kornia/core/exceptions.py L34-37 BaseError
#   kornia/core/exceptions.py L40-57 ShapeError
#   kornia/core/exceptions.py L60-77 TypeCheckError
#   (kornia/core/exceptions.py sha256 dcb13ecf131b3393f9e5079f30644906a5fc0b8ab45044ef356ec619271c6b6a)
#   kornia/core/check.py L63-79 _should_enable_checks
#   kornia/core/check.py L83-83 _KORNIA_CHECKS_ENABLED
#   kornia/core/check.py L131-216 KORNIA_CHECK_SHAPE
#   kornia/core/check.py L323-370 KORNIA_CHECK_IS_TENSOR
#   (kornia/core/check.py sha256 ce6bbc9837d7aeafbc79e287060d04119b07dfeaed4b3d2c0171d4d3056334ef)
#   kornia/color/rgb.py L229-253 rgb_to_linear_rgb
#   kornia/color/rgb.py L256-281 linear_rgb_to_rgb
#   (kornia/color/rgb.py sha256 09bffba4aa85ca430879e81f73d2ded6d6ae0a09accae2719a25b1ecffa10255)
#   kornia/color/xyz.py L29-60 rgb_to_xyz
#   kornia/color/xyz.py L63-92 xyz_to_rgb
#   kornia/color/xyz.py L95-139 _apply_linear_transformation
#   (kornia/color/xyz.py sha256 685a5cea586445337ae0f3faa7a751bf300d44ee451cbc27a686b200e6726c5b)
#   kornia/color/lab.py L34-84 rgb_to_lab
#   kornia/color/lab.py L87-146 lab_to_rgb
#   (kornia/color/lab.py sha256 35bbac4a1fcb79fdf312d2d58dfe76b8060771cbe48708337f4f9eb196406640)
from __future__ import annotations

import os
from typing import Any, Optional

import torch
import torch.nn.functional as F


# kornia 0.8.3 kornia/core/exceptions.py L34-37
class BaseError(Exception):
    """Base exception class for all Kornia errors."""

    pass


# kornia 0.8.3 kornia/core/exceptions.py L40-57
class ShapeError(BaseError):
    """Raised when tensor shape validation fails.

    Attributes:
        actual_shape: The actual shape of the tensor that failed validation.
        expected_shape: The expected shape specification.
    """

    def __init__(
        self,
        message: str,
        *,
        actual_shape: Optional[tuple[int, ...] | list[int]] = None,
        expected_shape: Optional[list[str] | tuple[int, ...]] = None,
    ):
        super().__init__(message)
        self.actual_shape = actual_shape
        self.expected_shape = expected_shape


# kornia 0.8.3 kornia/core/exceptions.py L60-77
class TypeCheckError(BaseError):
    """Raised when type validation fails.

    Attributes:
        actual_type: The actual type that failed validation.
        expected_type: The expected type.
    """

    def __init__(
        self,
        message: str,
        *,
        actual_type: Optional[type] = None,
        expected_type: Optional[type | tuple[type, ...]] = None,
    ):
        super().__init__(message)
        self.actual_type = actual_type
        self.expected_type = expected_type


# kornia 0.8.3 kornia/core/check.py L63-79
def _should_enable_checks() -> bool:
    """Determine if checks should be enabled.

    Returns:
        True if checks should be enabled, False otherwise.

    Checks are enabled by default in debug mode (normal Python execution).
    Checks are disabled when:
    - Running with `python -O` (optimized mode)
    - Environment variable KORNIA_CHECKS=0 is set
    """
    env_var = os.getenv("KORNIA_CHECKS", None)
    if env_var is not None:
        # Explicit override via environment variable
        return env_var.lower() in ("1", "true", "yes", "on")
    # Default: enabled in debug mode, disabled in optimized mode
    return __debug__


# kornia 0.8.3 kornia/core/check.py L83-83
_KORNIA_CHECKS_ENABLED: bool = _should_enable_checks()


# kornia 0.8.3 kornia/core/check.py L131-216
def KORNIA_CHECK_SHAPE(x: torch.Tensor, shape: list[str], msg: Optional[str] = None, raises: bool = True) -> bool:
    """Check whether a tensor has a specified shape.

    The shape can be specified with a implicit or explicit list of strings.
    The guard also check whether the variable is a type `Tensor`.

    Args:
        x: the tensor to evaluate.
        shape: a list with strings with the expected shape.
        msg: optional custom message to append to error.
        raises: bool indicating whether an exception should be raised upon failure.

    Raises:
        ShapeError: if the input tensor does not have the expected shape and raises is True.

    Note:
        Checks can be disabled in Python mode using `disable_checks()` or the KORNIA_CHECKS
        environment variable. In TorchScript-compiled code, checks always run (TorchScript
        cannot access module-level globals, but the validation logic is fast). When running
        with `python -O`, Python's optimizer may eliminate some checks.

    Example:
        >>> x = torch.rand(2, 3, 4, 4)
        >>> KORNIA_CHECK_SHAPE(x, ["B", "C", "H", "W"])  # implicit
        True

        >>> x = torch.rand(2, 3, 4, 4)
        >>> KORNIA_CHECK_SHAPE(x, ["2", "3", "H", "W"])  # explicit
        True

    """
    if not torch.jit.is_scripting():
        if not _KORNIA_CHECKS_ENABLED:
            return True

    if "*" == shape[0]:
        shape_to_check = shape[1:]
        x_shape_to_check = x.shape[-len(shape) + 1 :]
    elif "*" == shape[-1]:
        shape_to_check = shape[:-1]
        x_shape_to_check = x.shape[: len(shape) - 1]
    else:
        shape_to_check = shape
        x_shape_to_check = x.shape

    if len(x_shape_to_check) != len(shape_to_check):
        if raises:
            expected_dims = len(shape_to_check)
            actual_dims = len(x_shape_to_check)
            error_msg = f"Shape dimension mismatch: expected {expected_dims} dimensions, got {actual_dims}.\n"
            error_msg += f"  Expected shape: {shape}\n"
            x_shape_list = list(x.shape)
            error_msg += f"  Actual shape: {x_shape_list}"
            if msg is not None:
                error_msg += f"\n  {msg}"
            raise ShapeError(
                error_msg,
                actual_shape=x_shape_list,
                expected_shape=shape,
            )
        else:
            return False

    for i in range(len(x_shape_to_check)):
        # The voodoo below is because torchscript does not like
        # that dim can be both int and str
        dim_: str = shape_to_check[i]
        if not dim_.isnumeric():
            continue
        dim = int(dim_)
        if x_shape_to_check[i] != dim:
            if raises:
                error_msg = f"Shape mismatch at dimension {i}: expected {dim}, got {x_shape_to_check[i]}.\n"
                error_msg += f"  Expected shape: {shape}\n"
                x_shape_list = list(x.shape)
                error_msg += f"  Actual shape: {x_shape_list}"
                if msg is not None:
                    error_msg += f"\n  {msg}"
                raise ShapeError(
                    error_msg,
                    actual_shape=x_shape_list,
                    expected_shape=shape,
                )
            else:
                return False
    return True


# kornia 0.8.3 kornia/core/check.py L323-370
def KORNIA_CHECK_IS_TENSOR(x: Any, msg: Optional[str] = None, raises: bool = True) -> bool:
    """Check the input variable is a Tensor.

    Args:
        x: any input variable.
        msg: message to show in the exception.
        raises: bool indicating whether an exception should be raised upon failure.

    Raises:
        TypeCheckError: if the input variable does not match with the expected and raises is True.

    Note:
        Checks can be disabled in Python mode using `disable_checks()` or the KORNIA_CHECKS
        environment variable. In TorchScript-compiled code, checks always run (TorchScript
        cannot access module-level globals, but the validation logic is fast). When running
        with `python -O`, Python's optimizer may eliminate some checks.

    Example:
        >>> x = torch.rand(2, 3, 3)
        >>> KORNIA_CHECK_IS_TENSOR(x, "Invalid tensor")
        True

    """
    if not torch.jit.is_scripting():
        if not _KORNIA_CHECKS_ENABLED:
            return True

    if not isinstance(x, torch.Tensor):
        if raises:
            # JIT doesn't support try-except or type introspection, so use simple message
            if torch.jit.is_scripting():
                error_msg = "Type mismatch: expected Tensor."
                if msg is not None:
                    error_msg += f"\n  {msg}"
                raise TypeCheckError(error_msg)
            else:
                # In Python mode, we can safely use type introspection
                type_name = str(type(x))
                error_msg = f"Type mismatch: expected Tensor, got {type_name}."
                if msg is not None:
                    error_msg += f"\n  {msg}"
                raise TypeCheckError(
                    error_msg,
                    actual_type=type(x),
                    expected_type=torch.Tensor,
                )
        return False
    return True


# kornia 0.8.3 kornia/color/rgb.py L229-253
def rgb_to_linear_rgb(image: torch.Tensor) -> torch.Tensor:
    r"""Convert an sRGB image to linear RGB. Used in colorspace conversions.

    .. image:: _static/img/rgb_to_linear_rgb.png

    Args:
        image: sRGB Image to be converted to linear RGB of shape :math:`(*,3,H,W)`.

    Returns:
        linear RGB version of the image with shape of :math:`(*,3,H,W)`.

    Example:
        >>> input = torch.rand(2, 3, 4, 5)
        >>> output = rgb_to_linear_rgb(input) # 2x3x4x5

    """
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"Input type is not a torch.Tensor. Got {type(image)}")

    if len(image.shape) < 3 or image.shape[-3] != 3:
        raise ValueError(f"Input size must have a shape of (*, 3, H, W).Got {image.shape}")

    lin_rgb: torch.Tensor = torch.where(image > 0.04045, torch.pow(((image + 0.055) / 1.055), 2.4), image / 12.92)

    return lin_rgb


# kornia 0.8.3 kornia/color/rgb.py L256-281
def linear_rgb_to_rgb(image: torch.Tensor) -> torch.Tensor:
    r"""Convert a linear RGB image to sRGB. Used in colorspace conversions.

    Args:
        image: linear RGB Image to be converted to sRGB of shape :math:`(*,3,H,W)`.

    Returns:
        sRGB version of the image with shape of shape :math:`(*,3,H,W)`.

    Example:
        >>> input = torch.rand(2, 3, 4, 5)
        >>> output = linear_rgb_to_rgb(input) # 2x3x4x5

    """
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"Input type is not a torch.Tensor. Got {type(image)}")

    if len(image.shape) < 3 or image.shape[-3] != 3:
        raise ValueError(f"Input size must have a shape of (*, 3, H, W).Got {image.shape}")

    threshold = 0.0031308
    rgb: torch.Tensor = torch.where(
        image > threshold, 1.055 * torch.pow(image.clamp(min=threshold), 1 / 2.4) - 0.055, 12.92 * image
    )

    return rgb


# kornia 0.8.3 kornia/color/xyz.py L29-60
def rgb_to_xyz(image: torch.Tensor) -> torch.Tensor:
    r"""Convert a RGB image to XYZ.

    .. image:: _static/img/rgb_to_xyz.png

    Args:
        image: RGB Image to be converted to XYZ with shape :math:`(*, 3, H, W)`.

    Returns:
         XYZ version of the image with shape :math:`(*, 3, H, W)`.

    Example:
        >>> input = torch.rand(2, 3, 4, 5)
        >>> output = rgb_to_xyz(input)  # 2x3x4x5

    """
    KORNIA_CHECK_IS_TENSOR(image)
    KORNIA_CHECK_SHAPE(image, ["*", "3", "H", "W"])

    # CIE RGB to XYZ Matrix (D65 White Point)
    kernel = torch.tensor(
        [
            [0.412453, 0.357580, 0.180423],
            [0.212671, 0.715160, 0.072169],
            [0.019334, 0.119193, 0.950227],
        ],
        device=image.device,
        dtype=torch.float32,
    )

    # Apply Optimized Linear Transformation
    return _apply_linear_transformation(image, kernel)


# kornia 0.8.3 kornia/color/xyz.py L63-92
def xyz_to_rgb(image: torch.Tensor) -> torch.Tensor:
    r"""Convert a XYZ image to RGB.

    Args:
        image: XYZ Image to be converted to RGB with shape :math:`(*, 3, H, W)`.

    Returns:
        RGB version of the image with shape :math:`(*, 3, H, W)`.

    Example:
        >>> input = torch.rand(2, 3, 4, 5)
        >>> output = xyz_to_rgb(input)  # 2x3x4x5

    """
    KORNIA_CHECK_IS_TENSOR(image)
    KORNIA_CHECK_SHAPE(image, ["*", "3", "H", "W"])

    # CIE XYZ to RGB Matrix (D65 White Point)
    kernel = torch.tensor(
        [
            [3.2404813432005266, -1.5371515162713185, -0.4985363261688878],
            [-0.9692549499965682, 1.8759900014898907, 0.0415559265582928],
            [0.0556466391351772, -0.2040413383665112, 1.0573110696453443],
        ],
        device=image.device,
        dtype=torch.float32,
    )

    # Apply Optimized Linear Transformation
    return _apply_linear_transformation(image, kernel)


# kornia 0.8.3 kornia/color/xyz.py L95-139
def _apply_linear_transformation(image: torch.Tensor, kernel: torch.Tensor) -> torch.Tensor:
    """Apply a 3x3 linear color transformation with device-aware optimization.

    Args:
        image: Input image tensor with shape :math:`(*, 3, H, W)`.
        kernel: Transformation matrix with shape :math:`(3, 3)` applied along the channel
            dimension.

    Returns:
        Tensor with the same shape as ``image`` containing the transformed values.
    """
    # Handle Integer inputs by casting to float safely
    # If it's already floating point (e.g. float64 from gradcheck), we preserve it
    if image.is_floating_point():
        image_compute = image
    else:
        image_compute = image.float()

    # Match kernel dtype to the image (propagates float64 if needed)
    kernel_compute = kernel.to(dtype=image_compute.dtype, device=image_compute.device)

    input_shape = image_compute.shape

    # Empirical benchmarks show that einsum is faster on CPU for this specific pattern,
    # while conv2d offers significant speedups on GPU/CUDA.
    # We branch to ensure optimal performance on both devices.
    # BRANCH 1: CPU (Einsum)
    if image_compute.device.type == "cpu":
        out = torch.einsum("...chw,oc->...ohw", image_compute, kernel_compute)
        out = out.contiguous()

    # BRANCH 2: GPU/Accelerators (Conv2d)
    else:
        # Reshape for conv2d: (B*..., C, H, W)
        input_flat = image_compute.reshape(-1, 3, input_shape[-2], input_shape[-1])

        # Reshape kernel: (3, 3) -> (3, 3, 1, 1)
        weight = kernel_compute.view(3, 3, 1, 1)

        out_flat = F.conv2d(input_flat, weight)

        # Unflatten back to original shape
        out = out_flat.reshape(input_shape)

    return out


# kornia 0.8.3 kornia/color/lab.py L34-84
def rgb_to_lab(image: torch.Tensor) -> torch.Tensor:
    r"""Convert a RGB image to Lab.

    .. image:: _static/img/rgb_to_lab.png

    The input RGB image is assumed to be in the range of :math:`[0, 1]`. Lab
    color is computed using the D65 illuminant and Observer 2.

    Args:
        image: RGB Image to be converted to Lab with shape :math:`(*, 3, H, W)`.

    Returns:
        Lab version of the image with shape :math:`(*, 3, H, W)`.
        The L channel values are in the range 0..100. a and b are in the range -128..127.

    Example:
        >>> input = torch.rand(2, 3, 4, 5)
        >>> output = rgb_to_lab(input)  # 2x3x4x5

    """
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"Input type is not a torch.Tensor. Got {type(image)}")

    if len(image.shape) < 3 or image.shape[-3] != 3:
        raise ValueError(f"Input size must have a shape of (*, 3, H, W). Got {image.shape}")

    # Convert from sRGB to Linear RGB
    lin_rgb = rgb_to_linear_rgb(image)

    xyz_im: torch.Tensor = rgb_to_xyz(lin_rgb)

    # F.normalize for D65 white point
    xyz_ref_white = torch.tensor([0.95047, 1.0, 1.08883], device=xyz_im.device, dtype=xyz_im.dtype)[..., :, None, None]
    xyz_normalized = torch.div(xyz_im, xyz_ref_white)

    threshold = 0.008856
    power = torch.pow(xyz_normalized.clamp(min=threshold), 1 / 3.0)
    scale = 7.787 * xyz_normalized + 4.0 / 29.0
    xyz_int = torch.where(xyz_normalized > threshold, power, scale)

    x: torch.Tensor = xyz_int[..., 0, :, :]
    y: torch.Tensor = xyz_int[..., 1, :, :]
    z: torch.Tensor = xyz_int[..., 2, :, :]

    L: torch.Tensor = (116.0 * y) - 16.0
    a: torch.Tensor = 500.0 * (x - y)
    _b: torch.Tensor = 200.0 * (y - z)

    out: torch.Tensor = torch.stack([L, a, _b], dim=-3)

    return out


# kornia 0.8.3 kornia/color/lab.py L87-146
def lab_to_rgb(image: torch.Tensor, clip: bool = True) -> torch.Tensor:
    r"""Convert a Lab image to RGB.

    The L channel is assumed to be in the range of :math:`[0, 100]`.
    a and b channels are in the range of :math:`[-128, 127]`.

    Args:
        image: Lab image to be converted to RGB with shape :math:`(*, 3, H, W)`.
        clip: Whether to apply clipping to insure output RGB values in range :math:`[0, 1]`.

    Returns:
        Lab version of the image with shape :math:`(*, 3, H, W)`.
        The output RGB image are in the range of :math:`[0, 1]`.

    Example:
        >>> input = torch.rand(2, 3, 4, 5)
        >>> output = lab_to_rgb(input)  # 2x3x4x5

    """
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"Input type is not a torch.Tensor. Got {type(image)}")

    if len(image.shape) < 3 or image.shape[-3] != 3:
        raise ValueError(f"Input size must have a shape of (*, 3, H, W). Got {image.shape}")

    L: torch.Tensor = image[..., 0, :, :]
    a: torch.Tensor = image[..., 1, :, :]
    _b: torch.Tensor = image[..., 2, :, :]

    fy = (L + 16.0) / 116.0
    fx = (a / 500.0) + fy
    fz = fy - (_b / 200.0)

    # if color data out of range: Z < 0
    fz = fz.clamp(min=0.0)

    fxyz = torch.stack([fx, fy, fz], dim=-3)

    # Convert from Lab to XYZ
    power = torch.pow(fxyz, 3.0)
    scale = (fxyz - 4.0 / 29.0) / 7.787
    xyz = torch.where(fxyz > 0.2068966, power, scale)

    # For D65 white point
    xyz_ref_white = torch.tensor([0.95047, 1.0, 1.08883], device=xyz.device, dtype=xyz.dtype)[..., :, None, None]
    xyz_im = xyz * xyz_ref_white

    rgbs_im: torch.Tensor = xyz_to_rgb(xyz_im)

    # https://github.com/richzhang/colorization-pytorch/blob/66a1cb2e5258f7c8f374f582acc8b1ef99c13c27/util/util.py#L107
    #     rgbs_im = torch.where(rgbs_im < 0, torch.zeros_like(rgbs_im), rgbs_im)

    # Convert from RGB Linear to sRGB
    rgb_im = linear_rgb_to_rgb(rgbs_im)

    # Clip to 0,1 https://www.w3.org/Graphics/Color/srgb
    if clip:
        rgb_im = torch.clamp(rgb_im, min=0.0, max=1.0)

    return rgb_im
