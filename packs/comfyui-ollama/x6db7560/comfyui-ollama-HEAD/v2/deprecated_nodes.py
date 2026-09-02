"""Secure compatibility implementations for the three deprecated V1 nodes."""
from __future__ import annotations

from collections import OrderedDict

from comfy_api.latest import io, sdk

from .CompfyuiOllama import (
    _DEFAULT_ENDPOINT,
    _MAX_CHAT_SESSIONS,
    _bounded_text,
    _cache_set,
    _context_tokens,
    _endpoint,
    _format,
    _model,
    _response,
    _response_context,
    _session_key,
    _strip_thinking,
    _validate_image_ref,
)


_ADVANCED_CONTEXTS: OrderedDict[str, list[int]] = OrderedDict()


class OllamaVision(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaVision",
            display_name="Ollama Vision (deprecated)",
            category="Ollama",
            is_deprecated=True,
            inputs=[
                io.Image.Input("images"),
                io.String.Input(
                    "query", multiline=True, default="describe the image"
                ),
                io.Combo.Input(
                    "debug", options=["enable", "disable"], default="enable"
                ),
                io.String.Input("url", default=_DEFAULT_ENDPOINT),
                io.Combo.Input("model", options=[""], default=""),
                io.Int.Input("keep_alive", default=5, min=-1, max=60, step=1),
                io.Combo.Input(
                    "format", options=["text", "json", ""], default="text"
                ),
                io.Int.Input("seed", default=1, min=0, max=2**31, step=1),
            ],
            outputs=[io.String.Output("description")],
        )

    @classmethod
    async def execute(
        cls, images, query, debug, url, model, seed, keep_alive, format
    ) -> io.NodeOutput:
        del debug
        response = _response(
            await sdk.ctx().integrations.ollama.generate(
                endpoint=_endpoint(url),
                model=_model(model),
                system="",
                prompt=_bounded_text(query, "query"),
                images=_validate_image_ref(images),
                context=None,
                think=False,
                options={"seed": int(seed)},
                keep_alive=int(keep_alive),
                keep_alive_unit="minutes",
                format=_format(format),
            )
        )
        return io.NodeOutput(_bounded_text(response.get("response"), "response"))


class OllamaGenerate(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaGenerate",
            display_name="Ollama Generate (deprecated)",
            category="Ollama",
            is_deprecated=True,
            inputs=[
                io.String.Input(
                    "prompt", multiline=True, default="What is Art?"
                ),
                io.Combo.Input(
                    "debug", options=["enable", "disable"], default="enable"
                ),
                io.String.Input("url", default=_DEFAULT_ENDPOINT),
                io.Combo.Input("model", options=[""], default=""),
                io.Int.Input("keep_alive", default=5, min=-1, max=60, step=1),
                io.Combo.Input(
                    "format", options=["text", "json", ""], default="text"
                ),
                io.Boolean.Input("filter_thinking", default=True),
            ],
            outputs=[io.String.Output("response")],
        )

    @classmethod
    async def execute(
        cls, prompt, debug, url, model, keep_alive, format, filter_thinking
    ) -> io.NodeOutput:
        del debug
        response = _response(
            await sdk.ctx().integrations.ollama.generate(
                endpoint=_endpoint(url),
                model=_model(model),
                system="",
                prompt=_bounded_text(prompt, "prompt"),
                images=None,
                context=None,
                think=False,
                options=None,
                keep_alive=int(keep_alive),
                keep_alive_unit="minutes",
                format=_format(format),
            )
        )
        text = _bounded_text(response.get("response"), "response")
        if filter_thinking:
            text = _strip_thinking(text)
        return io.NodeOutput(text)


class OllamaGenerateAdvance(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("integrations.ollama",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OllamaGenerateAdvance",
            display_name="Ollama Generate Advance (deprecated)",
            category="Ollama",
            is_deprecated=True,
            inputs=[
                io.String.Input(
                    "prompt", multiline=True, default="What is Art?"
                ),
                io.Boolean.Input("debug", default=False),
                io.String.Input("url", default=_DEFAULT_ENDPOINT),
                io.Combo.Input("model", options=[""], default=""),
                io.String.Input(
                    "system",
                    multiline=True,
                    default=(
                        "You are an art expert, gracefully describing your "
                        "knowledge in art domain."
                    ),
                ),
                io.Int.Input("seed", default=1, min=0, max=2**31, step=1),
                io.Int.Input("top_k", default=40, min=0, max=100, step=1),
                io.Float.Input("top_p", default=0.9, min=0, max=1, step=0.05),
                io.Float.Input(
                    "temperature", default=0.8, min=0, max=1, step=0.05
                ),
                io.Int.Input(
                    "num_predict", default=-1, min=-2, max=2048, step=1
                ),
                io.Float.Input("tfs_z", default=1, min=1, max=1000, step=0.05),
                io.Int.Input("keep_alive", default=5, min=-1, max=60, step=1),
                io.Boolean.Input("keep_context", default=False),
                io.Combo.Input(
                    "format", options=["text", "json", ""], default="text"
                ),
                io.Boolean.Input("filter_thinking", default=True),
                io.String.Input("context", force_input=True, optional=True),
            ],
            outputs=[
                io.String.Output("response"),
                io.String.Output("context"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls,
        prompt,
        debug,
        url,
        model,
        system,
        seed,
        top_k,
        top_p,
        temperature,
        num_predict,
        tfs_z,
        keep_alive,
        keep_context,
        format,
        filter_thinking,
        context=None,
        unique_id=None,
    ) -> io.NodeOutput:
        del debug
        node_key = _session_key(None, unique_id)
        tokens = _context_tokens(context)
        if keep_context and tokens is None:
            tokens = _ADVANCED_CONTEXTS.get(node_key)
        options = {
            "seed": int(seed),
            "top_k": int(top_k),
            "top_p": float(top_p),
            "temperature": float(temperature),
            "num_predict": int(num_predict),
            "tfs_z": float(tfs_z),
        }
        response = _response(
            await sdk.ctx().integrations.ollama.generate(
                endpoint=_endpoint(url),
                model=_model(model),
                system=_bounded_text(system, "system"),
                prompt=_bounded_text(prompt, "prompt"),
                images=None,
                context=tokens,
                think=False,
                options=options,
                keep_alive=int(keep_alive),
                keep_alive_unit="minutes",
                format=_format(format),
            )
        )
        output_context = _response_context(response)
        if keep_context:
            _cache_set(
                _ADVANCED_CONTEXTS,
                node_key,
                output_context,
                _MAX_CHAT_SESSIONS,
            )
        text = _bounded_text(response.get("response"), "response")
        if filter_thinking:
            text = _strip_thinking(text)
        return io.NodeOutput(
            text, ",".join(str(token) for token in output_context)
        )


NODE_CLASS_MAPPINGS = {
    "OllamaVision": OllamaVision,
    "OllamaGenerate": OllamaGenerate,
    "OllamaGenerateAdvance": OllamaGenerateAdvance,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OllamaGenerate",
    "OllamaGenerateAdvance",
    "OllamaVision",
]
