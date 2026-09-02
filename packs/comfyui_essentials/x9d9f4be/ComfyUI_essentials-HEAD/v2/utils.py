import torch
import numpy as np
import scipy
import os
import math
#import re
from pathlib import Path

FONTS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "fonts")
LUTS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "luts")

# from https://github.com/pythongosssss/ComfyUI-Custom-Scripts
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

def min_(tensor_list):
    # return the element-wise min of the tensor list.
    x = torch.stack(tensor_list)
    mn = x.min(axis=0)[0]
    return torch.clamp(mn, min=0)

def max_(tensor_list):
    # return the element-wise max of the tensor list.
    x = torch.stack(tensor_list)
    mx = x.max(axis=0)[0]
    return torch.clamp(mx, max=1)

def expand_mask(mask, expand, tapered_corners):
    c = 0 if tapered_corners else 1
    kernel = np.array([[c, 1, c],
                       [1, 1, 1],
                       [c, 1, c]])
    mask = mask.reshape((-1, mask.shape[-2], mask.shape[-1]))
    out = []
    for m in mask:
        output = m.numpy()
        for _ in range(abs(expand)):
            if expand < 0:
                output = scipy.ndimage.grey_erosion(output, footprint=kernel)
            else:
                output = scipy.ndimage.grey_dilation(output, footprint=kernel)
        output = torch.from_numpy(output)
        out.append(output)

    return torch.stack(out, dim=0)

def parse_string_to_list(s, *, max_items=4096):
    """Parse Essentials' comma/range syntax without unbounded expansion.

    The upstream parser loops forever for a zero range step and can allocate
    without limit for a tiny step.  Valid existing inputs keep their numerical
    behaviour, while malformed/non-finite values and oversized grids fail
    closed inside the guest.
    """
    elements = s.split(',')
    result = []

    def parse_number(s):
        try:
            value = float(s) if '.' in s else int(s)
        except ValueError:
            return 0
        if not math.isfinite(float(value)):
            raise ValueError(f"non-finite number: {s!r}")
        return value

    def decimal_places(s):
        if '.' in s:
            return len(s.split('.')[1])
        return 0

    for element in elements:
        element = element.strip()
        if '...' in element:
            try:
                start, rest = element.split('...', 1)
                end, step = rest.rsplit('+', 1)
            except ValueError as exc:
                raise ValueError(f"invalid number range: {element!r}") from exc
            decimals = decimal_places(step)
            start = parse_number(start)
            end = parse_number(end)
            step = parse_number(step)
            if step == 0:
                raise ValueError(f"number range step must not be zero: {element!r}")
            current = start
            if (start > end and step > 0) or (start < end and step < 0):
                step = -step
            compare = ((lambda value: value <= end)
                       if step > 0 else (lambda value: value >= end))
            while compare(current):
                if len(result) >= max_items:
                    raise ValueError(
                        f"number grid exceeds {max_items} values")
                result.append(round(current, decimals))
                current += step
        else:
            if len(result) >= max_items:
                raise ValueError(f"number grid exceeds {max_items} values")
            result.append(round(parse_number(element), decimal_places(element)))

    return result
