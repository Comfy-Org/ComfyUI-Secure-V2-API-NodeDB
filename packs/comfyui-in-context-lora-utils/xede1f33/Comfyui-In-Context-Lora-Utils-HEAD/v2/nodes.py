"""Secure Nodes V2 registrations for In-Context LoRA utilities."""

from .InContextLoraUtils import AddMaskForICLora
from .InContextUtils import AutoPatch, ConcatContextWindow, CreateContextWindow


NODE_CLASS_MAPPINGS = {
    "AddMaskForICLora": AddMaskForICLora,
    "CreateContextWindow": CreateContextWindow,
    "ConcatContextWindow": ConcatContextWindow,
    "AutoPatch": AutoPatch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AddMaskForICLora": "Add Mask For IC Lora",
    "CreateContextWindow": "Create Context Window",
    "ConcatContextWindow": "Concatenate Context Window",
    "AutoPatch": "Auto Patch",
}


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "AddMaskForICLora",
    "AutoPatch",
    "ConcatContextWindow",
    "CreateContextWindow",
]
