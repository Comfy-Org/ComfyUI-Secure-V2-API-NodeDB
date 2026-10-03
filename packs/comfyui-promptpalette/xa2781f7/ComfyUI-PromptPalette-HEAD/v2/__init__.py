"""Secure Nodes V2 conversion of ComfyUI-PromptPalette."""

from .nodes import PromptPalette


NODE_CLASS_MAPPINGS = {"PromptPalette": PromptPalette}
NODE_DISPLAY_NAME_MAPPINGS = {"PromptPalette": "Prompt Palette"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
