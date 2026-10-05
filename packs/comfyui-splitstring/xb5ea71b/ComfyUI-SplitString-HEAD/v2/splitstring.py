"""Authority-free Secure Nodes V2 Split String node."""

from comfy_api.latest import ComfyExtension, io


class SplitString(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Split String",
            display_name="Split String",
            inputs=[io.String.Input("string")],
            outputs=[io.String.Output() for _ in range(12)],
        )

    @classmethod
    def execute(cls, string: str) -> io.NodeOutput:
        del cls
        return io.NodeOutput(*string.split("\n\n")[:12])


NODE_CLASS_MAPPINGS = {"Split String": SplitString}


class SplitStringExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [SplitString]


async def comfy_entrypoint() -> ComfyExtension:
    return SplitStringExtension()
