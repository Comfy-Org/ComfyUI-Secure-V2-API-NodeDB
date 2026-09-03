"""Secure Nodes V2 implementation of comfyui-ollama.

Prompt construction, option filtering, context chaining, and conversation
history remain pack-owned.  The host sees only three bounded Ollama operations
through ``ctx.integrations.call("ollama", ...)``; the pack never receives a
socket, client, credential, filesystem path, or raw image tensor.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import json
import re
from typing import Any

from comfy_api.latest import ComfyExtension, io, sdk


OLLAMA_OPTIONS = io.Custom("OLLAMA_OPTIONS")
OLLAMA_CONNECTIVITY = io.Custom("OLLAMA_CONNECTIVITY")
OLLAMA_CONTEXT = io.Custom("OLLAMA_CONTEXT")
OLLAMA_META = io.Custom("OLLAMA_META")
OLLAMA_HISTORY = io.Custom("OLLAMA_HISTORY")

_DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
_CONTEXT_FOLDER = "ollama_contexts"
_MAX_CONTEXT_TOKENS = 131_072
_MAX_PROMPT_CHARS = 262_144
_MAX_CHAT_SESSIONS = 512
_MAX_CHAT_MESSAGES = 256

_LOOPBACK_ENDPOINT = re.compile(
    r"^http://(?:127\.0\.0\.1|localhost|\[::1\]):11434$",
    re.IGNORECASE,
)
_NAMED_ENDPOINT = re.compile(r"^ollama://[a-z0-9][a-z0-9._-]{0,63}$")
_SAFE_CONTEXT_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_SAFE_SESSION_KEY = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_THINKING_BLOCKS = re.compile(
    r"<(?:think|thinking)>.*?</(?:think|thinking)>\s*",
    flags=re.DOTALL | re.IGNORECASE,
)

_OPTION_NAMES = (
    "mirostat",
    "mirostat_eta",
    "mirostat_tau",
    "num_ctx",
    "repeat_last_n",
    "repeat_penalty",
    "temperature",
    "seed",
    "stop",
    "tfs_z",
    "num_predict",
    "top_k",
    "top_p",
    "min_p",
)


def _filter_enabled_options(
    options: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the legacy option payload after applying its enable switches."""
    if not options:
        return None
    filtered = {
        name: options[name]
        for name in _OPTION_NAMES
        if options.get(f"enable_{name}", False) and name in options
    }
    return filtered or None


def _strip_thinking(text: str) -> str:
    return _THINKING_BLOCKS.sub("", str(text)).strip()


def _bounded_text(value: Any, field_name: str) -> str:
    text = str(value or "")
    if len(text) > _MAX_PROMPT_CHARS or "\x00" in text:
        raise ValueError(
            f"{field_name} must contain at most {_MAX_PROMPT_CHARS} "
            "characters and no NUL"
        )
    return text


def _endpoint(value: Any) -> str:
    endpoint = str(value or _DEFAULT_ENDPOINT).strip()
    match = _LOOPBACK_ENDPOINT.fullmatch(endpoint)
    if match:
        return endpoint
    if _NAMED_ENDPOINT.fullmatch(endpoint):
        return endpoint
    raise ValueError(
        "Ollama endpoints must be loopback origins or host-configured "
        "ollama:// profiles"
    )


def _model(value: Any) -> str:
    model = str(value or "").strip()
    if not model or len(model) > 256 or "\x00" in model:
        raise ValueError("Ollama model must be 1..256 characters with no NUL")
    return model


def _format(value: Any) -> str:
    value = str(value or "")
    if value in ("", "text"):
        return ""
    if value == "json":
        return "json"
    raise ValueError("Ollama format must be text or json")


def _keep_alive(connectivity: dict[str, Any]) -> tuple[int, str]:
    value = connectivity.get("keep_alive", 5)
    unit = str(connectivity.get("keep_alive_unit", "minutes"))
    if type(value) is not int or not -1 <= value <= 120:
        raise ValueError("Ollama keep_alive must be an integer in [-1, 120]")
    if unit not in ("minutes", "hours"):
        raise ValueError("Ollama keep_alive_unit must be minutes or hours")
    return value, unit


def _connection(connectivity: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(connectivity, dict):
        raise ValueError("Ollama connectivity is required")
    keep_alive, keep_alive_unit = _keep_alive(connectivity)
    return {
        "url": _endpoint(connectivity.get("url")),
        "model": _model(connectivity.get("model")),
        "keep_alive": keep_alive,
        "keep_alive_unit": keep_alive_unit,
    }


def _merged_meta(
    connectivity: dict[str, Any] | None,
    options: dict[str, Any] | None,
    meta: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(meta or {})
    if connectivity is not None:
        merged["connectivity"] = connectivity
    if options is not None:
        merged["options"] = options
    elif "options" not in merged:
        merged["options"] = None
    merged["connectivity"] = _connection(merged.get("connectivity"))
    if merged["options"] is not None and not isinstance(
        merged["options"], dict
    ):
        raise TypeError("Ollama options must be a mapping")
    return merged


def _context_tokens(value: Any) -> list[int] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = [part.strip() for part in value.split(",") if part.strip()]
        except Exception as error:
            raise ValueError("Ollama context is not a comma-separated token list") from error
    if not isinstance(value, (list, tuple)):
        raise TypeError("Ollama context must be a token list or comma string")
    if len(value) > _MAX_CONTEXT_TOKENS:
        raise ValueError("Ollama context exceeds the 131072-token limit")
    tokens: list[int] = []
    for token in value:
        if isinstance(token, bool):
            raise ValueError("Ollama context tokens must be integers")
        try:
            parsed = int(token)
        except (TypeError, ValueError) as error:
            raise ValueError("Ollama context tokens must be integers") from error
        if not 0 <= parsed <= 2**31 - 1:
            raise ValueError("Ollama context token is outside uint31")
        tokens.append(parsed)
    return tokens


def _context_filename(value: Any) -> str:
    name = str(value or "context").strip().replace("\\", "/").split("/")[-1]
    if name.lower().endswith((".png", ".json")):
        name = name.rsplit(".", 1)[0]
    name = _SAFE_CONTEXT_NAME.sub("_", name).strip("._-") or "context"
    return f"{_CONTEXT_FOLDER}/{name[:96]}.json"


def _validate_image_ref(images: Any) -> sdk.ImageRef | None:
    if images is None:
        return None
    if not isinstance(images, sdk.ImageRef):
        raise TypeError("images must be an IMAGE ref")
    return images


def _response(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise TypeError("Ollama integration returned a non-object response")
    return response


def _response_context(response: dict[str, Any]) -> list[int]:
    return _context_tokens(response.get("context")) or []


def _cache_set(cache: OrderedDict[str, Any], key: str, value: Any, limit: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)


_GENERATE_CONTEXTS: OrderedDict[str, list[int]] = OrderedDict()


@dataclass
class ChatSession:
    messages: list[dict[str, str]] = field(default_factory=list)
    model: str = ""


_CHAT_SESSIONS: OrderedDict[str, ChatSession] = OrderedDict()


def _session_key(history: Any, unique_id: Any) -> str:
    value = str(history if history not in (None, "") else unique_id or "default")
    if not _SAFE_SESSION_KEY.fullmatch(value):
        raise ValueError("Ollama history id must be a short opaque identifier")
    return value


def _trim_messages(messages: list[dict[str, str]]) -> None:
    if len(messages) <= _MAX_CHAT_MESSAGES:
        return
    system = (
        messages[0]
        if messages and messages[0].get("role") == "system"
        else None
    )
    keep = messages[-(_MAX_CHAT_MESSAGES - (1 if system else 0)) :]
    messages[:] = ([system] if system else []) + keep


class OllamaSaveContext(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("output",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaSaveContext",
            display_name="Ollama Save Context",
            category="Ollama",
            is_output_node=True,
            inputs=[
                OLLAMA_CONTEXT.Input("context"),
                io.String.Input("filename", default="context"),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, context=None, filename="context") -> io.NodeOutput:
        tokens = _context_tokens(context) or []
        logical_name = _context_filename(filename)
        body = json.dumps(
            {"format": "ollama-context-v2", "context": tokens},
            separators=(",", ":"),
            sort_keys=True,
        )
        await sdk.ctx().output.write_text(
            body,
            logical_name,
            folder="output",
            mode="overwrite",
        )
        return io.NodeOutput(
            ui={"context": tokens, "context_file": logical_name}
        )


class OllamaLoadContext(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaLoadContext",
            display_name="Ollama Load Context",
            category="Ollama",
            inputs=[io.String.Input("context_file", default="context.json")],
            outputs=[OLLAMA_CONTEXT.Output("context")],
        )

    @classmethod
    async def execute(cls, context_file="context.json") -> io.NodeOutput:
        logical_name = _context_filename(context_file)
        ref = await sdk.ctx().assets.resolve("output", logical_name)
        data = await sdk.ctx().assets.read_bytes(ref)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("saved Ollama context exceeds 2 MiB")
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("saved Ollama context is not valid JSON") from error
        if not isinstance(document, dict) or document.get("format") != "ollama-context-v2":
            raise ValueError("saved Ollama context has an unknown format")
        tokens = _context_tokens(document.get("context")) or []
        return io.NodeOutput(tokens)


class OllamaOptionsV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaOptionsV2",
            display_name="Ollama Options",
            category="Ollama",
            description=(
                "Advanced Ollama inference options. An option is sent only "
                "when its matching enable switch is on."
            ),
            inputs=[
                io.Boolean.Input("enable_mirostat", default=False),
                io.Int.Input("mirostat", default=0, min=0, max=2, step=1),
                io.Boolean.Input("enable_mirostat_eta", default=False),
                io.Float.Input("mirostat_eta", default=0.1, min=0, step=0.1),
                io.Boolean.Input("enable_mirostat_tau", default=False),
                io.Float.Input("mirostat_tau", default=5.0, min=0, step=0.1),
                io.Boolean.Input("enable_num_ctx", default=False),
                io.Int.Input("num_ctx", default=2048, min=0, max=2**31, step=1),
                io.Boolean.Input("enable_repeat_last_n", default=False),
                io.Int.Input("repeat_last_n", default=64, min=-1, max=64, step=1),
                io.Boolean.Input("enable_repeat_penalty", default=False),
                io.Float.Input(
                    "repeat_penalty", default=1.1, min=0, max=2, step=0.05
                ),
                io.Boolean.Input("enable_temperature", default=False),
                io.Float.Input(
                    "temperature", default=0.8, min=-10, max=10, step=0.05
                ),
                io.Boolean.Input("enable_seed", default=False),
                io.Int.Input("seed", default=1, min=0, max=2**31, step=1),
                io.Boolean.Input("enable_stop", default=False),
                io.String.Input("stop", default=""),
                io.Boolean.Input("enable_tfs_z", default=False),
                io.Float.Input("tfs_z", default=1, min=1, max=1000, step=0.05),
                io.Boolean.Input("enable_num_predict", default=False),
                io.Int.Input(
                    "num_predict", default=-1, min=-2, max=2048, step=1
                ),
                io.Boolean.Input("enable_top_k", default=False),
                io.Int.Input("top_k", default=40, min=0, max=100, step=1),
                io.Boolean.Input("enable_top_p", default=False),
                io.Float.Input("top_p", default=0.9, min=0, max=1, step=0.05),
                io.Boolean.Input("enable_min_p", default=False),
                io.Float.Input("min_p", default=0.0, min=0, max=1, step=0.05),
                io.Boolean.Input("debug", default=False),
            ],
            outputs=[OLLAMA_OPTIONS.Output("options")],
        )

    @classmethod
    async def execute(cls, **kwargs) -> io.NodeOutput:
        return io.NodeOutput(dict(kwargs))


class OllamaConnectivityV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaConnectivityV2",
            display_name="Ollama Connectivity",
            category="Ollama",
            description=(
                "Select a loopback Ollama daemon or an administrator-defined "
                "ollama:// endpoint profile and one of its models."
            ),
            inputs=[
                io.String.Input("url", default=_DEFAULT_ENDPOINT),
                io.Combo.Input("model", options=[""], default=""),
                io.Int.Input("keep_alive", default=5, min=-1, max=120, step=1),
                io.Combo.Input(
                    "keep_alive_unit",
                    options=["minutes", "hours"],
                    default="minutes",
                ),
            ],
            outputs=[OLLAMA_CONNECTIVITY.Output("connection")],
        )

    @classmethod
    async def execute(
        cls, url, model, keep_alive=5, keep_alive_unit="minutes"
    ) -> io.NodeOutput:
        return io.NodeOutput(
            _connection(
                {
                    "url": url,
                    "model": model,
                    "keep_alive": keep_alive,
                    "keep_alive_unit": keep_alive_unit,
                }
            )
        )


class OllamaGenerateV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaGenerateV2",
            display_name="Ollama Generate",
            category="Ollama",
            description=(
                "Ollama text or vision generation with optional chained "
                "context, metadata, thinking, and advanced options."
            ),
            inputs=[
                io.String.Input(
                    "system", multiline=True, default="You are an AI artist."
                ),
                io.String.Input(
                    "prompt", multiline=True, default="What is art?"
                ),
                io.Boolean.Input("think", default=False),
                io.Boolean.Input("keep_context", default=False),
                io.Combo.Input(
                    "format", options=["text", "json"], default="text"
                ),
                OLLAMA_CONNECTIVITY.Input("connectivity", optional=True),
                OLLAMA_OPTIONS.Input("options", optional=True),
                io.Image.Input("images", optional=True),
                OLLAMA_CONTEXT.Input("context", optional=True),
                OLLAMA_META.Input("meta", optional=True),
            ],
            outputs=[
                io.String.Output("result"),
                io.String.Output("thinking"),
                OLLAMA_CONTEXT.Output("context"),
                OLLAMA_META.Output("meta"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls,
        system,
        prompt,
        think,
        keep_context,
        format,
        connectivity=None,
        options=None,
        images=None,
        context=None,
        meta=None,
        unique_id=None,
    ) -> io.NodeOutput:
        merged = _merged_meta(connectivity, options, meta)
        connection = merged["connectivity"]
        node_key = _session_key(None, unique_id)
        tokens = _context_tokens(context)
        if keep_context and tokens is None:
            tokens = _GENERATE_CONTEXTS.get(node_key)
        response = _response(
            await sdk.ctx().integrations.call("ollama", "generate", endpoint=connection["url"], model=connection["model"], system=_bounded_text(system, "system"), prompt=_bounded_text(prompt, "prompt"), images=_validate_image_ref(images), context=tokens, think=bool(think), options=_filter_enabled_options(merged.get("options")), keep_alive=connection["keep_alive"], keep_alive_unit=connection["keep_alive_unit"], format=_format(format))
        )
        result = _bounded_text(response.get("response"), "response")
        thinking = (
            _bounded_text(response.get("thinking"), "thinking")
            if think
            else ""
        )
        output_context = _response_context(response)
        if keep_context:
            _cache_set(
                _GENERATE_CONTEXTS,
                node_key,
                output_context,
                _MAX_CHAT_SESSIONS,
            )
        return io.NodeOutput(result, thinking, output_context, merged)


class OllamaChat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaChat",
            display_name="Ollama Chat",
            category="Ollama",
            description=(
                "Multi-turn Ollama chat with bounded pack-owned history and "
                "optional vision input."
            ),
            inputs=[
                io.String.Input(
                    "system", multiline=True, default="You are an AI artist."
                ),
                io.String.Input(
                    "prompt", multiline=True, default="What is art?"
                ),
                io.Boolean.Input("think", default=False),
                io.Combo.Input(
                    "format", options=["text", "json"], default="text"
                ),
                OLLAMA_CONNECTIVITY.Input("connectivity", optional=True),
                OLLAMA_OPTIONS.Input("options", optional=True),
                io.Image.Input("images", optional=True),
                OLLAMA_META.Input("meta", optional=True),
                OLLAMA_HISTORY.Input("history", optional=True),
                io.Boolean.Input("reset_session", default=False, optional=True),
            ],
            outputs=[
                io.String.Output("result"),
                io.String.Output("thinking"),
                OLLAMA_META.Output("meta"),
                OLLAMA_HISTORY.Output("history"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls,
        system,
        prompt,
        think,
        format,
        unique_id,
        connectivity=None,
        options=None,
        images=None,
        meta=None,
        history=None,
        reset_session=False,
    ) -> io.NodeOutput:
        merged = _merged_meta(connectivity, options, meta)
        connection = merged["connectivity"]
        key = _session_key(history, unique_id)
        if reset_session:
            _CHAT_SESSIONS.pop(key, None)
        session = _CHAT_SESSIONS.get(key)
        if session is None:
            session = ChatSession(model=connection["model"])
            _cache_set(_CHAT_SESSIONS, key, session, _MAX_CHAT_SESSIONS)
        else:
            _CHAT_SESSIONS.move_to_end(key)

        system_text = _bounded_text(system, "system")
        prompt_text = _bounded_text(prompt, "prompt")
        if system_text:
            if session.messages and session.messages[0].get("role") == "system":
                session.messages[0] = {"role": "system", "content": system_text}
            else:
                session.messages.insert(
                    0, {"role": "system", "content": system_text}
                )
        session.messages.append({"role": "user", "content": prompt_text})
        _trim_messages(session.messages)
        messages = [dict(message) for message in session.messages]

        response = _response(
            await sdk.ctx().integrations.call("ollama", "chat", endpoint=connection["url"], model=connection["model"], messages=messages, images=_validate_image_ref(images), think=bool(think), options=_filter_enabled_options(merged.get("options")), keep_alive=connection["keep_alive"], keep_alive_unit=connection["keep_alive_unit"], format=_format(format))
        )
        result = _bounded_text(response.get("response"), "response")
        thinking = (
            _bounded_text(response.get("thinking"), "thinking")
            if think
            else ""
        )
        session.messages.append({"role": "assistant", "content": result})
        _trim_messages(session.messages)
        return io.NodeOutput(result, thinking, merged, key)


NODE_CLASS_MAPPINGS = {
    "OllamaOptionsV2": OllamaOptionsV2,
    "OllamaConnectivityV2": OllamaConnectivityV2,
    "OllamaGenerateV2": OllamaGenerateV2,
    "OllamaSaveContext": OllamaSaveContext,
    "OllamaLoadContext": OllamaLoadContext,
    "OllamaChat": OllamaChat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


class OllamaV2Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


__all__ = [
    "ChatSession",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OllamaChat",
    "OllamaConnectivityV2",
    "OllamaGenerateV2",
    "OllamaLoadContext",
    "OllamaOptionsV2",
    "OllamaSaveContext",
    "OllamaV2Extension",
]
