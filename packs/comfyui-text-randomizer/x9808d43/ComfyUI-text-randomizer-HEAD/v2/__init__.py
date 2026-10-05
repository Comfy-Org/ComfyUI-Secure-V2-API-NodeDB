"""Secure Nodes V2 conversion of ComfyUI Text Randomizer."""

from .nodes import (
    ConcatText,
    RandomizeText,
    RandomizeTextWithCheck,
    RandomTextChoice,
    ShowText,
)


NODE_CLASS_MAPPINGS = {
    "RandomizeText": RandomizeText,
    "RandomizeTextWithCheck": RandomizeTextWithCheck,
    "RandomTextChoice": RandomTextChoice,
    "ConcatText": ConcatText,
    "ShowText": ShowText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomizeText": "Text randomizer",
    "RandomizeTextWithCheck": "Text randomizer with check",
    "RandomTextChoice": "Get one text or another at random",
    "ConcatText": "Concatenate text",
    "ShowText": "Show text",
}

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
