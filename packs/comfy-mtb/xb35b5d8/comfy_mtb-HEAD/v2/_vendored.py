"""Two library functions the converted comfy_mtb nodes call, copied so the guest needs only torch and numpy.

- `TF.gaussian_blur` (Uncrop): torchvision 0.23.0 `transforms.functional.gaussian_blur`, tensor path, and the
  `transforms._functional_tensor` helpers it dispatches to, verbatim. The PIL-image path and the API-usage
  logging call are left out; Uncrop passes tensors. torchvision is BSD-3-Clause licensed (Copyright (c) Soumith
  Chintala 2016, all rights reserved).
- `compare_images` (Image Compare, checkerboard): scikit-image 0.25.2 `skimage.util.compare_images`, verbatim except
  that `img_as_float` is the identity for the float arrays the node passes and refuses other dtypes. scikit-image is
  BSD-3-Clause licensed (Copyright (C) 2019, the scikit-image team, all rights reserved).
The converted nodes' parity tests run the original nodes with the real libraries.
"""

import types
from itertools import product
from typing import Optional

import numpy as np
import torch
from torch import Tensor
from torch.nn.functional import conv2d, pad as torch_pad


# ---------------------------------------------------------------- torchvision 0.23.0, transforms/_functional_tensor.py
def _is_tensor_a_torch_image(x: Tensor) -> bool:
    return x.ndim >= 2


def _assert_image_tensor(img: Tensor) -> None:
    if not _is_tensor_a_torch_image(img):
        raise TypeError("Tensor is not a torch image.")


def _cast_squeeze_in(img: Tensor, req_dtypes: list[torch.dtype]) -> tuple[Tensor, bool, bool, torch.dtype]:
    need_squeeze = False
    # make image NCHW
    if img.ndim < 4:
        img = img.unsqueeze(dim=0)
        need_squeeze = True

    out_dtype = img.dtype
    need_cast = False
    if out_dtype not in req_dtypes:
        need_cast = True
        req_dtype = req_dtypes[0]
        img = img.to(req_dtype)
    return img, need_cast, need_squeeze, out_dtype


def _cast_squeeze_out(img: Tensor, need_cast: bool, need_squeeze: bool, out_dtype: torch.dtype) -> Tensor:
    if need_squeeze:
        img = img.squeeze(dim=0)

    if need_cast:
        if out_dtype in (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64):
            # it is better to round before cast
            img = torch.round(img)
        img = img.to(out_dtype)

    return img


def _get_gaussian_kernel1d(kernel_size: int, sigma: float, dtype: torch.dtype, device: torch.device) -> Tensor:
    ksize_half = (kernel_size - 1) * 0.5

    x = torch.linspace(-ksize_half, ksize_half, steps=kernel_size, dtype=dtype, device=device)
    pdf = torch.exp(-0.5 * (x / sigma).pow(2))
    kernel1d = pdf / pdf.sum()

    return kernel1d


def _get_gaussian_kernel2d(
    kernel_size: list[int], sigma: list[float], dtype: torch.dtype, device: torch.device
) -> Tensor:
    kernel1d_x = _get_gaussian_kernel1d(kernel_size[0], sigma[0], dtype, device)
    kernel1d_y = _get_gaussian_kernel1d(kernel_size[1], sigma[1], dtype, device)
    kernel2d = torch.mm(kernel1d_y[:, None], kernel1d_x[None, :])
    return kernel2d


def _functional_tensor_gaussian_blur(img: Tensor, kernel_size: list[int], sigma: list[float]) -> Tensor:
    if not (isinstance(img, torch.Tensor)):
        raise TypeError(f"img should be Tensor. Got {type(img)}")

    _assert_image_tensor(img)

    dtype = img.dtype if torch.is_floating_point(img) else torch.float32
    kernel = _get_gaussian_kernel2d(kernel_size, sigma, dtype=dtype, device=img.device)
    kernel = kernel.expand(img.shape[-3], 1, kernel.shape[0], kernel.shape[1])

    img, need_cast, need_squeeze, out_dtype = _cast_squeeze_in(img, [kernel.dtype])

    # padding = (left, right, top, bottom)
    padding = [kernel_size[0] // 2, kernel_size[0] // 2, kernel_size[1] // 2, kernel_size[1] // 2]
    img = torch_pad(img, padding, mode="reflect")
    img = conv2d(img, kernel, groups=img.shape[-3])

    img = _cast_squeeze_out(img, need_cast, need_squeeze, out_dtype)
    return img


# ---------------------------------------------------------------- torchvision 0.23.0, transforms/functional.py
def gaussian_blur(img: Tensor, kernel_size: list[int], sigma: Optional[list[float]] = None) -> Tensor:
    if not isinstance(kernel_size, (int, list, tuple)):
        raise TypeError(f"kernel_size should be int or a sequence of integers. Got {type(kernel_size)}")
    if isinstance(kernel_size, int):
        kernel_size = [kernel_size, kernel_size]
    if len(kernel_size) != 2:
        raise ValueError(f"If kernel_size is a sequence its length should be 2. Got {len(kernel_size)}")
    for ksize in kernel_size:
        if ksize % 2 == 0 or ksize < 0:
            raise ValueError(f"kernel_size should have odd and positive integers. Got {kernel_size}")

    if sigma is None:
        sigma = [ksize * 0.15 + 0.35 for ksize in kernel_size]

    if sigma is not None and not isinstance(sigma, (int, float, list, tuple)):
        raise TypeError(f"sigma should be either float or sequence of floats. Got {type(sigma)}")
    if isinstance(sigma, (int, float)):
        sigma = [float(sigma), float(sigma)]
    if isinstance(sigma, (list, tuple)) and len(sigma) == 1:
        sigma = [sigma[0], sigma[0]]
    if len(sigma) != 2:
        raise ValueError(f"If sigma is a sequence, its length should be 2. Got {len(sigma)}")
    for s in sigma:
        if s <= 0.0:
            raise ValueError(f"sigma should have positive values. Got {sigma}")

    t_img = img
    if not isinstance(img, torch.Tensor):
        raise TypeError(f"img should be a Tensor here (the PIL path is not copied). Got {type(img)}")

    output = _functional_tensor_gaussian_blur(t_img, kernel_size, sigma)
    return output


# The name the original module uses: `import torchvision.transforms.functional as TF`.
TF = types.SimpleNamespace(gaussian_blur=gaussian_blur)


# ---------------------------------------------------------------- scikit-image 0.25.2, util/compare.py
def img_as_float(image):
    # skimage.util.img_as_float returns a floating-point array unchanged; the node passes float32 tensors' arrays.
    if not (isinstance(image, np.ndarray) and image.dtype.kind == "f"):
        raise TypeError("Image Compare (V2): only floating-point images are supported here")
    return image


def compare_images(image0, image1, *, method='diff', n_tiles=(8, 8)):
    if image1.shape != image0.shape:
        raise ValueError('Images must have the same shape.')

    img1 = img_as_float(image0)
    img2 = img_as_float(image1)

    if method == 'diff':
        comparison = np.abs(img2 - img1)
    elif method == 'blend':
        comparison = 0.5 * (img2 + img1)
    elif method == 'checkerboard':
        if img1.ndim != 2:
            raise ValueError(
                'Images must be 2-dimensional to be compared with the '
                'checkerboard method.'
            )
        shapex, shapey = img1.shape
        mask = np.full((shapex, shapey), False)
        stepx = int(shapex / n_tiles[0])
        stepy = int(shapey / n_tiles[1])
        for i, j in product(range(n_tiles[0]), range(n_tiles[1])):
            if (i + j) % 2 == 0:
                mask[i * stepx : (i + 1) * stepx, j * stepy : (j + 1) * stepy] = True
        comparison = np.zeros_like(img1)
        comparison[mask] = img1[mask]
        comparison[~mask] = img2[~mask]
    else:
        raise ValueError(
            'Wrong value for `method`. '
            'Must be either "diff", "blend" or "checkerboard".'
        )
    return comparison
