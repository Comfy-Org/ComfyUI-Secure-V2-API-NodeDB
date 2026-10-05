"""Secure Nodes V2 backend for ComfyUI Prompt Formatter."""

from __future__ import annotations

from comfy_api.latest import io, sdk


class CLIPTextEncodeFormatter(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CLIPTextEncodeFormatter",
            display_name="CLIP Text Encode (Prompt Formatter)",
            category="prompt_formatter",
            description=(
                "Encodes a text prompt using a CLIP model into an embedding "
                "that can be used to guide the diffusion model towards "
                "generating specific images."
            ),
            inputs=[
                io.String.Input(
                    "text",
                    multiline=True,
                    dynamic_prompts=True,
                    tooltip="The text to be encoded.",
                ),
                io.Clip.Input(
                    "clip",
                    tooltip="The CLIP model used for encoding the text.",
                ),
            ],
            outputs=[
                io.Conditioning.Output(
                    tooltip=(
                        "A conditioning containing the embedded text used to "
                        "guide the diffusion model."
                    ),
                ),
            ],
        )

    @classmethod
    async def execute(cls, text: str, clip: sdk.ClipRef) -> io.NodeOutput:
        if clip is None:
            raise RuntimeError(
                "ERROR: clip input is invalid: None\n\nIf the clip is from a "
                "checkpoint loader node your checkpoint does not contain a "
                "valid clip or text encoder model."
            )
        return io.NodeOutput(await clip.encode(text))


class TextOnlyFormatter(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TextOnlyFormatter",
            display_name="Prompt Formatter (Only Text)",
            category="prompt_formatter",
            description=(
                "A simple node that returns the input text as-is. Useful for "
                "debugging or chaining text-based operations."
            ),
            inputs=[
                io.String.Input(
                    "text",
                    multiline=True,
                    dynamic_prompts=True,
                    tooltip="The raw text prompt to pass through or format.",
                ),
            ],
            outputs=[
                io.String.Output(
                    tooltip=(
                        "Returns the raw text input for use in further "
                        "processing."
                    ),
                ),
            ],
        )

    @classmethod
    def execute(cls, text: str) -> io.NodeOutput:
        return io.NodeOutput(text)


class TextAppendFormatter(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TextAppendFormatter",
            display_name="Append String",
            category="prompt_formatter",
            description=(
                "Appends two strings together cleanly, removing unnecessary "
                "commas, spaces, or other artifacts."
            ),
            inputs=[
                io.String.Input(
                    "string1",
                    default="",
                    force_input=True,
                    tooltip="First string.",
                ),
                io.String.Input(
                    "string2",
                    default="",
                    force_input=True,
                    tooltip="String to append.",
                ),
                io.Boolean.Input(
                    "comma",
                    default=True,
                    tooltip="Add comma between strings.",
                ),
                io.Boolean.Input(
                    "dedupe",
                    default=True,
                    tooltip=(
                        "Prevents appending tokens from string2 if they "
                        "already exist in string1."
                    ),
                ),
            ],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(
        cls,
        string1: str,
        string2: str,
        comma: bool,
        dedupe: bool,
    ) -> io.NodeOutput:
        append_string = string2
        if dedupe and string1 and string2:
            existing = {
                token.strip() for token in string1.split(",") if token.strip()
            }
            append_string = ",".join(
                token
                for token in string2.split(",")
                if token.strip() not in existing
            )

        if not append_string.strip(" ,"):
            return io.NodeOutput(string1)

        first = string1.rstrip(" ,")
        second = append_string.lstrip(" ,")
        if not first:
            return io.NodeOutput(second)
        if not second:
            return io.NodeOutput(string1)
        separator = ", " if comma else " "
        return io.NodeOutput(f"{first}{separator}{second}")


NODE_CLASS_MAPPINGS = {
    "CLIPTextEncodeFormatter": CLIPTextEncodeFormatter,
    "TextOnlyFormatter": TextOnlyFormatter,
    "TextAppendFormatter": TextAppendFormatter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CLIPTextEncodeFormatter": "CLIP Text Encode (Prompt Formatter)",
    "TextOnlyFormatter": "Prompt Formatter (Only Text)",
    "TextAppendFormatter": "Append String",
}
