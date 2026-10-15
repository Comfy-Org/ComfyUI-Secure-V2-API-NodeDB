"""Pinned metadata formatting over explicit closed record projections.

This does not capture execution globals or certify authored catalogue backing.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any


CIVITAI_SAMPLER_MAP = {
    "euler": "Euler",
    "euler_ancestral": "Euler a",
    "lms": "LMS",
    "heun": "Heun",
    "dpm_2": "DPM2",
    "dpm_2_ancestral": "DPM2 a",
    "dpmpp_2s_ancestral": "DPM++ 2S a",
    "dpmpp_2m": "DPM++ 2M",
    "dpmpp_sde": "DPM++ SDE",
    "dpmpp_sde_gpu": "DPM++ SDE",
    "dpmpp_2m_sde": "DPM++ 2M SDE",
    "dpmpp_2m_sde_gpu": "DPM++ 2M SDE",
    "dpmpp_3m_sde": "DPM++ 3M SDE",
    "dpm_fast": "DPM fast",
    "dpm_adaptive": "DPM adaptive",
    "ddim": "DDIM",
    "plms": "PLMS",
    "uni_pc_bh2": "UniPC",
    "uni_pc": "UniPC",
    "lcm": "LCM",
}

# Base model display name → AIR URN slug
# Sourced from civitai source: src/shared/constants/basemodel.constants.ts
BASE_MODEL_AIR_SLUG = {
    # Stable Diffusion family
    "SD 1.4": "sd1",
    "SD 1.5": "sd1",
    "SD 1.5 LCM": "sd1",
    "SD 1.5 Hyper": "sd1",
    "SD 2.0": "sd2",
    "SD 2.0 768": "sd2",
    "SD 2.1": "sd2",
    "SD 2.1 768": "sd2",
    "SD 2.1 Unclip": "sd2",
    "SD 3.0": "sd3",
    "SD 3.5": "sd35",
    "SD 3.5 Large": "sd35",
    "SD 3.5 Large Turbo": "sd35",
    "SD 3.5 Medium": "sd35",
    "SDXL 0.9": "sdxl",
    "SDXL 1.0": "sdxl",
    "SDXL 1.0 LCM": "sdxl",
    "SDXL Lightning": "sdxl",
    "SDXL Hyper": "sdxl",
    "SDXL Turbo": "sdxl",
    "SDXL Distilled": "sdxldistilled",
    "Stable Cascade": "scascade",
    "Stable Video Diffusion": "svd",
    "SVD": "svd",
    "SVD XT": "svdxt",

    # SDXL community fine-tunes
    "Pony": "pony",
    "Pony Diffusion": "pony",
    "Illustrious": "illustrious",
    "NoobAI": "noobai",
    "Animagine": "illustrious",

    # Flux family
    "Flux.1": "flux1",
    "Flux.1 D": "flux1",
    "Flux.1 S": "flux1",
    "Flux.1 Krea": "fluxkrea",
    "Flux.1 Kontext": "flux1kontext",
    "Flux.2": "flux2",
    "Flux.2 D": "flux2",
    "Flux.2 Klein 9B": "flux2klein_9b",
    "Flux.2 Klein 9B Base": "flux2klein_9b_base",
    "Flux.2 Klein 4B": "flux2klein_4b",
    "Flux.2 Klein 4B Base": "flux2klein_4b_base",

    # Other image models (sorted alphabetically)
    "AuraFlow": "auraflow",
    "Chroma": "chroma",
    "HiDream": "hidream",
    "HiDream-O1": "hidream-o1",
    "Hunyuan DiT": "hydit1",
    "Hunyuan Video": "hyv1",
    "Kolors": "kolors",
    "Lumina": "lumina",
    "Mochi": "mochi",
    "ODOR": "odor",
    "PixArt Alpha": "pixarta",
    "PixArt Sigma": "pixarte",
    "Playground v2": "playgroundv2",
    "Playground v2.5": "playgroundv2",
    "Pony Diffusion V7": "ponyv7",

    # Video models
    "CogVideoX": "cogvideox",
    "LTX Video": "ltxv",
    "LTX Video 2": "ltxv2",
    "LTX Video 2.3": "ltxv23",
    "Wan Video": "wanvideo",
    "Wan Video 1.3B T2V": "wanvideo_13b_t2v",
    "Wan Video 14B T2V": "wanvideo_14b_t2v",
    "Wan Video 14B I2V 480p": "wanvideo_14b_i2v_480p",
    "Wan Video 14B I2V 720p": "wanvideo_14b_i2v_720p",

    # Third-party / proprietary image models
    "Boogu": "boogu",
    "Ernie": "ernie",
    "Grok": "grok",
    "HappyHorse": "happyhorse",
    "Ideogram": "ideogram",
    "Ideogram 4.0": "ideogram",
    "Imagen": "imagen4",
    "Imagen 4": "imagen4",
    "Krea": "krea2",
    "Krea 2": "krea2",
    "Lens": "lens",
    "MAI": "mai",
    "Nano Banana": "nanobanana",
    "OpenAI": "openai",
    "Reve": "reve",
    "Reve 2": "reve",
    "Reve 2.1": "reve",
    "Seedream": "seedream",
    "Sora": "sora2",
    "Sora 2": "sora2",
    "Veo": "veo3",
    "Veo 2": "veo3",
    "Veo 3": "veo3",
    "ZImageTurbo": "zimageturbo",
    "ZImageBase": "zimagebase",
    "ZImage": "zimagebase",

    # Third-party video models
    "Hailuo by MiniMax": "minimax",
    "Haiper": "haiper",
    "Kling": "kling",
    "Lightricks": "lightricks",
    "Seedance": "seedance",
    "Vidu": "vidu",

    # Qwen family
    "Qwen": "qwen",
    "Qwen 2": "qwen2",

    # Anima
    "Anima": "anima",

    # Special
    "Upscaler": "upscaler",
    "Other": "other",
}


class ImageParameterFormatter:
    def __init__(self, resources=None):
        self.resources = resources or {}
        if type(self.resources) is not dict or set(self.resources) - {'checkpoint_scanner', 'lora_scanner'}:
            raise ValueError('Image metadata resource projection identity is invalid')
        for table in self.resources.values():
            if type(table) is not dict:
                raise ValueError('Image metadata resource projection exceeds bounds')
            for row in table.values():
                if (type(row) is not dict or set(row) != {'sha256','civitai','base_model'}
                        or type(row['sha256']) is not str or type(row['civitai']) is not dict
                        or type(row['base_model']) is not str):
                    raise ValueError('Image metadata resource projection identity is invalid')

    def _resolve_model_cache_entry(self, scanner_type, name):
        row = self.resources.get(scanner_type, {}).get(name)
        return ('', {}, '') if row is None else (row['sha256'].lower(), row['civitai'], row['base_model'])

    @staticmethod
    def _get_civitai_sampler_name(sampler_name: str, scheduler: str) -> str:
        if sampler_name in CIVITAI_SAMPLER_MAP:
            civitai_name = CIVITAI_SAMPLER_MAP[sampler_name]
            if scheduler == "karras":
                civitai_name += " Karras"
            elif scheduler == "exponential":
                civitai_name += " Exponential"
            return civitai_name
        else:
            if scheduler and scheduler != "normal":
                return f"{sampler_name}_{scheduler}"
            return sampler_name

    @staticmethod
    def _build_air_string(base_model: str, model_type: str, model_id: int, version_id: int) -> str:
        slug = BASE_MODEL_AIR_SLUG.get(base_model, "other")
        type_lower = model_type.lower() if model_type else "other"
        return f"urn:air:{slug}:{type_lower}:civitai:{model_id}@{version_id}"

    def format_metadata(self, metadata_dict: dict[str, Any], add_loras_to_prompt: bool = False) -> str:
        """Format metadata as A1111-compatible parameters string with Hashes JSON and Civitai resources."""
        if not metadata_dict: return ""

        prompt = metadata_dict.get("prompt", "")
        negative_prompt = metadata_dict.get("negative_prompt", "")
        steps = metadata_dict.get("steps")
        cfg = metadata_dict.get("guidance")
        if cfg is None:
            cfg = metadata_dict.get("cfg_scale")
        if cfg is None:
            cfg = metadata_dict.get("cfg")
        seed = metadata_dict.get("seed")
        size = metadata_dict.get("size")
        sampler = metadata_dict.get("sampler") or ""
        scheduler = metadata_dict.get("scheduler") or "normal"
        checkpoint = metadata_dict.get("checkpoint") or ""
        loras_text = metadata_dict.get("loras", "")
        clip_skip = metadata_dict.get("clip_skip")

        # Parse LoRA entries from <lora:name:strength> format
        lora_entries: list[tuple[str, float]] = []
        if loras_text:
            for match in re.findall(r"<lora:([^:]+):([^>]+)>", loras_text):
                lora_name, strength_str = match
                try:
                    strength = float(strength_str)
                except (ValueError, TypeError):
                    strength = 1.0
                lora_entries.append((lora_name, strength))

        # Resolve checkpoint hash and Civitai data from local cache
        ckpt_hash, ckpt_civitai, ckpt_base_model = "", {}, ""
        ckpt_display_name = ""
        if checkpoint:
            ckpt_hash, ckpt_civitai, ckpt_base_model = self._resolve_model_cache_entry(
                "checkpoint_scanner", checkpoint
            )
            ckpt_display_name = os.path.splitext(os.path.basename(checkpoint))[0]

        # Resolve LoRA hash and Civitai data from local cache
        loras_data: list[dict[str, Any]] = []
        for lora_name, strength in lora_entries:
            lora_hash, lora_civitai, lora_base_model = self._resolve_model_cache_entry(
                "lora_scanner", lora_name
            )
            loras_data.append({
                "name": lora_name,
                "strength": strength,
                "hash": lora_hash,
                "civitai": lora_civitai,
                "base_model": lora_base_model,
            })

        # Build Hashes JSON (A1111 / Civitai standard format)
        hashes: dict[str, str] = {}
        if ckpt_hash:
            hashes["model"] = ckpt_hash[:10].upper()
        for lora in loras_data:
            if lora["hash"]:
                hashes[f"LORA:{lora['name']}"] = lora["hash"][:10].upper()

        # Build Civitai resources JSON array
        civitai_resources: list[dict[str, Any]] = []
        if ckpt_civitai.get("id", 0) > 0:
            ckpt_resource: dict[str, Any] = {}
            ckpt_type = (ckpt_civitai.get("model") or {}).get("type", "Checkpoint")
            model_id = ckpt_civitai.get("modelId", 0)
            version_id = ckpt_civitai.get("id", 0)
            if model_id and version_id:
                ckpt_resource["air"] = self._build_air_string(
                    ckpt_base_model, ckpt_type, int(model_id), int(version_id)
                )
            elif version_id:
                ckpt_resource["modelVersionId"] = int(version_id)
            if ckpt_civitai.get("name"):
                ckpt_resource["versionName"] = ckpt_civitai["name"]
            if ckpt_resource:
                civitai_resources.append(ckpt_resource)

        for lora in loras_data:
            lora_civitai = lora["civitai"]
            if not lora_civitai or lora_civitai.get("id", 0) <= 0:
                continue
            lora_resource: dict[str, Any] = {"weight": lora["strength"]}
            lora_type = (lora_civitai.get("model") or {}).get("type", "LORA")
            model_id = lora_civitai.get("modelId", 0)
            version_id = lora_civitai.get("id", 0)
            if model_id and version_id:
                lora_resource["air"] = self._build_air_string(
                    lora["base_model"], lora_type, int(model_id), int(version_id)
                )
            elif version_id:
                lora_resource["modelVersionId"] = int(version_id)
            if lora_civitai.get("name"):
                lora_resource["versionName"] = lora_civitai["name"]
            civitai_resources.append(lora_resource)

        sampler_name = CIVITAI_SAMPLER_MAP.get(sampler, sampler) if sampler else None

        scheduler_mapping = {
            "normal": "Normal",
            "karras": "Karras",
            "exponential": "Exponential",
            "sgm_uniform": "SGM Uniform",
            "sgm_quadratic": "SGM Quadratic",
        }
        scheduler_name = scheduler_mapping.get(scheduler, scheduler) if scheduler else None

        # Build output lines
        prompt_line = prompt if prompt else ""
        if add_loras_to_prompt and loras_text:
            prompt_line = f"{prompt_line}\n{loras_text}" if prompt_line else loras_text
        lines = [prompt_line] if prompt_line else [""]
        if negative_prompt:
            lines.append(f"Negative prompt: {negative_prompt}")

        params: list[str] = []
        if steps is not None:
            params.append(f"Steps: {steps}")
        if sampler_name:
            if scheduler_name:
                params.append(f"Sampler: {sampler_name} {scheduler_name}")
            else:
                params.append(f"Sampler: {sampler_name}")
        if cfg is not None:
            params.append(f"CFG scale: {cfg}")
        if seed is not None:
            params.append(f"Seed: {seed}")
        if size:
            params.append(f"Size: {size}")
        if clip_skip is not None:
            try:
                params.append(f"Clip skip: {abs(int(clip_skip))}")
            except (ValueError, TypeError):
                pass
        additional_data = metadata_dict.get("additional_data", "")
        if additional_data:
            params.append(additional_data)
        if ckpt_hash:
            params.append(f"Model hash: {ckpt_hash[:10].upper()}")
        if ckpt_display_name:
            params.append(f"Model: {ckpt_display_name}")
        if hashes:
            params.append(f"Hashes: {json.dumps(hashes, separators=(',', ':'))}")
        params.append("Version: ComfyUI")
        if civitai_resources:
            params.append(
                f"Civitai resources: {json.dumps(civitai_resources, separators=(',', ':'))}"
            )

        lines.append(", ".join(params))
        return "\n".join(lines)



def image_parameters(metadata, resources=None, *, add_loras_to_prompt=False):
    return ImageParameterFormatter(resources).format_metadata(metadata, add_loras_to_prompt)
