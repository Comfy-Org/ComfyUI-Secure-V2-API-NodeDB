"""Pack-owned policy and data for the Secure Nodes V2 QwenVL port.

Model execution is deliberately absent from this module.  The host owns
weight installation and inference; this file retains the upstream catalogue,
prompt selection, frame selection, cleanup, and retry policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import pathlib
import re
from typing import Any, Iterable

from comfy_api.latest import sdk

from .AILab_OutputCleaner import OutputCleanConfig, clean_model_output


_ROOT = pathlib.Path(__file__).resolve().parent
MODEL_CATALOG = json.loads(
    (_ROOT / "secure_model_catalog.json").read_text(encoding="utf-8")
)
PROMPT_CATALOG = json.loads(
    (_ROOT / "AILab_System_Prompts.json").read_text(encoding="utf-8")
)

SYSTEM_PROMPTS: dict[str, str] = dict(PROMPT_CATALOG.get("qwenvl") or {})
TEXT_PROMPTS: dict[str, Any] = dict(PROMPT_CATALOG.get("qwen_text") or {})
TEXT_STYLES: dict[str, dict[str, str]] = dict(TEXT_PROMPTS.get("styles") or {})
TRANSLATION_PROMPT = str(TEXT_PROMPTS.get("translation_prompt") or "")

MAX_PROMPT_CHARS = 262_144
MAX_OUTPUT_CHARS = 262_144

QUANTIZATION = {
    "4-bit (VRAM-friendly)": "int4",
    "8-bit (Balanced)": "int8",
    "None (FP16)": "fp16",
}

_PLANNING = re.compile(
    r"(?im)^\s*(okay[,.:]?|first[,.:]?|next[,.:]?|then[,.:]?|wait[,.:]?)\b"
    r"|(?i:\b(i\s+(should|need|must|will|am\s+going\s+to|have\s+to))\b)"
)


def bounded_text(value: Any, field: str, *, maximum: int = MAX_PROMPT_CHARS) -> str:
    text = str(value or "")
    if "\x00" in text or len(text) > maximum:
        raise ValueError(
            f"{field} must contain at most {maximum} characters and no NUL"
        )
    return text


def prompt_for(preset: str, custom: str) -> str:
    custom = bounded_text(custom, "custom_prompt").strip()
    if custom:
        return custom
    preset = bounded_text(preset, "preset_prompt").strip()
    return bounded_text(SYSTEM_PROMPTS.get(preset, preset), "resolved prompt")


def enhancer_prompt(style: str, custom: str, prompt_text: str) -> str:
    custom = bounded_text(custom, "custom_system_prompt").strip()
    style_entry = TEXT_STYLES.get(str(style), {})
    instruction = custom or str(style_entry.get("system_prompt") or "").strip()
    user = bounded_text(prompt_text, "prompt_text").strip() or "Describe a scene vividly."
    return bounded_text(f"{instruction}\n\n{user}".strip(), "enhancer prompt")


def gguf_enhancer_prompts(
    style: str,
    custom: str,
    prompt_text: str,
) -> tuple[str, str]:
    custom = bounded_text(custom, "custom_system_prompt").strip()
    style_entry = TEXT_STYLES.get(str(style), {})
    system = custom or str(style_entry.get("system_prompt") or "").strip()
    if not system:
        raise ValueError(
            "system_prompt is empty; check AILab_System_Prompts.json or "
            "the preset selection"
        )
    system = bounded_text(
        f"{system}\n\n"
        "Return only the final prompt text. No preface, no explanations, "
        "no analysis, no JSON, no markdown fences, and no <think>.\n"
        "Do not write planning steps (no 'First', 'Next', 'Then') and do "
        "not use first-person ('I', 'we').",
        "system_prompt",
    )
    user = bounded_text(prompt_text, "prompt_text").strip() or "Describe a scene vividly."
    return system, user


def uniform_frame_indices(total: int, requested: int) -> list[int]:
    """Return the upstream ``linspace(..., dtype=int)`` frame indices."""
    if type(total) is not int or total < 1:
        raise ValueError("video batch must contain at least one frame")
    if type(requested) is not int or not 1 <= requested <= 64:
        raise ValueError("frame_count must be in [1, 64]")
    if total <= requested:
        return list(range(total))
    if requested == 1:
        return [0]
    # NumPy's legacy implementation multiplies a binary64 step before the
    # integer cast.  Preserve that detail: exact rational floor differs at a
    # few boundaries (for example 31 frames sampled down to 23).
    step = (total - 1) / (requested - 1)
    result = [int(index * step) for index in range(requested)]
    result[-1] = total - 1
    return result


async def prepare_media(
    image: sdk.ImageRef | None,
    video: sdk.ImageRef | None,
    frame_count: int,
) -> tuple[sdk.ImageRef | None, sdk.ImageRef | None]:
    if image is not None:
        if not isinstance(image, sdk.ImageRef):
            raise TypeError("image must be an IMAGE ref")
        image_count = await image.batch_size()
        if image_count != 1:
            image = await image.select_batch([0])
    if video is not None:
        if not isinstance(video, sdk.ImageRef):
            raise TypeError("video must be an IMAGE ref")
        total = await video.batch_size()
        indices = uniform_frame_indices(total, int(frame_count))
        if indices != list(range(total)):
            video = await video.select_batch(indices)
    return image, video


def clean_text_output(value: Any) -> str:
    text = bounded_text(value, "model output", maximum=MAX_OUTPUT_CHARS)
    return clean_model_output(text, OutputCleanConfig(mode="text")).strip()


def clean_prompt_output(value: Any) -> str:
    text = bounded_text(value, "model output", maximum=MAX_OUTPUT_CHARS)
    return clean_model_output(text, OutputCleanConfig(mode="prompt")).strip()


def looks_like_planning(value: str) -> bool:
    return bool(_PLANNING.search(value or ""))


def retry_prompts(raw: str) -> tuple[str, str]:
    system = (
        "You are a professional photography prompt writer.\n"
        "Output ONLY ONE final photography prompt paragraph.\n"
        "No analysis, no planning steps, no first-person, and no <think>.\n"
        "No bullet points, no headings, no JSON, no markdown, no quotes."
    )
    user = f"Rewrite the following into the final prompt paragraph:\n\n{raw}\n"
    return system, bounded_text(user, "retry prompt")


def seed_offset(seed: int, delta: int) -> int:
    # Node inputs are independently constrained to [1, 2^32-1]. Derived
    # retry/translation seeds may wrap to zero and must remain valid uint32s.
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be a uint32")
    return (seed + int(delta)) & 0xFFFFFFFF


@dataclass(frozen=True)
class WeightArtifact:
    repo_id: str
    revision: str
    filename: str
    sha256: str
    size: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WeightArtifact":
        result = cls(
            repo_id=str(value["repo_id"]),
            revision=str(value["revision"]),
            filename=str(value["filename"]),
            sha256=str(value["sha256"]),
            size=int(value["size"]),
        )
        if not re.fullmatch(r"[0-9a-f]{40}", result.revision):
            raise ValueError(f"invalid Hugging Face revision for {result.filename}")
        if not re.fullmatch(r"[0-9a-f]{64}", result.sha256):
            raise ValueError(f"invalid Hugging Face SHA for {result.filename}")
        if result.size < 1:
            raise ValueError(f"invalid Hugging Face size for {result.filename}")
        return result

    def declaration(self) -> sdk.HuggingFaceWeight:
        return sdk.HuggingFaceWeight(
            repo_id=self.repo_id,
            filename=self.filename,
            folder="text_encoders",
            revision=self.revision,
            sha256=self.sha256,
            on_demand=True,
        )


def _artifact(value: dict[str, Any]) -> WeightArtifact:
    return WeightArtifact.from_dict(value)


def hf_spec(name: str) -> dict[str, Any]:
    try:
        return MODEL_CATALOG["hf"][str(name)]
    except KeyError as error:
        raise ValueError(f"unknown Qwen Hugging Face model {name!r}") from error


def gguf_vl_spec(name: str) -> dict[str, Any]:
    try:
        return MODEL_CATALOG["gguf_vl"][str(name)]
    except KeyError as error:
        raise ValueError(f"unknown Qwen vision GGUF model {name!r}") from error


def gguf_text_spec(name: str) -> dict[str, Any]:
    try:
        return MODEL_CATALOG["gguf_text"][str(name)]
    except KeyError as error:
        raise ValueError(f"unknown Qwen text GGUF model {name!r}") from error


def hf_artifacts(names: Iterable[str]) -> tuple[WeightArtifact, ...]:
    result: list[WeightArtifact] = []
    for name in names:
        result.extend(_artifact(item) for item in hf_spec(name)["weights"])
    return dedupe_artifacts(result)


def gguf_vl_artifacts(names: Iterable[str]) -> tuple[WeightArtifact, ...]:
    result: list[WeightArtifact] = []
    for name in names:
        spec = gguf_vl_spec(name)
        result.extend((_artifact(spec["model"]), _artifact(spec["mmproj"])))
    return dedupe_artifacts(result)


def gguf_text_artifacts(names: Iterable[str]) -> tuple[WeightArtifact, ...]:
    return dedupe_artifacts(
        _artifact(gguf_text_spec(name)["model"]) for name in names
    )


def dedupe_artifacts(
    artifacts: Iterable[WeightArtifact],
) -> tuple[WeightArtifact, ...]:
    result: list[WeightArtifact] = []
    seen: set[tuple[str, str, str]] = set()
    for artifact in artifacts:
        key = (artifact.repo_id, artifact.revision, artifact.filename)
        if key not in seen:
            seen.add(key)
            result.append(artifact)
    return tuple(result)


def declarations(
    artifacts: Iterable[WeightArtifact],
) -> tuple[sdk.HuggingFaceWeight, ...]:
    return tuple(artifact.declaration() for artifact in artifacts)


_DOWNLOADED: dict[WeightArtifact, str] = {}


async def download_artifact(artifact: WeightArtifact) -> str:
    logical = _DOWNLOADED.get(artifact)
    if logical is None:
        logical = await sdk.ctx().models.download_huggingface_weights(
            artifact.repo_id,
            artifact.filename,
            "text_encoders",
            revision=artifact.revision,
            sha256=artifact.sha256,
        )
        _DOWNLOADED[artifact] = logical
    return logical


async def download_artifacts(
    artifacts: Iterable[WeightArtifact],
) -> list[str]:
    result: list[str] = []
    for artifact in artifacts:
        result.append(await download_artifact(artifact))
    return result


HF_VL_NAMES = tuple(
    name for name, spec in MODEL_CATALOG["hf"].items()
    if spec["family"].startswith(("qwen3_vl", "qwen2_5_vl"))
)
HF_ALL_NAMES = tuple(MODEL_CATALOG["hf"])
GGUF_VL_NAMES = tuple(MODEL_CATALOG["gguf_vl"])
GGUF_TEXT_NAMES = tuple(MODEL_CATALOG["gguf_text"])

HF_VL_REQUIRED = declarations(hf_artifacts(HF_VL_NAMES))
HF_ALL_REQUIRED = declarations(hf_artifacts(HF_ALL_NAMES))
GGUF_VL_REQUIRED = declarations(gguf_vl_artifacts(GGUF_VL_NAMES))
GGUF_TEXT_REQUIRED = declarations(gguf_text_artifacts(GGUF_TEXT_NAMES))


__all__ = [
    "GGUF_TEXT_NAMES",
    "GGUF_TEXT_REQUIRED",
    "GGUF_VL_NAMES",
    "GGUF_VL_REQUIRED",
    "HF_ALL_NAMES",
    "HF_ALL_REQUIRED",
    "HF_VL_NAMES",
    "HF_VL_REQUIRED",
    "MODEL_CATALOG",
    "QUANTIZATION",
    "SYSTEM_PROMPTS",
    "TEXT_STYLES",
    "TRANSLATION_PROMPT",
    "WeightArtifact",
    "bounded_text",
    "clean_prompt_output",
    "clean_text_output",
    "download_artifact",
    "download_artifacts",
    "enhancer_prompt",
    "gguf_enhancer_prompts",
    "gguf_text_artifacts",
    "gguf_text_spec",
    "gguf_vl_artifacts",
    "gguf_vl_spec",
    "hf_artifacts",
    "hf_spec",
    "looks_like_planning",
    "prepare_media",
    "prompt_for",
    "retry_prompts",
    "seed_offset",
    "uniform_frame_indices",
]
