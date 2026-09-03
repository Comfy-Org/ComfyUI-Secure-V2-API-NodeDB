"""Secure Nodes V2 implementation of ComfyUI-Ollama-Describer.

Prompt construction, caption formatting, text transforms, JSON lookup, video
frame selection, tool aggregation, and the agent loop remain pack-owned.  The
host owns Ollama transport, images, managed assets, outputs, credentials, and
web access.  The pack never receives a socket, raw tensor, credential, or
ambient filesystem path.
"""
from __future__ import annotations

import json
import re
from typing import Any

from comfy_api.latest import ComfyExtension, io, sdk

from .config import configurations


EXTRA_OPTIONS = tuple(configurations["extra_options"])
CAPTION_TYPES = tuple(configurations["caption_types"])
CAPTION_LENGTHS = tuple(configurations["caption_lengths"])
MULTIMODAL_MODELS = tuple(configurations["multimodal_models"])
TEXT_MODELS = tuple(configurations["text_models"])
TOOL_CALLING_MODELS = tuple(configurations.get("tool_calling_models", ()))

EXTRA_OPTIONS_TYPE = io.Custom("Extra_Options")
OLLAMA_TOOL = io.Custom("OLLAMA_TOOL")

_DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
_LOOPBACK_ENDPOINT = re.compile(
    r"^http://(?:127\.0\.0\.1|localhost|\[::1\]):11434$", re.IGNORECASE
)
_NAMED_ENDPOINT = re.compile(r"^ollama://[a-z0-9][a-z0-9._-]{0,63}$")
_TOOL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_MAX_TEXT = 262_144


def _bounded_text(value: Any, field: str, maximum: int = _MAX_TEXT) -> str:
    text = str(value or "")
    if "\x00" in text or len(text) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters and contain no NUL")
    return text


def _endpoint(value: Any) -> str:
    endpoint = str(value or _DEFAULT_ENDPOINT).strip()
    if _LOOPBACK_ENDPOINT.fullmatch(endpoint) or _NAMED_ENDPOINT.fullmatch(endpoint):
        return endpoint
    raise ValueError(
        "Ollama endpoints must be loopback port 11434 or an administrator "
        "configured ollama:// profile"
    )


def _model(model: Any, custom_model: Any = "") -> str:
    selected = str(custom_model or "").strip()
    if not selected:
        selected = str(model or "").split(" ", 1)[0].strip()
    if not selected or len(selected) > 256 or "\x00" in selected:
        raise ValueError("Ollama model must be 1..256 characters and contain no NUL")
    return selected


def _keep_alive(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("keep_model_alive must be an integer")
    if not -1 <= value <= 120:
        raise ValueError("keep_model_alive must be in [-1, 120]")
    return value


def _format(value: Any) -> str | dict[str, Any]:
    """Normalize an optional bounded JSON-Schema response format."""
    if value is None or value == "":
        return ""
    parsed = value
    if isinstance(value, str):
        if value.strip() == "json":
            return "json"
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(
                "structured_output_format must be 'json' or valid JSON Schema"
            ) from error
    if not isinstance(parsed, dict):
        raise ValueError(
            "structured_output_format must be 'json' or a JSON object"
        )
    return parsed


def _timeout(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout must be numeric")
    result = float(value)
    if not 1.0 <= result <= 600.0:
        raise ValueError("timeout must be in [1, 600] seconds")
    return result


def _managed_directory(value: Any, field: str, root: str) -> str:
    """Return a relative managed-directory name, never an ambient path."""
    text = _bounded_text(value, field, 4096).strip().replace("\\", "/")
    if text == root:
        return ""
    marker = root + "/"
    if text.startswith(marker):
        text = text[len(marker):]
    if text.startswith("/") or ":" in text:
        raise ValueError(f"{field} must be relative to the managed {root} directory")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"{field} escapes the managed {root} directory")
    return "/".join(parts)


def _options(
    *, num_ctx: int, max_tokens: int, temperature: float, top_k: int,
    top_p: float, repeat_penalty: float, seed_number: int,
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "num_ctx": int(num_ctx),
        "num_predict": int(max_tokens),
        "temperature": float(temperature),
        "top_k": int(top_k),
        "top_p": float(top_p),
        "repeat_penalty": float(repeat_penalty),
    }
    if int(seed_number) >= 0:
        options["seed"] = int(seed_number)
    return options


def _response_text(response: Any) -> str:
    if not isinstance(response, dict):
        raise TypeError("Ollama integration returned a non-object response")
    return _bounded_text(response.get("response", ""), "Ollama response", 4_194_304)


async def _generate(
    *, endpoint: str, model: str, system: str, prompt: str,
    images: sdk.ImageRef | None, keep_alive: int, options: dict[str, Any],
    structured_output_format: Any, timeout: float,
    capture_errors: bool = True,
) -> str:
    try:
        response = await sdk.ctx().integrations.call("ollama", "generate", endpoint=_endpoint(endpoint), model=model, system=_bounded_text(system, "system"), prompt=_bounded_text(prompt, "prompt"), images=images, options=options, keep_alive=_keep_alive(keep_alive), keep_alive_unit="minutes", format=_format(structured_output_format), timeout_seconds=_timeout(timeout))
        return _response_text(response)
    except Exception as error:
        if capture_errors:
            return f"Error: {error}"
        raise


def _common_generate_inputs(
    models: tuple[str, ...], *, video: bool = False,
    temperature_max: float = 10,
):
    inputs: list[Any] = [
        io.Combo.Input("model", options=list(models), default=models[0]),
        io.String.Input("custom_model", default=""),
        io.String.Input("api_host", default="http://localhost:11434"),
        io.Int.Input("timeout", default=300, min=1, max=600, step=1),
        io.Float.Input(
            "temperature", default=0.2, min=0, max=temperature_max, step=0.1,
        ),
        io.Int.Input("top_k", default=40, min=0, max=100, step=1),
        io.Float.Input("top_p", default=0.9, min=0, max=1, step=0.1),
        io.Float.Input("repeat_penalty", default=1.1, min=0, max=2, step=0.1),
        io.Int.Input("seed_number", default=42, min=-1, max=2**31, step=1),
        io.Int.Input("num_ctx", default=4096 if video else 2048, min=1, max=2**31, step=64),
        io.Int.Input("max_tokens", default=4096 if video else 1024, min=1, max=32_768, step=128 if video else 64),
        io.Int.Input("keep_model_alive", default=-1, min=-1, max=120, step=1),
    ]
    return inputs


class OllamaCaptionerExtraOptions(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaCaptionerExtraOptions",
            display_name="🦙 Ollama Captioner Extra Options 🦙",
            category="Ollama",
            inputs=[io.Boolean.Input(option, default=False) for option in EXTRA_OPTIONS],
            outputs=[EXTRA_OPTIONS_TYPE.Output("extra_options")],
        )

    @classmethod
    async def execute(cls, **kwargs):
        return io.NodeOutput([option for option in EXTRA_OPTIONS if kwargs.get(option) is True])


class OllamaImageCaptioner(io.ComfyNode):
    """Caption a managed input-directory image set into managed output."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "output", "integrations.ollama")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaImageCaptioner",
            display_name="🦙 Ollama Image Captioner 🦙",
            category="Ollama",
            is_output_node=True,
            description=(
                "Caption managed image assets in a directory and write one adjacent "
                ".txt caption per image."
            ),
            inputs=[
                io.Combo.Input("model", options=list(MULTIMODAL_MODELS), default=MULTIMODAL_MODELS[0]),
                io.String.Input("custom_model", default=""),
                io.String.Input("api_host", default="http://localhost:11434"),
                io.Int.Input("timeout", default=300, min=1, max=600, step=1),
                io.String.Input("input_dir", default=""),
                io.String.Input("output_dir", default=""),
                io.Int.Input("max_images", default=-1, min=-1, max=4096),
                io.Boolean.Input("low_vram", default=False),
                io.Int.Input(
                    "keep_model_alive", default=-1, min=-1, max=120, step=1,
                ),
                io.Float.Input("top_p", default=0.9, min=0, max=1, step=0.01),
                io.Float.Input("temperature", default=0.6, min=0, max=1, step=0.01),
                io.Combo.Input("caption_type", options=list(CAPTION_TYPES), default=CAPTION_TYPES[0]),
                io.Combo.Input("caption_length", options=list(CAPTION_LENGTHS), default=CAPTION_LENGTHS[0]),
                io.String.Input("name", default=""),
                io.String.Input("custom_prompt", default=""),
                io.String.Input("prefix_caption", default=""),
                io.String.Input("suffix_caption", default=""),
                EXTRA_OPTIONS_TYPE.Input("extra_options", optional=True),
                io.String.Input("structured_output_format", optional=True, force_input=True),
            ],
            outputs=[io.String.Output("result")],
        )

    @classmethod
    async def execute(
        cls, model, custom_model, api_host, timeout, input_dir, output_dir,
        max_images, low_vram, keep_model_alive, top_p, temperature,
        caption_type, caption_length, name, custom_prompt, prefix_caption,
        suffix_caption, extra_options=None, structured_output_format=None,
    ):
        source_prefix = _managed_directory(input_dir, "input_dir", "input")
        destination = _managed_directory(
            output_dir if str(output_dir or "").strip() else source_prefix,
            "output_dir", "output",
        )
        if caption_type not in configurations["caption_types"]:
            raise ValueError("unknown caption_type")
        if caption_length not in CAPTION_LENGTHS:
            raise ValueError("unknown caption_length")

        length: int | str | None = (
            None if caption_length == "any" else caption_length
        )
        if isinstance(length, str):
            try:
                length = int(length)
            except ValueError:
                pass
        map_index = 0 if length is None else (1 if isinstance(length, int) else 2)
        prompt = configurations["caption_types"][caption_type][map_index]
        if custom_prompt:
            prompt += " " + _bounded_text(custom_prompt, "custom_prompt")
        selected_options = list(extra_options or [])
        if len(selected_options) > len(EXTRA_OPTIONS) or any(
            option not in EXTRA_OPTIONS for option in selected_options
        ):
            raise ValueError("extra_options contains an unknown caption instruction")
        if selected_options:
            prompt += " " + " ".join(selected_options)
        prompt = prompt.format(
            name=_bounded_text(name, "name", 4096),
            length=caption_length,
            word_count=caption_length,
        )

        names = await sdk.ctx().assets.list(
            "input", prefix=source_prefix, recursive=False,
        )
        image_names = [
            item for item in names
            if item.lower().endswith((".jpg", ".png", ".jpeg", ".bmp", ".webp"))
        ]
        limit = int(max_images)
        if limit >= 0:
            image_names = image_names[:limit]

        finished = 0
        errors = 0
        format_value = _format(structured_output_format)
        for logical_name in image_names:
            try:
                asset = await sdk.ctx().assets.resolve("input", logical_name)
                image = await sdk.ctx().assets.load_image(asset)
                caption = await _generate(
                    endpoint=api_host,
                    model=_model(model, custom_model),
                    system="You are a helpful image captioner.",
                    prompt=prompt,
                    images=image,
                    keep_alive=keep_model_alive,
                    options={
                        "temperature": float(temperature),
                        "top_p": float(top_p),
                        "main_gpu": 0,
                        "low_vram": bool(low_vram),
                    },
                    structured_output_format=format_value,
                    timeout=timeout,
                    capture_errors=False,
                )
                if prefix_caption:
                    caption = f"{_bounded_text(prefix_caption, 'prefix_caption')} {caption}"
                if suffix_caption:
                    caption = f"{caption} {_bounded_text(suffix_caption, 'suffix_caption')}"
                filename = logical_name.rsplit("/", 1)[-1]
                stem = filename.rsplit(".", 1)[0]
                target = f"{destination}/{stem}.txt" if destination else f"{stem}.txt"
                await sdk.ctx().output.write_text(
                    caption, filename=target, folder="output", mode="overwrite",
                )
                finished += 1
            except Exception:
                errors += 1
        return io.NodeOutput(
            f"result: finished count: {finished}, error count: {errors}"
        )


class OllamaImageDescriber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaImageDescriber",
            display_name="🦙 Ollama Image Describer 🦙",
            category="Ollama",
            is_output_node=True,
            description="Describe an IMAGE batch with a selected Ollama vision model.",
            inputs=_common_generate_inputs(MULTIMODAL_MODELS) + [
                io.Image.Input("images"),
                io.String.Input(
                    "system_context", multiline=True,
                    default=(
                        "You are a helpful AI assistant specialized in generating "
                        "detailed and accurate textual descriptions of images. Your "
                        "task is to analyze the information provided about an image "
                        "and create a clear, concise, and informative description. "
                        "Focus on the key elements of the image, such as objects, "
                        "people, actions, and the overall scene. Ensure the "
                        "description is easy to understand and relevant to the context."
                    ),
                ),
                io.String.Input(
                    "prompt", multiline=True,
                    default=(
                        "Describe the following image in detail, focusing on its key "
                        "elements such as objects, people, actions, and the overall "
                        "scene. Provide a clear and concise description that "
                        "highlights the most important aspects. Image:"
                    ),
                ),
                io.String.Input("structured_output_format", optional=True, force_input=True),
            ],
            outputs=[io.String.Output("result")],
        )

    @classmethod
    async def execute(
        cls, model, custom_model, api_host, timeout, temperature, top_k, top_p,
        repeat_penalty, seed_number, num_ctx, max_tokens, keep_model_alive,
        images, system_context, prompt, structured_output_format=None,
    ):
        if not isinstance(images, sdk.ImageRef):
            raise TypeError("images must be an IMAGE ref")
        return io.NodeOutput(await _generate(
            endpoint=api_host,
            model=_model(model, custom_model),
            system=system_context,
            prompt=prompt,
            images=images,
            keep_alive=keep_model_alive,
            options=_options(
                num_ctx=num_ctx, max_tokens=max_tokens, temperature=temperature,
                top_k=top_k, top_p=top_p, repeat_penalty=repeat_penalty,
                seed_number=seed_number,
            ),
            structured_output_format=structured_output_format,
            timeout=timeout,
        ))


class OllamaTextDescriber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaTextDescriber",
            display_name="🦙 Ollama Text Describer 🦙",
            category="Ollama",
            is_output_node=True,
            description="Generate a text response with a selected Ollama model.",
            inputs=_common_generate_inputs(TEXT_MODELS, temperature_max=1) + [
                io.String.Input(
                    "system_context", multiline=True,
                    default=(
                        "You are a helpful AI assistant specialized in generating "
                        "detailed and accurate textual descriptions. Your task is to "
                        "analyze the input provided and create a clear, concise, and "
                        "informative description. Focus on the key aspects of the "
                        "input, and ensure the description is easy to understand and "
                        "relevant to the context."
                    ),
                ),
                io.String.Input(
                    "prompt", multiline=True,
                    default=(
                        "Describe the following input in detail, focusing on its key "
                        "features and context. Provide a clear and concise description "
                        "that highlights the most important aspects. Input:"
                    ),
                ),
                io.String.Input("structured_output_format", optional=True, force_input=True),
            ],
            outputs=[io.String.Output("result")],
        )

    @classmethod
    async def execute(
        cls, model, custom_model, api_host, timeout, temperature, top_k, top_p,
        repeat_penalty, seed_number, num_ctx, max_tokens, keep_model_alive,
        system_context, prompt, structured_output_format=None,
    ):
        return io.NodeOutput(await _generate(
            endpoint=api_host,
            model=_model(model, custom_model),
            system=system_context,
            prompt=prompt,
            images=None,
            keep_alive=keep_model_alive,
            options=_options(
                num_ctx=num_ctx, max_tokens=max_tokens, temperature=temperature,
                top_k=top_k, top_p=top_p, repeat_penalty=repeat_penalty,
                seed_number=seed_number,
            ),
            structured_output_format=structured_output_format,
            timeout=timeout,
        ))


class TextTransformer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TextTransformer",
            display_name="📝 Text Transformer 📝",
            category="Ollama",
            inputs=[
                io.String.Input("text", multiline=True, default="", force_input=True),
                io.String.Input("prepend_text", multiline=True, default="", optional=True),
                io.String.Input("append_text", multiline=True, default="", optional=True),
                io.Combo.Input(
                    "replace_find_mode",
                    options=["normal", "regular expression (regex)"],
                    default="normal", optional=True,
                ),
                io.String.Input("replace_find", default="", optional=True),
                io.String.Input("replace_with", default="", optional=True),
            ],
            outputs=[io.String.Output("text")],
        )

    @staticmethod
    def _unescape(value: Any) -> str:
        return (_bounded_text(value, "text")
                .replace("\\n", "\n").replace("\\t", "\t")
                .replace("\\r", "\r").replace("\\b", "\b")
                .replace("\\f", "\f").replace("\\v", "\v")
                .replace("\\\\", "\\").replace("\\'", "'")
                .replace('\\"', '"').replace("\\a", "\a"))

    @classmethod
    async def execute(
        cls, text, prepend_text="", append_text="", replace_find_mode="normal",
        replace_find="", replace_with="",
    ):
        result = cls._unescape(text)
        if prepend_text:
            result = cls._unescape(prepend_text) + result
        if append_text:
            result += cls._unescape(append_text)
        if replace_find:
            if replace_find_mode == "normal":
                result = result.replace(str(replace_find), str(replace_with))
            elif replace_find_mode == "regular expression (regex)":
                try:
                    result = re.sub(
                        _bounded_text(replace_find, "replace_find", 16_384).strip(),
                        _bounded_text(replace_with, "replace_with"), result,
                    )
                except re.error as error:
                    return io.NodeOutput(
                        f"Error: Invalid regular expression '{replace_find}'. Details: {error}"
                    )
            else:
                raise ValueError("unknown replacement mode")
        return io.NodeOutput(result)


class InputText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="InputText",
            display_name="📝 Input Text (Multiline) 📝",
            category="Ollama",
            inputs=[io.String.Input("string", default="", multiline=True)],
            outputs=[io.String.Output("string")],
        )

    @classmethod
    async def execute(cls, string):
        return io.NodeOutput(_bounded_text(string, "string"))


class JsonPropertyExtractorNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="JsonPropertyExtractorNode",
            display_name="📝 Json Property Extractor 📝",
            category="Custom Nodes/JSON",
            description="Return the value at a dot-delimited path in a JSON object.",
            inputs=[
                io.String.Input("json_input", multiline=True, default="{}"),
                io.String.Input("property_path", default=""),
            ],
            outputs=[io.String.Output("selected_value")],
        )

    @classmethod
    async def execute(cls, json_input, property_path):
        if not json_input or not property_path:
            raise ValueError("JSON input and property path are required.")
        try:
            current: Any = json.loads(_bounded_text(json_input, "json_input", 1_048_576))
        except json.JSONDecodeError as error:
            raise ValueError(f"Error decoding JSON: {error}") from error
        for part in _bounded_text(property_path, "property_path", 4096).split("."):
            if not isinstance(current, dict) or part not in current:
                raise ValueError(f"Property '{part}' not found in JSON.")
            current = current[part]
        return io.NodeOutput(str(current))


class OllamaVideoDescriber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaVideoDescriber",
            display_name="🦙 Ollama Video Describer 🦙",
            category="Ollama",
            is_output_node=True,
            description="Sample a bounded frame sequence and ask Ollama to describe the events.",
            inputs=_common_generate_inputs(MULTIMODAL_MODELS, video=True) + [
                io.Image.Input("video_frames"),
                io.Int.Input("frame_skip", default=5, min=1, max=1000, step=1),
                io.Int.Input("max_frames", default=16, min=1, max=128, step=1),
                io.String.Input(
                    "system_context", multiline=True,
                    default=(
                        "You are a helpful AI assistant specialized in analyzing a "
                        "sequence of video frames and generating a detailed and "
                        "accurate textual description of the events. Describe the "
                        "actions, people, objects, and how the scene evolves across "
                        "the frames."
                    ),
                ),
                io.String.Input(
                    "prompt", multiline=True,
                    default=(
                        "Describe the events happening in this sequence of video "
                        "frames in detail. Provide a clear and concise description "
                        "that highlights the most important actions. Video:"
                    ),
                ),
                io.String.Input("structured_output_format", optional=True, force_input=True),
            ],
            outputs=[io.String.Output("result")],
        )

    @classmethod
    async def execute(
        cls, model, custom_model, api_host, timeout, temperature, top_k, top_p,
        repeat_penalty, seed_number, num_ctx, max_tokens, keep_model_alive,
        video_frames, frame_skip, max_frames, system_context, prompt,
        structured_output_format=None,
    ):
        if not isinstance(video_frames, sdk.ImageRef):
            raise TypeError("video_frames must be an IMAGE ref")
        batch_size = await video_frames.batch_size()
        indices = list(range(0, batch_size, int(frame_skip)))[: int(max_frames)]
        if not indices:
            raise ValueError("video_frames must contain at least one frame")
        selected = await video_frames.op("image.select_batch", indices=indices)
        return io.NodeOutput(await _generate(
            endpoint=api_host,
            model=_model(model, custom_model),
            system=system_context,
            prompt=prompt,
            images=selected,
            keep_alive=keep_model_alive,
            options=_options(
                num_ctx=num_ctx, max_tokens=max_tokens, temperature=temperature,
                top_k=top_k, top_p=top_p, repeat_penalty=repeat_penalty,
                seed_number=seed_number,
            ),
            structured_output_format=structured_output_format,
            timeout=timeout,
        ))


def _tool_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    if len(values) > 16 or any(not isinstance(item, dict) for item in values):
        raise ValueError("OLLAMA_TOOL must be a bounded tool descriptor list")
    return [dict(item) for item in values]


class OllamaToolCombine(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaToolCombine",
            display_name="🛠️ Combine Ollama Tools 🛠️",
            category="Ollama/Tools",
            inputs=[
                OLLAMA_TOOL.Input("tool_1"),
                OLLAMA_TOOL.Input("tool_2", optional=True),
                OLLAMA_TOOL.Input("tool_3", optional=True),
                OLLAMA_TOOL.Input("tool_4", optional=True),
            ],
            outputs=[OLLAMA_TOOL.Output("tools")],
        )

    @classmethod
    async def execute(cls, tool_1, tool_2=None, tool_3=None, tool_4=None):
        combined: list[dict[str, Any]] = []
        for value in (tool_1, tool_2, tool_3, tool_4):
            combined.extend(_tool_list(value))
        if len(combined) > 16:
            raise ValueError("at most 16 tools may be combined")
        return io.NodeOutput(combined)


class OllamaTool_WebSearch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaTool_WebSearch",
            display_name="🛠️ Tool: Web Search 🛠️",
            category="Ollama/Tools",
            description="Declare a bounded host-brokered web-search tool for Ollama Agent.",
            inputs=[
                io.String.Input(
                    "tool_name", default="search_internet",
                    tooltip=(
                        "The tool name shown to the Agent; names such as "
                        "'google_search' or 'web_lookup' can clarify when to use it."
                    ),
                ),
                io.Combo.Input(
                    "search_provider",
                    options=["DuckDuckGo (free)", "Ollama API (requires key)"],
                    default="DuckDuckGo (free)",
                    tooltip=(
                        "Choose free DuckDuckGo search or the host-configured "
                        "Ollama web-search profile."
                    ),
                ),
                io.Int.Input(
                    "max_results", default=5, min=1, max=10,
                    tooltip=(
                        "Maximum search results returned; fewer results use less "
                        "agent context."
                    ),
                ),
                io.String.Input(
                    "ollama_api_key", default="", optional=True,
                    tooltip=(
                        "Ignored in Secure V2. Ollama web credentials are configured "
                        "by the host and never enter the workflow or guest."
                    ),
                ),
            ],
            outputs=[OLLAMA_TOOL.Output("tool")],
        )

    @classmethod
    async def execute(
        cls, tool_name="search_internet", search_provider="DuckDuckGo (free)",
        max_results=5, ollama_api_key="",
    ):
        name = str(tool_name).strip()
        if not _TOOL_NAME.fullmatch(name):
            raise ValueError("tool_name must be a short Python-style identifier")
        profiles = {
            "DuckDuckGo (free)": "duckduckgo",
            "Ollama API (requires key)": "ollama",
        }
        if search_provider not in profiles:
            raise ValueError("unknown search_provider")
        provider = profiles[search_provider]
        # Raw credentials deliberately do not enter the descriptor or guest tool.
        return io.NodeOutput({
            "kind": "web_search",
            "name": name,
            "provider_profile": provider,
            "max_results": max(1, min(10, int(max_results))),
            "description": "Search the internet for current information, news, or facts.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": "Search the internet for current information, news, or facts.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
        })


class OllamaTool_FileSearch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaTool_FileSearch",
            display_name="🛠️ Tool: Read File 🛠️",
            category="Ollama/Tools",
            description="Security-rejected: lets model output select an ambient local path.",
            inputs=[io.String.Input("tool_name", default="read_local_file")],
            outputs=[OLLAMA_TOOL.Output("tool")],
        )

    @classmethod
    async def execute(cls, tool_name="read_local_file"):
        raise PermissionError(
            "OllamaTool_FileSearch is security-rejected: model-selected ambient filesystem reads are not permitted"
        )


class OllamaTool_PythonCode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaTool_PythonCode",
            display_name="🛠️ Tool: Custom Python Code 🛠️",
            category="Ollama/Tools",
            description="Security-rejected: executes arbitrary supplied Python with connected objects.",
            inputs=[
                io.String.Input("tool_name", default="custom_python_tool"),
                io.String.Input("python_code", multiline=True, default=""),
                io.AnyType.Input("my_ext_var", optional=True),
                io.AnyType.Input("my_ext_var_2", optional=True),
                io.AnyType.Input("my_ext_var_3", optional=True),
            ],
            outputs=[OLLAMA_TOOL.Output("tool")],
        )

    @classmethod
    async def execute(cls, **kwargs):
        raise PermissionError(
            "OllamaTool_PythonCode is security-rejected: arbitrary Python execution and imports are not permitted"
        )


class OllamaAgent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.llm", "integrations.web")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaAgent",
            display_name="🤖 Ollama Agent 🤖",
            category="Ollama/Agent",
            is_output_node=True,
            description=(
                "Run a bounded pack-owned Ollama agent loop. Tool schemas and tool "
                "results are brokered; arbitrary code and ambient file tools are refused."
            ),
            inputs=[
                io.Combo.Input("model", options=list(TOOL_CALLING_MODELS), default=TOOL_CALLING_MODELS[0]),
                io.String.Input("custom_model", default=""),
                io.String.Input("api_host", default="http://localhost:11434"),
                io.Int.Input("timeout", default=300, min=1, max=600, step=1),
                io.Float.Input("temperature", default=0.2, min=0, max=10, step=0.1),
                io.Int.Input("max_tokens", default=2048, min=1, max=32_768, step=64),
                io.String.Input(
                    "system_context", multiline=True,
                    default=(
                        "You are a helpful and intelligent agent. You have access to "
                        "tools that you can call to answer user queries. \n\n"
                        "IMPORTANT: If the user asks for real-time information (like "
                        "current time, date, local weather, or web searches), DO NOT "
                        "refuse or say you do not have access. Instead, use the "
                        "available tools (like 'search_internet') IMMEDIATELY to find "
                        "the answer. Always prioritize using tools over guessing or "
                        "refusing."
                    ),
                ),
                io.String.Input("prompt", multiline=True, default="What time is it right now?"),
                io.Boolean.Input(
                    "think", default=False, label_on="enabled",
                    label_off="disabled",
                    tooltip=(
                        "Enable reasoning (e.g. for Qwen3, DeepSeek-R1) before "
                        "outputting the final answer."
                    ),
                ),
                OLLAMA_TOOL.Input(
                    "tools", optional=True,
                    tooltip=(
                        "Connect Ollama tool nodes so the Agent can call them to "
                        "gather current information."
                    ),
                ),
            ],
            outputs=[io.String.Output("result")],
        )

    @classmethod
    async def execute(
        cls, model, custom_model, api_host, timeout, temperature, max_tokens,
        system_context, prompt, think, tools=None,
    ):
        declared_tools = _tool_list(tools)
        tool_schemas: list[dict[str, Any]] = []
        tools_by_name: dict[str, dict[str, Any]] = {}
        for descriptor in declared_tools:
            if descriptor.get("kind") != "web_search":
                raise ValueError("only host-brokered web-search tools are supported")
            name = descriptor.get("name")
            description = descriptor.get("description")
            parameters = descriptor.get("parameters")
            if not isinstance(name, str) or not _TOOL_NAME.fullmatch(name):
                raise ValueError("tool descriptor has an invalid name")
            if name in tools_by_name:
                raise ValueError(f"duplicate tool name: {name}")
            if not isinstance(description, str) or not isinstance(parameters, dict):
                raise ValueError("tool descriptor has an invalid schema")
            profile = descriptor.get("provider_profile")
            limit = descriptor.get("max_results")
            if profile not in {"duckduckgo", "ollama"}:
                raise ValueError("web-search tool has an invalid provider profile")
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
                raise ValueError("web-search tool max_results must be in [1, 10]")
            tool_schemas.append({
                "name": name,
                "description": _bounded_text(description, "tool description", 4096),
                "parameters": parameters,
            })
            tools_by_name[name] = descriptor

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _bounded_text(system_context, "system_context")},
            {"role": "user", "content": _bounded_text(prompt, "prompt")},
        ]
        try:
            for _iteration in range(10):
                response = await sdk.ctx().integrations.call("llm", "chat", provider="ollama", profile=_endpoint(api_host), model=_model(model, custom_model), messages=messages, tools=tool_schemas or None, temperature=float(temperature), max_tokens=int(max_tokens), thinking=bool(think), response_format="", timeout_seconds=_timeout(timeout), vendor_options={
                        "ollama": {
                            "keep_alive": 5,
                            "keep_alive_unit": "minutes",
                        },
                    })
                if not isinstance(response, dict):
                    raise TypeError("LLM integration returned a non-object response")
                content = _bounded_text(
                    response.get("content", ""), "agent response", 4_194_304,
                )
                thinking = response.get("thinking")
                calls = response.get("tool_calls", [])
                if not isinstance(calls, list) or len(calls) > 32:
                    raise ValueError("LLM tool_calls must be a bounded list")
                normalized_calls = []
                for call in calls:
                    if (not isinstance(call, dict)
                            or set(call) != {"name", "arguments"}
                            or not isinstance(call.get("arguments"), dict)):
                        raise ValueError("LLM tool call has an invalid shape")
                    call_name = call["name"]
                    if not isinstance(call_name, str) or not _TOOL_NAME.fullmatch(call_name):
                        raise ValueError("LLM tool call has an invalid name")
                    normalized_calls.append({
                        "name": call_name,
                        "arguments": dict(call["arguments"]),
                    })

                assistant: dict[str, Any] = {
                    "role": "assistant", "content": content,
                }
                if think and thinking is not None:
                    assistant["thinking"] = _bounded_text(
                        thinking, "thinking", 4_194_304,
                    )
                if normalized_calls:
                    assistant["tool_calls"] = normalized_calls
                messages.append(assistant)

                if not normalized_calls:
                    result = content
                    if think and assistant.get("thinking"):
                        result = f"<think>\n{assistant['thinking']}\n</think>\n\n{result}"
                    return io.NodeOutput(result)

                for call in normalized_calls:
                    call_name = call["name"]
                    descriptor = tools_by_name.get(call_name)
                    if descriptor is None:
                        tool_result = f"Error: Tool {call_name} not found."
                    else:
                        try:
                            arguments = call["arguments"]
                            if set(arguments) != {"query"}:
                                raise ValueError("web-search tool accepts only query")
                            query = _bounded_text(
                                arguments["query"], "web-search query", 16_384,
                            ).strip()
                            if not query:
                                raise ValueError("web-search query must not be empty")
                            results = await sdk.ctx().integrations.call("web", "search", query=query, provider_profile=descriptor["provider_profile"], limit=descriptor["max_results"], vendor_options=None)
                            if not results:
                                tool_result = f"No results found for '{query}'."
                            elif descriptor["provider_profile"] == "ollama":
                                snippets = [
                                    f"• {item['title']}\n  {item['url']}\n  {item['snippet']}"
                                    for item in results
                                ]
                                tool_result = "Web Search Results:\n\n" + "\n\n".join(snippets)
                            else:
                                tool_result = (
                                    "Web Search Results (DuckDuckGo):\n- "
                                    + "\n- ".join(item["snippet"] for item in results)
                                )
                        except Exception as error:
                            tool_result = f"Error executing tool {call_name}: {error}"
                    messages.append({
                        "role": "tool",
                        "name": call_name,
                        "content": _bounded_text(tool_result, "tool result", 262_144),
                    })
            return io.NodeOutput(
                "Error: Maximum iterations reached without a final answer."
            )
        except Exception as error:
            return io.NodeOutput(f"Error: {error}")


NODE_CLASS_MAPPINGS = {
    "OllamaImageDescriber": OllamaImageDescriber,
    "OllamaImageCaptioner": OllamaImageCaptioner,
    "OllamaTextDescriber": OllamaTextDescriber,
    "OllamaVideoDescriber": OllamaVideoDescriber,
    "OllamaAgent": OllamaAgent,
    "OllamaToolCombine": OllamaToolCombine,
    "OllamaTool_WebSearch": OllamaTool_WebSearch,
    "OllamaTool_FileSearch": OllamaTool_FileSearch,
    "OllamaTool_PythonCode": OllamaTool_PythonCode,
    "TextTransformer": TextTransformer,
    "InputText": InputText,
    "OllamaCaptionerExtraOptions": OllamaCaptionerExtraOptions,
    "JsonPropertyExtractorNode": JsonPropertyExtractorNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


class OllamaDescriberExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OllamaDescriberExtension",
]
