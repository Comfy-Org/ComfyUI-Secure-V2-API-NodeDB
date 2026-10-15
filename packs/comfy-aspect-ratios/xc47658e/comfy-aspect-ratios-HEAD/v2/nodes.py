from comfy_api.latest import ComfyExtension, io, sdk

from .algorithm import PRESETS, calc_resolution

NODE_ID = "jupo.AspectRatios.AspectRatios"


class AspectRatios(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=NODE_ID,
            display_name="Aspect Ratios",
            category="jupo/AspectRatios",
            inputs=[
                io.Int.Input("base", default=1024, min=64, step=8),
                io.Combo.Input("fixed_side", options=["none", "short", "long"]),
                io.Int.Input("step", default=8, min=8, step=8),
                io.Int.Input("aspect_w", default=1, min=1),
                io.Int.Input("aspect_h", default=1, min=1),
                io.Combo.Input("preset", options=PRESETS),
                io.Int.Input("batch_size", default=1, min=1),
            ],
            outputs=[
                io.Latent.Output(display_name="latent"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
        )

    @classmethod
    async def execute(cls, **kwargs):
        bounds = {
            "base": (64, 8192),
            "step": (8, 8192),
            "aspect_w": (1, 4096),
            "aspect_h": (1, 4096),
            "batch_size": (1, 64),
        }
        for key, (lo, hi) in bounds.items():
            value = kwargs.get(
                key,
                1
                if key in ("aspect_w", "aspect_h", "batch_size")
                else 1024
                if key == "base"
                else 8,
            )
            if type(value) is not int:
                raise TypeError(f"{key} must be an integer")
            if not lo <= value <= hi:
                raise ValueError(f"{key} exceeds the bounded range")
        if kwargs.get("fixed_side", "none") not in ("none", "short", "long"):
            raise ValueError("unknown fixed_side")
        if kwargs.get("preset", "none") not in PRESETS:
            raise ValueError("unknown preset")
        width, height = calc_resolution(**kwargs)
        batch = kwargs.get("batch_size", 1)
        if not 8 <= width <= 8192 or not 8 <= height <= 8192:
            raise ValueError("rounded geometry is outside allocation bounds")
        if batch * 4 * (width // 8) * (height // 8) > 16_777_216:
            raise ValueError("latent exceeds the bounded element budget")
        latent = await sdk.LatentRef.empty(
            (width // 8) * 8,
            (height // 8) * 8,
            batch,
            channels=4,
            spatial_downscale_ratio=8,
        )
        return io.NodeOutput(latent, width, height)


NODE_CLASS_MAPPINGS = {NODE_ID: AspectRatios}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: "Aspect Ratios"}


class Extension(ComfyExtension):
    async def get_node_list(self):
        return [AspectRatios]


async def comfy_entrypoint():
    return Extension()
