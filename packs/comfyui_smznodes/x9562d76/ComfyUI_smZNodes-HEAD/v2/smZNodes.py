"""Prompt scheduling and text-processing orchestration for the V2 mirror.

Upstream's smZNodes.py is, in the main, a set of replacements for core
functions. `register_hooks()` swapped seven of them in place, process-wide and
permanently, for every tenant and every workflow:

  * `comfy.samplers.get_area_and_mult` -- skipped a cond outside its
    prompt-editing step window. NOT NEEDED: core already does this natively.
    `calculate_start_end_timesteps` reads `start_percent` / `end_percent` off
    the cond dict, so `transform_schedules` below emits those instead of
    upstream's private `start_perc` / `end_perc` / `init_steps`.
  * `comfy.samplers.KSampler.sample` -- stashed `sigmas` into `model_options`.
    NOT NEEDED; existed only to feed the hook above.
  * `comfy.samplers.KSAMPLER.sample` -- stashed `sigmas` in a module global,
    and un-did other extensions' noise-sampler hijacks by name. NOT NEEDED,
    and reverting another pack's patches is not a pack's business.
  * `comfy.samplers.sample` -- injected eta / s_churn / s_tmin / s_tmax /
    s_noise into the sampler function. PENDING (D21); see the Settings node.
  * `comfy.samplers.Sampler.max_denoise` -- `sgm_noise_multiplier`.
    PENDING (D21).
  * `comfy.samplers.sampling_function` -- NGMS and skip_early_cond, plus the
    A1111 CFGDenoiser composable-diffusion CFG. PENDING (D21): pack-authored
    per-step tensor math.
  * `comfy.sample.prepare_noise` -- RNG source (cpu/gpu/nv) and ENSD.
    PENDING (D21).

Two more global effects are simply gone, and no replacement is wanted:

  * `CFGDenoiser` reached into its *callers'* stack frames with
    `ctypes.pythonapi.PyFrame_LocalsToFast` to rewrite their locals. Even in a
    trusted process that is not a supported way to compose with the sampler.
  * `PromptServer.instance.add_on_prompt_handler(prompt_handler)` installed a
    server-wide rewriter that walked every submitted prompt, found each
    `smZ CLIPTextEncode`, searched the graph for a downstream sampler and
    wrote that sampler's step count back into the node's `smZ_steps` input. A
    pack cannot read or edit other tenants' prompts. `smZ_steps` remains an
    ordinary optional input, so prompt editing is still available by linking
    or setting it; it is no longer inferred behind the user's back.

Also dropped: `add_custom_samplers()` inserted "dpmpp_2m_alt" into the
process-wide `comfy.samplers.KSampler.SAMPLERS` list and attached its sampler
function to `comfy.k_diffusion.sampling`. A pack cannot extend a server-wide
sampler enum that every tenant reads. Its recurrence is isolated in
`sampler_programs.py` for the bounded custom-sampler broker, but truthful
reachability still needs a declarative sampler-provider registry outside a
prompt-scoped node dispatch.

What DOES live here is upstream's own scheduling math, unchanged, plus the
construction of the per-component text-processing engines that replaces the
`HijackClip` / `HijackClipComfy` context managers.
"""
from __future__ import annotations

import re
import torch
from decimal import Decimal
from typing import NamedTuple

from . import _clipbridge
from .modules.shared import logger
from .modules.text_processing import prompt_parser
from .modules.text_processing.classic_engine import ClassicTextProcessingEngine


class UnsupportedOption(RuntimeError):
    """A selected option has no expression in the closed API."""


def _unsupported_old_emphasis(_texts):
    """Upstream bound `process_texts_past` here for `use_old_emphasis_implementation`.

    That engine reads `self.token_mults`, which upstream built by sweeping the
    tokenizer's entire vocabulary for entries containing brackets, and calls
    `tokenizer.get_vocab()` / `convert_tokens_to_string()` directly. No CLIP
    operation publishes a vocabulary, so the option fails loudly here rather
    than silently applying the new emphasis implementation instead.
    """
    raise UnsupportedOption(
        "use_old_emphasis_implementation needs the text encoder's full token "
        "vocabulary to rebuild its per-token bracket multipliers, and no CLIP "
        "operation publishes a vocabulary"
    )


async def build_text_processing_engines(clip, opts):
    """Replaces `HijackClip`.

    Upstream walked `clip.tokenizer.__dict__` and
    `clip.cond_stage_model.__dict__` looking for any object exposing
    `tokenize_with_weights` / `encode_token_weights`, built an engine per
    component, and then REPLACED those bound methods on the live objects for
    the duration of the encode -- restoring them in a `finally`. Any exception
    between the two, or two encodes racing on one shared CLIP, left core's
    objects patched.

    Here each component gets the same engine, but the engine talks to the host
    over closed ops and nothing on the CLIP is touched, so there is no window
    to restore and no shared object to race on.
    """
    bridges = await _clipbridge.build_bridges(clip)
    emphasis_name = 'Original' if opts.prompt_mean_norm else "No norm"
    engines = {}
    for component, bridge in bridges.items():
        # Upstream chose T5TextProcessingEngine when the component name
        # contained 't5'. `encode_token_weights_component` is defined for the
        # conventional l/g encoders only, so `build_bridges` has already
        # refused a T5 model and only the classic engine can be reached.
        engine = ClassicTextProcessingEngine(
            bridge,
            embedding_key='clip_g' if component == 'g' else 'clip_l',
            emphasis_name=emphasis_name,
        )
        engine.opts = opts
        engine.process_texts_past = _unsupported_old_emphasis
        engines[component] = engine
    return engines


async def encode_texts(engines, texts):
    """Answer every host question this batch of texts needs, then return the
    synchronous callable `prompt_parser.get_learned_conditioning` expects.

    Upstream handed it
    `lambda txt: clip.encode_from_tokens(clip.tokenize(txt), ...)`, which
    reached the hijacked engines through core. The engines are called directly
    here; core's CLIP object is not involved.
    """
    for engine in engines.values():
        await engine.prepare(texts)

    def model(batch):
        outputs = {
            component: engine.encode_token_weights(list(batch))
            for component, engine in engines.items()
        }
        return compose_components(outputs)

    return model


def compose_components(outputs):
    """Combine per-component embeddings the way core's own encoders do.

    `SDXLClipModel.encode_token_weights` concatenates CLIP-L and CLIP-G along
    the feature dimension after cropping both to the shorter sequence, and
    keeps CLIP-G's pooled output. Reproduced exactly so an SDXL prompt encoded
    here matches one encoded by core.
    """
    if "g" in outputs and "l" in outputs:
        l_out, _l_pooled = outputs["l"]
        g_out, g_pooled = outputs["g"]
        cut_to = min(l_out.shape[1], g_out.shape[1])
        cond = torch.cat([l_out[:, :cut_to], g_out[:, :cut_to]], dim=-1)
        pooled = g_pooled
    else:
        component = "g" if "g" in outputs else "l"
        cond, pooled = outputs[component]
    out = {"cond": cond}
    if pooled is not None:
        out["pooled_output"] = pooled
    return out


class ConditioningSlice(NamedTuple):
    tensor: torch.Tensor
    pooled: torch.Tensor | None
    start: float
    end: float


def transform_schedules(steps, schedules, weight=None, with_weight=False):
    end_steps = [schedule.end_at_step for schedule in schedules]
    start_end_pairs = list(zip([0] + end_steps[:-1], end_steps))
    with_prompt_editing = len(schedules) > 1

    def process(schedule, start_step, end_step):
        nonlocal with_prompt_editing
        if weight is not None and with_weight:
            raise UnsupportedOption(
                "composable prompt weights require smZNodes' sampler CFG "
                "formula and cannot be represented as core strength"
            )
        data = schedule.cond
        if not isinstance(data, dict) or "cond" not in data:
            raise TypeError("weighted prompt encoder returned no cond tensor")
        pooled = data.get("pooled_output")
        start = (
            float(Decimal(start_step) / Decimal(steps))
            if with_prompt_editing else 0.0
        )
        end = (
            float(Decimal(end_step) / Decimal(steps))
            if with_prompt_editing else 1.0
        )
        return ConditioningSlice(data["cond"], pooled, start, end)
    return [
        process(schedule, start_step, end_step)
        for schedule, (start_step, end_step) in zip(schedules, start_end_pairs)
    ]


def flatten(nested_list):
    return [item for sublist in nested_list for item in sublist]


def convert_schedules_to_comfy(schedules, steps, multi=False):
    if multi:
        out = [[transform_schedules(steps, x.schedules, x.weight, len(batch)>1) for x in batch] for batch in schedules.batch]
        out = flatten(out)
    else:
        out = [transform_schedules(steps, sublist) for sublist in schedules]
    return flatten(out)


def get_learned_conditioning(model, prompts, steps, multi=False, *args, **kwargs):
    if multi:
        schedules = prompt_parser.get_multicond_learned_conditioning(model, prompts, steps, *args, **kwargs)
    else:
        schedules = prompt_parser.get_learned_conditioning(model, prompts, steps, *args, **kwargs)
    schedules_c = convert_schedules_to_comfy(schedules, steps, multi)
    return schedules_c


def scheduled_texts(prompts, steps, multi, use_old_scheduling=False):
    """Every text the schedule above will ask the host to encode.

    `prepare()` needs the full list before any encoding happens, and the list
    is a pure function of the prompts: `get_learned_conditioning_prompt_schedules`
    does no model work at all. This is what makes it possible to satisfy the
    async SDK ops without threading `async` through upstream's parser.
    """
    if multi:
        _indexes, flat, _lookup = prompt_parser.get_multicond_prompt_list(prompts)
        prompts = flat
    texts = []
    for schedule in prompt_parser.get_learned_conditioning_prompt_schedules(
        list(prompts), steps, None, use_old_scheduling
    ):
        for _end_at_step, text in schedule:
            if text not in texts:
                texts.append(text)
    return texts


re_AND = re.compile(r"\bAND\b")

__all__ = [
    "UnsupportedOption",
    "ConditioningSlice",
    "build_text_processing_engines",
    "compose_components",
    "convert_schedules_to_comfy",
    "encode_texts",
    "flatten",
    "get_learned_conditioning",
    "logger",
    "re_AND",
    "scheduled_texts",
    "transform_schedules",
]
