"""Secure Nodes V2 implementation of Denoise Chooser."""

from __future__ import annotations

from comfy_api.latest import io, sdk


class DenoiseChooser(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DenoiseChooser|Koushakur",
            display_name="Denoise Chooser",
            category="advanced",
            inputs=[
                io.Latent.Input("Latent"),
                io.Float.Input(
                    "FloatIfEmpty", default=1.0, min=0.0, max=100.0,
                    step=0.05,
                ),
                io.Float.Input(
                    "FloatIfNot", default=0.75, min=0.0, max=100.0,
                    step=0.05,
                ),
            ],
            outputs=[
                io.Latent.Output("LATENT", display_name="LATENT"),
                io.Float.Output("FLOAT", display_name="FLOAT"),
            ],
        )

    @staticmethod
    def _normalize(value: float) -> float:
        return value if value <= 1.0 else value / 100

    @classmethod
    async def execute(
        cls,
        Latent: sdk.LatentRef,
        FloatIfEmpty: float,
        FloatIfNot: float,
    ) -> io.NodeOutput:
        latent_value = await Latent.value()
        nonzero_count = latent_value["samples"].count_nonzero().item()
        selected = FloatIfNot if nonzero_count > 0 else FloatIfEmpty
        return io.NodeOutput(Latent, cls._normalize(selected))


NODE_CLASS_MAPPINGS = {
    "DenoiseChooser|Koushakur": DenoiseChooser,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DenoiseChooser|Koushakur": "Denoise Chooser",
}
