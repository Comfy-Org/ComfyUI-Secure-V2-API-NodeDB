"""Secure Nodes V2 backend for ToggleMaster."""

from __future__ import annotations

from comfy_api.latest import io


class DynamicTextConcatenate(io.ComfyNode):
    """Join up to ten linked strings in numeric input order."""

    DELIMITER_MAP = {
        "space": " ",
        "none": "",
        "comma": ", ",
        "newline": "\n",
        "pipe": " | ",
    }

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DynamicTextConcatenate",
            display_name="Dynamic Text Concatenate",
            category="utils",
            inputs=[
                *[
                    io.String.Input(
                        f"text_{index}", optional=True, force_input=True,
                    )
                    for index in range(1, 11)
                ],
                io.Combo.Input(
                    "delimiter",
                    options=["space", "none", "comma", "newline", "pipe", "custom"],
                    default="space",
                    optional=True,
                ),
                io.String.Input("custom_delimiter", default="", optional=True),
            ],
            outputs=[io.String.Output("text", display_name="text")],
        )

    @classmethod
    def execute(
        cls,
        delimiter: str = "space",
        custom_delimiter: str = "",
        **kwargs: object,
    ) -> io.NodeOutput:
        separator = (
            custom_delimiter
            if delimiter == "custom"
            else cls.DELIMITER_MAP.get(delimiter, " ")
        )
        values = [
            str(kwargs[key])
            for index in range(1, 11)
            if (key := f"text_{index}") in kwargs
            and kwargs[key] is not None
            and kwargs[key] != ""
        ]
        return io.NodeOutput(separator.join(values))


NODE_CLASS_MAPPINGS = {
    "DynamicTextConcatenate": DynamicTextConcatenate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DynamicTextConcatenate": "Dynamic Text Concatenate",
}
