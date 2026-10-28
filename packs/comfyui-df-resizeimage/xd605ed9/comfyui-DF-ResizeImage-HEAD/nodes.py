import math


def snap_to_multiple(value, multiple, rounding):
    if multiple <= 1:
        return max(1, int(round(value)))

    scaled = value / multiple
    if rounding == "floor":
        snapped = math.floor(scaled) * multiple
    elif rounding == "ceil":
        snapped = math.ceil(scaled) * multiple
    else:
        snapped = round(scaled) * multiple

    return max(multiple, int(snapped))


def resolve_target_size(width, height, mode, long_side, short_side, scale_factor, multiple, rounding):
    is_landscape = width >= height

    if mode == "long_side":
        target_long = snap_to_multiple(long_side, multiple, rounding)
        if is_landscape:
            target_width = target_long
            target_height = snap_to_multiple(height * (target_width / width), multiple, rounding)
        else:
            target_height = target_long
            target_width = snap_to_multiple(width * (target_height / height), multiple, rounding)
    elif mode == "short_side":
        target_short = snap_to_multiple(short_side, multiple, rounding)
        if is_landscape:
            target_height = target_short
            target_width = snap_to_multiple(width * (target_height / height), multiple, rounding)
        else:
            target_width = target_short
            target_height = snap_to_multiple(height * (target_width / width), multiple, rounding)
    elif mode == "scale_factor":
        target_width = snap_to_multiple(width * scale_factor, multiple, rounding)
        target_height = snap_to_multiple(height * scale_factor, multiple, rounding)
    elif mode == "long_and_short":
        target_long = snap_to_multiple(long_side, multiple, rounding)
        target_short = snap_to_multiple(short_side, multiple, rounding)
        if is_landscape:
            target_width = target_long
            target_height = target_short
        else:
            target_width = target_short
            target_height = target_long
    else:
        raise ValueError(f"Unsupported resize mode: {mode}")

    return max(1, int(target_width)), max(1, int(target_height))


def resize_image_tensor(image, target_width, target_height, interpolation):
    import torch.nn.functional as F

    samples = image.movedim(-1, 1)
    kwargs = {}
    if interpolation in {"bilinear", "bicubic"}:
        kwargs["align_corners"] = False
        kwargs["antialias"] = True
    resized = F.interpolate(samples, size=(target_height, target_width), mode=interpolation, **kwargs)
    return resized.movedim(1, -1).clamp(0.0, 1.0)


class FlexibleResizeToMultiple:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mode": (["long_side", "short_side", "scale_factor", "long_and_short"],),
                "interpolation": (["bicubic", "bilinear", "area", "nearest"],),
                "multiple_of": ("INT", {"default": 16, "min": 1, "max": 512, "step": 1}),
                "rounding": (["nearest", "floor", "ceil"],),
                "long_side": ("INT", {"default": 1536, "min": 1, "max": 32768, "step": 1}),
                "short_side": ("INT", {"default": 1024, "min": 1, "max": 32768, "step": 1}),
                "scale_factor": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 64.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "resize"
    CATEGORY = "image/resize"

    def resize(self, image, mode, interpolation, multiple_of, rounding, long_side, short_side, scale_factor):
        _, input_height, input_width, _ = image.shape

        target_width, target_height = resolve_target_size(
            width=input_width,
            height=input_height,
            mode=mode,
            long_side=long_side,
            short_side=short_side,
            scale_factor=scale_factor,
            multiple=multiple_of,
            rounding=rounding,
        )

        resized = resize_image_tensor(image, target_width, target_height, interpolation)
        return resized, target_width, target_height


NODE_CLASS_MAPPINGS = {
    "comfyui-DF-ResizeImage": FlexibleResizeToMultiple,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "comfyui-DF-ResizeImage": "comfyui-DF-ResizeImage",
}
