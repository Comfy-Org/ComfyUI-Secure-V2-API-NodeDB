"""Secure Nodes V2 conversion of ComfyUI Sigmoid Offset Scheduler."""

from .nodes import SigmoidOffsetScheduler


NODE_CLASS_MAPPINGS = {
    "SigmoidOffsetScheduler": SigmoidOffsetScheduler,
}

__all__ = ["NODE_CLASS_MAPPINGS"]
