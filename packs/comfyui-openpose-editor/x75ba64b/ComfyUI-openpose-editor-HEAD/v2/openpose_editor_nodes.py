"""Secure JSON loader for the OpenPose Editor pack."""
from __future__ import annotations

import json

from comfy_api.latest import io


POSE_KEYPOINT = io.Custom("POSE_KEYPOINT")


class LoadOpenposeJSONNode(io.ComfyNode):
    """Parse the editor's JSON text into the pack's POSE_KEYPOINT value."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="huchenlei.LoadOpenposeJSON",
            display_name="Load Openpose JSON",
            category="openpose",
            inputs=[io.String.Input("json_str", multiline=True)],
            outputs=[POSE_KEYPOINT.Output(display_name="POSE_KEYPOINT")],
        )

    @classmethod
    async def execute(cls, json_str: str) -> io.NodeOutput:
        return io.NodeOutput(json.loads(json_str))


__all__ = ["LoadOpenposeJSONNode", "POSE_KEYPOINT"]
