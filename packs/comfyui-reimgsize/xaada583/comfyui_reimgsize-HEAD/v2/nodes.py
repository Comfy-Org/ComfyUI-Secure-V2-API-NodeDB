"""Pack-owned dimension math; canonical resize through opaque image refs."""
import math
from comfy_api.latest import io, sdk

METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
CROPS = ["disabled", "center"]
MAX_BATCH = 32
MAX_EDGE = 8192
MAX_PIXELS = 4_194_304


def _integer(value, name, maximum=8192):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} is outside the bounded range")


def _ratio(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(value) or not .001 <= value <= 64.:
        raise ValueError(f"{name} is outside the finite ratio bounds")


async def _shape(image):
    if not isinstance(image, sdk.ImageRef):
        raise TypeError("image must be an opaque IMAGE ref")
    shape = (await image.describe())["shape"]
    if not isinstance(shape, (list, tuple)) or len(shape) != 4:
        raise ValueError("image must be BHWC")
    batch, height, width, channels = shape
    if any(type(x) is not int for x in shape) or channels not in (1, 3, 4):
        raise ValueError("image requires 1, 3 or 4 channels")
    if not 1 <= batch <= MAX_BATCH or not 1 <= height <= MAX_EDGE or not 1 <= width <= MAX_EDGE:
        raise ValueError("image exceeds batch/edge bounds")
    if batch * height * width > MAX_PIXELS:
        raise ValueError("image exceeds the bounded pixel budget")
    return batch, height, width, channels


async def _resize(image, shape, width, height, method, crop):
    # Reject before broker allocation. Never clamp round-to-zero dimensions.
    if not 1 <= width <= MAX_EDGE or not 1 <= height <= MAX_EDGE:
        raise ValueError("rounded resize dimensions exceed the bounded range")
    batch, _, _, channels = shape
    if batch * width * height > MAX_PIXELS:
        raise ValueError("resized image exceeds the bounded pixel budget")
    result = await image.resize(width, height, method=method, crop=crop)
    return io.NodeOutput(result, width, height, batch, channels)


def _image_inputs(crop_default):
    return [io.Image.Input("image"),
            io.Combo.Input("upscale_method", options=METHODS, default="bicubic"),
            io.Combo.Input("crop_methods", options=CROPS, default=crop_default)]


def _image_outputs():
    return [io.Image.Output(display_name="image"), io.Int.Output(display_name="width"),
            io.Int.Output(display_name="height"), io.Int.Output(display_name="count"),
            io.Int.Output(display_name="channels")]


def _choices(method, crop):
    if method not in METHODS or crop not in CROPS:
        raise ValueError("unknown interpolation/crop method")


class Reimgsize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="Reimgsize", display_name="Reimgsize", category="comfyui_reimgsize",
            inputs=_image_inputs("disabled") + [
                io.Int.Input("img_size", default=1024, min=1, max=8192, step=1),
                io.Int.Input("GCD", default=64, min=1, max=512, step=1),
                io.Int.Input("width", optional=True, min=1, max=8192, step=1, extra_dict={"defaultInput": True}),
                io.Int.Input("height", optional=True, min=1, max=8192, step=1, extra_dict={"defaultInput": True})],
            outputs=_image_outputs())

    @classmethod
    async def execute(cls, image, img_size, upscale_method, crop_methods, GCD, width=None, height=None):
        _integer(img_size, "img_size"); _integer(GCD, "GCD", 512)
        if width is not None:
            _integer(width, "width")
        if height is not None:
            _integer(height, "height")
        _choices(upscale_method, crop_methods)
        shape = await _shape(image)
        aspect_ratio = shape[2] / shape[1]
        if width is not None or height is not None:
            if width is not None and height is not None:
                new_width, new_height = width, height
            elif width is not None:
                new_width, new_height = width, int(width / aspect_ratio)
            else:
                new_height, new_width = height, int(height * aspect_ratio)
        else:
            new_height = int((img_size**2 / aspect_ratio) ** .5)
            new_width = int(new_height * aspect_ratio)
        new_width = round(new_width / GCD) * GCD
        new_height = round(new_height / GCD) * GCD
        return await _resize(image, shape, new_width, new_height, upscale_method, crop_methods)


class Cropimg(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="Cropimg", display_name="Cropimg", category="comfyui_reimgsize",
            inputs=_image_inputs("center") + [
                io.Float.Input("width_ratio", default=1., min=.001, max=64., step=.001),
                io.Float.Input("height_ratio", default=1., min=.001, max=64., step=.001)],
            outputs=_image_outputs())

    @classmethod
    async def execute(cls, image, upscale_method, crop_methods, width_ratio, height_ratio):
        _ratio(width_ratio, "width_ratio"); _ratio(height_ratio, "height_ratio")
        _choices(upscale_method, crop_methods)
        shape = await _shape(image)
        _, original_height, original_width, _ = shape
        original_resolution = original_width * original_height
        desired_aspect = width_ratio / height_ratio
        aspect = original_width / original_height
        if aspect > desired_aspect:
            new_width, new_height = int(original_height * desired_aspect), original_height
        else:
            new_width, new_height = original_width, int(original_width / desired_aspect)
        # Preserve upstream division-by-zero for a degenerate aspect.
        scale = (original_resolution / (new_width * new_height)) ** .5
        new_width, new_height = int(new_width * scale), int(new_height * scale)
        return await _resize(image, shape, new_width, new_height, upscale_method, crop_methods)


class Resizebyratio(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="Resizebyratio", display_name="Resizebyratio", category="comfyui_reimgsize",
            inputs=[io.Int.Input("size", default=1024, min=32, max=8192, step=1),
                    io.Float.Input("width_ratio", default=1., min=.001, max=64., step=.001),
                    io.Float.Input("height_ratio", default=1., min=.001, max=64., step=.001),
                    io.Int.Input("GCD", default=64, min=1, max=512, step=1)],
            outputs=[io.Int.Output(display_name="width"), io.Int.Output(display_name="height")])

    @classmethod
    def execute(cls, size, width_ratio, height_ratio, GCD):
        _integer(size, "size"); _integer(GCD, "GCD", 512)
        _ratio(width_ratio, "width_ratio"); _ratio(height_ratio, "height_ratio")
        target = size**2
        ratio = width_ratio / height_ratio
        height = (target / ratio) ** .5
        width = ratio * height
        height = round(height / GCD) * GCD
        width = round(width / GCD) * GCD
        return io.NodeOutput(width, height)


NODE_CLASS_MAPPINGS = {"Reimgsize": Reimgsize, "Cropimg": Cropimg, "Resizebyratio": Resizebyratio}
NODE_DISPLAY_NAME_MAPPINGS = {"Reimgsize": "Reimgsize", "Cropimg": "Cropimg", "Resizebyratio": "Resizebyratio"}
