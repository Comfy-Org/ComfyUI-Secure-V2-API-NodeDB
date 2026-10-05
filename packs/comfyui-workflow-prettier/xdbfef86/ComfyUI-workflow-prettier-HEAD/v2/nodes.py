"""Backend schema for Workflow Prettifier.

The node is intentionally a backend no-op. Its graph-editing controls run in
the sandboxed frontend and use only typed graph handles.
"""

from __future__ import annotations

from comfy_api.latest import io


LAYOUTS = [
    "Layered (Vertical Stacks)",
    "Linear",
    "Compact (Tight Rectangle)",
    "Sort by Type",
]

DIRECTIONS = [
    "Left to Right",
    "Top to Bottom",
    "Right to Left",
]

GROUP_HANDLING = [
    "Auto (Respect Groups)",
    "Respect Groups",
    "Ignore Groups",
]


class WorkflowPrettifier(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WorkflowPrettifier",
            display_name="Workflow Prettifier",
            category="utils",
            description=(
                "Auto-arrange your workflow nodes.\n\n"
                "Layouts: Layered (DAG columns), Linear (single row), "
                "Compact (tight rectangle), Sort by Type (group same nodes).\n\n"
                "Supports groups, configurable direction, and undo stack (10 deep).\n\n"
                "Right-click selected nodes for alignment tools."
            ),
            inputs=[
                io.Combo.Input("layout", options=LAYOUTS),
                io.Combo.Input("direction", options=DIRECTIONS),
                io.Combo.Input("group_handling", options=GROUP_HANDLING),
                io.Int.Input(
                    "horizontal_spacing", default=100, min=30, max=400, step=10
                ),
                io.Int.Input(
                    "vertical_spacing", default=100, min=20, max=200, step=10
                ),
                io.Int.Input(
                    "group_padding", default=100, min=20, max=150, step=10
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, **_kwargs) -> io.NodeOutput:
        return io.NodeOutput()
