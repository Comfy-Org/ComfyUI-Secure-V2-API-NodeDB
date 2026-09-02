"""Secure Nodes V2 bindings for the pinned ComfyUI-QwenVL release.

The reviewed model catalogue, prompt selection, media-frame selection, output
cleanup, and retry/translation policy remain in this pack.  The host only owns
hash-pinned weight installation and opaque native/llama.cpp inference.
"""
from __future__ import annotations

import math
from typing import Any

from ._secure_runtime import SCHEMAS, bind_node, sdk
from .qwen_pack import (
    GGUF_TEXT_REQUIRED,
    GGUF_VL_REQUIRED,
    HF_ALL_REQUIRED,
    HF_VL_REQUIRED,
    MAX_OUTPUT_CHARS,
    bounded_text,
    clean_prompt_output,
    clean_text_output,
    download_artifacts,
    enhancer_prompt,
    gguf_enhancer_prompts,
    gguf_text_artifacts,
    gguf_text_spec,
    gguf_vl_artifacts,
    gguf_vl_spec,
    hf_artifacts,
    hf_spec,
    looks_like_planning,
    prepare_media,
    prompt_for,
    retry_prompts,
    seed_offset,
    TRANSLATION_PROMPT,
)


_UINT32_MAX = 2**32 - 1
_QUANTIZATION = {
    "4-bit (VRAM-friendly)",
    "8-bit (Balanced)",
    "None (FP16)",
}
_ATTENTION = {"auto", "sage", "flash_attention_2", "sdpa"}


def _ctx():
    return sdk.ctx()


def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result != value or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return result


def _bounded_float(
    value: Any,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return result


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{name} must be boolean")
    return value


def _device(value: Any) -> str:
    """Map legacy accelerator hints onto the closed canonical host policy."""
    result = str(value or "auto").strip().lower()
    if result == "cpu":
        return "cpu"
    if result in {"auto", "mps", "cuda"} or (
        result.startswith("cuda:") and result[5:].isdigit()
    ):
        return "default"
    raise ValueError("device must be auto, cpu, mps, cuda, or cuda:N")


def _llama_device(value: Any) -> str:
    result = str(value or "auto").strip().lower()
    if result in {"auto", "cpu", "mps", "cuda"}:
        return result
    if result.startswith("cuda:") and result[5:].isdigit():
        return result
    raise ValueError("device must be auto, cpu, mps, cuda, or cuda:N")


def _host_hints(
    quantization: Any,
    attention_mode: Any,
    use_torch_compile: Any,
) -> None:
    """Validate legacy UI hints without turning them into pack authority.

    Secure V2 treats these as host-owned scheduling/optimization hints.  They
    never select a downloader, execute a compiler, or import an attention
    implementation in the guest.
    """
    if str(quantization) not in _QUANTIZATION:
        raise ValueError("unknown quantization hint")
    if str(attention_mode) not in _ATTENTION:
        raise ValueError("unknown attention-mode hint")
    if not isinstance(use_torch_compile, bool):
        raise TypeError("use_torch_compile must be boolean")


async def _generate_native(
    *,
    model_name: str,
    prompt: str,
    image: sdk.ImageRef | None,
    video: sdk.ImageRef | None,
    max_tokens: int,
    temperature: float,
    top_p: float,
    num_beams: int,
    repetition_penalty: float,
    seed: int,
    keep_model_loaded: bool,
    device: str,
    use_default_template: bool,
    report_load_progress: bool = False,
) -> str:
    spec = hf_spec(model_name)
    if spec.get("backend") != "canonical":
        raise ValueError(f"{model_name!r} is not a canonical SafeTensors model")
    artifacts = hf_artifacts((model_name,))
    weights = await download_artifacts(artifacts)
    model = await _ctx().models.load_language_model(
        weights,
        family=str(spec["family"]),
        device=_device(device),
        cache=_boolean(keep_model_loaded, "keep_model_loaded"),
    )
    if report_load_progress:
        await _ctx().progress.update(2, 3)
    output = await model.generate_text(
        bounded_text(prompt, "prompt", maximum=32_768),
        image=image,
        video=video,
        max_length=int(max_tokens),
        do_sample=int(num_beams) == 1,
        temperature=float(temperature),
        top_k=None,
        top_p=float(top_p),
        min_p=0.0,
        repetition_penalty=float(repetition_penalty),
        seed=int(seed),
        presence_penalty=0.0,
        thinking=bool(spec.get("thinking", False)),
        use_default_template=bool(use_default_template),
        num_beams=int(num_beams),
    )
    return bounded_text(
        output,
        "model output",
        maximum=MAX_OUTPUT_CHARS,
    ).strip()


async def _qwen_vl(
    model_name,
    quantization,
    attention_mode,
    preset_prompt,
    custom_prompt,
    max_tokens,
    keep_model_loaded,
    seed,
    image=None,
    video=None,
    **_kwargs,
):
    _host_hints(quantization, attention_mode, False)
    max_tokens = _bounded_int(max_tokens, "max_tokens", 64, 2048)
    seed = _bounded_int(seed, "seed", 1, _UINT32_MAX)
    image, video = await prepare_media(image, video, 16)
    await _ctx().progress.update(1, 3)
    result = await _generate_native(
        model_name=str(model_name),
        prompt=prompt_for(preset_prompt, custom_prompt),
        image=image,
        video=video,
        max_tokens=max_tokens,
        temperature=0.6,
        top_p=0.9,
        num_beams=1,
        repetition_penalty=1.2,
        seed=seed,
        keep_model_loaded=_boolean(keep_model_loaded, "keep_model_loaded"),
        device="auto",
        use_default_template=True,
        report_load_progress=True,
    )
    await _ctx().progress.update(3, 3)
    return (result,)


async def _qwen_vl_advanced(
    model_name,
    quantization,
    attention_mode,
    use_torch_compile,
    device,
    preset_prompt,
    custom_prompt,
    max_tokens,
    temperature,
    top_p,
    num_beams,
    repetition_penalty,
    frame_count,
    keep_model_loaded,
    seed,
    image=None,
    video=None,
    **_kwargs,
):
    _host_hints(quantization, attention_mode, use_torch_compile)
    max_tokens = _bounded_int(max_tokens, "max_tokens", 64, 4096)
    temperature = _bounded_float(temperature, "temperature", 0.1, 1.0)
    top_p = _bounded_float(top_p, "top_p", 0.0, 1.0)
    num_beams = _bounded_int(num_beams, "num_beams", 1, 8)
    repetition_penalty = _bounded_float(
        repetition_penalty, "repetition_penalty", 0.5, 2.0
    )
    frame_count = _bounded_int(frame_count, "frame_count", 1, 64)
    seed = _bounded_int(seed, "seed", 1, _UINT32_MAX)
    image, video = await prepare_media(image, video, frame_count)
    await _ctx().progress.update(1, 3)
    result = await _generate_native(
        model_name=str(model_name),
        prompt=prompt_for(preset_prompt, custom_prompt),
        image=image,
        video=video,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        num_beams=num_beams,
        repetition_penalty=repetition_penalty,
        seed=seed,
        keep_model_loaded=_boolean(keep_model_loaded, "keep_model_loaded"),
        device=str(device),
        use_default_template=True,
        report_load_progress=True,
    )
    await _ctx().progress.update(3, 3)
    return (result,)


async def _qwen_prompt_enhancer(
    model_name,
    quantization,
    attention_mode,
    use_torch_compile,
    device,
    prompt_text,
    enhancement_style,
    custom_system_prompt,
    max_tokens,
    temperature,
    top_p,
    repetition_penalty,
    keep_model_loaded,
    seed,
    **_kwargs,
):
    _host_hints(quantization, attention_mode, use_torch_compile)
    spec = hf_spec(str(model_name))
    if spec.get("backend") != "canonical":
        # The sole reviewed GGUF fallback is bound after the canonical
        # integrations.llama_cpp surface is frozen.
        return await _qwen_prompt_enhancer_llama_cpp(
            model_name=model_name,
            device=device,
            prompt_text=prompt_text,
            enhancement_style=enhancement_style,
            custom_system_prompt=custom_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            keep_model_loaded=keep_model_loaded,
            seed=seed,
        )
    max_tokens = _bounded_int(max_tokens, "max_tokens", 32, 1024)
    temperature = _bounded_float(temperature, "temperature", 0.1, 1.0)
    top_p = _bounded_float(top_p, "top_p", 0.0, 1.0)
    repetition_penalty = _bounded_float(
        repetition_penalty, "repetition_penalty", 0.5, 2.0
    )
    seed = _bounded_int(seed, "seed", 1, _UINT32_MAX)
    prompt = enhancer_prompt(
        enhancement_style,
        custom_system_prompt,
        prompt_text,
    )
    family = str(spec["family"])
    is_vlm = family.startswith(("qwen3_vl", "qwen2_5_vl"))
    if is_vlm:
        await _ctx().progress.update(1, 3)
    result = await _generate_native(
        model_name=str(model_name),
        prompt=prompt,
        image=None,
        video=None,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        num_beams=1,
        repetition_penalty=repetition_penalty,
        seed=seed,
        keep_model_loaded=_boolean(keep_model_loaded, "keep_model_loaded"),
        device=str(device),
        # Upstream tokenizes its two text-only checkpoints directly.  VLM
        # checkpoints continue to use their family-owned chat template.
        use_default_template=is_vlm,
        report_load_progress=is_vlm,
    )
    if is_vlm:
        await _ctx().progress.update(3, 3)
    return (result,)


async def _load_llama_model(
    *,
    artifacts,
    family: str,
    device: str,
    context_length: int,
    batch_size: int,
    gpu_layers: int,
    image_max_tokens: int = 4096,
    top_k: int = 0,
    pool_size: int = 4_194_304,
    cache: bool = True,
    multimodal: bool = False,
) -> sdk.LlamaCppModelRef:
    logical = await download_artifacts(artifacts)
    expected = 2 if multimodal else 1
    if len(logical) != expected:
        raise RuntimeError("sealed llama.cpp artifact set has changed")
    return await _ctx().integrations.llama_cpp.load_chat_model(
        logical[0],
        logical[1] if multimodal else None,
        family=str(family),
        device=_llama_device(device),
        context_length=int(context_length),
        batch_size=int(batch_size),
        gpu_layers=int(gpu_layers),
        image_max_tokens=int(image_max_tokens),
        top_k=int(top_k),
        pool_size=int(pool_size),
        cache=bool(cache),
    )


async def _generate_llama(
    model: sdk.LlamaCppModelRef,
    *,
    system: str,
    prompt: str,
    image: sdk.ImageRef | None = None,
    video: sdk.ImageRef | None = None,
    max_tokens: int,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
    seed: int,
) -> str:
    return bounded_text(
        await model.generate(
            bounded_text(system, "system prompt"),
            bounded_text(prompt, "user prompt"),
            image=image,
            video=video,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            repetition_penalty=float(repetition_penalty),
            seed=int(seed),
        ),
        "model output",
        maximum=MAX_OUTPUT_CHARS,
    )


async def _qwen_prompt_enhancer_llama_cpp(
    *,
    model_name,
    device,
    prompt_text,
    enhancement_style,
    custom_system_prompt,
    max_tokens,
    temperature,
    top_p,
    repetition_penalty,
    keep_model_loaded,
    seed,
):
    spec = hf_spec(str(model_name))
    if spec.get("backend") != "llama_cpp":
        raise ValueError("model is not in the sealed llama.cpp fallback catalogue")
    max_tokens = _bounded_int(max_tokens, "max_tokens", 32, 1024)
    temperature = _bounded_float(temperature, "temperature", 0.1, 1.0)
    top_p = _bounded_float(top_p, "top_p", 0.0, 1.0)
    repetition_penalty = _bounded_float(
        repetition_penalty, "repetition_penalty", 0.5, 2.0
    )
    seed = _bounded_int(seed, "seed", 1, _UINT32_MAX)
    model = await _load_llama_model(
        artifacts=hf_artifacts((str(model_name),)),
        family=str(spec["family"]),
        device=str(device),
        context_length=8192,
        batch_size=1024,
        gpu_layers=-1,
        cache=_boolean(keep_model_loaded, "keep_model_loaded"),
    )
    # The upstream HF enhancer tokenized this merged prompt directly, without
    # a chat template.  An empty system turn is the closest closed llama.cpp
    # expression and leaves the entire style/user merge pack-owned.
    result = await _generate_llama(
        model,
        system="",
        prompt=enhancer_prompt(
            enhancement_style,
            custom_system_prompt,
            prompt_text,
        ),
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        seed=seed,
    )
    return (result.strip(),)


_VISION_SYSTEM = (
    "You are a helpful vision-language assistant. Answer directly with the "
    "final answer only. No <think> and no reasoning."
)


async def _qwen_vl_gguf_common(
    *,
    model_name: str,
    device: str,
    preset_prompt: str,
    custom_prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
    frame_count: int,
    context_length: int,
    batch_size: int,
    gpu_layers: int,
    image_max_tokens: int,
    top_k: int,
    pool_size: int,
    keep_model_loaded: bool,
    seed: int,
    image: sdk.ImageRef | None,
    video: sdk.ImageRef | None,
) -> tuple[str]:
    spec = gguf_vl_spec(model_name)
    image, video = await prepare_media(image, video, frame_count)
    model = await _load_llama_model(
        artifacts=gguf_vl_artifacts((model_name,)),
        family=str(spec["family"]),
        device=device,
        context_length=context_length,
        batch_size=batch_size,
        gpu_layers=gpu_layers,
        image_max_tokens=image_max_tokens,
        top_k=top_k,
        pool_size=pool_size,
        cache=keep_model_loaded,
        multimodal=True,
    )
    raw = await _generate_llama(
        model,
        system=_VISION_SYSTEM,
        prompt=prompt_for(preset_prompt, custom_prompt),
        image=image,
        video=video,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        seed=seed,
    )
    return (clean_text_output(raw),)


async def _qwen_vl_gguf(
    model_name,
    preset_prompt,
    custom_prompt,
    max_tokens,
    keep_model_loaded,
    seed,
    image=None,
    video=None,
    **_kwargs,
):
    spec = gguf_vl_spec(str(model_name))
    defaults = spec["defaults"]
    return await _qwen_vl_gguf_common(
        model_name=str(model_name),
        device="auto",
        preset_prompt=preset_prompt,
        custom_prompt=custom_prompt,
        max_tokens=_bounded_int(max_tokens, "max_tokens", 64, 2048),
        temperature=0.6,
        top_p=0.9,
        repetition_penalty=1.2,
        frame_count=16,
        context_length=int(defaults["context_length"]),
        batch_size=int(defaults["n_batch"]),
        gpu_layers=int(defaults["gpu_layers"]),
        image_max_tokens=int(defaults["image_max_tokens"]),
        top_k=int(defaults["top_k"]),
        pool_size=int(defaults["pool_size"]),
        keep_model_loaded=_boolean(keep_model_loaded, "keep_model_loaded"),
        seed=_bounded_int(seed, "seed", 1, _UINT32_MAX),
        image=image,
        video=video,
    )


async def _qwen_vl_gguf_advanced(
    model_name,
    device,
    preset_prompt,
    custom_prompt,
    max_tokens,
    temperature,
    top_p,
    repetition_penalty,
    frame_count,
    ctx,
    n_batch,
    gpu_layers,
    image_max_tokens,
    top_k,
    pool_size,
    keep_model_loaded,
    seed,
    image=None,
    video=None,
    **_kwargs,
):
    return await _qwen_vl_gguf_common(
        model_name=str(model_name),
        device=str(device),
        preset_prompt=preset_prompt,
        custom_prompt=custom_prompt,
        max_tokens=_bounded_int(max_tokens, "max_tokens", 64, 4096),
        temperature=_bounded_float(temperature, "temperature", 0.0, 2.0),
        top_p=_bounded_float(top_p, "top_p", 0.0, 1.0),
        repetition_penalty=_bounded_float(
            repetition_penalty, "repetition_penalty", 0.5, 2.0
        ),
        frame_count=_bounded_int(frame_count, "frame_count", 1, 64),
        context_length=_bounded_int(ctx, "ctx", 1024, 262144),
        batch_size=_bounded_int(n_batch, "n_batch", 64, 32768),
        gpu_layers=_bounded_int(gpu_layers, "gpu_layers", -1, 200),
        image_max_tokens=_bounded_int(
            image_max_tokens, "image_max_tokens", 256, 1_024_000
        ),
        top_k=_bounded_int(top_k, "top_k", 0, 32768),
        pool_size=_bounded_int(
            pool_size, "pool_size", 1_048_576, 10_485_760
        ),
        keep_model_loaded=_boolean(keep_model_loaded, "keep_model_loaded"),
        seed=_bounded_int(seed, "seed", 1, _UINT32_MAX),
        image=image,
        video=video,
    )


async def _invoke_gguf_prompt(
    model: sdk.LlamaCppModelRef,
    *,
    system: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
    seed: int,
) -> str:
    raw = await _generate_llama(
        model,
        system=system,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        seed=seed,
    )
    cleaned = clean_prompt_output(raw)
    if not cleaned or looks_like_planning(cleaned) or "<think" in raw.lower():
        retry_system, retry_user = retry_prompts(raw)
        retry_raw = await _generate_llama(
            model,
            system=retry_system,
            prompt=retry_user,
            max_tokens=max_tokens,
            temperature=0.4,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            seed=seed_offset(seed, 999),
        )
        retry_cleaned = clean_prompt_output(retry_raw)
        if retry_cleaned and not looks_like_planning(retry_cleaned):
            return retry_cleaned
    return cleaned or ""


async def _qwen_gguf_prompt_enhancer(
    model_name,
    prompt_text,
    preset_system_prompt,
    custom_system_prompt,
    max_tokens,
    temperature,
    top_p,
    repetition_penalty,
    english_output,
    device,
    seed,
    **_kwargs,
):
    spec = gguf_text_spec(str(model_name))
    max_tokens = _bounded_int(max_tokens, "max_tokens", 32, 1024)
    temperature = _bounded_float(temperature, "temperature", 0.1, 1.0)
    top_p = _bounded_float(top_p, "top_p", 0.0, 1.0)
    repetition_penalty = _bounded_float(
        repetition_penalty, "repetition_penalty", 0.5, 2.0
    )
    seed = _bounded_int(seed, "seed", 1, _UINT32_MAX)
    defaults = spec["defaults"]
    model = await _load_llama_model(
        artifacts=gguf_text_artifacts((str(model_name),)),
        family=str(spec["family"]),
        device=str(device),
        context_length=int(defaults["context_length"]),
        batch_size=1024,
        gpu_layers=-1,
        cache=True,
    )
    system, user = gguf_enhancer_prompts(
        preset_system_prompt,
        custom_system_prompt,
        prompt_text,
    )
    enhanced = await _invoke_gguf_prompt(
        model,
        system=system,
        prompt=user,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        seed=seed,
    )
    if _boolean(english_output, "english_output"):
        translated = await _invoke_gguf_prompt(
            model,
            system=(TRANSLATION_PROMPT or (
                "Return a single English paragraph (150-300 words). No "
                "prefixes, bullets, JSON, or <think>. Output only the prompt."
            )),
            prompt=enhanced,
            max_tokens=max_tokens,
            temperature=0.3,
            top_p=0.95,
            repetition_penalty=1.05,
            seed=seed_offset(seed, 1),
        )
        final = clean_prompt_output(translated) or translated.strip()
    else:
        final = clean_prompt_output(enhanced) or enhanced.strip()
    return (final,)


_HANDLERS = {
    "AILab_QwenVL": _qwen_vl,
    "AILab_QwenVL_Advanced": _qwen_vl_advanced,
    "AILab_QwenVL_GGUF": _qwen_vl_gguf,
    "AILab_QwenVL_GGUF_Advanced": _qwen_vl_gguf_advanced,
    "AILab_QwenVL_GGUF_PromptEnhancer": _qwen_gguf_prompt_enhancer,
    "AILab_QwenVL_PromptEnhancer": _qwen_prompt_enhancer,
}


def _permissions(node_id: str) -> tuple[str, ...]:
    result = ["models.download"]
    if node_id in {
        "AILab_QwenVL",
        "AILab_QwenVL_Advanced",
        "AILab_QwenVL_PromptEnhancer",
    }:
        result.insert(0, "models")
    if node_id in {
        "AILab_QwenVL_GGUF",
        "AILab_QwenVL_GGUF_Advanced",
        "AILab_QwenVL_GGUF_PromptEnhancer",
        "AILab_QwenVL_PromptEnhancer",
    }:
        result.append("integrations.llama_cpp")
    return tuple(result)


_REQUIRED = {
    "AILab_QwenVL": HF_VL_REQUIRED,
    "AILab_QwenVL_Advanced": HF_VL_REQUIRED,
    "AILab_QwenVL_PromptEnhancer": HF_ALL_REQUIRED,
    "AILab_QwenVL_GGUF": GGUF_VL_REQUIRED,
    "AILab_QwenVL_GGUF_Advanced": GGUF_VL_REQUIRED,
    "AILab_QwenVL_GGUF_PromptEnhancer": GGUF_TEXT_REQUIRED,
}


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(node_id, _HANDLERS[node_id], permissions=_permissions(node_id))
    for node_id in _HANDLERS
}
for _node_id, _node_class in NODE_CLASS_MAPPINGS.items():
    _node_class.SDK_REQUIRED_WEIGHTS = _REQUIRED[_node_id]

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in NODE_CLASS_MAPPINGS
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
