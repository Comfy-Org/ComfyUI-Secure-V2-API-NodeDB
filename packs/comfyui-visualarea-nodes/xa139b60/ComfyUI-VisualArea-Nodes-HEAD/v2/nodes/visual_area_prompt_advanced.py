"""Secure Nodes V2 implementation of Visual Area Prompt Advanced."""

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


class VisualAreaPromptAdvanced(io.ComfyNode):
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
            node_id="VisualAreaPromptAdvanced",
            display_name='Visual Area Prompt "Advanced"',
            category="RegionalPrompt",
            accept_all_inputs=True,
            enable_expand=True,
            inputs=[
                io.Conditioning.Input(
                    "all_area_conditioning",
                    tooltip=(
                        "Base conditioning. Will be concatenated to all other "
                        "conditionings, including global."
                    ),
                ),
                io.Conditioning.Input(
                    "global_conditioning",
                    tooltip="Will be applied to the whole image once.",
                ),
                io.Boolean.Input(
                    "merge_global", default=False,
                    tooltip=(
                        "Turning this on will make it so that the global "
                        "conditioning will be concatenated to all other "
                        "conditionings before being applied. (will not affect "
                        "combined_conditioning output)."
                    ),
                ),
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
        all_area_conditioning: sdk.CondRef,
        global_conditioning: sdk.CondRef,
        merge_global: bool,
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
        concatenated = add_concat_chain(
            nodes,
            [all_area_conditioning, *conditionings, global_conditioning],
            "all_concat",
        )
        conditioned = []
        for index, conditioning in enumerate(conditionings):
            node_id = f"base_concat_{index}"
            nodes.append({
                "id": node_id,
                "class_type": "ConditioningConcat",
                "inputs": {
                    "conditioning_to": all_area_conditioning,
                    "conditioning_from": conditioning,
                },
            })
            conditioned.append(graph_link(node_id))
        area_links = add_area_nodes(nodes, conditioned, areas)
        combined_areas = add_combine_chain(nodes, area_links, "combine")
        nodes.append({
            "id": "output",
            "class_type": "ConditioningCombine",
            "inputs": {
                "conditioning_1": combined_areas,
                "conditioning_2": concatenated if merge_global else global_conditioning,
            },
        })
        return await sdk.ctx().graph.expand_nodes(
            nodes, [graph_link("output"), concatenated],
        )
