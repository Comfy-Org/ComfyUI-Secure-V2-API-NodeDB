"""Bounded graph-building helpers shared by the Visual Area nodes."""

from __future__ import annotations

import math
import re
from typing import Any

from comfy_api.latest import sdk


_AREA_INPUT = re.compile(r"area_conditioning_(\d+)")
_MAX_AREAS = 64


def graph_link(node: str, output: int = 0) -> dict[str, Any]:
    return {"node": node, "output": output}


def ordered_conditionings(values: dict[str, Any]) -> list[sdk.CondRef]:
    indexed: list[tuple[int, sdk.CondRef]] = []
    for name, value in values.items():
        match = _AREA_INPUT.fullmatch(name)
        if match is None:
            raise ValueError(f"unsupported dynamic input {name!r}")
        if not isinstance(value, sdk.CondRef):
            raise TypeError(f"{name} must be a CONDITIONING reference")
        indexed.append((int(match.group(1)), value))
    indexed.sort(key=lambda item: item[0])
    if not indexed:
        raise ValueError("at least one area conditioning must be connected")
    if len(indexed) > _MAX_AREAS:
        raise ValueError(f"at most {_MAX_AREAS} area conditionings are supported")
    if [index for index, _ in indexed] != list(range(len(indexed))):
        raise ValueError("area conditioning inputs must be contiguous from zero")
    return [value for _, value in indexed]


def workflow_areas(
    extra_pnginfo: Any,
    unique_id: str,
    count: int,
) -> list[tuple[float, float, float, float, float]]:
    if not isinstance(extra_pnginfo, dict):
        raise ValueError("workflow metadata is required for visual areas")
    workflow = extra_pnginfo.get("workflow")
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("workflow metadata has no node list")
    node_data = next(
        (
            node for node in workflow["nodes"]
            if isinstance(node, dict) and str(node.get("id")) == str(unique_id)
        ),
        None,
    )
    if node_data is None:
        raise ValueError("current node is missing from workflow metadata")
    properties = node_data.get("properties")
    raw_areas = properties.get("area_values") if isinstance(properties, dict) else None
    if not isinstance(raw_areas, list) or len(raw_areas) != count:
        raise ValueError("area values must match the connected conditionings")

    result: list[tuple[float, float, float, float, float]] = []
    for index, raw in enumerate(raw_areas):
        if not isinstance(raw, (list, tuple)) or len(raw) != 5:
            raise ValueError(f"area {index} must contain five numbers")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw):
            raise TypeError(f"area {index} contains a non-numeric value")
        area = tuple(float(value) for value in raw)
        if not all(math.isfinite(value) for value in area):
            raise ValueError(f"area {index} contains a non-finite value")
        x, y, width, height, strength = area
        if not (
            0.0 <= x <= 1.0
            and 0.0 <= y <= 1.0
            and 0.0 <= width <= 1.0
            and 0.0 <= height <= 1.0
            and 0.0 <= strength <= 10.0
        ):
            raise ValueError(f"area {index} is outside the supported range")
        result.append((x, y, width, height, strength))
    return result


def add_concat_chain(
    nodes: list[dict[str, Any]], values: list[Any], prefix: str,
) -> Any:
    current: Any = values[0]
    for index, value in enumerate(values[1:], start=1):
        node_id = f"{prefix}_{index}"
        nodes.append({
            "id": node_id,
            "class_type": "ConditioningConcat",
            "inputs": {"conditioning_to": current, "conditioning_from": value},
        })
        current = graph_link(node_id)
    return current

def add_area_nodes(
    nodes: list[dict[str, Any]],
    conditionings: list[Any],
    areas: list[tuple[float, float, float, float, float]],
    prefix: str = "area",
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for index, (conditioning, area) in enumerate(zip(conditionings, areas, strict=True)):
        x, y, width, height, strength = area
        node_id = f"{prefix}_{index}"
        nodes.append({
            "id": node_id,
            "class_type": "ConditioningSetAreaPercentage",
            "inputs": {
                "conditioning": conditioning,
                "width": width,
                "height": height,
                "x": x,
                "y": y,
                "strength": strength,
            },
        })
        links.append(graph_link(node_id))
    return links


def add_combine_chain(
    nodes: list[dict[str, Any]], values: list[Any], prefix: str,
) -> Any:
    current: Any = values[0]
    for index, value in enumerate(values[1:], start=1):
        node_id = f"{prefix}_{index}"
        nodes.append({
            "id": node_id,
            "class_type": "ConditioningCombine",
            "inputs": {"conditioning_1": current, "conditioning_2": value},
        })
        current = graph_link(node_id)
    return current
