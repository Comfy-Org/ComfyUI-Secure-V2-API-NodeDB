"""
ComfyUI Preview Image with Pause
Version: 1.0
Author: Cordux (with help from Grok and Claude)
"""
import comfy
from server import PromptServer
from aiohttp import web
import time
import os
import random
import numpy as np
from PIL import Image as PILImage
import folder_paths
from comfy.model_management import InterruptProcessingException


class ImagePreviewPause:
    status_by_id = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
            },
            "hidden": {
                "id": "UNIQUE_ID",
                "prompt": "PROMPT",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "execute"
    CATEGORY = "image"
    OUTPUT_NODE = True

    def execute(self, images, id=None, prompt=None):
        # Save images for preview
        filename_prefix = "preview_pause_" + ''.join(random.choice("abcdefghijklmnopqrstupvxyz") for _ in range(5))

        full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix,
            folder_paths.get_temp_directory(),
            images[0].shape[1],
            images[0].shape[0]
        )

        results = []
        for batch_number, image in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = PILImage.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), compress_level=1)

            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": "temp"
            })
            counter += 1

        # Send preview to UI immediately using PromptServer
        PromptServer.instance.send_sync("executing", {
            "node": id,
            "prompt_id": None  # You might need to track this
        })

        # Send the preview images
        PromptServer.instance.send_sync("executed", {
            "node": id,
            "output": {
                "images": results
            },
            "prompt_id": None
        })

        # Small delay to ensure UI receives it
        time.sleep(0.3)

        # Now pause and wait
        self.status_by_id[id] = "paused"

        while self.status_by_id[id] == "paused":
            time.sleep(0.1)

        # Check for cancel (key still exists)
        if self.status_by_id[id] == "cancelled":
            raise InterruptProcessingException()

        # Safe cleanup on continue path
        self.status_by_id.pop(id, None)

        # Return images to continue workflow
        return (images,)
    #    return {
    #        "ui": {"images": results},
    #        "result": (images,)
    #    }


@PromptServer.instance.routes.post("/image_preview_pause/continue/{node_id}")
async def handle_continue(request):
    node_id = request.match_info["node_id"].strip()
    ImagePreviewPause.status_by_id[node_id] = "continue"
    return web.json_response({"status": "ok"})


@PromptServer.instance.routes.post("/image_preview_pause/cancel")
async def handle_cancel(request):
    comfy.model_management.interrupt_current_processing()
    for node_id in ImagePreviewPause.status_by_id:
        ImagePreviewPause.status_by_id[node_id] = "cancelled"
    return web.json_response({"status": "ok"})
