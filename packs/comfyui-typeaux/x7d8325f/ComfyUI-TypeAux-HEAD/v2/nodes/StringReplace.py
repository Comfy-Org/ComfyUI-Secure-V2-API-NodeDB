"""Bounded native Python replacement; regex CPU deadline is host-enforced."""
import re
from comfy_api.latest import io

MAX_TEXT_BYTES = 65_536
MAX_PATTERN_BYTES = 8_192
MAX_REPLACEMENT_BYTES = 1_024
MAX_OUTPUT_BYTES = 131_072


def _size(value, name, limit):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    size = len(value.encode("utf-8"))
    if size > limit:
        raise ValueError(f"{name} exceeds the {limit}-byte UTF-8 limit")
    return size


def _regex_replace(text, match, value):
    pattern = re.compile(match, re.DOTALL)
    # Validate native replacement templates even when text has no matches.
    pattern.sub(value, "", count=1)
    emitted = 0
    cursor = 0

    def replacement(found):
        nonlocal emitted, cursor
        expanded = found.expand(value)
        emitted += len(text[cursor:found.start()].encode("utf-8"))
        emitted += len(expanded.encode("utf-8"))
        if emitted > MAX_OUTPUT_BYTES:
            raise ValueError("replacement output exceeds the 128 KiB UTF-8 limit")
        cursor = found.end()
        return expanded

    # Native zero-width ordering, flags and numeric/named backreferences.
    # No whitelist, alternate engine, thread timeout or private parser.
    result = pattern.sub(replacement, text)
    if emitted + len(text[cursor:].encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("replacement output exceeds the 128 KiB UTF-8 limit")
    return result


class StringReplace(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="StringReplaceFunction", category="ComfyUI-TypeAux",
            inputs=[
                io.String.Input("text", default="", multiline=True,
                                extra_dict={"defaultInput": True}),
                io.String.Input("match", default=r"\<think\>.*\<\/think\>\n+",
                                multiline=True, extra_dict={"defaultInput": False}),
                io.String.Input("value", default="", multiline=True,
                                dynamic_prompts=True, extra_dict={"defaultInput": False}),
                io.Combo.Input("match_type", options=["text", "regex"], default="regex"),
            ], outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, text, match, value, match_type):
        text_size = _size(text, "text", MAX_TEXT_BYTES)
        match_size = _size(match, "match", MAX_PATTERN_BYTES)
        value_size = _size(value, "value", MAX_REPLACEMENT_BYTES)
        if match_type == "regex":
            result = _regex_replace(text, match, value)
        elif match_type == "text":
            # Preflight literal growth, including empty-search len(text)+1.
            result_size = text_size + text.count(match) * (value_size - match_size)
            if result_size > MAX_OUTPUT_BYTES:
                raise ValueError("replacement output exceeds the 128 KiB UTF-8 limit")
            result = text.replace(match, value)
        else:
            raise ValueError("match_type must be text or regex")
        return io.NodeOutput(result)
