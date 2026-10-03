"""Secure Nodes V2 backend for ComfyUI Nixie Timer."""

from comfy_api.latest import io


TUBE_COLORS = ["红色", "绿色", "蓝色", "琥珀", "紫色", "青色", "白色"]


class NixieTimer(io.ComfyNode):
    """An inert graph node whose mounted frontend displays the timer."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="NixieTimer",
            display_name="🕰️ 辉光管计时器",
            category="utils",
            inputs=[
                io.Combo.Input(
                    "tube_color",
                    options=TUBE_COLORS,
                    default="红色",
                )
            ],
            outputs=[],
        )

    @classmethod
    def execute(cls, tube_color: str) -> io.NodeOutput:
        del tube_color
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {"NixieTimer": NixieTimer}
NODE_DISPLAY_NAME_MAPPINGS = {"NixieTimer": "🕰️ 辉光管计时器"}
