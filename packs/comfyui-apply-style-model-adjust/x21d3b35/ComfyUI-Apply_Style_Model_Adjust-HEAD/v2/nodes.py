import torch
import os
import sys
import json
import hashlib
import traceback
import math
import time
import random

class ApplyStyleModelAdjust:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                "conditioning": ("CONDITIONING", ),
                "style_model": ("STYLE_MODEL", ),
                "clip_vision_output": ("CLIP_VISION_OUTPUT", ),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                }}
    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "apply_stylemodel"

    CATEGORY = "conditioning/style_model"

    def apply_stylemodel(self, clip_vision_output, style_model, conditioning, strength):
        cond = style_model.get_cond(clip_vision_output).flatten(start_dim=0, end_dim=1).unsqueeze(dim=0)
        c = []
        for t in conditioning:
            # Enhance original prompt power when strength is low
            base_cond = t[0] * (3.0 - 2.0 * strength)  # Will boost prompt up to 3x when strength=0
            style_cond = cond * (strength * 0.7)  # Reduce style influence
            mixed_cond = torch.cat((base_cond, style_cond), dim=1)
            n = [mixed_cond, t[1].copy()]
            c.append(n)
        return (c, )

# Node class mappings
NODE_CLASS_MAPPINGS = {
    "ApplyStyleModelAdjust": ApplyStyleModelAdjust,
}

# Display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "ApplyStyleModelAdjust": "Apply Style Model (Adjusted)",
}