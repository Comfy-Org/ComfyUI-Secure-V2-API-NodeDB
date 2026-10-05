"""Secure Nodes V2 conversion of comfyui-workflow-name."""

from .nodes import WorkflowNameNode


NODE_CLASS_MAPPINGS = {"WorkflowName": WorkflowNameNode}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
