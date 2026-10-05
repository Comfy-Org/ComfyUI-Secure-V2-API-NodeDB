"""Authority-free Secure Nodes V2 backend for SimpleCounter."""

from __future__ import annotations

from typing import Any

from comfy_api.latest import io


def _always_changed(cls: type, **_kwargs: Any) -> float:
    del cls
    return float("nan")


def _nonnegative_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


class SimpleCounter(io.ComfyNode):
    """Return the frontend-supplied counter value."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Simple Counter",
            display_name="Simple Counter",
            category="utils",
            not_idempotent=True,
            inputs=[
                io.Int.Input("start", default=0, min=0, step=1),
                io.Int.Input("count", default=0, min=0, step=1),
            ],
            outputs=[io.Int.Output("index")],
        )

    @classmethod
    def execute(cls, start: int, count: int) -> io.NodeOutput:
        _nonnegative_integer(start, "start")
        return io.NodeOutput(_nonnegative_integer(count, "count"))


NODE_CLASS_MAPPINGS = {"Simple Counter": SimpleCounter}
