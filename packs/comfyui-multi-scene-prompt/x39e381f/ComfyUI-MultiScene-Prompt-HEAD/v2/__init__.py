"""Secure Nodes V2 conversion of ComfyUI-MultiScene-Prompt."""

from .nodes import MultiScenePrompt


NODE_CLASS_MAPPINGS = {"MultiScenePrompt": MultiScenePrompt}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiScenePrompt": "Multi-Scene Prompt Editor",
}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
