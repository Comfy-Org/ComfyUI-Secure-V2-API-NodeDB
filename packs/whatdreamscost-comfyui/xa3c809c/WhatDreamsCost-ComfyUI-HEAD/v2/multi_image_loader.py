import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image, ImageOps
import io as bytes_io

from comfy_api.latest import io, sdk

class MultiImageLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "raw")

    @classmethod
    def define_schema(cls):
        paths = io.String.Input("image_paths", default="", multiline=True)
        paths.extra_dict = {
            "remote": {
                "route": "/secure-nodes/assets/input?kind=image",
                "refresh_button": True,
            }
        }
        return io.Schema(
            node_id="MultiImageLoader",
            display_name="Multi Image Loader",
            category="WhatDreamsCost",
            inputs=[
                paths,
                io.Int.Input("width", default=0, min=0, max=8192, step=1),
                io.Int.Input("height", default=0, min=0, max=8192, step=1),
                io.Combo.Input("interpolation", options=["lanczos", "nearest", "bilinear", "bicubic", "area", "nearest-exact"], default="lanczos"),
                io.Combo.Input("resize_method", options=["keep proportion", "stretch", "pad", "pad green", "crop"], default="keep proportion"),
                io.Int.Input("multiple_of", default=32, min=0, max=512, step=1),
                io.Int.Input("img_compression", default=18, min=0, max=100, step=1),
            ],
            outputs=[
                io.Image.Output("multi_output", display_name="multi_output"),
                *[io.Image.Output(f"image_{index}", display_name=f"image_{index}") for index in range(1, 51)],
            ],
        )

    def resize_image(self, image, width, height, resize_method="keep proportion", interpolation="nearest", multiple_of=0):
        MAX_RESOLUTION = 8192
        _, oh, ow, _ = image.shape
        x = y = x2 = y2 = 0
        pad_left = pad_right = pad_top = pad_bottom = 0

        if multiple_of > 1:
            width = width - (width % multiple_of)
            height = height - (height % multiple_of)

        if resize_method == 'keep proportion' or resize_method == 'pad':
            if width == 0 and oh < height:
                width = MAX_RESOLUTION
            elif width == 0 and oh >= height:
                width = ow

            if height == 0 and ow < width:
                height = MAX_RESOLUTION
            elif height == 0 and ow >= width:
                height = oh

            ratio = min(width / ow, height / oh)
            new_width = round(ow * ratio)
            new_height = round(oh * ratio)

            if resize_method == 'pad' or resize_method == 'pad green':
                pad_left = (width - new_width) // 2
                pad_right = width - new_width - pad_left
                pad_top = (height - new_height) // 2
                pad_bottom = height - new_height - pad_top

            width = new_width
            height = new_height
            
        elif resize_method == 'crop':
            width = width if width > 0 else ow
            height = height if height > 0 else oh

            ratio = max(width / ow, height / oh)
            new_width = round(ow * ratio)
            new_height = round(oh * ratio)
            x = (new_width - width) // 2
            y = (new_height - height) // 2
            x2 = x + width
            y2 = y + height
            if x2 > new_width:
                x -= (x2 - new_width)
            if x < 0:
                x = 0
            if y2 > new_height:
                y -= (y2 - new_height)
            if y < 0:
                y = 0
            width = new_width
            height = new_height
            
        else:
            width = width if width > 0 else ow
            height = height if height > 0 else oh

        # Always apply resize logic
        outputs = image.permute(0, 3, 1, 2)

        if interpolation == "lanczos":
            images = [
                Image.fromarray(
                    np.clip(255.0 * item.movedim(0, -1).cpu().numpy(), 0, 255).astype(np.uint8)
                ).resize((width, height), resample=Image.Resampling.LANCZOS)
                for item in outputs
            ]
            outputs = torch.stack([
                torch.from_numpy(np.array(item).astype(np.float32) / 255.0).movedim(-1, 0)
                for item in images
            ]).to(outputs.device, outputs.dtype)
        else:
            outputs = F.interpolate(outputs, size=(height, width), mode=interpolation)

        if resize_method == 'pad' or resize_method == 'pad green':
            if pad_left > 0 or pad_right > 0 or pad_top > 0 or pad_bottom > 0:
                outputs = F.pad(outputs, (pad_left, pad_right, pad_top, pad_bottom), value=0)
                if resize_method == 'pad green':
                    if pad_top > 0:
                        outputs[:, 0, :pad_top, :] = 102 / 255.0
                        outputs[:, 1, :pad_top, :] = 1.0
                        outputs[:, 2, :pad_top, :] = 0.0
                    if pad_bottom > 0:
                        outputs[:, 0, -pad_bottom:, :] = 102 / 255.0
                        outputs[:, 1, -pad_bottom:, :] = 1.0
                        outputs[:, 2, -pad_bottom:, :] = 0.0
                    if pad_left > 0:
                        outputs[:, 0, :, :pad_left] = 102 / 255.0
                        outputs[:, 1, :, :pad_left] = 1.0
                        outputs[:, 2, :, :pad_left] = 0.0
                    if pad_right > 0:
                        outputs[:, 0, :, -pad_right:] = 102 / 255.0
                        outputs[:, 1, :, -pad_right:] = 1.0
                        outputs[:, 2, :, -pad_right:] = 0.0

        outputs = outputs.permute(0, 2, 3, 1)

        if resize_method == 'crop':
            if x > 0 or y > 0 or x2 > 0 or y2 > 0:
                outputs = outputs[:, y:y2, x:x2, :]

        if multiple_of > 1 and (outputs.shape[2] % multiple_of != 0 or outputs.shape[1] % multiple_of != 0):
            width = outputs.shape[2]
            height = outputs.shape[1]
            x = (width % multiple_of) // 2
            y = (height % multiple_of) // 2
            x2 = width - ((width % multiple_of) - x)
            y2 = height - ((height % multiple_of) - y)
            outputs = outputs[:, y:y2, x:x2, :]
        
        outputs = torch.clamp(outputs, 0, 1)

        return outputs

    @classmethod
    async def execute(cls, image_paths, width, height, interpolation, resize_method, multiple_of, img_compression):
        self = cls()
        results = []
        valid_paths = [p.strip() for p in image_paths.split("\n") if p.strip()]

        for path in valid_paths[:50]:
            try:
                asset = await sdk.ctx().assets.resolve("input", path)
                image = Image.open(bytes_io.BytesIO(await sdk.ctx().assets.read_bytes(asset)))
                image = ImageOps.exif_transpose(image)
                image = image.convert("RGB")

                # Convert to Torch Tensor to prepare for Advanced Resize Logic
                image_np = np.array(image).astype(np.float32) / 255.0
                image_tensor = torch.from_numpy(image_np)[None,]

                # Apply Advanced Resize
                image_tensor = self.resize_image(image_tensor, width, height, resize_method, interpolation, multiple_of)

                # Compression (Applied after resize to accurately maintain the effect)
                if img_compression > 0:
                    img_np = (image_tensor[0].numpy() * 255).clip(0, 255).astype(np.uint8)
                    img_pil = Image.fromarray(img_np)
                    img_byte_arr = bytes_io.BytesIO()
                    img_pil.save(img_byte_arr, format="JPEG", quality=max(1, 100 - img_compression))
                    img_pil = Image.open(img_byte_arr)
                    image_tensor = torch.from_numpy(np.array(img_pil).astype(np.float32) / 255.0)[None,]

                results.append(image_tensor)
            except Exception as e:
                print(f"Error loading {path}: {e}")

        # Combine all successfully loaded images into a single batched tensor for multi_output
        if len(results) > 0:
            # Safety Check: Advanced resize methods might output differently sized tensors (e.g., 'keep proportion')
            first_shape = results[0].shape
            all_same_shape = all(r.shape == first_shape for r in results)
            
            if all_same_shape:
                multi_output = torch.cat(results, dim=0)
            else:
                print("MultiImageLoader Warning: Images have different dimensions due to resize settings. Cannot batch into multi_output. Outputting zero tensor for the batch, but individual output nodes will still work fine.")
                multi_output = torch.zeros((1, 64, 64, 3))
        else:
            # Fallback empty tensor if no valid paths
            multi_output = torch.zeros((1, 64, 64, 3))
            results = [multi_output]

        # Pad individual outputs exactly to length 50 as defined in RETURN_TYPES
        padded_results = results + [torch.zeros((1, 64, 64, 3))] * (50 - len(results))

        # Return the multi batch output first, followed by the individual padded items
        refs = [await sdk.ImageRef._from_raw(item) for item in (multi_output, *padded_results[:50])]
        return io.NodeOutput(*refs)


NODE_CLASS_MAPPINGS = {"MultiImageLoader": MultiImageLoader}
