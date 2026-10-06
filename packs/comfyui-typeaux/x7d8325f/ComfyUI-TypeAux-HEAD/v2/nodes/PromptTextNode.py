"""STRING to legacy TEXT passthrough without host authority."""
from comfy_api.latest import io

MAX_TEXT_BYTES = 131_072


class PromptTextNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PromptTextNodeFunction", category="ComfyUI-TypeAux",
            inputs=[io.String.Input("text", multiline=True, dynamic_prompts=True)],
            outputs=[io.Custom("TEXT").Output()],
        )

    @classmethod
    def execute(cls, text):
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("text exceeds the 128 KiB UTF-8 limit")
        return io.NodeOutput(text)
