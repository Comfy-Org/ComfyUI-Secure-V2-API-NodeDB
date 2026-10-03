"""Presence node for the AutoNotes frontend."""

from comfy_api.latest import io


class AutoNotesNode(io.ComfyNode):
    """Keep the legacy palette entry without acquiring backend authority."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AutoNotesNode",
            display_name="Auto Notes",
            category="AutoNotes",
            inputs=[],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls) -> io.NodeOutput:
        return io.NodeOutput()
