"""Secure V2 implementation of DebugNode-ComfyUI.

The node formats inert values locally.  Live ComfyUI values stay opaque and
cross the boundary only through the host's bounded ``Ref.describe`` projection.
"""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk


_MAX_ITEMS = 100
_MAX_VALUE_CHARS = 32768
_MAX_DEPTH = 32
_PLAIN_SCALARS = {type(None), bool, int, float, str, bytes}
_PLAIN_CONTAINERS = {list, tuple, dict}


def _append(parts: list[str], text: str, remaining: list[int]) -> bool:
    """Append at most the remaining character budget."""
    if remaining[0] <= 0:
        return False
    if len(text) <= remaining[0]:
        parts.append(text)
        remaining[0] -= len(text)
        return True
    parts.append(text[: remaining[0]])
    remaining[0] = 0
    return False


def _append_string_literal(
    parts: list[str], value: str, remaining: list[int]
) -> bool:
    if not _append(parts, "'", remaining):
        return False
    for character in value:
        if character == "'":
            rendered = "\\'"
        elif character == "\\":
            rendered = "\\\\"
        elif character.isprintable():
            rendered = character
        else:
            rendered = ascii(character)[1:-1]
        if not _append(parts, rendered, remaining):
            return False
    return _append(parts, "'", remaining)


def _append_bytes_literal(
    parts: list[str], value: bytes, remaining: list[int]
) -> bool:
    if not _append(parts, "b'", remaining):
        return False
    for byte in value:
        if byte == 39:
            rendered = "\\'"
        elif byte == 92:
            rendered = "\\\\"
        elif 32 <= byte < 127:
            rendered = chr(byte)
        else:
            rendered = f"\\x{byte:02x}"
        if not _append(parts, rendered, remaining):
            return False
    return _append(parts, "'", remaining)


def _render_plain(
    value: Any,
    parts: list[str],
    remaining: list[int],
    *,
    depth: int = 0,
) -> bool:
    """Render exact built-in data without invoking user-defined behavior."""
    exact = type(value)
    if exact is str:
        return _append_string_literal(parts, value, remaining)
    if exact is bytes:
        return _append_bytes_literal(parts, value, remaining)
    if exact in _PLAIN_SCALARS:
        try:
            text = repr(value)
        except ValueError:
            text = f"<int bits={value.bit_length()}>"
        return _append(parts, text, remaining)
    if exact not in _PLAIN_CONTAINERS:
        return _append(parts, "<opaque value>", remaining)
    if depth >= _MAX_DEPTH:
        return _append(parts, "<depth limit>", remaining)

    if exact is dict:
        if not _append(parts, "{", remaining):
            return False
        for index, (key, item) in enumerate(value.items()):
            if index and not _append(parts, ", ", remaining):
                return False
            if type(key) is not str:
                if not _append(parts, "<opaque key>", remaining):
                    return False
            elif not _append_string_literal(parts, key, remaining):
                return False
            if not _append(parts, ": ", remaining):
                return False
            if not _render_plain(
                item, parts, remaining, depth=depth + 1
            ):
                return False
        return _append(parts, "}", remaining)

    opening, closing = ("[", "]") if exact is list else ("(", ")")
    if not _append(parts, opening, remaining):
        return False
    for index in range(len(value)):
        if index and not _append(parts, ", ", remaining):
            return False
        if not _render_plain(
            value[index], parts, remaining, depth=depth + 1
        ):
            return False
    if exact is tuple and len(value) == 1:
        if not _append(parts, ",", remaining):
            return False
    return _append(parts, closing, remaining)


def _plain_summary(value: Any) -> str:
    if type(value) is str:
        if len(value) <= _MAX_VALUE_CHARS:
            return value
        return value[: _MAX_VALUE_CHARS - 1] + "…"
    parts: list[str] = []
    remaining = [_MAX_VALUE_CHARS]
    complete = _render_plain(value, parts, remaining)
    text = "".join(parts)
    if complete:
        return text
    if len(text) >= _MAX_VALUE_CHARS:
        return text[: _MAX_VALUE_CHARS - 1] + "…"
    return text + "…"


def _plain_item(value: Any) -> dict[str, Any]:
    exact = type(value)
    if exact not in _PLAIN_SCALARS | _PLAIN_CONTAINERS:
        return {
            "type": "opaque value",
            "value": "<opaque value>",
        }

    info: dict[str, Any] = {"type": f"<class '{exact.__name__}'>"}
    if exact in {str, bytes, list, tuple, dict}:
        info["len"] = len(value)
    if exact in {bytes, list, tuple, dict}:
        if value:
            first = next(iter(value))
            info["firstIterItem"] = f"<class '{type(first).__name__}'>"
        else:
            info["firstIterItem"] = "List had no items"
    info["value"] = None if value is None else _plain_summary(value)
    return info


async def _describe_item(value: Any) -> dict[str, Any]:
    if isinstance(value, sdk.Ref):
        description = await value.describe(_MAX_VALUE_CHARS)
        info: dict[str, Any] = {
            "type": description["type"],
            "value": description["summary"],
        }
        if description["length"] is not None:
            info["len"] = description["length"]
        if description["first"] is not None:
            info["firstIterItem"] = description["first"]
        if description["shape"] is not None:
            info["shape"] = _plain_summary(description["shape"])
        return info
    return _plain_item(value)


class WTFDebugNode(io.ComfyNode):
    """What's That Field? Show bounded, non-behavioral diagnostics."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect",)
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WTFDebugNode",
            display_name="🐜 WTF?",
            category="debug",
            description=(
                "Displays bounded type, size, shape, first-item, and value "
                "diagnostics without materializing live ComfyUI objects."
            ),
            inputs=[io.AnyType.Input("anything")],
            outputs=[],
            is_input_list=True,
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, anything: Any = None) -> io.NodeOutput:
        if type(anything) in {list, tuple}:
            values = anything
        elif anything is None:
            values = ()
        else:
            values = (anything,)
        items = []
        for index in range(min(len(values), _MAX_ITEMS)):
            items.append(await _describe_item(values[index]))
        return io.NodeOutput(ui={"items": items})


NODE_CLASS_MAPPINGS = {"WTFDebugNode": WTFDebugNode}
NODE_DISPLAY_NAME_MAPPINGS = {"WTFDebugNode": "🐜 WTF?"}

__all__ = [
    "WTFDebugNode",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
