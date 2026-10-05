"""Secure Nodes V2 implementation of Multiple Angle Camera Control."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io


class CameraControlPromptNode(io.ComfyNode):
    """Build the pinned bilingual MultiAngle camera prompt."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CameraControlPromptNode",
            display_name="Camera Control Prompt Generator",
            category="prompt/camera",
            inputs=[
                io.Combo.Input(
                    "move_horizontal",
                    options=["none", "left", "right"],
                    default="none",
                ),
                io.Combo.Input(
                    "move_vertical",
                    options=["none", "up", "down"],
                    default="none",
                ),
                io.Combo.Input(
                    "move_forward", options=["no", "yes"], default="no",
                ),
                io.Int.Input(
                    "rotate",
                    default=0,
                    min=-90,
                    max=90,
                    step=45,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Boolean.Input("view_top_down", default=False),
                io.Boolean.Input("view_wide_angle", default=False),
                io.Boolean.Input("view_close_up", default=False),
                io.Boolean.Input("view_bottom_up", default=False),
            ],
            outputs=[io.String.Output("prompt", display_name="prompt")],
        )

    @classmethod
    def execute(
        cls,
        move_horizontal: str,
        move_vertical: str,
        move_forward: str,
        rotate: int,
        view_top_down: bool,
        view_wide_angle: bool,
        view_close_up: bool,
        view_bottom_up: bool,
    ) -> io.NodeOutput:
        prompt_parts: list[str] = []

        if move_horizontal == "left":
            prompt_parts.append("将镜头向左移动 Move the camera left.")
        elif move_horizontal == "right":
            prompt_parts.append("将镜头向右移动 Move the camera right.")

        if move_vertical == "up":
            prompt_parts.append("将镜头向上移动 Move the camera up.")
        elif move_vertical == "down":
            prompt_parts.append("将镜头向下移动 Move the camera down.")

        if move_forward == "yes":
            prompt_parts.append("将镜头向前移动 Move the camera forward.")

        if rotate < 0:
            degrees = abs(rotate)
            prompt_parts.append(
                f"将镜头向左旋转{degrees}度 Rotate the camera {degrees} degrees to the left."
            )
        elif rotate > 0:
            prompt_parts.append(
                f"将镜头向右旋转{rotate}度 Rotate the camera {rotate} degrees to the right."
            )

        if view_top_down:
            prompt_parts.append("将镜头转为俯视 Turn the camera to a top-down view.")
        if view_wide_angle:
            prompt_parts.append(
                "将镜头转为广角镜头 Turn the camera to a wide-angle lens."
            )
        if view_close_up:
            prompt_parts.append("将镜头转为特写镜头 Turn the camera to a close-up.")
        if view_bottom_up:
            prompt_parts.append(
                "將相機方向調整為由下而上的視角 Turn the camera to a bottom-up view."
            )

        return io.NodeOutput(" ".join(prompt_parts))


class RelightingPromptNode(io.ComfyNode):
    """Build the pinned bilingual relighting prompt."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    LIGHT_DIRECTIONS = [
        "front",
        "front_left",
        "left",
        "back_left",
        "back",
        "back_right",
        "right",
        "front_right",
        "above",
        "below",
    ]

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RelightingPromptNode",
            display_name="Relighting Prompt Generator",
            category="relighting",
            inputs=[
                io.Combo.Input(
                    "light_direction",
                    options=cls.LIGHT_DIRECTIONS,
                    default="front",
                ),
                io.Boolean.Input("use_chinese", default=True),
            ],
            outputs=[io.String.Output("prompt", display_name="prompt")],
        )

    @classmethod
    def execute(cls, light_direction: str, use_chinese: bool) -> io.NodeOutput:
        light_directions_cn = {
            "front": "光源来自前方",
            "front_left": "光源来自左前方",
            "left": "光源来自左方",
            "back_left": "光源来自左后方",
            "back": "光源来自后方",
            "back_right": "光源来自右后方",
            "right": "光源来自右方",
            "front_right": "光源来自右前方",
            "above": "光源来自上方",
            "below": "光源来自下方",
        }
        light_directions_en = {
            "front": "light source from the front",
            "front_left": "light source from the front left",
            "left": "light source from the left",
            "back_left": "light source from the back left",
            "back": "light source from the back",
            "back_right": "light source from the back right",
            "right": "light source from the right",
            "front_right": "light source from the front right",
            "above": "light source from above",
            "below": "light source from below",
        }

        if use_chinese:
            direction_text = light_directions_cn.get(light_direction, "光源来自前方")
            prompt = f"使用图2的亮度贴图对图1重新照明({direction_text})"
        else:
            direction_text = light_directions_en.get(
                light_direction, "light source from the front",
            )
            prompt = (
                "Relight Figure 1 using the luminance map from Figure 2 "
                f"({direction_text})"
            )
        return io.NodeOutput(prompt)


NODE_CLASS_MAPPINGS = {
    "CameraControlPromptNode": CameraControlPromptNode,
    "RelightingPromptNode": RelightingPromptNode,
}


class MultipleAngleCameraControlExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [CameraControlPromptNode, RelightingPromptNode]


async def comfy_entrypoint() -> MultipleAngleCameraControlExtension:
    return MultipleAngleCameraControlExtension()


__all__ = [
    "CameraControlPromptNode",
    "MultipleAngleCameraControlExtension",
    "NODE_CLASS_MAPPINGS",
    "RelightingPromptNode",
    "comfy_entrypoint",
]
