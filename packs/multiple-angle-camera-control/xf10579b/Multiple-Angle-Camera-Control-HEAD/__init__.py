"""
Camera Control Prompt Node - ComfyUI Custom Node
Optimized for dx8152's MultiAngle LoRA

Author: Lorenzo Mercu
Optimized for: dx8152's MultiAngle LoRA
License: MIT
"""

from .camera_control_prompt_node import NODE_CLASS_MAPPINGS as CAMERA_MAPPINGS
from .camera_control_prompt_node import NODE_DISPLAY_NAME_MAPPINGS as CAMERA_DISPLAY_MAPPINGS
from .light_control_prompt_node import NODE_CLASS_MAPPINGS as LIGHT_MAPPINGS
from .light_control_prompt_node import NODE_DISPLAY_NAME_MAPPINGS as LIGHT_DISPLAY_MAPPINGS

# Merge dei mappings da entrambi i nodi
NODE_CLASS_MAPPINGS = {**CAMERA_MAPPINGS, **LIGHT_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {**CAMERA_DISPLAY_MAPPINGS, **LIGHT_DISPLAY_MAPPINGS}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
