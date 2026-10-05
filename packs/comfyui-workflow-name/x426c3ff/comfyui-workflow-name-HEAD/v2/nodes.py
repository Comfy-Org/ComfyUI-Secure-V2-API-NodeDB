"""Authority-free Secure Nodes V2 backend for Workflow Name."""

from __future__ import annotations

from comfy_api.latest import io


FALLBACK_NAME = "NO_WORKFLOW_NAME"


class WorkflowNameNode(io.ComfyNode):
    """Return the workflow name synchronized by the typed frontend facade."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WorkflowName",
            display_name="Workflow Name",
            category="utils",
            inputs=[io.String.Input("workflow_name", default=FALLBACK_NAME)],
            outputs=[io.String.Output("workflow_name")],
        )

    @classmethod
    def execute(cls, workflow_name: str = FALLBACK_NAME) -> io.NodeOutput:
        del cls
        if not isinstance(workflow_name, str):
            raise TypeError("workflow_name must be a string")
        name = workflow_name.strip() if workflow_name else FALLBACK_NAME
        return io.NodeOutput(name)


NODE_CLASS_MAPPINGS = {"WorkflowName": WorkflowNameNode}
