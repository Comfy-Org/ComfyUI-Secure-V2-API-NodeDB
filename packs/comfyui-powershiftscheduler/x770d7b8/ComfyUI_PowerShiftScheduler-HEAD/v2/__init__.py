"""Secure Nodes V2 conversion of ComfyUI Power Shift Scheduler."""

from .nodes import (
    PowerShiftSchedulerNode,
    RadianceShiftSchedulerNode,
    SigmaCurveFromPointsSchedulerNode,
    SigmaCurvePchipSchedulerNode,
)


NODE_CLASS_MAPPINGS = {
    "PowerShiftScheduler": PowerShiftSchedulerNode,
    "RadianceShiftScheduler": RadianceShiftSchedulerNode,
    "SigmaCurveFromPointsScheduler": SigmaCurveFromPointsSchedulerNode,
    "SigmaCurvePchipScheduler": SigmaCurvePchipSchedulerNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PowerShiftScheduler": "Power Shift Scheduler",
    "RadianceShiftScheduler": "Radiance Shift Scheduler",
    "SigmaCurveFromPointsScheduler": "From Points Scheduler",
    "SigmaCurvePchipScheduler": "PCHIP Scheduler",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
