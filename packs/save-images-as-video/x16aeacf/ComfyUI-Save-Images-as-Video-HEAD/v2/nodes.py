"""Secure Nodes V2 implementation of the three San4itos video nodes."""

from __future__ import annotations

import shlex

from comfy_api.latest import io, sdk


VIDEO_CODECS = ["libx264", "libx265", "libvpx-vp9", "libsvtav1"]
TRANSCODE_CODECS = [*VIDEO_CODECS, "copy"]
PIXEL_FORMATS = [
    "yuv420p",
    "yuv422p",
    "yuv444p",
    "yuv420p10le",
    "yuv422p10le",
    "yuv444p10le",
    "rgb24",
]
TRANSCODE_PIXEL_FORMATS = [
    "yuv420p",
    "yuv422p",
    "yuv444p",
    "yuv420p10le",
    "yuv422p10le",
    "rgb24",
    "copy",
]
OUTPUT_FORMATS = ["mp4", "webm", "mov", "avi", "mkv"]
AUDIO_CODECS = ["aac", "mp3", "libopus", "copy"]
TRANSCODE_AUDIO_CODECS = ["aac", "mp3", "libopus"]
AUDIO_BITRATES = ["96k", "128k", "160k", "192k", "256k", "320k"]
CODEC_NAMES = {
    "libx264": "h264",
    "libx265": "hevc",
    "libvpx-vp9": "vp9",
    "libsvtav1": "av1",
    "copy": "copy",
}


def _preset_options(value: str, codec: str) -> dict[str, str]:
    """Translate the legacy text box without exposing arbitrary FFmpeg args."""
    tokens = shlex.split(str(value or ""))
    if not tokens:
        return {}
    if len(tokens) != 2 or tokens[0] != "-preset":
        raise ValueError(
            "Secure mode accepts only '-preset <name>' in output_file_opt; "
            "arbitrary FFmpeg arguments are intentionally unavailable."
        )
    if codec not in {"libx264", "libx265"}:
        return {}
    return {"preset": tokens[1]}


def _audio_bitrate(value: str) -> int:
    text = str(value).lower()
    if not text.endswith("k") or not text[:-1].isdigit():
        raise ValueError("audio bitrate must be one of the declared kbps choices")
    return int(text[:-1])


def _video_ui(ui_value: dict) -> dict:
    """Keep the legacy `videos` preview key while retaining V2 metadata."""
    value = dict(ui_value)
    if "images" in value and "videos" not in value:
        value["videos"] = list(value["images"])
    return value


class SaveFramesToVideoFFmpeg(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("output",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveFramesToVideoFFmpeg_san4itos",
            display_name="Save Images to Video (FFmpeg)",
            category="San4itos",
            description=(
                "Encodes an image batch with the managed server media service. "
                "Secure nodes never receive an FFmpeg executable or output path."
            ),
            inputs=[
                io.Image.Input("images"),
                io.String.Input("filename_prefix", default="VID"),
                io.Float.Input("fps", default=24.0, min=1.0, max=120.0, step=1.0),
                io.Combo.Input("codec", options=VIDEO_CODECS, default="libx264"),
                io.Combo.Input(
                    "pixel_format", options=PIXEL_FORMATS, default="yuv420p"
                ),
                io.Int.Input("crf", default=23, min=0, max=63, step=1),
                io.Combo.Input("output_format", options=OUTPUT_FORMATS, default="mp4"),
                io.Audio.Input("audio", optional=True),
                io.Combo.Input(
                    "audio_codec", options=AUDIO_CODECS, default="aac", optional=True
                ),
                io.Combo.Input(
                    "audio_bitrate",
                    options=AUDIO_BITRATES,
                    default="192k",
                    optional=True,
                ),
                io.String.Input(
                    "output_file_opt",
                    default="-preset medium",
                    multiline=True,
                    optional=True,
                    tooltip="Secure mode accepts the bounded '-preset <name>' option.",
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        images,
        filename_prefix,
        fps,
        codec,
        pixel_format,
        crf,
        output_format,
        audio=None,
        audio_codec="aac",
        audio_bitrate="192k",
        output_file_opt="-preset medium",
    ) -> io.NodeOutput:
        options = {
            "pixel_format": pixel_format,
            "crf": int(crf),
            **_preset_options(output_file_opt, codec),
        }
        ui_value = await sdk.ctx().output.save_video(
            images,
            audio=audio,
            fps=float(fps),
            filename_prefix=filename_prefix,
            format=output_format,
            codec=CODEC_NAMES[codec],
            encoder_options=options,
            audio_codec="auto" if audio_codec == "copy" else audio_codec,
            audio_bitrate_kbps=_audio_bitrate(audio_bitrate),
        )
        return io.NodeOutput(ui=_video_ui(ui_value))


class LoadVideoByPathSan4itos(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoadVideoByPath_san4itos",
            display_name="Load Video by Path",
            category="San4itos",
            description=(
                "Loads an uploaded video by logical input name. Host filesystem "
                "paths are never exposed to the node."
            ),
            inputs=[
                io.Combo.Input(
                    "video_file",
                    options=[],
                    default="",
                    remote=io.RemoteOptions(
                        route="/secure-nodes/assets/input?kind=video",
                        refresh_button=True,
                    ),
                ),
            ],
            outputs=[io.Video.Output()],
        )

    @classmethod
    async def execute(cls, video_file) -> io.NodeOutput:
        asset = await sdk.ctx().assets.resolve("input", video_file)
        video = await sdk.ctx().assets.load_video(asset)
        return io.NodeOutput(video)


class ConvertVideoFFmpeg(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("output",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConvertVideoFFmpeg_san4itos",
            display_name="Convert Video (FFmpeg)",
            category="San4itos",
            description="Transcodes an opaque video with the managed server media service.",
            inputs=[
                io.Video.Input("video"),
                io.String.Input("filename_prefix", default="VID_conv"),
                io.Combo.Input("codec", options=TRANSCODE_CODECS, default="libx264"),
                io.Combo.Input(
                    "pixel_format", options=TRANSCODE_PIXEL_FORMATS, default="yuv420p"
                ),
                io.Int.Input("crf", default=23, min=0, max=63, step=1),
                io.Combo.Input("output_format", options=OUTPUT_FORMATS, default="mp4"),
                io.Combo.Input(
                    "audio_handling",
                    options=["copy original", "replace with new", "remove audio"],
                    default="copy original",
                ),
                io.Audio.Input("audio", optional=True),
                io.Combo.Input(
                    "audio_codec",
                    options=TRANSCODE_AUDIO_CODECS,
                    default="aac",
                    optional=True,
                ),
                io.Combo.Input(
                    "audio_bitrate",
                    options=AUDIO_BITRATES,
                    default="192k",
                    optional=True,
                ),
                io.String.Input(
                    "output_file_opt",
                    default="-preset medium",
                    multiline=True,
                    optional=True,
                    tooltip="Secure mode accepts the bounded '-preset <name>' option.",
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        video,
        filename_prefix,
        codec,
        pixel_format,
        crf,
        output_format,
        audio_handling,
        audio=None,
        audio_codec="aac",
        audio_bitrate="192k",
        output_file_opt="-preset medium",
    ) -> io.NodeOutput:
        options = {}
        if codec != "copy":
            if pixel_format == "copy":
                raise ValueError("pixel_format='copy' requires codec='copy'")
            options.update({"pixel_format": pixel_format, "crf": int(crf)})
            options.update(_preset_options(output_file_opt, codec))
        elif pixel_format != "copy":
            raise ValueError("codec='copy' requires pixel_format='copy'")

        audio_modes = {
            "copy original": "source",
            "replace with new": "replace",
            "remove audio": "remove",
        }
        ui_value = await sdk.ctx().output.transcode_video(
            video,
            audio=audio,
            filename_prefix=filename_prefix,
            format=output_format,
            codec=CODEC_NAMES[codec],
            encoder_options=options,
            audio_mode=audio_modes[audio_handling],
            audio_codec=audio_codec,
            audio_bitrate_kbps=_audio_bitrate(audio_bitrate),
        )
        return io.NodeOutput(ui=_video_ui(ui_value))


NODE_CLASS_MAPPINGS = {
    "SaveFramesToVideoFFmpeg_san4itos": SaveFramesToVideoFFmpeg,
    "ConvertVideoFFmpeg_san4itos": ConvertVideoFFmpeg,
    "LoadVideoByPath_san4itos": LoadVideoByPathSan4itos,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveFramesToVideoFFmpeg_san4itos": "Save Images to Video (FFmpeg)",
    "ConvertVideoFFmpeg_san4itos": "Convert Video (FFmpeg)",
    "LoadVideoByPath_san4itos": "Load Video by Path",
}
