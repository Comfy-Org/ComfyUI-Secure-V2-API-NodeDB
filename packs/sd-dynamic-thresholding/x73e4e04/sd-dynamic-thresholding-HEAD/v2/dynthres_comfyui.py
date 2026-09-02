"""Secure V2 nodes for Dynamic Thresholding.

The published V2 model transform owns the canonical host hook and clones the
MODEL.  This pack contributes only its two schemas and the closed transform
parameters.  It never receives the ModelPatcher, diffusion model, or sampler
callback object.
"""
from __future__ import annotations

from comfy_api.latest import io


MODES = [
    "Constant",
    "Linear Down",
    "Cosine Down",
    "Half Cosine Down",
    "Linear Up",
    "Cosine Up",
    "Half Cosine Up",
    "Power Up",
    "Power Down",
    "Linear Repeating",
    "Cosine Repeating",
    "Sawtooth",
]
STARTPOINTS = ["MEAN", "ZERO"]
VARIABILITIES = ["AD", "STD"]


async def _patch(
    model,
    *,
    mimic_scale: float,
    threshold_percentile: float,
    mimic_mode: str,
    mimic_scale_min: float,
    cfg_mode: str,
    cfg_scale_min: float,
    sched_val: float,
    separate_feature_channels: bool,
    scaling_startpoint: str,
    variability_measure: str,
    interpolate_phi: float,
):
    return await model.patch(
        "dynamic_thresholding",
        mimic_scale=float(mimic_scale),
        threshold_percentile=float(threshold_percentile),
        mimic_mode=str(mimic_mode),
        mimic_scale_min=float(mimic_scale_min),
        cfg_mode=str(cfg_mode),
        cfg_scale_min=float(cfg_scale_min),
        schedule_value=float(sched_val),
        separate_feature_channels=bool(separate_feature_channels),
        scaling_startpoint=str(scaling_startpoint),
        variability_measure=str(variability_measure),
        interpolate_phi=float(interpolate_phi),
    )


class DynamicThresholdingSimpleComfyNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DynamicThresholdingSimple",
            display_name="DynamicThresholdingSimple",
            category="advanced/mcmonkey",
            description=(
                "Clamp classifier-free guidance to the variability of a "
                "lower mimic scale."
            ),
            inputs=[
                io.Model.Input("model"),
                io.Float.Input(
                    "mimic_scale", default=7.0, min=0.0, max=100.0,
                    step=0.5,
                ),
                io.Float.Input(
                    "threshold_percentile", default=1.0, min=0.0, max=1.0,
                    step=0.01,
                ),
            ],
            outputs=[io.Model.Output("model")],
        )

    @classmethod
    async def execute(
        cls, model, mimic_scale: float, threshold_percentile: float,
    ) -> io.NodeOutput:
        patched = await _patch(
            model,
            mimic_scale=mimic_scale,
            threshold_percentile=threshold_percentile,
            mimic_mode="Constant",
            mimic_scale_min=0.0,
            cfg_mode="Constant",
            cfg_scale_min=0.0,
            sched_val=1.0,
            separate_feature_channels=False,
            scaling_startpoint="MEAN",
            variability_measure="AD",
            interpolate_phi=1.0,
        )
        return io.NodeOutput(patched)


class DynamicThresholdingComfyNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DynamicThresholdingFull",
            display_name="DynamicThresholdingFull",
            category="advanced/mcmonkey",
            description=(
                "Dynamic Thresholding with scheduled mimic/CFG scales and "
                "selectable variability math."
            ),
            inputs=[
                io.Model.Input("model"),
                io.Float.Input(
                    "mimic_scale", default=7.0, min=0.0, max=100.0,
                    step=0.5,
                ),
                io.Float.Input(
                    "threshold_percentile", default=1.0, min=0.0, max=1.0,
                    step=0.01,
                ),
                io.Combo.Input("mimic_mode", options=MODES),
                io.Float.Input(
                    "mimic_scale_min", default=0.0, min=0.0, max=100.0,
                    step=0.5,
                ),
                io.Combo.Input("cfg_mode", options=MODES),
                io.Float.Input(
                    "cfg_scale_min", default=0.0, min=0.0, max=100.0,
                    step=0.5,
                ),
                io.Float.Input(
                    "sched_val", default=1.0, min=0.0, max=100.0,
                    step=0.01,
                ),
                io.Combo.Input(
                    "separate_feature_channels",
                    options=["enable", "disable"],
                ),
                io.Combo.Input(
                    "scaling_startpoint", options=STARTPOINTS,
                ),
                io.Combo.Input(
                    "variability_measure", options=VARIABILITIES,
                ),
                io.Float.Input(
                    "interpolate_phi", default=1.0, min=0.0, max=1.0,
                    step=0.01,
                ),
            ],
            outputs=[io.Model.Output("model")],
        )

    @classmethod
    async def execute(
        cls,
        model,
        mimic_scale: float,
        threshold_percentile: float,
        mimic_mode: str,
        mimic_scale_min: float,
        cfg_mode: str,
        cfg_scale_min: float,
        sched_val: float,
        separate_feature_channels: str,
        scaling_startpoint: str,
        variability_measure: str,
        interpolate_phi: float,
    ) -> io.NodeOutput:
        patched = await _patch(
            model,
            mimic_scale=mimic_scale,
            threshold_percentile=threshold_percentile,
            mimic_mode=mimic_mode,
            mimic_scale_min=mimic_scale_min,
            cfg_mode=cfg_mode,
            cfg_scale_min=cfg_scale_min,
            sched_val=sched_val,
            separate_feature_channels=(
                separate_feature_channels == "enable"
            ),
            scaling_startpoint=scaling_startpoint,
            variability_measure=variability_measure,
            interpolate_phi=interpolate_phi,
        )
        return io.NodeOutput(patched)


NODE_CLASS_MAPPINGS = {
    "DynamicThresholdingSimple": DynamicThresholdingSimpleComfyNode,
    "DynamicThresholdingFull": DynamicThresholdingComfyNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DynamicThresholdingSimple": "DynamicThresholdingSimple",
    "DynamicThresholdingFull": "DynamicThresholdingFull",
}
