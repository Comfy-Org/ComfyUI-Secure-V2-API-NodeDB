"""Pinned recovery/override/report algorithms; image and live catalogue APIs pending.

This is a pure consumer of bounded image fields and host-supplied sampling-name
snapshots, not a substitute sampler registry or canonical pixel decoder.
"""
from __future__ import annotations

import json
from typing import Any

from .generation_metadata import (
    GenerationMetadata, MetadataError, extract_generation_metadata,
    finite_number, split_lora_tags,
)
from .bounds import bounded_json, MAX_STRING_BYTES
from ..secure_services.image_metadata_source import _validate_fields
from ..secure_services.documents import _preflight_json_depth

DEFAULTS = {
    "positive": "", "negative": "", "seed": 0, "steps": 20, "cfg": 7.0,
    "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
}
# An SDXL-sized starter preset inspired by ComfyUI's bottle example. These
# values are explicitly synthetic, never presented as recovered metadata.
EMPTY_IMAGE_DEFAULTS = {
    **DEFAULTS,
    "positive": "beautiful scenery inside a glass bottle, purple galaxy, intricate miniature landscape, highly detailed",
    "negative": "text, watermark",
    "width": 1024,
    "height": 1024,
}
ALLOWED_OVERRIDES = set(DEFAULTS) | {"model_name", "checkpoint_name", "unet_name", "width", "height", "loras"}


def parse_overrides(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text or "{}")
    except ValueError as exc:
        raise MetadataError(f"Invalid overrides_json: {exc}") from exc
    if not isinstance(value, dict):
        raise MetadataError("overrides_json must be an object")
    unknown = set(value) - ALLOWED_OVERRIDES
    if unknown:
        raise MetadataError(f"Unknown override keys: {', '.join(sorted(unknown))}")
    model_keys = [key for key in ("model_name", "checkpoint_name", "unet_name") if key in value]
    if len(model_keys) > 1:
        raise MetadataError("Specify only one model_name override (checkpoint_name/unet_name are legacy aliases)")
    if model_keys:
        key = model_keys[0]
        name = value.pop(key)
        if not isinstance(name, str) or not name.strip():
            raise MetadataError("model_name override must be nonempty text")
        value["model_name"] = name.strip()
    return value


_MODEL_FILE_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf")


def _model_stem(name: str) -> str:
    """Remove a known file extension, retaining dots in model/version names."""
    for extension in _MODEL_FILE_EXTENSIONS:
        if name.lower().endswith(extension):
            return name[:-len(extension)]
    return name



class MetadataPolicies:
    @staticmethod
    def _readable_report(
        image: str, values: dict[str, Any], requested_loras: list[tuple[str, float, float]],
        stack: list[tuple[str, float, float]], source: dict[str, Any], notes: list[str],
    ) -> str:
        errors = [note for note in notes if note.startswith("ERROR")]
        lines = ["🖼️ IMAGE GENERATION SETTINGS", f"Image: {image}"]
        if errors:
            lines.extend(["", "❌ ERROR — RECOVERED SETTINGS / DEFAULTS", *errors])
        else:
            lines.append("✅ Metadata extracted")
        lines.extend(["", "📦 MODEL"])
        for key, label in (("checkpoint_name", "Checkpoint"), ("unet_name", "UNet")):
            if source.get(key):
                lines.append(f"{label} recorded in image: {source[key]}")
        if values["model_name"]:
            lines.append(f"Model resolved locally: {values['model_name']} ({values['model_type']})")
        else:
            lines.append("No local model resolved.")
        lines.extend([
            "", "⚙️ SAMPLING", f"Seed: {values['seed']}", f"Steps: {values['steps']}",
            f"CFG: {values['cfg']:g}", f"Sampler: {values['sampler_name']}",
            f"Scheduler: {values['scheduler']}", f"Size: {values['width']} × {values['height']}",
            f"Denoise: {values['denoise']:g}", "", "🧩 LORAS",
        ])
        if requested_loras:
            for name, model_strength, clip_strength in requested_loras:
                lines.append(f"- {name} (model: {model_strength:g}, CLIP: {clip_strength:g})")
        else:
            lines.append("No LoRA entries extracted or selected.")
        for hint in source.get("resource_hints", []):
            if hint.get("name") not in {entry[0] for entry in requested_loras}:
                lines.append(f"- Recorded resource: {hint['name']} (strength unresolved)")
        lines.append(f"Resolved locally: {len(stack)} of {len(requested_loras)} requested entries.")
        lines.extend(["", "➕ POSITIVE PROMPT", values["positive"] or "(empty)",
                      "", "➖ NEGATIVE PROMPT", values["negative"] or "(empty)",
                      "", "📋 NOTES AND WARNINGS"])
        lines.extend(f"{'❌' if note.startswith('ERROR') else '⚠️' if note.startswith('WARNING') else 'ℹ️'} {note}" for note in notes)
        return "\n".join(lines)

    @staticmethod
    def _override_loras(value: Any) -> list[tuple[str, float, float]]:
        if not isinstance(value, list):
            raise MetadataError("loras override must be a list of [name, model_strength, clip_strength]")
        entries = []
        for entry in value:
            if not isinstance(entry, list) or len(entry) != 3 or not isinstance(entry[0], str):
                raise MetadataError("Each LoRA override must be [name, model_strength, clip_strength]")
            entries.append((entry[0], finite_number(entry[1]), finite_number(entry[2])))
        return entries

    @staticmethod
    def _validate_values(values: dict[str, Any], samplers: list[str], schedulers: list[str], strict: bool, notes: list[str]) -> None:
        for key in ("positive", "negative"):
            if not isinstance(values[key], str):
                raise MetadataError(f"{key} must be text")
        for key, low, high in (("seed", 0, 2**64 - 1), ("steps", 1, 10000), ("width", 1, 16384), ("height", 1, 16384)):
            raw = values[key]
            try:
                number = int(raw)
                if isinstance(raw, bool) or (isinstance(raw, float) and raw != number) or not low <= number <= high:
                    raise ValueError()
            except (ValueError, TypeError, OverflowError) as exc:
                raise MetadataError(f"{key} must be an integer between {low} and {high}") from exc
            values[key] = number
        for key, low, high in (("cfg", 0, 100), ("denoise", 0, 1)):
            try:
                number = finite_number(values[key])
                if not low <= number <= high:
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise MetadataError(f"{key} must be a finite number between {low} and {high}") from exc
            values[key] = number
        for key, choices in (("sampler_name", samplers), ("scheduler", schedulers)):
            if values[key] not in choices:
                if strict:
                    raise MetadataError(f"Unsupported {key}: {values[key]!r}; set an explicit override")
                fallback = DEFAULTS[key]
                if fallback not in choices:
                    raise MetadataError(f"Default {key} {fallback!r} is unavailable in this ComfyUI installation")
                notes.append(f"WARNING Replaced unsupported {key} {values[key]!r} with {fallback!r}.")
                values[key] = fallback


def _sampling_names(names: list[str]) -> None:
    if type(names) is not list or len(names) > 512:
        raise ValueError("Sampling catalogue snapshot exceeds bounds")
    if any(type(name) is not str or not name or len(name.encode("utf-8")) > 128
           or any(ord(char) < 32 or ord(char) == 127 for char in name) for name in names):
        raise ValueError("Sampling catalogue name exceeds bounds")
    if len(set(names)) != len(names):
        raise ValueError("Sampling catalogue contains duplicate names")


def prepare_settings(
    fields: dict[str, str | None], *, image_width: int, image_height: int,
    samplers: list[str], schedulers: list[str], diagnostics: str,
    sampler_node_id: str = "", missing_settings: str = "use_defaults",
    overrides_json: str = "{}", prefer_saved_image_metadata: bool = True,
) -> dict[str, Any]:
    """Recover scalar settings before managed model/LoRA catalogue resolution."""
    _validate_fields(fields)
    bounded_json([diagnostics, sampler_node_id, overrides_json, missing_settings])
    _preflight_json_depth(overrides_json)
    if type(prefer_saved_image_metadata) is not bool:
        raise ValueError("Image metadata selection flag must be Boolean")
    if any(type(axis) is not int or not 1 <= axis <= 8192 for axis in (image_width, image_height)):
        raise ValueError("Image dimensions exceed admitted bounds")
    if image_width * image_height > 16777216:
        raise ValueError("Image dimensions exceed admitted bounds")
    _sampling_names(samplers)
    _sampling_names(schedulers)
    overrides = parse_overrides(overrides_json)
    if missing_settings not in ("strict", "use_defaults"):
        raise MetadataError("Invalid missing_settings policy")
    no_metadata = False
    try:
        no_metadata = not any(fields.values())
        if no_metadata:
            extracted = GenerationMetadata(
                values=dict(EMPTY_IMAGE_DEFAULTS),
                notes=[
                    "ERROR: No generation metadata found. Using the SDXL bottle starter preset; these settings were not extracted from the image.",
                    diagnostics,
                ],
            )
        else:
            extracted = extract_generation_metadata(fields, sampler_node_id, prefer_saved_image_metadata)
    except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
        error = f"ERROR: Metadata extraction failed: {exc}"
        extracted = GenerationMetadata(issues={"source": str(exc)})
        # An unsupported API graph need not make valid saved generation
        # parameters unusable. Do not execute or infer custom graph nodes.
        if (fields.get("prompt") or fields.get("workflow")) and (fields.get("parameters") or fields.get("comment")):
            try:
                extracted = extract_generation_metadata({
                    "parameters": fields.get("parameters"), "comment": fields.get("comment"),
                })
                extracted.notes.append(error + "; recovered saved generation parameters instead.")
                if sampler_node_id.strip():
                    extracted.notes.append("ERROR: Global saved parameters cannot verify the requested sampler stage; they are an image-level fallback.")
            except (ValueError, TypeError, KeyError, RecursionError) as fallback_exc:
                extracted.notes.append(f"ERROR: Parameter fallback failed: {fallback_exc}")
        if "source" in extracted.issues:
            extracted.notes.extend([error, diagnostics])
    source_resources = {"checkpoint_name": extracted.values.get("checkpoint_name"), "unet_name": extracted.values.get("unet_name"), "loras": list(extracted.loras), "resource_hints": extracted.resource_hints}
    values = extracted.values
    notes = extracted.notes
    for key, value in overrides.items():
        values[key] = value
        extracted.issues.pop(key, None)
        notes.append(f"Explicit override: {key}.")
    if "model_name" in overrides:
        extracted.issues.pop("model", None)
        values.pop("checkpoint_name", None)
        values.pop("unet_name", None)
    if "loras" in overrides:
        extracted.loras = MetadataPolicies._override_loras(overrides["loras"])
    notes.extend(f"ERROR: {key}: {message}" for key, message in extracted.issues.items())
    # Discard incomplete graph results instead of outputting half a LoRA
    # chain or a prompt known to differ from its conditioning.
    for key in extracted.issues:
        if key not in overrides:
            values.pop(key, None)
    if "loras" in extracted.issues and "loras" not in overrides:
        extracted.loras = []
    if "model" in extracted.issues and "model_name" not in overrides:
        values.pop("checkpoint_name", None)
        values.pop("unet_name", None)
    # Extraction without a recognized latent source (e.g. img2img) leaves
    # width/height unset; the source image dimensions are the best
    # estimate then. The synthetic starter preset keeps its fixed size.
    image_fallback = not no_metadata and "source" not in extracted.issues
    for key, default in EMPTY_IMAGE_DEFAULTS.items():
        if key in values:
            continue
        if image_fallback and key in ("width", "height"):
            values[key] = image_width if key == "width" else image_height
            notes.append(f"WARNING Missing {key}; using source image dimension {values[key]}.")
        else:
            values[key] = default
            notes.append(f"ERROR: Missing {key}; using default {default!r}.")
    # Validate independently so one invalid value cannot erase the other
    # successfully extracted settings. Invalid explicit overrides still
    # identify a user configuration error rather than an extraction error.
    for key in EMPTY_IMAGE_DEFAULTS:
        trial = {**EMPTY_IMAGE_DEFAULTS, key: values[key]}
        try:
            MetadataPolicies._validate_values(trial, samplers, schedulers, True, [])
            values[key] = trial[key]
        except (ValueError, TypeError, OverflowError) as exc:
            if key in overrides:
                raise MetadataError(f"Invalid override {key}: {exc}") from exc
            values[key] = EMPTY_IMAGE_DEFAULTS[key]
            notes.append(f"ERROR: Invalid {key}: {exc}; using default {values[key]!r}.")
    # Only A1111 directives represent LoRA application. In ComfyUI graphs,
    # literal tags in encoder text are not executed by CLIPTextEncode.
    for key in ("positive", "negative"):
        try:
            clean, tags = split_lora_tags(values[key])
        except (ValueError, TypeError) as exc:
            if key in overrides:
                raise MetadataError(f"Invalid override {key}: {exc}") from exc
            values[key] = EMPTY_IMAGE_DEFAULTS[key]
            notes.append(f"ERROR: Invalid LoRA directive in {key}: {exc}; using starter prompt.")
            continue
        if tags:
            if notes and notes[0] == "A1111/Forge parameters.":
                if "loras" not in overrides:
                    extracted.loras.extend(tags)
                values[key] = clean
            else:
                notes.append(f"Literal LoRA tags retained in {key}; the embedded ComfyUI graph determines the stack.")

    result = {
        "values": values, "notes": notes, "issues": extracted.issues,
        "requested_loras": extracted.loras, "source_resources": source_resources,
        "no_metadata": no_metadata, "overrides": overrides,
    }
    bounded_json(result, allow_tuples=True)
    return result


MAX_CATALOGUE_ROWS = 6144
CATALOGUE_FOLDERS = {
    "checkpoints": "checkpoint", "diffusion_models": "diffusion_model", "loras": "lora",
}


def validate_catalogue(rows: list[dict[str, Any]]) -> None:
    """Admit logical registered names, never a cached filesystem path."""
    if type(rows) is not list or len(rows) > MAX_CATALOGUE_ROWS:
        raise ValueError("Metadata catalogue exceeds work bounds")
    bounded_json(rows)
    identities = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"folder", "name", "file_name", "model_name", "sub_type"}:
            raise ValueError("Metadata catalogue row identity is invalid")
        folder, name = row["folder"], row["name"]
        if folder not in CATALOGUE_FOLDERS or row["sub_type"] != CATALOGUE_FOLDERS[folder]:
            raise ValueError("Metadata catalogue folder is invalid")
        if type(name) is not str or not name or len(name.encode("utf-8")) > 4096 or "\\" in name or ":" in name or any(part in ("", ".", "..") for part in name.split("/")):
            raise ValueError("Metadata catalogue name is not logical")
        for alias in (row["file_name"], row["model_name"]):
            if type(alias) is not str or len(alias.encode("utf-8")) > 4096:
                raise ValueError("Metadata catalogue alias exceeds bounds")
        identity = (folder, name)
        if identity in identities:
            raise ValueError("Duplicate metadata catalogue identity")
        identities.add(identity)


def resolve_logical_resource(name: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    """Pinned four-level matching over an admitted managed catalogue snapshot.

    Absolute legacy paths in image metadata are only inert search text: output
    always uses an existing folder/name identity, never grants that path.
    """
    if not isinstance(name, str) or not name.strip():
        raise MetadataError("Missing model name")
    normalized = name.strip().replace("\\", "/")
    levels: list[list[dict[str, Any]]] = [[], [], [], []]
    for item in resources:
        path = item["name"]
        exact = normalized in (path, _model_stem(path))
        basename = normalized.rsplit("/", 1)[-1] == path.rsplit("/", 1)[-1]
        stem = _model_stem(normalized.rsplit("/", 1)[-1]) == _model_stem(path.rsplit("/", 1)[-1])
        alias = any(normalized in (value.strip(), _model_stem(value.strip())) for value in (item["file_name"], item["model_name"]))
        for index, matched in enumerate((exact, basename, stem, alias)):
            if matched:
                levels[index].append(item)
    for matches in levels:
        unique = {(item["folder"], item["name"]): item for item in matches}
        if len(unique) == 1:
            return next(iter(unique.values()))
        if unique:
            names = ", ".join(folder + "/" + name for folder, name in unique)
            raise MetadataError(f"Ambiguous local model '{name}': {names}. Specify its relative path in overrides_json.")
    raise MetadataError(f"Model '{name}' could not be matched to an existing file in the local LoRA Manager catalog")


def finish_settings(
    prepared: dict[str, Any], catalogue: list[dict[str, Any]], image: str,
    *, library_error: str | None = None,
) -> dict[str, Any]:
    """Resolve names and generate reports; canonical image/mask stays separate."""
    import copy

    bounded_json(prepared, allow_tuples=True)
    validate_catalogue(catalogue)
    bounded_json([image, library_error])
    prepared = copy.deepcopy(prepared)
    values, notes = prepared["values"], prepared["notes"]
    issues, requested_loras = prepared["issues"], prepared["requested_loras"]
    overrides, no_metadata = prepared["overrides"], prepared["no_metadata"]
    source_resources = prepared["source_resources"]
    models = [row for row in catalogue if row["folder"] != "loras"]
    loras = [row for row in catalogue if row["folder"] == "loras"]
    if library_error is not None:
        models, loras = [], []
        notes.append(f"ERROR: Local library lookup failed: {library_error}. Extracted names remain in source_resources.")
    if (no_metadata or "source" in issues) and "model_name" not in overrides:
        base_candidates = [
            item for item in models
            if item.get("sub_type") == "checkpoint"
            and item["name"].rsplit("/", 1)[-1].lower() == "sd_xl_base_1.0.safetensors"
        ]
        if len(base_candidates) == 1:
            values["model_name"] = base_candidates[0]["name"]
            notes.append("Starter checkpoint: indexed sd_xl_base_1.0.safetensors.")
        else:
            notes.append("Select an SDXL checkpoint manually, or set model_name in overrides_json. No unambiguous SDXL base checkpoint was found.")
    missing_entries = []
    name = values.get("model_name") or values.get("checkpoint_name") or values.get("unet_name")
    values.pop("checkpoint_name", None)
    values.pop("unet_name", None)
    values["model_name"] = ""
    values["model_type"] = ""
    if name:
        try:
            # A1111's generic Model label can refer to either category.
            # Search both together so duplicate names remain ambiguous.
            available_models = [item for item in models if item.get("sub_type") in ("checkpoint", "diffusion_model")]
            item = resolve_logical_resource(name, available_models)
            values["model_name"] = item["name"]
            values["model_type"] = item["sub_type"]
            notes.append(f"Resolved model_name: {values['model_name']} ({values['model_type']}).")
        except MetadataError as exc:
            missing_entries.append(f"Model: {name} — {exc}")
            notes.append(f"WARNING {exc}; model_name is empty.")
    if not values["model_name"]:
        notes.append("WARNING No model resolved. Select a model manually on your loader.")
    stack = []
    for name, model_strength, clip_strength in requested_loras:
        try:
            item = resolve_logical_resource(name, loras)
            stack.append((item["name"], model_strength, clip_strength))
        except MetadataError as exc:
            missing_entries.append(f"LoRA: {name} | model weight: {model_strength:g} | CLIP weight: {clip_strength:g} — {exc}")
            notes.append(f"WARNING Skipped LoRA: {exc}.")
    notes.append(f"Resolved {len(stack)} LoRA entries; preserve stack order and avoid adding them again in the loader widget.")
    notes.append("Metadata settings do not restore VAE, text encoders, ControlNet, regional conditioning or the original latent pipeline.")
    lora_stack_text = "\n".join(
        f"{path} | model weight: {model_strength:g} | CLIP weight: {clip_strength:g}"
        for path, model_strength, clip_strength in stack
    )
    missing_files = "\n".join(missing_entries)
    report = "\n".join(notes) + "\n\n" + json.dumps({**values, "loras": stack, "lora_stack_text": lora_stack_text, "source_resources": source_resources, "missing_files": missing_files}, ensure_ascii=False, indent=2)
    readable_report = MetadataPolicies._readable_report(image, values, requested_loras, stack, source_resources, notes)

    result = {"values": values, "lora_stack": stack, "lora_stack_text": lora_stack_text,
              "report": report, "readable_report": readable_report,
              "missing_files": missing_files, "source_resources": source_resources,
              "requested_loras": requested_loras, "notes": notes}
    bounded_json(result, allow_tuples=True)
    return result
