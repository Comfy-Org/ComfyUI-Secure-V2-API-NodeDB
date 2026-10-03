"""Secure scalar slider nodes."""

from __future__ import annotations

from comfy_api.latest import io


class ConfigurableIntSlider(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConfigurableIntSlider",
            display_name="Configurable Int Slider",
            category="utils/sliders",
            inputs=[
                io.Int.Input(
                    "value", default=50, min=-1_000_000, max=1_000_000, step=1,
                ),
                io.Int.Input(
                    "min_value", default=0, min=-1_000_000, max=1_000_000, step=1,
                ),
                io.Int.Input(
                    "max_value", default=100, min=-1_000_000, max=1_000_000, step=1,
                ),
                io.Int.Input(
                    "step", default=1, min=1, max=1_000_000, step=1,
                ),
            ],
            outputs=[io.Int.Output("int", display_name="int")],
        )

    @classmethod
    def execute(
        cls, value: int, min_value: int, max_value: int, step: int,
    ) -> io.NodeOutput:
        del step
        return io.NodeOutput(max(int(min_value), min(int(max_value), int(value))))


class SimpleFloatSlider(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SimpleFloatSlider",
            display_name="Simple Float Slider",
            category="utils/sliders",
            inputs=[
                io.Float.Input(
                    "value", default=0.5, min=0.0, max=1.0, step=0.01,
                ),
            ],
            outputs=[io.Float.Output("float", display_name="float")],
        )

    @classmethod
    def execute(cls, value: float) -> io.NodeOutput:
        return io.NodeOutput(round(float(value), 2))


class ConfigurableFloatSlider(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConfigurableFloatSlider",
            display_name="Configurable Float Slider",
            category="utils/sliders",
            inputs=[
                io.Float.Input(
                    "value", default=0.5, min=-10_000.0, max=10_000.0,
                    step=0.0001,
                ),
                io.Float.Input(
                    "min_value", default=0.0, min=-10_000.0, max=10_000.0,
                    step=0.01,
                ),
                io.Float.Input(
                    "max_value", default=1.0, min=-10_000.0, max=10_000.0,
                    step=0.01,
                ),
                io.Int.Input("precision", default=2, min=0, max=4, step=1),
                io.Float.Input(
                    "step", default=0.01, min=0.0001, max=1_000.0, step=0.01,
                ),
            ],
            outputs=[io.Float.Output("float", display_name="float")],
        )

    @classmethod
    def execute(
        cls,
        value: float,
        min_value: float,
        max_value: float,
        precision: int,
        step: float,
    ) -> io.NodeOutput:
        del step
        clamped = max(float(min_value), min(float(max_value), float(value)))
        return io.NodeOutput(round(clamped, int(precision)))


NODE_CLASS_MAPPINGS = {
    "ConfigurableIntSlider": ConfigurableIntSlider,
    "SimpleFloatSlider": SimpleFloatSlider,
    "ConfigurableFloatSlider": ConfigurableFloatSlider,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ConfigurableIntSlider": "Configurable Int Slider",
    "SimpleFloatSlider": "Simple Float Slider",
    "ConfigurableFloatSlider": "Configurable Float Slider",
}
