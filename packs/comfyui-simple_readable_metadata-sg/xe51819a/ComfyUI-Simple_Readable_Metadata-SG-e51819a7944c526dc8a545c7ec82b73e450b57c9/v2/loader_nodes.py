"""Pinned algorithms; brokered inputs and bounded owned numerical buffers."""
from comfy_api.latest import io, sdk
from .image_algorithms import ImageAlgorithms
from .max_algorithms import MaxAlgorithms
from .video_transport import analyze_video, ENCODED_MAX
from .limits import image_work, logical_label, text, container_work, ENCODED_IMAGE_BYTES
from .sampling_names import SAMPLERS, SCHEDULERS


def file_input(name, *, video=False):
    return io.Combo.Input(name, options=[], upload=io.UploadType.video if video else io.UploadType.image,
        remote=io.RemoteOptions("/secure-nodes/assets/input?kind=file", refresh_button=True,
            initial_selection="first"))


async def read_input(label, maximum):
    logical_label(label)
    asset = await sdk.ctx().assets.resolve("input", label)
    size = await sdk.ctx().assets.size(asset)
    if size > maximum:
        raise ValueError("encoded managed-input workload exceeded")
    # Read a bounded snapshot, never a whole mutable file. The tail detects
    # growth beyond our profile without importing an oversized buffer.
    data = await sdk.ctx().assets.read_range(asset, 0, maximum)
    tail = await sdk.ctx().assets.read_range(asset, maximum, 1)
    after = await sdk.ctx().assets.size(asset)
    if tail or len(data) != size or after != size or len(data) > maximum:
        raise ValueError("managed-input size changed or workload exceeded")
    return data


def output_result(value):
    for item in value["result"]:
        if isinstance(item, str):
            text(item)
    container_work(value["ui"])
    return io.NodeOutput(*value["result"], ui=value["ui"])


class SimpleReadableMetadataSG(io.ComfyNode):
    SDK_PERMISSIONS = ("assets", "raw")
    FUNCTION = "execute"

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=cls.__name__, display_name="Simple Readable Metadata-SG",
            category="image/analysis", is_output_node=True,
            inputs=[file_input("image"), io.Boolean.Input("emoji_in_readable_text", default=True),
                    io.Combo.Input("show_info", options=["both", "properties", "metadata", "none"], default="both")],
            outputs=[io.String.Output("Simple_Readable_Metadata"), io.Image.Output("image"),
                io.Mask.Output("mask"), io.String.Output("metadata_raw"), io.String.Output("Positive_Prompt"),
                io.String.Output("Negative_Prompt"), io.Int.Output("seed"), io.String.Output("file_name_text")])

    @classmethod
    async def fingerprint_inputs(cls, image, **kwargs):
        logical_label(image)
        asset = await sdk.ctx().assets.resolve("input", image)
        return await sdk.ctx().assets.digest(asset, "sha256")

    @classmethod
    async def execute(cls, image, emoji_in_readable_text=True, show_info="both"):
        if show_info not in ("both", "properties", "metadata", "none"):
            raise ValueError("declared display option required")
        data = await read_input(image, ENCODED_IMAGE_BYTES)
        image_work(data)
        helper = ImageAlgorithms()
        helper.input_label, helper.source_bytes = image, data
        return output_result(helper.load_analyze_extract(image,
            emoji_in_readable_text=emoji_in_readable_text, show_info=show_info))


class SimpleReadableMetadataMAXSG(SimpleReadableMetadataSG):
    # Existing public sampling_names is permissioned under models.
    SDK_PERMISSIONS = ("assets", "raw", "models")
    @classmethod
    async def fingerprint_inputs(cls, image, **kwargs):
        return await super().fingerprint_inputs(image, **kwargs)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=cls.__name__, display_name="Simple Readable Metadata MAX-SG",
            category="image/analysis", is_output_node=True,
            inputs=[file_input("image"), io.Combo.Input("show_info", options=["on", "off"]),
                    io.Boolean.Input("emoji_in_readable_text", default=True)],
            outputs=[io.String.Output("Simple_Readable_Metadata"), io.Image.Output("image"),
                io.Mask.Output("mask"), io.Int.Output("width"), io.Int.Output("height"),
                io.Float.Output("width_ratio"), io.Float.Output("height_ratio"), io.Float.Output("Resolution_in_MP"),
                io.String.Output("metadata_raw"), io.String.Output("Positive_Prompt"), io.String.Output("Negative_Prompt"),
                io.Int.Output("seed"), io.Int.Output("steps"), io.Float.Output("cfg_scale"),
                io.Combo.Output("sampler", options=SAMPLERS), io.Combo.Output("scheduler", options=SCHEDULERS),
                io.String.Output("file_name_text")])

    @classmethod
    async def execute(cls, image, show_info="on", emoji_in_readable_text=True):
        if show_info not in ("on", "off"):
            raise ValueError("declared display option required")
        names = await sdk.ctx().models.sampling_names()
        if names.get("samplers") != SAMPLERS or names.get("schedulers") != SCHEDULERS:
            raise ValueError("canonical sampling names drifted outside tested local schema")
        data = await read_input(image, ENCODED_IMAGE_BYTES)
        image_work(data)
        helper = MaxAlgorithms()
        helper.input_label, helper.source_bytes = image, data
        helper.sampler_names, helper.scheduler_names = names["samplers"], names["schedulers"]
        return output_result(helper.load_analyze_extract(image, show_info=show_info,
            emoji_in_readable_text=emoji_in_readable_text))


class SimpleReadableMetadataVideoSG(io.ComfyNode):
    SDK_PERMISSIONS = ("assets", "raw")
    FUNCTION = "execute"

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=cls.__name__, display_name="Simple Readable Metadata (VIDEO)-SG",
            category="image/video", is_output_node=True,
            inputs=[file_input("video", video=True),
                io.Int.Input("force_rate", default=0, min=0, max=60, step=1, display_mode=io.NumberDisplay.number,
                    tooltip="Target FPS. 0 = Original."),
                io.Int.Input("max_frames", default=0, min=0, max=10000, step=1, display_mode=io.NumberDisplay.number,
                    tooltip="Limit total frames. 0 = All."),
                io.Int.Input("resize_long_edge", default=0, min=0, max=4096, step=64, display_mode=io.NumberDisplay.number,
                    tooltip="Resize longest side. 0 = Original."),
                io.Boolean.Input("emoji_in_readable_text", default=True)],
            outputs=[io.String.Output("Simple_Readable_Metadata"), io.Image.Output("frames"),
                io.Mask.Output("mask"), io.Int.Output("frame_count"), io.Int.Output("fps"),
                io.String.Output("filename_text"), io.String.Output("metadata_raw"), io.String.Output("Positive_Prompt"),
                io.String.Output("Negative_Prompt"), io.Int.Output("seed")])

    @classmethod
    async def fingerprint_inputs(cls, video, force_rate=0, max_frames=0, resize_long_edge=0, **kwargs):
        logical_label(video)
        asset = await sdk.ctx().assets.resolve("input", video)
        # Content revision rather than host mtime identity.
        return (await sdk.ctx().assets.digest(asset, "sha256"), force_rate, max_frames, resize_long_edge)

    @classmethod
    async def execute(cls, video, force_rate=0, max_frames=0, resize_long_edge=0, emoji_in_readable_text=True):
        data = await read_input(video, ENCODED_MAX)
        return output_result(analyze_video(data, video, force_rate, max_frames,
            resize_long_edge, emoji_in_readable_text))
