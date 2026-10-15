import json
import os
import random
from typing import Any
from unittest.mock import MagicMock

try:
    import folder_paths  # pyright: ignore[reportMissingImports]
except ImportError:
    folder_paths = MagicMock()

import numpy as np
import PIL.Image
import torch
from PIL.PngImagePlugin import PngInfo

from comfyui_jh_misc_nodes import jh_types


class JHPreviewImage:
    def __init__(self) -> None:
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + "".join(
            random.choice("abcdefghijklmnopqrstupvxyz") for x in range(5)
        )
        self.compress_level = 1

    @classmethod
    def INPUT_TYPES(cls) -> jh_types.JHInputTypesType:
        # fmt: off
        return {
            "required": {
                "images": (
                    jh_types.JHNodeInputOutputTypeEnum.IMAGE, {}
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }
        # fmt: on

    RETURN_TYPES = (jh_types.JHNodeInputOutputTypeEnum.IMAGE,)
    FUNCTION = "preview_images"
    CATEGORY = "JH Misc Nodes"
    OUTPUT_NODE = True
    EXPERIMENTAL = True

    def preview_images(
        self,
        images: torch.Tensor,
        filename_prefix: str = "ComfyUI",
        prompt: dict[str, Any] | None = None,
        extra_pnginfo: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = (
            folder_paths.get_save_image_path(
                filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0]
            )
        )
        results = []

        for batch_number, image in enumerate(images):
            i = 255.0 * image.cpu().numpy()
            img = PIL.Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(
                os.path.join(full_output_folder, file),
                compress_level=self.compress_level,
            )
            results.append(
                {"filename": file, "subfolder": subfolder, "type": self.type}
            )
            counter += 1

        # fmt: off
        return {
            "ui": {
                "images": results
            },
            "result": (images,),
        }
        # fmt: on
