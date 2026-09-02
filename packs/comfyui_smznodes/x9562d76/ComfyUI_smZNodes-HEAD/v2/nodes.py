"""Secure Nodes V2 implementations for the two pinned smZNodes IDs.

The prompt grammar, emphasis arithmetic, and schedule construction remain in
this pack.  Live CLIP objects stay host-owned behind ``ClipRef`` and only the
two bounded questions needed by the weighted encoders cross the boundary.
"""
from __future__ import annotations

import logging

from comfy_api.latest import ComfyExtension, io, sdk
from typing_extensions import override

from . import smZNodes
from .modules.shared import logger, opts_default


MAX_RESOLUTION = 16384
PARSERS = ["comfy", "comfy++", "A1111", "full", "compel", "fixed attention"]


def _text_input(name: str, **kwargs):
    return io.String.Input(name, multiline=True, dynamic_prompts=True, **kwargs)


async def _combine(parts):
    result = None
    for part in parts:
        result = part if result is None else await result.combine(part)
    if result is None:
        raise RuntimeError("smZ CLIPTextEncode produced no conditioning")
    return result


async def _native_sdxl(clip, *, text, text_g, text_l, ascore, width, height,
                       crop_w, crop_h, target_width, target_height):
    """Use only token component shape to select base/refiner behavior."""
    tokens = await clip.tokenize(text)
    components = set(tokens)
    if components == {"l", "g"}:
        tokens_g = await clip.tokenize(text_g)
        tokens_l = await clip.tokenize(text_l)
        tokens = tokens_g
        tokens["l"] = tokens_l["l"]
        empty = await clip.tokenize("")
        while len(tokens["l"]) < len(tokens["g"]):
            tokens["l"] += empty["l"]
        while len(tokens["g"]) < len(tokens["l"]):
            tokens["g"] += empty["g"]
        return await clip.encode_from_tokens_scheduled(tokens, add_dict={
            "width": int(width), "height": int(height),
            "crop_w": int(crop_w), "crop_h": int(crop_h),
            "target_width": int(target_width),
            "target_height": int(target_height),
        })
    if components == {"g"}:
        raise smZNodes.UnsupportedOption(
            "a CLIP-G-only tokenizer is ambiguous between SDXL Refiner and "
            "other model families; the closed CLIP API needs a bounded family "
            "tag before with_SDXL can be applied exactly"
        )
    # ``with_SDXL`` was a no-op for non-SDXL encoders at the pinned source.
    return await clip.encode(text)


async def _raw_conditioning(tensor, pooled=None):
    metadata = {}
    if pooled is not None:
        metadata["pooled_output"] = pooled
    return await sdk.CondRef.from_value([[tensor, metadata]])


async def _weighted_single(clip, opts, texts_by_component):
    engines = await smZNodes.build_text_processing_engines(clip, opts)
    unknown = set(texts_by_component) - set(engines)
    if unknown:
        raise smZNodes.UnsupportedOption(
            f"this CLIP has no weighted encoder for {sorted(unknown)}"
        )
    outputs = {}
    for component, engine in engines.items():
        texts = list(texts_by_component.get(component, [""]))
        await engine.prepare(texts)
        outputs[component] = engine.encode_token_weights(texts)
    value = smZNodes.compose_components(outputs)
    return value["cond"], value.get("pooled_output")


async def _comfy_plus(clip, opts, text):
    tokens = await clip.tokenize(text)
    engines = await smZNodes.build_text_processing_engines(clip, opts)
    if set(tokens) != set(engines):
        raise smZNodes.UnsupportedOption(
            "Comfy++ needs a closed component encoder for every tokenizer "
            f"component; tokenizer={sorted(tokens)}, encoders={sorted(engines)}"
        )
    outputs = {}
    for component, engine in engines.items():
        pairs = tokens[component]
        await engine.prepare_token_pairs(pairs)
        outputs[component] = engine.encode_token_weights(pairs)
    value = smZNodes.compose_components(outputs)
    return await _raw_conditioning(
        value["cond"], value.get("pooled_output")
    )


async def _scheduled_weighted(clip, opts, text, steps):
    if opts.multi_conditioning and len(smZNodes.re_AND.split(text)) > 1:
        raise smZNodes.UnsupportedOption(
            "weighted multi-conditioning needs smZNodes' composable CFG "
            "sampling function; core conditioning strength is not the same "
            "normalization, so this path fails closed"
        )
    texts = smZNodes.scheduled_texts([text], steps, False)
    engines = await smZNodes.build_text_processing_engines(clip, opts)
    model = await smZNodes.encode_texts(engines, texts)
    slices = smZNodes.get_learned_conditioning(model, [text], steps, False)
    parts = []
    for item in slices:
        cond = await _raw_conditioning(item.tensor, item.pooled)
        if item.start != 0.0 or item.end != 1.0:
            cond = await cond.with_timestep_range(item.start, item.end)
        parts.append(cond)
    return await _combine(parts)


class smZ_CLIPTextEncode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="smZ CLIPTextEncode",
            display_name="CLIP Text Encode++",
            category="conditioning",
            description=(
                "smZ prompt parsers and scheduling using bounded CLIP ops. "
                "See SECURE_CONVERSION.md for fail-closed model features."
            ),
            inputs=[
                _text_input("text"),
                io.Clip.Input("clip"),
                io.Combo.Input("parser", options=PARSERS, default="comfy"),
                io.Boolean.Input("mean_normalization", default=True),
                io.Boolean.Input("multi_conditioning", default=True),
                io.Boolean.Input("use_old_emphasis_implementation", default=False),
                io.Boolean.Input("with_SDXL", default=False),
                io.Float.Input("ascore", default=6.0, min=0.0, max=1000.0, step=0.01),
                io.Int.Input("width", default=1024, min=0, max=MAX_RESOLUTION),
                io.Int.Input("height", default=1024, min=0, max=MAX_RESOLUTION),
                io.Int.Input("crop_w", default=0, min=0, max=MAX_RESOLUTION),
                io.Int.Input("crop_h", default=0, min=0, max=MAX_RESOLUTION),
                io.Int.Input("target_width", default=1024, min=0, max=MAX_RESOLUTION),
                io.Int.Input("target_height", default=1024, min=0, max=MAX_RESOLUTION),
                _text_input("text_g", placeholder="CLIP_G"),
                _text_input("text_l", placeholder="CLIP_L"),
                io.Int.Input(
                    "smZ_steps", default=1, min=1,
                    max=0xffffffffffffffff, optional=True,
                ),
            ],
            outputs=[io.Conditioning.Output()],
        )

    @classmethod
    async def execute(
        cls, text, clip, parser, mean_normalization, multi_conditioning,
        use_old_emphasis_implementation, with_SDXL, ascore, width, height,
        crop_w, crop_h, target_width, target_height, text_g, text_l,
        smZ_steps=1,
    ):
        opts = opts_default.clone()
        opts.prompt_mean_norm = bool(mean_normalization)
        opts.multi_conditioning = bool(multi_conditioning)
        opts.use_old_emphasis_implementation = bool(
            use_old_emphasis_implementation
        )
        opts.prompt_attention = {
            "full": "Full parser", "compel": "Compel parser",
            "A1111": "A1111 parser", "fixed attention": "Fixed attention",
            "comfy++": "Comfy++ parser",
        }.get(str(parser), "Comfy parser")

        if opts.use_old_emphasis_implementation and parser != "comfy":
            smZNodes._unsupported_old_emphasis([str(text)])

        if parser == "comfy":
            if with_SDXL:
                components = set(await clip.tokenize(""))
                cond = await _native_sdxl(
                    clip, text=str(text), text_g=str(text_g), text_l=str(text_l),
                    ascore=ascore, width=width, height=height, crop_w=crop_w,
                    crop_h=crop_h, target_width=target_width,
                    target_height=target_height,
                )
                if components == {"l", "g"} and multi_conditioning:
                    cond = await _combine([
                        cond for _part in smZNodes.re_AND.split(str(text))
                    ])
                return io.NodeOutput(cond)
            prompts = smZNodes.re_AND.split(str(text)) if multi_conditioning else [str(text)]
            return io.NodeOutput(await _combine([
                await clip.encode(prompt) for prompt in prompts
            ]))

        if parser == "comfy++":
            if with_SDXL:
                components = set(await clip.tokenize(""))
                if components == {"l", "g"}:
                    tensor, pooled = await _weighted_single(
                        clip, opts, {"g": [str(text_g)], "l": [str(text_l)]}
                    )
                    cond = await _raw_conditioning(tensor, pooled)
                    cond = await cond.with_metadata(
                        width=int(width), height=int(height),
                        crop_w=int(crop_w), crop_h=int(crop_h),
                        target_width=int(target_width),
                        target_height=int(target_height),
                    )
                    return io.NodeOutput(cond)
                if components == {"g"}:
                    raise smZNodes.UnsupportedOption(
                        "with_SDXL cannot distinguish an SDXL Refiner from "
                        "another CLIP-G-only family through the closed API"
                    )
            prompts = smZNodes.re_AND.split(str(text)) if multi_conditioning else [str(text)]
            return io.NodeOutput(await _combine([
                await _comfy_plus(clip, opts, prompt) for prompt in prompts
            ]))

        components = set(await clip.tokenize("")) if with_SDXL else set()
        if components == {"g"}:
            raise smZNodes.UnsupportedOption(
                "with_SDXL cannot distinguish an SDXL Refiner from another "
                "CLIP-G-only family through the closed API"
            )
        if components == {"l", "g"}:
            tensor, pooled = await _weighted_single(
                clip, opts, {"g": [str(text_g)], "l": [str(text_l)]}
            )
            cond = await _raw_conditioning(tensor, pooled)
            cond = await cond.with_metadata(
                width=int(width), height=int(height), crop_w=int(crop_w),
                crop_h=int(crop_h), target_width=int(target_width),
                target_height=int(target_height),
            )
            return io.NodeOutput(cond)

        cond = await _scheduled_weighted(
            clip, opts, str(text), max(1, int(smZ_steps)),
        )
        return io.NodeOutput(cond)


def _heading(name: str, count: int):
    return io.String.Input("ㅤ" * count, default=name, placeholder=name, optional=True)


def _info(name: str, text: str):
    return io.String.Input(name, multiline=True, placeholder=text, optional=True)


def _settings_inputs():
    # IDs and defaults are pinned for workflow compatibility. The prose is
    # deliberately shorter; the exact behavioral ledger lives beside the pack.
    return [
        io.AnyType.Input("*", extra_dict={"forceInput": True}),
        io.String.Input("extra", multiline=True, default='{"show_headings":true,"show_descriptions":false,"mode":"*"}', optional=True),
        _heading("Stable Diffusion", 1),
        _info("info_comma_padding_backtrack", "Prompt word wrap length limit"),
        io.Int.Input("Prompt word wrap length limit", default=20, min=0, max=74, step=1, optional=True),
        io.Boolean.Input("enable_emphasis", default=True, optional=True),
        _info("info_RNG", "Random number generator source"),
        io.Combo.Input("RNG", options=["cpu", "gpu", "nv"], default="cpu", optional=True),
        _heading("Compute Settings", 2),
        _info("info_disable_nan_check", "Disable NaN check"),
        io.Boolean.Input("disable_nan_check", default=True, optional=True),
        _heading("Sampler parameters", 3),
        _info("info_eta_ancestral", "Eta for k-diffusion samplers"),
        io.Float.Input("eta", default=1.0, min=0.0, max=1.0, step=0.01, optional=True),
        _info("info_s_churn", "Sigma churn"),
        io.Float.Input("s_churn", default=0.0, min=0.0, max=100.0, step=0.01, optional=True),
        _info("info_s_tmin", "Sigma tmin"),
        io.Float.Input("s_tmin", default=0.0, min=0.0, max=10.0, step=0.01, optional=True),
        _info("info_s_tmax", "Sigma tmax; zero means infinity"),
        io.Float.Input("s_tmax", default=0.0, min=0.0, max=999.0, step=0.01, optional=True),
        _info("info_s_noise", "Sigma noise"),
        io.Float.Input("s_noise", default=1.0, min=0.0, max=1.1, step=0.001, optional=True),
        _info("info_eta_noise_seed_delta", "Eta noise seed delta"),
        io.Int.Input("ENSD", default=0, min=0, max=0xffffffffffffffff, step=1, optional=True),
        _info("info_skip_early_cond", "Ignore negative prompt during early sampling"),
        io.Float.Input("skip_early_cond", default=0.0, min=0.0, max=1.0, step=0.01, optional=True),
        _info("info_sgm_noise_multiplier", "SGM noise multiplier"),
        io.Boolean.Input("sgm_noise_multiplier", default=True, optional=True),
        _info("info_upcast_sampling", "Upcast sampling"),
        io.Boolean.Input("upcast_sampling", default=True, optional=True),
        _heading("Optimizations", 4),
        _info("info_NGMS", "Negative Guidance minimum sigma"),
        io.Float.Input("NGMS", default=0.0, min=0.0, max=15.0, step=0.01, optional=True),
        _info("info_NGMS_all_steps", "Negative Guidance minimum sigma all steps"),
        io.Boolean.Input("NGMS all steps", default=False, optional=True),
        _info("info_pad_cond_uncond", "Pad prompt and negative prompt"),
        io.Boolean.Input("pad_cond_uncond", default=False, optional=True),
        _info("info_batch_cond_uncond", "Batch conditional and unconditional"),
        io.Boolean.Input("batch_cond_uncond", default=True, optional=True),
        _heading("Compatibility", 5),
        _info("info_use_prev_scheduling", "Previous prompt editing timelines"),
        io.Boolean.Input("Use previous prompt editing timelines", default=True, optional=True),
        _heading("Experimental", 6),
        _info("info_use_CFGDenoiser", "Use the legacy CFGDenoiser"),
        io.Boolean.Input("Use CFGDenoiser", default=False, optional=True),
        _info("info_debug", "Debugging messages"),
        io.Boolean.Input("debug", default=False, label_on="on", label_off="off", optional=True),
    ]


_MODEL_UNSUPPORTED_DEFAULTS = {
    "eta": 1.0, "s_churn": 0.0,
    "s_tmin": 0.0, "s_tmax": 0.0, "s_noise": 1.0,
    "skip_early_cond": 0.0, "sgm_noise_multiplier": True,
    "NGMS": 0.0, "NGMS all steps": False,
}

# These two were exceptional: Settings stored them on a CLIP, the encoder
# copied them into the process-global opts object, and prepare_noise read that
# global later. Storing them on a MODEL had no effect because prepare_noise did
# not inspect model_options.
_CLIP_UNSUPPORTED_DEFAULTS = {"RNG": "cpu", "ENSD": 0}


class smZ_Settings(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="smZ Settings",
            display_name="Settings (smZ)",
            category="advanced",
            description=(
                "Workflow-compatible pass-through. Non-default settings that "
                "depended on forbidden global sampler/noise hooks fail closed."
            ),
            inputs=_settings_inputs(),
            outputs=[io.AnyType.Output("*", tooltip="The unchanged input value.")],
        )

    @classmethod
    async def execute(cls, **kwargs):
        value = kwargs.get("*")
        defaults = (
            _MODEL_UNSUPPORTED_DEFAULTS
            if isinstance(value, sdk.ModelRef)
            else _CLIP_UNSUPPORTED_DEFAULTS
            if isinstance(value, sdk.ClipRef)
            else {}
        )
        changed = [
            name for name, default in defaults.items()
            if kwargs.get(name, default) != default
        ]
        if changed:
            raise smZNodes.UnsupportedOption(
                "these Settings values require the removed process-global "
                f"sampler/noise hooks: {', '.join(changed)}"
            )
        # Upstream returned before changing logger state for wildcard values
        # without a clone method. Model and CLIP were its two meaningful
        # carriers, represented here by their typed refs.
        if isinstance(value, (sdk.ModelRef, sdk.ClipRef)):
            logger.setLevel(
                logging.DEBUG
                if bool(kwargs.get("debug", False)) else logging.INFO
            )
        return io.NodeOutput(value)


NODE_CLASS_MAPPINGS = {
    "smZ CLIPTextEncode": smZ_CLIPTextEncode,
    "smZ Settings": smZ_Settings,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "smZ CLIPTextEncode": "CLIP Text Encode++",
    "smZ Settings": "Settings (smZ)",
}


class smZNodesExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [smZ_CLIPTextEncode, smZ_Settings]


async def comfy_entrypoint():
    return smZNodesExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS",
    "smZ_CLIPTextEncode", "smZ_Settings", "smZNodesExtension",
    "comfy_entrypoint",
]
