"""Secure Nodes V2 implementation of the pinned LumaAI pack.

The pack keeps workflow validation and reference assembly in the guest.  The
host owns the two fixed provider clients, their credentials on the wire,
bounded polling, public-media validation, downloads, and output writes.
"""
from __future__ import annotations

import posixpath
from typing import Any

from comfy_api.latest import io, sdk


LUMA_CLIENT = io.Custom("LUMACLIENT")
REFERENCE = io.Custom("REFERENCE")
CONCAT_REFERENCES = io.Custom("CONCAT_REFERENCES")
CHARACTER_REFERENCE = io.Custom("CHARACTER_REFERENCE")

VIDEO_MODELS = ["ray-flash-2", "ray-2", "ray-1.6"]
IMAGE_MODELS = ["photon-1", "photon-flash-1"]
ASPECT_RATIOS = ["9:16", "3:4", "1:1", "4:3", "16:9", "21:9"]
VIDEO_DURATIONS = ["5s", "9s"]
VIDEO_RESOLUTIONS = ["540p", "720p"]
UPSCALE_RESOLUTIONS = ["540p", "720p", "1080p", "4k"]


def _always_changed(cls, **_kwargs: Any) -> float:
    return float("NaN")


async def _materialize(value: Any) -> Any:
    if isinstance(value, sdk.ValueRef):
        return await _materialize(await value.value())
    if isinstance(value, list):
        return [await _materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await _materialize(item) for item in value])
    if isinstance(value, dict):
        return {key: await _materialize(item) for key, item in value.items()}
    return value


async def _api_key(client: Any) -> str:
    value = await _materialize(client)
    if (
        not isinstance(value, dict)
        or set(value) != {"secure_kind", "api_key"}
        or value.get("secure_kind") != "luma.client"
        or not isinstance(value.get("api_key"), str)
        or not value["api_key"]
    ):
        raise ValueError("client must be a LumaAI client descriptor")
    return value["api_key"]


def _custom_input(kind: io.Custom, name: str, *, optional: bool = False):
    return kind.Input(
        name,
        optional=optional,
        extra_dict={"forceInput": True},
    )


def _video_outputs() -> list[io.Output]:
    return [
        io.String.Output("video_url", display_name="video_url"),
        io.String.Output("generation_id", display_name="generation_id"),
    ]


def _image_outputs() -> list[io.Output]:
    return [
        io.String.Output("image_url", display_name="image_url"),
        io.String.Output("generation_id", display_name="generation_id"),
        io.Image.Output("image", display_name="image"),
    ]


def _image_filename(filename: str, generation_id: str) -> str:
    if not isinstance(filename, str):
        raise TypeError("filename must be a string")
    logical = filename.replace("\\", "/")
    logical = posixpath.splitext(logical)[0]
    if logical.endswith("/"):
        logical += generation_id
    elif not posixpath.basename(logical):
        logical = generation_id
    if not logical:
        logical = generation_id
    return logical + ".jpg"


async def _save_generated_image(
    image: sdk.ImageRef,
    filename: str,
    generation_id: str,
) -> None:
    await sdk.ctx().output.save_images(
        image,
        image_format="jpg",
        quality=95,
        filenames=[_image_filename(filename, generation_id)],
    )


class LumaAIClient(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaAIClient",
            display_name="LumaAI Client",
            category="LumaAI",
            inputs=[io.String.Input("api_key", default="")],
            outputs=[LUMA_CLIENT.Output("client", display_name="client")],
        )

    @classmethod
    async def execute(cls, api_key: str) -> io.NodeOutput:
        if not isinstance(api_key, str) or not api_key:
            # config.ini is checked in with an empty value at this pin.  V2
            # deliberately does not read process-global environment secrets.
            raise ValueError("API Key is required")
        return io.NodeOutput({"secure_kind": "luma.client", "api_key": api_key})


class ImgBBUpload(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.imgbb",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImgBBUpload",
            display_name="ImgBB Upload",
            category="image/upload",
            inputs=[
                io.Image.Input("image"),
                io.String.Input("api_key", default="", multiline=False),
                io.Boolean.Input("expire", default=False),
                io.Int.Input(
                    "expiration_time", default=60, min=60,
                    max=15_552_000, step=1,
                ),
            ],
            outputs=[io.String.Output("image_url", display_name="image_url")],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        api_key: str,
        expire: bool,
        expiration_time: int,
    ) -> io.NodeOutput:
        if not api_key:
            raise ValueError("API Key is required")
        expiration = int(expiration_time) if expire else None
        url = await sdk.ctx().integrations.call("imgbb", "upload", api_key=api_key, image=image, expiration_seconds=expiration)
        return io.NodeOutput(url)


class LumaText2Video(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma",)
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaText2Video",
            display_name="Text to Video",
            category="LumaAI/Ray",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.Combo.Input("model", options=VIDEO_MODELS),
                io.String.Input("prompt", multiline=True, default=""),
                io.Combo.Input("duration", options=VIDEO_DURATIONS),
                io.Boolean.Input("loop", default=False),
                io.Combo.Input("aspect_ratio", options=ASPECT_RATIOS),
                io.Combo.Input("resolution", options=VIDEO_RESOLUTIONS),
                io.Boolean.Input("save", default=True),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_video_outputs(),
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls, client: Any, model: str, prompt: str, duration: str,
        loop: bool, aspect_ratio: str, resolution: str, save: bool,
        filename: str = "",
    ) -> io.NodeOutput:
        if prompt == "":
            raise ValueError("Prompt is required")
        result = await sdk.ctx().integrations.call("luma", "create_video", api_key=await _api_key(client), prompt=prompt, model=model, duration=duration, loop=loop, aspect_ratio=aspect_ratio, resolution=resolution, save=save, filename=filename)
        generation_id = result["generation_id"]
        return io.NodeOutput(
            result["url"], generation_id,
            ui={"text": [generation_id]},
        )


class LumaImage2Video(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma",)
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaImage2Video",
            display_name="Image to Video",
            category="LumaAI/Ray",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.String.Input("prompt", multiline=True, default=""),
                io.Combo.Input("model", options=VIDEO_MODELS),
                io.Combo.Input("duration", options=VIDEO_DURATIONS),
                io.Boolean.Input("loop", default=False),
                io.Combo.Input("resolution", options=VIDEO_RESOLUTIONS),
                io.Boolean.Input("save", default=True),
                io.String.Input(
                    "init_image_url", default="", force_input=True,
                    optional=True,
                ),
                io.String.Input(
                    "final_image_url", default="", force_input=True,
                    optional=True,
                ),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_video_outputs(),
        )

    @classmethod
    async def execute(
        cls, client: Any, prompt: str, model: str, duration: str,
        loop: bool, resolution: str, save: bool,
        init_image_url: str = "", final_image_url: str = "",
        filename: str = "",
    ) -> io.NodeOutput:
        if not init_image_url and not final_image_url:
            raise ValueError("At least one image URL is required")
        keyframes: dict[str, dict[str, str]] = {}
        if init_image_url:
            keyframes["frame0"] = {"type": "image", "url": init_image_url}
        if final_image_url:
            keyframes["frame1"] = {"type": "image", "url": final_image_url}
        result = await sdk.ctx().integrations.call("luma", "create_video", api_key=await _api_key(client), prompt=prompt, model=model, duration=duration, loop=loop, resolution=resolution, keyframes=keyframes, save=save, filename=filename)
        generation_id = result["generation_id"]
        return io.NodeOutput(
            result["url"], generation_id,
            ui={"text": [generation_id]},
        )


class LumaInterpolateGenerations(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma",)
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaInterpolateGenerations",
            display_name="Interpolate Generations",
            category="LumaAI/Ray",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.String.Input("prompt", multiline=True, default=""),
                io.Combo.Input("model", options=VIDEO_MODELS),
                io.Combo.Input("resolution", options=VIDEO_RESOLUTIONS),
                io.Boolean.Input("save", default=True),
                io.String.Input(
                    "generation_id_1", default="", force_input=True,
                ),
                io.String.Input(
                    "generation_id_2", default="", force_input=True,
                ),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_video_outputs(),
        )

    @classmethod
    async def execute(
        cls, client: Any, prompt: str, model: str, resolution: str,
        save: bool, generation_id_1: str, generation_id_2: str,
        filename: str = "",
    ) -> io.NodeOutput:
        if not generation_id_1 or not generation_id_2:
            raise ValueError("Both generation IDs are required")
        keyframes = {
            "frame0": {"type": "generation", "id": generation_id_1},
            "frame1": {"type": "generation", "id": generation_id_2},
        }
        result = await sdk.ctx().integrations.call("luma", "create_video", api_key=await _api_key(client), prompt=prompt, model=model, resolution=resolution, keyframes=keyframes, save=save, filename=filename)
        generation_id = result["generation_id"]
        return io.NodeOutput(
            result["url"], generation_id,
            ui={"text": [generation_id]},
        )


class LumaExtendGeneration(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma",)
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaExtendGeneration",
            display_name="Extend Generation",
            category="LumaAI/Ray",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.String.Input("prompt", multiline=True, default=""),
                io.Combo.Input("model", options=VIDEO_MODELS),
                io.Boolean.Input("loop", default=False),
                io.Combo.Input("resolution", options=VIDEO_RESOLUTIONS),
                io.Boolean.Input("save", default=True),
                io.String.Input(
                    "init_image_url", default="", force_input=True,
                    optional=True,
                ),
                io.String.Input(
                    "final_image_url", default="", force_input=True,
                    optional=True,
                ),
                io.String.Input(
                    "init_generation_id", default="", force_input=True,
                    optional=True,
                ),
                io.String.Input(
                    "final_generation_id", default="", force_input=True,
                    optional=True,
                ),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_video_outputs(),
        )

    @classmethod
    async def execute(
        cls, client: Any, prompt: str, model: str, loop: bool,
        resolution: str, save: bool, init_image_url: str = "",
        final_image_url: str = "", init_generation_id: str = "",
        final_generation_id: str = "", filename: str = "",
    ) -> io.NodeOutput:
        if not init_generation_id and not final_generation_id:
            raise ValueError("You must provide at least one generation id")
        if init_image_url and init_generation_id:
            raise ValueError(
                "You cannot provide both an init image and a init generation"
            )
        if final_image_url and final_generation_id:
            raise ValueError(
                "You cannot provide both a final image and a final generation"
            )
        keyframes: dict[str, dict[str, str]] = {}
        if init_image_url:
            keyframes["frame0"] = {"type": "image", "url": init_image_url}
        if final_image_url:
            keyframes["frame1"] = {"type": "image", "url": final_image_url}
        if init_generation_id:
            keyframes["frame0"] = {
                "type": "generation", "id": init_generation_id,
            }
        if final_generation_id:
            keyframes["frame1"] = {
                "type": "generation", "id": final_generation_id,
            }
        result = await sdk.ctx().integrations.call("luma", "create_video", api_key=await _api_key(client), prompt=prompt, model=model, loop=loop, resolution=resolution, keyframes=keyframes, save=save, filename=filename)
        generation_id = result["generation_id"]
        return io.NodeOutput(
            result["url"], generation_id,
            ui={"text": [generation_id]},
        )


class Reference(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Reference",
            display_name="Reference",
            category="LumaAI/Photon",
            inputs=[
                io.String.Input("image_url", force_input=True),
                io.Float.Input(
                    "weight", default=1.0, min=0.0, max=1.0, step=0.01,
                ),
            ],
            outputs=[REFERENCE.Output("reference", display_name="reference")],
        )

    @classmethod
    async def execute(cls, image_url: str, weight: float) -> io.NodeOutput:
        return io.NodeOutput({"url": image_url, "weight": weight})


class ConcatReferences(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConcatReferences",
            display_name="ConcatReferences",
            category="LumaAI/Photon",
            inputs=[
                _custom_input(REFERENCE, f"reference_{index}", optional=True)
                for index in range(1, 5)
            ],
            outputs=[
                CONCAT_REFERENCES.Output(
                    "concat_references", display_name="concat_references",
                )
            ],
        )

    @classmethod
    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        references = []
        for index in range(1, 5):
            value = kwargs.get(f"reference_{index}")
            if value is not None:
                references.append(await _materialize(value))
        if not references:
            raise ValueError("You must provide at least one reference")
        return io.NodeOutput(references)


class CharacterReference(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CharacterReference",
            display_name="CharacterReference",
            category="LumaAI/Photon",
            inputs=[
                io.String.Input(
                    f"character_image_url_{index}",
                    force_input=True,
                    optional=True,
                )
                for index in range(1, 5)
            ],
            outputs=[
                CHARACTER_REFERENCE.Output(
                    "character_reference", display_name="character_reference",
                )
            ],
        )

    @classmethod
    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        urls = [
            kwargs[f"character_image_url_{index}"]
            for index in range(1, 5)
            if kwargs.get(f"character_image_url_{index}") is not None
        ]
        if not urls:
            raise ValueError("You must provide at least one character image URL")
        return io.NodeOutput({"identity0": {"images": urls}})


class LumaImageGeneration(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma", "output")
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaImageGeneration",
            display_name="Image Generation",
            category="LumaAI/Photon",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.Combo.Input("model", options=IMAGE_MODELS),
                io.String.Input("prompt", force_input=True),
                io.Combo.Input("aspect_ratio", options=ASPECT_RATIOS),
                _custom_input(
                    CONCAT_REFERENCES, "image_ref", optional=True,
                ),
                _custom_input(REFERENCE, "style_ref", optional=True),
                _custom_input(
                    CHARACTER_REFERENCE, "character_ref", optional=True,
                ),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_image_outputs(),
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls, client: Any, model: str, prompt: str, aspect_ratio: str,
        image_ref: Any = None, style_ref: Any = None,
        character_ref: Any = None, filename: str = "",
    ) -> io.NodeOutput:
        images = await _materialize(image_ref) if image_ref is not None else None
        style = await _materialize(style_ref) if style_ref is not None else None
        character = (
            await _materialize(character_ref)
            if character_ref is not None else None
        )
        result = await sdk.ctx().integrations.call("luma", "create_image", api_key=await _api_key(client), prompt=prompt, model=model, aspect_ratio=aspect_ratio, image_ref=images, style_ref=[style] if style is not None else None, character_ref=character)
        generation_id = result["generation_id"]
        image = result["image"]
        await _save_generated_image(image, filename, generation_id)
        return io.NodeOutput(
            result["url"], generation_id, image,
            ui={"text": [generation_id]},
        )


class LumaModifyImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma", "output")
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaModifyImage",
            display_name="Modify Image",
            category="LumaAI/Photon",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.Combo.Input("model", options=IMAGE_MODELS),
                io.String.Input("prompt", force_input=True),
                _custom_input(REFERENCE, "modify_image_ref"),
            ],
            outputs=_image_outputs(),
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls, client: Any, model: str, prompt: str,
        modify_image_ref: Any,
    ) -> io.NodeOutput:
        result = await sdk.ctx().integrations.call("luma", "create_image", api_key=await _api_key(client), prompt=prompt, model=model, modify_image_ref=await _materialize(modify_image_ref))
        generation_id = result["generation_id"]
        image = result["image"]
        await _save_generated_image(image, "", generation_id)
        return io.NodeOutput(
            result["url"], generation_id, image,
            ui={"text": [generation_id]},
        )


class LumaAddAudio2Video(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma",)
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaAddAudio2Video",
            display_name="Add Audio to Video",
            category="LumaAI/Audio",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.String.Input("generation_id", default="", force_input=True),
                io.String.Input("prompt", multiline=True, default=""),
                io.String.Input("negative_prompt", multiline=True, default=""),
                io.Boolean.Input("save", default=True),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_video_outputs(),
        )

    @classmethod
    async def execute(
        cls, client: Any, generation_id: str, prompt: str,
        negative_prompt: str, save: bool, filename: str = "",
    ) -> io.NodeOutput:
        result = await sdk.ctx().integrations.call("luma", "add_audio", api_key=await _api_key(client), generation_id=generation_id, prompt=prompt, negative_prompt=negative_prompt, save=save, filename=filename)
        result_id = result["generation_id"]
        return io.NodeOutput(
            result["url"], result_id,
            ui={"text": [result_id]},
        )


class LumaUpscaleGeneration(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.luma",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LumaUpscaleGeneration",
            display_name="Upscale Generation",
            category="LumaAI/Upscale",
            inputs=[
                _custom_input(LUMA_CLIENT, "client"),
                io.String.Input("generation_id", default="", force_input=True),
                io.Combo.Input("resolution", options=UPSCALE_RESOLUTIONS),
                io.Boolean.Input("save", default=True),
                io.String.Input("filename", default="", optional=True),
            ],
            outputs=_video_outputs(),
        )

    @classmethod
    async def execute(
        cls, client: Any, generation_id: str, resolution: str,
        save: bool, filename: str = "",
    ) -> io.NodeOutput:
        result = await sdk.ctx().integrations.call("luma", "upscale_video", api_key=await _api_key(client), generation_id=generation_id, resolution=resolution, save=save, filename=filename)
        result_id = result["generation_id"]
        return io.NodeOutput(
            result["url"], result_id,
            ui={"text": [result_id]},
        )


NODE_CLASS_MAPPINGS = {
    "LumaAIClient": LumaAIClient,
    "ImgBBUpload": ImgBBUpload,
    "LumaText2Video": LumaText2Video,
    "LumaImage2Video": LumaImage2Video,
    "LumaInterpolateGenerations": LumaInterpolateGenerations,
    "LumaExtendGeneration": LumaExtendGeneration,
    "Reference": Reference,
    "ConcatReferences": ConcatReferences,
    "CharacterReference": CharacterReference,
    "LumaImageGeneration": LumaImageGeneration,
    "LumaModifyImage": LumaModifyImage,
    "LumaAddAudio2Video": LumaAddAudio2Video,
    "LumaUpscaleGeneration": LumaUpscaleGeneration,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LumaAIClient": "LumaAI Client",
    "ImgBBUpload": "ImgBB Upload",
    "LumaText2Video": "Text to Video",
    "LumaImage2Video": "Image to Video",
    "LumaInterpolateGenerations": "Interpolate Generations",
    "LumaExtendGeneration": "Extend Generation",
    "LumaImageGeneration": "Image Generation",
    "LumaModifyImage": "Modify Image",
    "LumaAddAudio2Video": "Add Audio to Video",
    "LumaUpscaleGeneration": "Upscale Generation",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
