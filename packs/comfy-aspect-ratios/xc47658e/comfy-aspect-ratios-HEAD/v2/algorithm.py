"""Original scalar resolution calculation, without host dependencies."""

import math

PRESETS = [
    "none",
    "[landscape] 3:1",
    "[landscape] 7:4",
    "[landscape] 19:13",
    "[landscape] 3:2",
    "[landscape] 7:5",
    "[landscape] 9:7",
    "[landscape] 4:3",
    "[square] 1:1",
    "[portrait] 3:4",
    "[portrait] 7:9",
    "[portrait] 5:7",
    "[portrait] 2:3",
    "[portrait] 13:19",
    "[portrait] 4:7",
    "[portrait] 1:3",
]


def calc_resolution(
    base=1024, fixed_side="none", step=8, aspect_w=1, aspect_h=1, **kwargs
):
    step = int(step)
    aspect_w = int(aspect_w)
    aspect_h = int(aspect_h)
    aspect_ratio = aspect_w / aspect_h
    if fixed_side == "none":
        area = base**2
        width = math.sqrt(area * aspect_ratio)
        height = width / aspect_ratio
    else:
        is_short = fixed_side == "short"
        is_portrait = aspect_w <= aspect_h
        if (is_short and is_portrait) or (not is_short and not is_portrait):
            width = base
            height = base * aspect_h / aspect_w
        else:
            height = base
            width = base * aspect_w / aspect_h
    step_w = math.lcm(step, aspect_w) if fixed_side == "none" else step
    step_h = math.lcm(step, aspect_h) if fixed_side == "none" else step
    width = int(width // step_w * step_w)
    height = int(height // step_h * step_h)
    return width, height
