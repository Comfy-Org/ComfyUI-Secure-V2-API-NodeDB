"""Secure Nodes V2 conversion of ComfyUI-WanMoEScheduler."""

from .nodes import WanMoEScheduler


NODE_CLASS_MAPPINGS = {"WanMoEScheduler": WanMoEScheduler}
NODE_DISPLAY_NAME_MAPPINGS = {"WanMoEScheduler": "WanMoEScheduler"}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
