"""Secure Nodes V2 backend for ComfyUI Custom Switch."""

from __future__ import annotations

from comfy_api.latest import io


class _OrchestratorBase(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    NODE_ID = ""
    DISPLAY_NAME = ""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id=cls.NODE_ID,
            display_name=cls.DISPLAY_NAME,
            category="Logic",
            inputs=[],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls) -> io.NodeOutput:
        return io.NodeOutput()


class OrchestratorNodeToogle(_OrchestratorBase):
    NODE_ID = "OrchestratorNodeToogle"
    DISPLAY_NAME = "OrchestratorNode Bypass autoconfig"


class OrchestratorNodeMuter(_OrchestratorBase):
    NODE_ID = "OrchestratorNodeMuter"
    DISPLAY_NAME = "OrchestratorNode Muter autoconfig"


class OrchestratorNodeGroupBypasser(_OrchestratorBase):
    NODE_ID = "OrchestratorNodeGroupBypasser"
    DISPLAY_NAME = "Orchestrator Group Bypasser"


class OrchestratorNodeGroupMuter(_OrchestratorBase):
    NODE_ID = "OrchestratorNodeGroupMuter"
    DISPLAY_NAME = "Orchestrator Group Muter"


class AutomaticImageSwitcher(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AutomaticImageSwitcher",
            display_name="Automatic Image Switch (3 inputs)",
            category="Logic",
            inputs=[
                io.Image.Input("image_1", optional=True),
                io.Image.Input("image_2", optional=True),
                io.Image.Input("image_3", optional=True),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, image_1=None, image_2=None, image_3=None) -> io.NodeOutput:
        for image in (image_1, image_2, image_3):
            if image is not None:
                return io.NodeOutput(image)

        import torch

        return io.NodeOutput(torch.zeros((1, 64, 64, 3), dtype=torch.float32))


NODE_CLASS_MAPPINGS = {
    "OrchestratorNodeToogle": OrchestratorNodeToogle,
    "OrchestratorNodeMuter": OrchestratorNodeMuter,
    "OrchestratorNodeGroupBypasser": OrchestratorNodeGroupBypasser,
    "OrchestratorNodeGroupMuter": OrchestratorNodeGroupMuter,
    "AutomaticImageSwitcher": AutomaticImageSwitcher,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    key: value.DISPLAY_NAME
    for key, value in NODE_CLASS_MAPPINGS.items()
    if issubclass(value, _OrchestratorBase)
}
NODE_DISPLAY_NAME_MAPPINGS["AutomaticImageSwitcher"] = (
    "Automatic Image Switch (3 inputs)"
)
