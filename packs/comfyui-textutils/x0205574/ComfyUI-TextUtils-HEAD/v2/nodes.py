"""Authority-free Secure Nodes V2 implementation of ComfyUI-TextUtils."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io


CATEGORY = "text utility"
MAX_TEXT_BYTES = 1_048_576
MAX_LIST_ITEMS = 10_000


def _text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError(f"{name} exceeds the {MAX_TEXT_BYTES}-byte limit")
    return value


def _texts(values: list[str]) -> list[str]:
    if not isinstance(values, list):
        raise TypeError("texts must be a list")
    if len(values) > MAX_LIST_ITEMS:
        raise ValueError(f"texts exceeds the {MAX_LIST_ITEMS}-item limit")
    return [_text(value, "texts item") for value in values]


class JoinStringsNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Text Utils - Join Strings",
            display_name="Join Strings",
            category=CATEGORY,
            inputs=[
                io.String.Input("text1", default=""),
                io.String.Input("text2", default=""),
            ],
            outputs=[io.String.Output("TEXT")],
        )

    @classmethod
    def execute(cls, text1: str, text2: str) -> io.NodeOutput:
        result = _text(text1, "text1") + _text(text2, "text2")
        _text(result, "result")
        return io.NodeOutput(result)


class SplitStringNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Text Utils - Split String to List",
            display_name="Split String to List",
            category=CATEGORY,
            inputs=[
                io.String.Input("text", default=""),
                io.String.Input("separator", default="/"),
            ],
            outputs=[io.String.Output("TEXT", is_output_list=True)],
        )

    @classmethod
    def execute(cls, text: str, separator: str) -> io.NodeOutput:
        text = _text(text, "text")
        separator = _text(separator, "separator")
        return io.NodeOutput(text.split(separator))


class JoinStringListNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Text Utils - Join String List",
            display_name="Join String List",
            category=CATEGORY,
            inputs=[
                io.String.Input("texts", force_input=True),
                io.String.Input("separator", default="/"),
            ],
            outputs=[io.String.Output("TEXT")],
            is_input_list=True,
        )

    @classmethod
    def execute(cls, texts: list[str], separator: list[str]) -> io.NodeOutput:
        texts = _texts(texts)
        if not separator:
            raise IndexError("list index out of range")
        result = _text(separator[0], "separator").join(texts)
        _text(result, "result")
        return io.NodeOutput(result)


class JoinStringListNElementNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Text Utils - Join N-Elements of String List",
            display_name="Join N-Element of String List",
            category=CATEGORY,
            inputs=[
                io.String.Input("texts", force_input=True),
                io.String.Input("separator", default="/"),
                io.Int.Input("n", default=1, min=0, max=10_000, step=1),
                io.Combo.Input("start_from", options=["front", "back"]),
            ],
            outputs=[io.String.Output("TEXT")],
            is_input_list=True,
        )

    @classmethod
    def execute(
        cls,
        texts: list[str],
        separator: list[str],
        n: list[int],
        start_from: list[str],
    ) -> io.NodeOutput:
        texts = _texts(texts)
        if not separator or not n or not start_from:
            raise IndexError("list index out of range")
        separator_value = _text(separator[0], "separator")
        count = n[0]
        direction = start_from[0]
        start = 0
        end = count
        if direction == "back":
            end = len(texts)
            start = max(0, end - count)
        result = separator_value.join(texts[start:end])
        _text(result, "result")
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {
    "Text Utils - Join Strings": JoinStringsNode,
    "Text Utils - Split String to List": SplitStringNode,
    "Text Utils - Join String List": JoinStringListNode,
    "Text Utils - Join N-Elements of String List": JoinStringListNElementNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Text Utils - Join Strings": "Join Strings",
    "Text Utils - Split String to List": "Split String to List",
    "Text Utils - Join String List": "Join String List",
    "Text Utils - Join N-Elements of String List": "Join N-Element of String List",
}


class TextUtilsExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> ComfyExtension:
    return TextUtilsExtension()
