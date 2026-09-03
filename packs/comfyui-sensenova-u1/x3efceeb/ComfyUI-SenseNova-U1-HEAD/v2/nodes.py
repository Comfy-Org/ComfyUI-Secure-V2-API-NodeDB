"""Sandboxed SenseNova cloud nodes.

Request construction and workflow-facing schemas remain pack code. The host
owns the fixed provider origin, credential, network, media validation, and the
large text results described by D33.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from comfy_api.latest import io, sdk


CATEGORY = "SenseNova"
VISION_SYSTEM_PROMPT = (
    "You are a careful vision assistant. Describe only visible details."
)
CHAT_MODELS = ["sensenova-6.7-flash-lite", "deepseek-v4"]
VISION_MODELS = ["sensenova-6.7-flash-lite"]
IMAGE_MODELS = ["sensenova-u1-fast"]
IMAGE_SIZE_OPTIONS = [
    "2752x1536|16:9",
    "1536x2752|9:16",
    "2048x2048|1:1",
    "2496x1664|3:2",
    "1664x2496|2:3",
    "2368x1760|4:3",
    "1760x2368|3:4",
    "2272x1824|5:4",
    "1824x2272|4:5",
    "3072x1376|21:9",
    "1344x3136|9:21",
]
_BUILDER_SHA256 = (
    "b7340a736b7c0553fd9ad6f128106ce3820e9feedb3367ef978eebfbd1a54bd4"
)


def _builder_prompt() -> str:
    data = (Path(__file__).with_name("prompts") / "builder_prompt.txt").read_bytes()
    if hashlib.sha256(data).hexdigest() != _BUILDER_SHA256:
        raise RuntimeError("vendored SenseNova builder prompt failed SHA-256")
    return data.decode("utf-8")


def _chat_inputs(*, builder: bool = False) -> list[io.Input]:
    return [
        io.String.Input(
            "prompt" if builder else "text",
            multiline=True,
            default="",
        ),
        io.String.Input(
            "system_prompt",
            multiline=True,
            default=(
                _builder_prompt()
                if builder
                else "You are a helpful assistant. Answer clearly and concisely."
            ),
        ),
        io.Combo.Input("model", options=CHAT_MODELS, default=CHAT_MODELS[0]),
        io.Float.Input(
            "temperature",
            default=0.3 if builder else 0.7,
            min=0.0,
            max=2.0,
            step=0.1,
        ),
        io.Float.Input("top_p", default=1.0, min=0.0, max=1.0, step=0.05),
        io.Int.Input("max_tokens", default=2048, min=1, max=65536),
        io.Int.Input("timeout", default=120, min=10, max=600),
    ]


def _chat_outputs(first: str) -> list[io.Output]:
    return [
        io.String.Output(display_name=first),
        io.String.Output(display_name="usage_json"),
        io.String.Output(display_name="raw_json"),
    ]


async def _chat(
    text: str,
    system_prompt: str,
    model: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> io.NodeOutput:
    result = await sdk.ctx().integrations.call("sensenova", "chat", text=text, system_prompt=system_prompt, model=model, temperature=temperature, top_p=top_p, max_tokens=max_tokens, timeout_seconds=timeout)
    return io.NodeOutput(
        result["text"], result["usage_json"], result["raw_json"])


class SenseNovaChat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.sensenova",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SenseNovaChat",
            display_name="SenseNova Chat",
            category=CATEGORY,
            inputs=_chat_inputs(),
            outputs=_chat_outputs("text"),
        )

    @classmethod
    async def execute(
        cls,
        text: str,
        system_prompt: str,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        timeout: int,
    ) -> io.NodeOutput:
        return await _chat(
            text, system_prompt, model, temperature, top_p, max_tokens, timeout)


class SenseNovaImageGenerate(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.sensenova",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SenseNovaImageGenerate",
            display_name="SenseNova Image Generate",
            category=CATEGORY,
            inputs=[
                io.String.Input("prompt", multiline=True, default=""),
                io.Combo.Input(
                    "model", options=IMAGE_MODELS, default=IMAGE_MODELS[0]),
                io.Combo.Input(
                    "size", options=IMAGE_SIZE_OPTIONS,
                    default=IMAGE_SIZE_OPTIONS[0]),
                io.Int.Input("timeout", default=300, min=30, max=900),
            ],
            outputs=[
                io.Image.Output(display_name="images"),
                io.String.Output(display_name="image_base64"),
                io.String.Output(display_name="image_url"),
                io.String.Output(display_name="raw_json"),
                io.String.Output(display_name="image_info"),
            ],
        )

    @classmethod
    async def execute(
        cls, prompt: str, model: str, size: str, timeout: int,
    ) -> io.NodeOutput:
        result = await sdk.ctx().integrations.call("sensenova", "generate_image", prompt=prompt, model=model, size=size, timeout_seconds=timeout)
        return io.NodeOutput(
            result["image"],
            result["image_base64"],
            result["image_url"],
            result["raw_json"],
            result["image_info"],
        )


class SenseNovaPromptBuilder(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.sensenova",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SenseNovaPromptBuilder",
            display_name="SenseNova Prompt Builder",
            category=CATEGORY,
            inputs=_chat_inputs(builder=True),
            outputs=_chat_outputs("prompt"),
        )

    @classmethod
    async def execute(
        cls,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        timeout: int,
    ) -> io.NodeOutput:
        return await _chat(
            prompt, system_prompt, model, temperature, top_p, max_tokens, timeout)


def _vision_inputs(first: io.Input) -> list[io.Input]:
    return [
        first,
        io.String.Input("prompt", multiline=True, default="Describe this image."),
        io.String.Input(
            "system_prompt", multiline=True, default=VISION_SYSTEM_PROMPT),
        io.Combo.Input("model", options=VISION_MODELS, default=VISION_MODELS[0]),
        io.Float.Input("temperature", default=0.2, min=0.0, max=2.0, step=0.1),
        io.Float.Input("top_p", default=1.0, min=0.0, max=1.0, step=0.05),
        io.Int.Input("max_tokens", default=2048, min=1, max=65536),
        io.Int.Input("timeout", default=120, min=10, max=600),
    ]


def _vision_output(result: dict[str, sdk.ValueRef]) -> io.NodeOutput:
    return io.NodeOutput(
        result["text"], result["usage_json"], result["raw_json"])


class SenseNovaVisionURL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.sensenova",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SenseNovaVisionURL",
            display_name="SenseNova Vision URL",
            category=CATEGORY,
            inputs=_vision_inputs(io.String.Input("image_url", default="")),
            outputs=_chat_outputs("text"),
        )

    @classmethod
    async def execute(
        cls,
        image_url: str,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        timeout: int,
    ) -> io.NodeOutput:
        result = await sdk.ctx().integrations.call("sensenova", "vision_url", image_url=image_url, prompt=prompt, system_prompt=system_prompt, model=model, temperature=temperature, top_p=top_p, max_tokens=max_tokens, timeout_seconds=timeout)
        return _vision_output(result)


class SenseNovaVisionImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.sensenova",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SenseNovaVisionImage",
            display_name="SenseNova Vision Image",
            category=CATEGORY,
            inputs=_vision_inputs(io.Image.Input("image")),
            outputs=_chat_outputs("text"),
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        timeout: int,
    ) -> io.NodeOutput:
        result = await sdk.ctx().integrations.call("sensenova", "vision_image", image=image, prompt=prompt, system_prompt=system_prompt, model=model, temperature=temperature, top_p=top_p, max_tokens=max_tokens, timeout_seconds=timeout)
        return _vision_output(result)


NODE_CLASS_MAPPINGS = {
    "SenseNovaChat": SenseNovaChat,
    "SenseNovaImageGenerate": SenseNovaImageGenerate,
    "SenseNovaPromptBuilder": SenseNovaPromptBuilder,
    "SenseNovaVisionURL": SenseNovaVisionURL,
    "SenseNovaVisionImage": SenseNovaVisionImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node.define_schema().display_name
    for node_id, node in NODE_CLASS_MAPPINGS.items()
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
