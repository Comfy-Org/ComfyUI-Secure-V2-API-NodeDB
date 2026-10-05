"""Scalar-only implementation for the declarative ``capitanZiT`` scheduler."""

from __future__ import annotations


def provide(projection, steps: int, config: dict) -> list[float]:
    if projection is not None:
        raise ValueError("capitanZiT does not accept a model projection")
    if config != {}:
        raise ValueError("capitanZiT does not accept scheduler configuration")
    if isinstance(steps, bool) or not isinstance(steps, int):
        raise TypeError("steps must be an integer")
    if not 1 <= steps <= 100:
        raise ValueError("steps must be between 1 and 100")
    return [1.0 - index / steps for index in range(steps + 1)]
