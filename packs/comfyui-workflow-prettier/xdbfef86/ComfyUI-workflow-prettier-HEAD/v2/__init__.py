"""Secure Nodes V2 conversion of ComfyUI Workflow Prettier."""

from .nodes import WorkflowPrettifier


NODE_CLASS_MAPPINGS = {
    "WorkflowPrettifier": WorkflowPrettifier,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WorkflowPrettifier": "Workflow Prettifier",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
