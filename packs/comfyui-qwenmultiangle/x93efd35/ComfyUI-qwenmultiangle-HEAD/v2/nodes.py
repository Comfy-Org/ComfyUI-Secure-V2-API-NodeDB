"""Secure V2 nodes for Qwen Multiangle's pinned two-node surface.

The camera prompt, camera geometry, and glossary remain pack-owned. The only
host service is the bounded UI preview broker, which turns an optional opaque
IMAGE ref into temporary preview metadata without exposing pixels or paths.
"""
from __future__ import annotations

import math

from comfy_api.latest import ComfyExtension, io, sdk

from .camera_glossary import (
    TARGET_LANGUAGE_OPTIONS,
    label_to_code,
    translate_camera_terms,
)


_SCENE_CENTER_Y = 0.5


def _build_camera_info(
    horizontal_angle: int, vertical_angle: int, zoom: float,
) -> dict:
    azimuth = math.radians(horizontal_angle)
    elevation = math.radians(vertical_angle)
    visual_distance = 2.6 - (zoom / 10.0) * 2.0
    return {
        "position": {
            "x": visual_distance * math.sin(azimuth) * math.cos(elevation),
            "y": _SCENE_CENTER_Y + visual_distance * math.sin(elevation),
            "z": visual_distance * math.cos(azimuth) * math.cos(elevation),
        },
        "target": {"x": 0.0, "y": _SCENE_CENTER_Y, "z": 0.0},
        "zoom": 1,
        "cameraType": "perspective",
    }


def _camera_prompt(
    horizontal_angle: int, vertical_angle: int, zoom: float,
) -> str:
    angle = horizontal_angle % 360
    if angle < 22.5 or angle >= 337.5:
        horizontal = "front view"
    elif angle < 67.5:
        horizontal = "front-right quarter view"
    elif angle < 112.5:
        horizontal = "right side view"
    elif angle < 157.5:
        horizontal = "back-right quarter view"
    elif angle < 202.5:
        horizontal = "back view"
    elif angle < 247.5:
        horizontal = "back-left quarter view"
    elif angle < 292.5:
        horizontal = "left side view"
    else:
        horizontal = "front-left quarter view"

    if vertical_angle < -15:
        vertical = "low-angle shot"
    elif vertical_angle < 15:
        vertical = "eye-level shot"
    elif vertical_angle < 45:
        vertical = "elevated shot"
    else:
        vertical = "high-angle shot"

    if zoom < 2:
        distance = "wide shot"
    elif zoom < 6:
        distance = "medium shot"
    else:
        distance = "close-up"
    return f"<sks> {horizontal} {vertical} {distance}"


class QwenMultiangleCameraNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("ui",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="QwenMultiangleCameraNode",
            display_name="Qwen Multiangle Camera",
            category="image/multiangle",
            is_output_node=True,
            description=(
                "Interactive 3D camera angle control for multi-angle image "
                "generation"
            ),
            inputs=[
                io.Int.Input(
                    "horizontal_angle", default=0, min=0, max=360, step=1,
                    display_name="Horizontal Angle",
                    tooltip="Camera azimuth angle (0-360°)",
                ),
                io.Int.Input(
                    "vertical_angle", default=0, min=-30, max=60, step=1,
                    display_name="Vertical Angle",
                    tooltip="Camera elevation angle (-30° to 60°)",
                ),
                io.Float.Input(
                    "zoom", default=5.0, min=0.0, max=10.0, step=0.1,
                    display_name="Zoom",
                    tooltip="Camera distance (0=wide, 10=close-up)",
                ),
                io.Boolean.Input(
                    "default_prompts", default=True,
                    display_name="Default Prompts",
                    tooltip="Deprecated, kept for backward compatibility",
                ),
                io.Boolean.Input(
                    "camera_view", default=False,
                    display_name="Camera View",
                    tooltip="Toggle camera perspective preview",
                ),
                io.Image.Input(
                    "image", optional=True,
                    tooltip="Optional input image to display in the 3D scene",
                ),
            ],
            outputs=[
                io.String.Output("prompt", display_name="Prompt"),
                io.Load3DCamera.Output(
                    "camera_info", display_name="Camera Info",
                ),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls,
        horizontal_angle,
        vertical_angle,
        zoom,
        default_prompts=True,
        camera_view=False,
        image=None,
    ) -> io.NodeOutput:
        del default_prompts, camera_view
        horizontal_angle = max(0, min(360, int(horizontal_angle)))
        vertical_angle = max(-30, min(60, int(vertical_angle)))
        zoom = max(0.0, min(10.0, float(zoom)))

        preview_images = []
        if image is not None:
            if not isinstance(image, sdk.ImageRef):
                raise TypeError("image must be an IMAGE ref")
            preview = await sdk.ctx().ui.preview_images(image)
            preview_images = list(preview.get("images", []))

        return io.NodeOutput(
            _camera_prompt(horizontal_angle, vertical_angle, zoom),
            _build_camera_info(horizontal_angle, vertical_angle, zoom),
            ui={"preview_images": preview_images},
        )

    @classmethod
    def fingerprint_inputs(
        cls,
        horizontal_angle,
        vertical_angle,
        zoom,
        default_prompts=True,
        camera_view=False,
        image=None,
    ):
        del default_prompts, camera_view
        parts = [str(horizontal_angle), str(vertical_angle), str(zoom)]
        if image is not None:
            if not isinstance(image, sdk.ImageRef):
                raise TypeError("image must be an IMAGE ref")
            parts.append(image.id)
        return "_".join(parts)


class QwenMultiangleCameraTranslateNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="QwenMultiangleCameraTranslateNode",
            display_name="Qwen Multiangle Camera Translate",
            category="image/multiangle",
            description=(
                "Translate camera/shot terms in a prompt to a target language "
                "via a maintained glossary; non-camera words pass through."
            ),
            inputs=[
                io.String.Input(
                    "prompt", multiline=True, default="",
                    display_name="Prompt",
                    tooltip=(
                        "Prompt text containing camera terms to translate "
                        "(link from the camera node, or paste text)"
                    ),
                ),
                io.Combo.Input(
                    "target_language", options=TARGET_LANGUAGE_OPTIONS,
                    default=TARGET_LANGUAGE_OPTIONS[0],
                    display_name="Target Language",
                    tooltip=(
                        "Language to translate camera terms into. Only glossary "
                        "phrases are translated; everything else is untouched. "
                        "Select English for a pass-through."
                    ),
                ),
            ],
            outputs=[io.String.Output("prompt", display_name="Prompt")],
        )

    @classmethod
    async def execute(cls, prompt, target_language) -> io.NodeOutput:
        language = label_to_code(str(target_language))
        return io.NodeOutput(
            translate_camera_terms(str(prompt or ""), language),
        )


NODE_CLASS_MAPPINGS = {
    "QwenMultiangleCameraNode": QwenMultiangleCameraNode,
    "QwenMultiangleCameraTranslateNode": QwenMultiangleCameraTranslateNode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


class QwenMultiangleExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return QwenMultiangleExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "QwenMultiangleCameraNode",
    "QwenMultiangleCameraTranslateNode",
    "QwenMultiangleExtension",
    "comfy_entrypoint",
]
