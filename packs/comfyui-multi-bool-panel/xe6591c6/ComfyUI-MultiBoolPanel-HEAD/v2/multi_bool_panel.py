"""Secure Nodes V2 backend for Multi Bool Panel.

The node intentionally has no backend behavior.  Its one input remains part of
the workflow wire format while the typed frontend extension performs the
interactive graph edits.
"""

from comfy_api.latest import io


class SolidlimeMultiBoolPanel(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SolidlimeMultiBoolPanel",
            display_name="Multi Bool Panel",
            category="Logic",
            inputs=[
                io.Combo.Input(
                    "mode",
                    options=["widgets", "bypass", "mute"],
                    default="widgets",
                )
            ],
            outputs=[],
        )

    @classmethod
    def execute(cls, **_kwargs) -> io.NodeOutput:
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {"SolidlimeMultiBoolPanel": SolidlimeMultiBoolPanel}
NODE_DISPLAY_NAME_MAPPINGS = {"SolidlimeMultiBoolPanel": "Multi Bool Panel"}
