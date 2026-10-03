"""Secure, correlated image review for ComfyUI workflows."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from comfy_api.latest import io, sdk


INTERACTION_KIND = "image-choice"
INTERACTION_VARIANT = "image-preview-pause.inline-v1"
INTERACTION_TIMEOUT_SECONDS = 540.0
MAX_PREVIEW_IMAGES = 256


def _preview_identity(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("preview identity must be an object")
    filename = value.get("filename", value.get("name"))
    folder = value.get("type", "temp")
    subfolder = value.get("subfolder", "") or ""
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename.encode("utf-8")) > 255
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
    ):
        raise ValueError("preview filename is invalid")
    if folder not in {"input", "temp", "output"}:
        raise ValueError("preview folder type is invalid")
    if not isinstance(subfolder, str) or len(subfolder.encode("utf-8")) > 1024:
        raise ValueError("preview subfolder is invalid")
    path = PurePosixPath(subfolder.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("preview subfolder escapes its catalogue")
    return {
        "filename": filename,
        "type": folder,
        "subfolder": path.as_posix() if subfolder else "",
    }


def _preview_images(display: Any) -> list[dict[str, str]]:
    images = display.get("images") if isinstance(display, dict) else None
    if (
        not isinstance(images, (list, tuple))
        or not 1 <= len(images) <= MAX_PREVIEW_IMAGES
    ):
        raise ValueError("preview did not return a bounded image list")
    return [_preview_identity(value) for value in images]


def _action(response: Any) -> str:
    if not isinstance(response, dict):
        raise TypeError("image review response must be an object")
    action = response.get("action")
    if action not in {"continue", "cancel"}:
        raise ValueError("image review response has an invalid action")
    return action


class ImagePreviewPause(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("ui", "ui.interact", "execution.interrupt")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImagePreviewPause",
            display_name="Preview Image with Pause",
            category="image",
            inputs=[io.Image.Input("images")],
            outputs=[io.Image.Output("images", display_name="images")],
            hidden=[io.Hidden.unique_id, io.Hidden.prompt],
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, images: sdk.ImageRef) -> io.NodeOutput:
        display = await sdk.ctx().ui.preview_images(images)
        previews = _preview_images(display)
        response = await sdk.ctx().interact.request(
            INTERACTION_KIND,
            {
                "variant": INTERACTION_VARIANT,
                "images": previews,
                "count": len(previews),
            },
            timeout=INTERACTION_TIMEOUT_SECONDS,
        )
        if _action(response) == "cancel":
            await sdk.ctx().execution.interrupt()
            raise RuntimeError("ImagePreviewPause: user cancelled")
        return io.NodeOutput(images, ui=display)


NODE_CLASS_MAPPINGS = {"ImagePreviewPause": ImagePreviewPause}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ImagePreviewPause": "Preview Image with Pause",
}

__all__ = [
    "ImagePreviewPause",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
