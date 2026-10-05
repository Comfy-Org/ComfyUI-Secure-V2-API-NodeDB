"""Secure Nodes V2 implementation of ComfyUI Better Strings."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io


class BetterString(io.ComfyNode):
    """Expose a multiline string and optionally prepend a chained string."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BetterString",
            display_name="Better Multiline String 💡",
            category="Better Things 💡",
            inputs=[
                io.String.Input("chain", optional=True, force_input=True),
                io.String.Input("string", multiline=True),
            ],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, string: str, chain: str = "") -> io.NodeOutput:
        if not chain.strip():
            return io.NodeOutput(string)

        chain = chain.rstrip()
        if chain[-1] != ",":
            chain += ","
        chain += "\n\n"
        return io.NodeOutput(chain + string)


NODE_CLASS_MAPPINGS = {"BetterString": BetterString}


class BetterStringsExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [BetterString]


async def comfy_entrypoint() -> BetterStringsExtension:
    return BetterStringsExtension()
