"""Secure Nodes V2 implementation of Visual Area Prompt."""

from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk

from ._secure_area import (
    add_area_nodes,
    add_combine_chain,
    add_concat_chain,
    graph_link,
    ordered_conditionings,
    workflow_areas,
)


class VisualAreaPrompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = (
        "graph.expand",
        "graph.expand.external:ConditioningCombine",
        "graph.expand.external:ConditioningConcat",
        "graph.expand.external:ConditioningSetAreaPercentage",
    )

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VisualAreaPrompt",
            display_name="Visual Area Prompt",
            category="RegionalPrompt",
            accept_all_inputs=True,
            enable_expand=True,
            inputs=[
                io.Int.Input(
                    "image_width", default=1024, min=16, max=16384,
                    tooltip="The width of the canvas. (only affects looks).",
                ),
                io.Int.Input(
                    "image_height", default=1024, min=16, max=16384,
                    tooltip="The height of the canvas. (only affects looks).",
                ),
            ],
            outputs=[
                io.Conditioning.Output(
                    "area_conditioning", display_name="area_conditioning",
                    tooltip="Area conditioning",
                ),
                io.Conditioning.Output(
                    "combined_conditioning", display_name="combined_conditioning",
                    tooltip="Combined conditioning",
                ),
            ],
            hidden=[io.Hidden.extra_pnginfo, io.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls,
        image_width: int,
        image_height: int,
        extra_pnginfo: Any,
        unique_id: str,
        **dynamic_inputs: Any,
    ) -> dict[str, Any]:
        del image_width, image_height
        conditionings = ordered_conditionings(dynamic_inputs)
        areas = workflow_areas(extra_pnginfo, unique_id, len(conditionings))
        nodes: list[dict[str, Any]] = []
        concatenated = add_concat_chain(nodes, conditionings, "concat")
        area_links = add_area_nodes(nodes, conditionings, areas)
        combined_areas = add_combine_chain(nodes, area_links, "combine")
        nodes.append({
            "id": "output",
            "class_type": "ConditioningCombine",
            "inputs": {
                "conditioning_1": combined_areas,
                "conditioning_2": concatenated,
            },
        })
        return await sdk.ctx().graph.expand_nodes(
            nodes, [graph_link("output"), concatenated],
        )
