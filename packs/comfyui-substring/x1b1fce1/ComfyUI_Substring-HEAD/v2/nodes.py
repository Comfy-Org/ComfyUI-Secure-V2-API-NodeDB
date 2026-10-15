"""Pack-owned bounded substring slicing; no host authority required."""

from comfy_api.latest import io

MAX_TEXT_BYTES = 1_048_576


class SubstringFunction(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SubstringTheory", display_name="Substring", category="utils",
            is_output_node=True,
            inputs=[io.String.Input("text", multiline=True),
                    io.Int.Input("length", default=75)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, text, length):
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if isinstance(length, bool) or not isinstance(length, int):
            raise TypeError("length must be an integer")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("text exceeds the 1 MiB UTF-8 limit")
        if text == "undefined":
            text = ""
        if length >= 0:
            out = text[:length]
        else:
            out = text[length:]
        return io.NodeOutput(out, ui={"text": (out,)})


NODE_CLASS_MAPPINGS = {
    "SubstringTheory": SubstringFunction,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SubstringTheory": "Substring"
}
