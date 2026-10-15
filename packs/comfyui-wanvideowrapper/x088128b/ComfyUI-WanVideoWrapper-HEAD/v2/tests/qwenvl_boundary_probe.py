"""Test-only public raw-denial/whole-conditioning controls, not a release node."""
from comfy_api.latest import io


class JackQwenBoundaryProbe(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="JackQwenBoundaryProbe",
            inputs=[io.Conditioning.Input("conditioning"), io.String.Input("mode")],
            outputs=[io.Custom("QWENVL_EMBEDS").Output()])

    @classmethod
    async def execute(cls, conditioning, mode):
        embedding = await conditioning.embedding()
        if mode == "raw":
            await embedding.raw()
        elif mode == "whole":
            await conditioning.value()
        return io.NodeOutput(embedding)
