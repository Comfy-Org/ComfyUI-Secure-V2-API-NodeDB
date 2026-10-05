"""Secure Nodes V2 conversion of ComfyUI CapitanZiT Scheduler."""

from .nodes import (
    CapitanZiTLinearSigma,
    FlowMatchSchedulerKleinEdit,
    FlowMatchSchedulerSmoothCosine,
    SamplerMinimalChangeFlow,
)


NODE_CLASS_MAPPINGS = {
    "CapitanZiTLinearSigma": CapitanZiTLinearSigma,
    "FlowMatchSchedulerKleinEdit": FlowMatchSchedulerKleinEdit,
    "FlowMatchSchedulerSmoothCosine": FlowMatchSchedulerSmoothCosine,
    "SamplerMinimalChangeFlow": SamplerMinimalChangeFlow,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CapitanZiTLinearSigma": "CapitanZiT Linear Sigma (for Z-Image Turbo)",
    "FlowMatchSchedulerKleinEdit": "Klein Edit Scheduler",
    "FlowMatchSchedulerSmoothCosine": "Flow Scheduler (Smooth Cosine)",
    "SamplerMinimalChangeFlow": "Minimal Change Flow",
}

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
