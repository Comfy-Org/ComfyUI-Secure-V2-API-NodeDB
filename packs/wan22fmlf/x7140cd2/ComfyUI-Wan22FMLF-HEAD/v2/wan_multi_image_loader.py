from comfy_api.latest import io, sdk
import torch
from PIL import Image, ImageOps
from io import BytesIO
import json
from pathlib import PurePosixPath

from ._secure_runtime import output_image

class WanMultiImageLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "raw")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WanMultiImageLoader",
            display_name="Wan Multi-Image Loader",
            category="ComfyUI-Wan22FMLF",
            inputs=[
                io.Int.Input(
                    "index",
                    default=0,
                    min=0,
                    max=999,
                    step=1,
                    display_mode=io.NumberDisplay.number,
                ),
                io.String.Input("images_data", optional=True),
            ],
            outputs=[
                io.Image.Output("image"),
            ],
        )

    @classmethod
    def _logical_name(cls, name: str, subfolder: str) -> str:
        if not isinstance(name, str) or not name or len(name) > 255:
            raise ValueError("image name missing or invalid in images_data")
        if not isinstance(subfolder, str) or len(subfolder) > 1024:
            raise ValueError("image subfolder is invalid")
        logical = PurePosixPath(subfolder.replace("\\", "/")) / name
        if logical.is_absolute() or any(
            part in {"", ".", ".."} for part in logical.parts
        ):
            raise ValueError("image identity must stay inside its catalogue")
        return logical.as_posix()

    @classmethod
    async def execute(cls, index, images_data=None):
        if not images_data:
            dummy = torch.zeros((1, 64, 64, 3))
            return io.NodeOutput(await output_image(dummy))

        try:
            data = json.loads(images_data)
        except Exception as e:
            print(f"WanMultiImageLoader: failed to parse images_data: {e}")
            dummy = torch.zeros((1, 64, 64, 3))
            return io.NodeOutput(await output_image(dummy))

        if not isinstance(data, list) or not data or len(data) > 50:
            dummy = torch.zeros((1, 64, 64, 3))
            return io.NodeOutput(await output_image(dummy))

        actual_index = max(0, min(index, len(data) - 1))

        try:
            info = data[actual_index]
            name = info.get("name")
            dir_type = info.get("type", "input")
            subfolder = info.get("subfolder", "") or ""

            if dir_type not in {"input", "temp", "output"}:
                raise ValueError("image type must be input, temp, or output")
            logical_name = cls._logical_name(name, subfolder)
            asset = await sdk.ctx().assets.resolve(dir_type, logical_name)
            image_bytes = await sdk.ctx().assets.read_bytes(asset)

            with Image.open(BytesIO(image_bytes)) as opened:
                img = ImageOps.exif_transpose(opened)

                if img.mode == "I":
                    img = img.point(lambda i: i * (1 / 255))
                img = img.convert("RGB")

                raw = bytearray(img.tobytes())
                img_tensor = torch.frombuffer(raw, dtype=torch.uint8).reshape(
                    img.height, img.width, 3
                ).clone().to(torch.float32).div_(255.0)[None, ...]

            return io.NodeOutput(await output_image(img_tensor))

        except Exception as e:
            # A missing/invalid image preserves the original node's dummy
            # fallback.  A denied broker capability is a security boundary,
            # however, and must remain fail-closed rather than looking like a
            # successfully loaded black image.
            if "capability" in str(e).lower():
                raise
            print(f"WanMultiImageLoader: Error loading image: {e}")
            dummy = torch.zeros((1, 64, 64, 3))
            return io.NodeOutput(await output_image(dummy))
