"""Secure Nodes 2.0 implementations for mxToolkit.

The seed and slider nodes remain ordinary pack-side value selection.  The Stop
node asks the host to interrupt only the active execution through the small,
brokered execution capability; no ComfyUI internals enter the guest.
"""
from __future__ import annotations

from ._secure_runtime import bind_node, sdk


async def _seed(X: int):
    return (int(X),)


async def _slider(Xi: int, Xf: float, isfloatX: int):
    return (float(Xf) if int(isfloatX) > 0 else int(Xi),)


async def _slider_2d(
    Xi: int,
    Xf: float,
    Yi: int,
    Yf: float,
    isfloatX: int,
    isfloatY: int,
):
    x = float(Xf) if int(isfloatX) > 0 else int(Xi)
    y = float(Yf) if int(isfloatY) > 0 else int(Yi)
    return x, y


async def _stop(In):
    await sdk.ctx().execution.interrupt()
    return (In,)


NODE_CLASS_MAPPINGS = {
    "mxSeed": bind_node("mxSeed", _seed),
    "mxStop": bind_node(
        "mxStop", _stop, permissions=("execution.interrupt",)
    ),
    "mxSlider": bind_node("mxSlider", _slider),
    "mxSlider2D": bind_node("mxSlider2D", _slider_2d),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "mxSeed": "Seed",
    "mxStop": "Stop",
    "mxSlider": "Slider",
    "mxSlider2D": "Slider 2D",
}
