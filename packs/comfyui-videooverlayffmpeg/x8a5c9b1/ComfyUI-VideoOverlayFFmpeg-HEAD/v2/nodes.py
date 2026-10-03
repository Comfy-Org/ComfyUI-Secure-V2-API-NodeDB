"""Secure Nodes V2 conversion of VideoOverlayFFmpeg.

The two compositor nodes deliberately describe their work to a bounded host
media service.  They never receive host paths, an FFmpeg executable, or a raw
filter expression.  The service call is the one remaining shared API gap; the
alignment conversion nodes are entirely pack-side and executable today.
"""

from __future__ import annotations

import json
from typing import Any

from comfy_api.latest import io, sdk

Alignment = io.Custom("whisper_alignment")

POSITIONS = ["right_bottom", "right_top", "left_bottom", "left_top", "center"]
SUBTITLE_POSITIONS = [
    "bottom_center",
    "top_center",
    "bottom_left",
    "bottom_right",
    "center",
    "custom",
]
FONTS = [
    "AlumniSansCollegiateOne-Regular.ttf",
    "Caveat-VariableFont_wght.ttf",
    "Chanakya Regular.ttf",
    "NotoSansArabic-Regular.ttf",
    "Oswald-Bold.ttf",
    "PixelifySans-Bold.ttf",
    "QianTuBiFengShouXieTi-2.ttf",
    "Quicksand-Bold.ttf",
    "Roboto-Bold.ttf",
    "Roboto-Regular copy.ttf",
    "Roboto-Regular.ttf",
    "YRDZST Semibold.ttf",
    "YoungSerif-Regular.ttf",
    "ZhanKuWenYiTi-2.ttf",
    "comic.ttf",
    "impact.ttf",
]


def _video_picker(name: str) -> io.Input:
    return io.Combo.Input(
        name,
        options=[],
        default="",
        remote=io.RemoteOptions(
            route="/secure-nodes/assets/input?kind=video",
            refresh_button=True,
        ),
        tooltip="Choose an uploaded video by logical input name.",
    )


def _common_inputs(*, subtitles: bool) -> list[io.Input]:
    inputs: list[io.Input] = [
        _video_picker("big_video_path"),
        _video_picker("small_video_path"),
        _video_picker("mask_video_path"),
        io.Float.Input("opacity", default=1.0, min=0.0, max=1.0, step=0.01),
        io.Combo.Input("position", options=POSITIONS, default="right_bottom"),
        io.Int.Input("margin_x", default=0, min=0, max=500, step=1),
        io.Int.Input("margin_y", default=0, min=0, max=500, step=1),
        io.Float.Input("size_ratio", default=0.25, min=0.1, max=1.0, step=0.05),
        io.Float.Input(
            "big_video_audio_volume", default=0.0, min=0.0, max=2.0, step=0.1
        ),
        io.Float.Input(
            "small_video_audio_volume", default=1.0, min=0.0, max=2.0, step=0.1
        ),
    ]
    if subtitles:
        inputs.append(
            io.Float.Input("video_fps", default=24.0, min=1.0, max=120.0, step=1.0)
        )
    inputs.extend(
        [
            io.Float.Input("big_video_speed", default=1.8, min=0.25, max=4.0, step=0.1),
            io.Float.Input(
                "small_video_speed", default=1.0, min=0.25, max=4.0, step=0.1
            ),
        ]
    )
    if subtitles:
        inputs.extend(
            [
                Alignment.Input("alignment", optional=True),
                io.Combo.Input(
                    "font_path", options=FONTS, default=FONTS[0], optional=True
                ),
                io.Int.Input(
                    "font_size", default=48, min=12, max=200, step=1, optional=True
                ),
                io.String.Input("font_color", default="white", optional=True),
                io.Int.Input(
                    "x_position",
                    default=0,
                    min=-1000,
                    max=3000,
                    step=10,
                    optional=True,
                ),
                io.Int.Input(
                    "y_position",
                    default=0,
                    min=-1000,
                    max=3000,
                    step=10,
                    optional=True,
                ),
                io.Combo.Input(
                    "subtitle_position",
                    options=SUBTITLE_POSITIONS,
                    default="bottom_center",
                    optional=True,
                ),
                io.Int.Input(
                    "max_subtitle_width",
                    default=0,
                    min=0,
                    max=4000,
                    step=10,
                    optional=True,
                ),
                io.Float.Input(
                    "subtitle_bg_opacity",
                    default=0.7,
                    min=0.0,
                    max=1.0,
                    step=0.1,
                    optional=True,
                ),
                io.String.Input("subtitle_bg_color", default="black", optional=True),
            ]
        )
    return inputs


def _alignment(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if not {"value", "start", "end"}.issubset(item):
            continue
        result.append(
            {
                "value": str(item["value"]),
                "start": float(item["start"]),
                "end": float(item["end"]),
            }
        )
    return result


async def _load_video(name: str):
    asset = await sdk.ctx().assets.resolve("input", name)
    return await sdk.ctx().assets.load_video(asset)


async def _compose(*, subtitles: list[dict[str, Any]] | None = None, **values):
    background, overlay, mask = await __import__("asyncio").gather(
        _load_video(values.pop("big_video_path")),
        _load_video(values.pop("small_video_path")),
        _load_video(values.pop("mask_video_path")),
    )
    request = {
        "background": background,
        "overlay": overlay,
        "mask": mask,
        "position": values.pop("position"),
        "margin_x": int(values.pop("margin_x")),
        "margin_y": int(values.pop("margin_y")),
        "size_ratio": float(values.pop("size_ratio")),
        "opacity": float(values.pop("opacity")),
        "background_speed": float(values.pop("big_video_speed")),
        "overlay_speed": float(values.pop("small_video_speed")),
        "background_volume": float(values.pop("big_video_audio_volume")),
        "overlay_volume": float(values.pop("small_video_audio_volume")),
        "subtitles": subtitles or [],
        **values,
    }
    # Shared API gap: a trusted, bounded composition job analogous to
    # output.transcode_video().  No raw FFmpeg arguments or paths cross this
    # call.  The pack is ready to bind once the host method is approved.
    result = await sdk.ctx().output.compose_video(**request)  # type: ignore[attr-defined]
    ui = dict(result)
    if "images" in ui and "videos" not in ui:
        ui["videos"] = list(ui["images"])
    return io.NodeOutput(ui=ui)


class VideoOverlayNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "output")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoOverlayNode",
            display_name="Video Overlay (画中画合成)",
            category="video",
            description=(
                "Composites uploaded videos through a bounded host media job; "
                "secure nodes never receive paths or an FFmpeg process."
            ),
            inputs=_common_inputs(subtitles=False),
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, **values) -> io.NodeOutput:
        return await _compose(filename_prefix="overlay", **values)


class VideoOverlayWithSubtitlesNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "output")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoOverlayWithSubtitlesNode",
            display_name="Video Overlay with Subtitles (画中画+字幕)",
            category="video",
            description=(
                "Composites uploaded videos and bounded timed text through the "
                "managed host media service."
            ),
            inputs=_common_inputs(subtitles=True),
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        alignment=None,
        font_path=FONTS[0],
        font_size=48,
        font_color="white",
        x_position=0,
        y_position=0,
        subtitle_position="bottom_center",
        max_subtitle_width=0,
        subtitle_bg_opacity=0.7,
        subtitle_bg_color="black",
        **values,
    ) -> io.NodeOutput:
        return await _compose(
            subtitles=_alignment(alignment),
            fps=float(values.pop("video_fps")),
            font_asset=f"fonts/{font_path}",
            font_size=int(font_size),
            font_color=str(font_color),
            subtitle_position=subtitle_position,
            subtitle_x=int(x_position),
            subtitle_y=int(y_position),
            subtitle_max_width=int(max_subtitle_width),
            subtitle_background_color=str(subtitle_bg_color),
            subtitle_background_opacity=float(subtitle_bg_opacity),
            filename_prefix="overlay_subtitle",
            **values,
        )


class Alignment2StringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Alignment2StringNode",
            display_name="Alignment to String (对齐数据转字符串)",
            category="whisper",
            inputs=[Alignment.Input("alignment")],
            outputs=[io.String.Output("alignment_string")],
        )

    @classmethod
    def execute(cls, alignment) -> io.NodeOutput:
        if not isinstance(alignment, list):
            return io.NodeOutput("[]")
        return io.NodeOutput(json.dumps(alignment, ensure_ascii=False, indent=2))


class String2AlignmentNode(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="String2AlignmentNode",
            display_name="String to Alignment (字符串转对齐数据)",
            category="whisper",
            inputs=[io.String.Input("alignment_string", default="[]", multiline=True)],
            outputs=[Alignment.Output("alignment")],
        )

    @classmethod
    def execute(cls, alignment_string) -> io.NodeOutput:
        if not alignment_string or not str(alignment_string).strip():
            return io.NodeOutput([])
        try:
            value = json.loads(str(alignment_string))
        except (TypeError, ValueError, json.JSONDecodeError):
            value = []
        return io.NodeOutput(value if isinstance(value, list) else [])


NODE_CLASS_MAPPINGS = {
    "VideoOverlayNode": VideoOverlayNode,
    "VideoOverlayWithSubtitlesNode": VideoOverlayWithSubtitlesNode,
    "Alignment2StringNode": Alignment2StringNode,
    "String2AlignmentNode": String2AlignmentNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: cls.define_schema().display_name
    for node_id, cls in NODE_CLASS_MAPPINGS.items()
}
