"""Test-only transport probe; not a registered node or manifest entry."""
from comfy_api.latest import io
from ..loader_nodes import read_input

class ReadRangeProbe(io.ComfyNode):
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="AmyReadRangeProbe", inputs=[io.String.Input("label"),
            io.Int.Input("maximum")], outputs=[io.String.Output()])

    @classmethod
    async def execute(cls, label, maximum):
        return io.NodeOutput((await read_input(label, maximum)).decode("ascii"))
