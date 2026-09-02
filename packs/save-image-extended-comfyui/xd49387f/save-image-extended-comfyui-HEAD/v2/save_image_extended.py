"""Sandboxed Save Image Extended implementation.

The pack still owns its naming, prompt lookup, counter, and jobs.json
algorithms.  V2 supplies only bounded graph data, image metadata, a confined
output catalogue, and host-owned image/text persistence.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from comfy_api.latest import io, sdk


VERSION = 2.88
MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin", ".pth")
COUNTER_POSITIONS = ("last", "first")
OUTPUT_EXTENSIONS = (
    ".webp",
    ".png",
    ".jpg",
    ".jpeg",
    ".j2k",
    ".jp2",
    ".gif",
    ".tiff",
    ".bmp",
    ".avif",
)
SAVE_JOB_OPTIONS = (
    "disabled",
    "prompt",
    "basic, prompt",
    "basic, sampler, prompt",
    "basic, models, sampler, prompt",
)

_MAX_PROMPT_NODES = 4096
_MAX_RECURSION = 64
_MAX_KEYS = 256
_MAX_COMPONENT_BYTES = 255
_MAX_LOGICAL_NAME_BYTES = 2048
_MAX_JOB_BYTES = 4 * 1024 * 1024

DESCRIPTION = r"""
## Advice
Enable node-id badges when selecting a value from a particular node, then use
`node_id.widget_name` in a filename or folder key.

Unqualified widget names use the last matching prompt value. `resolution`,
checkpoint/LoRA/control-net names and paths, and strftime tokens are supported.
Generated names are confined to ComfyUI's managed output directory; absolute
paths and parent-directory traversal are rejected.
"""


def _ctx():
    return sdk.ctx()


def _prompt_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("prompt metadata must be a dictionary")
    if len(value) > _MAX_PROMPT_NODES:
        raise ValueError(f"prompt metadata exceeds {_MAX_PROMPT_NODES} nodes")
    return value


def _clean_value(value: Any):
    if isinstance(value, str):
        for extension in MODEL_EXTENSIONS:
            value = value.removesuffix(extension)
    return value


def _content_value(value: Any):
    if isinstance(value, dict):
        return value.get("content", "")
    return value


def _model_name_and_parent(value: Any) -> tuple[str, str]:
    text = str(_content_value(value) or "").replace("\\", "/")
    path = PurePosixPath(text)
    name = str(_clean_value(path.name))
    parent = "" if str(path.parent) == "." else str(path.parent)
    return name, parent


def _find_keys_recursively(
    prompt: dict[str, Any],
    keys_to_find: list[str],
    found_values: dict[str, Any] | None = None,
    *,
    depth: int = 0,
) -> dict[str, Any]:
    if depth > _MAX_RECURSION:
        raise ValueError("prompt metadata nesting exceeds 64 levels")
    found = {} if found_values is None else found_values
    targets = set(keys_to_find)
    for key, original in prompt.items():
        value = _content_value(original)
        if key in targets:
            if key in {"ckpt_path", "ckpt_name"}:
                name, parent = _model_name_and_parent(value)
                if "ckpt_path" in targets:
                    found["ckpt_path"] = parent
                elif "ckpt_name" in targets:
                    found["ckpt_name"] = name
            elif key in {"control_net_path", "control_net_name"}:
                name, parent = _model_name_and_parent(value)
                if "control_net_path" in targets:
                    found["control_net_path"] = parent
                elif "control_net_name" in targets:
                    found["control_net_name"] = name
            elif key in {"lora_path", "lora_name"}:
                name, parent = _model_name_and_parent(value)
                if "lora_path" in targets:
                    found["lora_path"] = parent
                elif "lora_name" in targets:
                    found["lora_name"] = name
            else:
                found[key] = _clean_value(value)
        elif isinstance(original, dict):
            _find_keys_recursively(
                original,
                keys_to_find,
                found,
                depth=depth + 1,
            )
    return found


def _find_parameter_values(
    target_keys: list[str],
    prompt: dict[str, Any],
):
    found: dict[str, Any] = {}
    loras: list[str] = []

    def visit(value: dict[str, Any], depth: int) -> None:
        if depth > _MAX_RECURSION:
            raise ValueError("prompt metadata nesting exceeds 64 levels")
        for key, item in value.items():
            if (
                "loras" in target_keys
                and re.fullmatch(r"lora(_name)?(_\d+)?", key)
                and item is not None
            ):
                loras.append(str(_clean_value(_content_value(item))))
            if isinstance(item, dict):
                visit(item, depth + 1)
            if key in target_keys:
                found[key] = _clean_value(_content_value(item))

    visit(prompt, 0)
    if "loras" in target_keys and loras:
        found["loras"] = ", ".join(item for item in loras if item)
    if len(target_keys) == 1:
        return found.get(target_keys[0])
    return found


def _lookup_special(
    prompt: dict[str, Any],
    node_prompt: dict[str, Any],
    key: str,
    found: dict[str, Any],
) -> None:
    source = node_prompt or prompt
    if key == "ckpt_path":
        _find_keys_recursively(source, ["ckpt_name", key], found)
    elif key == "control_net_path":
        _find_keys_recursively(source, ["control_net_name", key], found)
    elif key == "lora_path":
        _find_keys_recursively(source, ["lora_name", key], found)
    else:
        _find_keys_recursively(source, [key], found)


def generate_custom_name(
    keys_to_extract: list[str],
    prefix: str,
    delimiter: str,
    prompt: dict[str, Any],
    resolution: str,
    timestamp: datetime,
    named_keys: bool = False,
) -> str:
    """Keep upstream's prompt-key/name formatting algorithm pack-side."""
    if len(keys_to_extract) > _MAX_KEYS:
        raise ValueError(f"a generated name is limited to {_MAX_KEYS} keys")
    custom_name: list[str] = []
    if prefix:
        custom_name.append(timestamp.strftime(prefix) if "%" in prefix else prefix)

    if keys_to_extract != [""]:
        found_values: dict[str, Any] = {}
        for original_key in keys_to_extract:
            key = original_key
            if not key:
                continue
            value: Any = None
            node_key: str | None = None

            if "%" in key:
                value = timestamp.strftime(key)

            if "/" in key:
                values = re.split(r"/+", key)
                if values[0] in ("", ".", ".."):
                    custom_name.append(values[0] + "/")
                    key = values[1] if len(values) > 1 else ""
                    if not key:
                        continue
                else:
                    key = values[0]

            if ((key.startswith("'") and key.endswith("'")) or
                    (key.startswith('"') and key.endswith('"'))):
                value = key

            if value is None:
                split_key = key.split(".")
                if len(split_key) == 2:
                    if "" not in split_key:
                        if split_key[0].isdecimal():
                            node_id, node_key = split_key
                            selected = prompt.get(node_id)
                            if not isinstance(selected, dict):
                                selected = prompt
                            _lookup_special(prompt, selected, node_key, found_values)
                        else:
                            value = _clean_value(key)
                    else:
                        value = key
                else:
                    node_key = key
                    if node_key == "resolution":
                        value = resolution
                    else:
                        _lookup_special(prompt, prompt, node_key, found_values)

            if value is None and node_key is not None:
                if node_key in found_values:
                    found = found_values[node_key]
                    value = f"{node_key}={found}" if named_keys else found
                if value is None:
                    value = node_key

            if isinstance(value, str):
                if node_key in {"ckpt_path", "control_net_path", "lora_path"}:
                    value = found_values.get(node_key, value)
                else:
                    value = _clean_value(value)
            elif isinstance(value, float):
                value = float(f"{value:.10g}")
            custom_name.append(str(value))

    custom_name = [str(item).strip() for item in custom_name if item]
    name = delimiter.join(custom_name)
    name = name.replace("/" + delimiter, "/")
    name = name.replace(delimiter + "/", "/")
    name = name.replace(delimiter + ".", ".")
    name = re.sub(r"\s+", " ", name)
    if delimiter:
        name = name.strip(delimiter)
    name = name.strip("/")
    if delimiter:
        name = name.strip(delimiter)
    name = name.strip(".")
    name = re.sub(r'[*?:"<>|]', "", name)
    return name.replace("\\", "/")


def _logical_components(value: str) -> list[str]:
    text = str(value or "").replace("\\", "/")
    if "\x00" in text or text.startswith("/"):
        raise ValueError("output names must be relative")
    result: list[str] = []
    for component in text.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            raise ValueError("output names cannot traverse parent directories")
        if len(component.encode("utf-8")) > _MAX_COMPONENT_BYTES:
            raise ValueError("an output-name component exceeds 255 bytes")
        result.append(component)
    return result


def _join_logical(*values: str) -> str:
    components: list[str] = []
    for value in values:
        components.extend(_logical_components(value))
    logical = "/".join(components)
    if len(logical.encode("utf-8")) > _MAX_LOGICAL_NAME_BYTES:
        raise ValueError("the output logical name exceeds 2048 bytes")
    return logical


def _directory_entries(names: list[str], folder: str) -> list[str]:
    expected = _join_logical(folder)
    result: list[str] = []
    for name in names:
        logical = _join_logical(name)
        path = PurePosixPath(logical)
        parent = "" if str(path.parent) == "." else str(path.parent)
        if parent == expected:
            result.append(path.name)
    return result


def get_latest_counter(
    files: list[str],
    filename: str,
    counter_digits: int,
    counter_position: str,
    output_ext: str,
) -> int:
    counter = 1
    matching = [item for item in files if item.endswith(output_ext)]
    if not matching:
        return counter
    if counter_position not in COUNTER_POSITIONS:
        counter_position = "last"
    extension_length = len(output_ext)
    if not filename:
        counters = [
            int(item[:counter_digits])
            if item[:counter_digits].isdecimal()
            and len(item) == counter_digits + extension_length
            else 0
            for item in matching
        ]
    elif counter_position == "last":
        counters = [
            int(item[-(extension_length + counter_digits):-extension_length])
            if item[-(extension_length + counter_digits):-extension_length].isdecimal()
            else 0
            for item in matching
            if item.startswith(filename)
        ]
    else:
        counters = [
            int(item[:counter_digits]) if item[:counter_digits].isdecimal() else 0
            for item in matching
            if item[counter_digits + 1:].startswith(filename)
        ]
    return max(counters) + 1 if counters else counter


def _image_name(
    filename: str,
    filename_prefix: str,
    delimiter: str,
    counter: int,
    counter_digits: int,
    counter_position: str,
    output_ext: str,
) -> str:
    if counter_digits > 0:
        number = f"{counter:0{counter_digits}}"
        if filename:
            return (
                f"{filename}{delimiter}{number}{output_ext}"
                if counter_position == "last"
                else f"{number}{delimiter}{filename}{output_ext}"
            )
        return f"{number}{output_ext}"
    return f"{filename if filename else filename_prefix}{output_ext}"


def _valid_prompt_text(value: Any) -> bool:
    return not (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and len(value[0]) < 6
        and isinstance(value[1], (int, float))
    )


def build_job_data(
    save_job_data: str,
    prompt: dict[str, Any],
    filename_prefix: str,
    positive_text_opt: Any,
    negative_text_opt: Any,
    job_custom_text: str,
    resolution: str,
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if "basic" in save_job_data:
        if filename_prefix:
            data["filename_prefix"] = filename_prefix
        data["resolution"] = resolution
    if job_custom_text:
        data["custom_text"] = job_custom_text

    if "models" in save_job_data:
        models = _find_parameter_values(
            ["ckpt_name", "loras", "vae_name", "model_name"], prompt
        )
        for source, target in (
            ("ckpt_name", "checkpoint"),
            ("loras", "loras"),
            ("vae_name", "vae"),
            ("model_name", "upscale_model"),
        ):
            if models.get(source):
                data[target] = models[source]

    if "sampler" in save_job_data:
        data["sampler_parameters"] = _find_parameter_values(
            ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
            prompt,
        )

    if "prompt" in save_job_data:
        if positive_text_opt is not None and _valid_prompt_text(positive_text_opt):
            data["positive_prompt"] = positive_text_opt
        if negative_text_opt is not None and _valid_prompt_text(negative_text_opt):
            data["negative_prompt"] = negative_text_opt
        if positive_text_opt is None and negative_text_opt is None:
            for node in prompt.values():
                if not isinstance(node, dict):
                    continue
                class_type = node.get("class_type")
                inputs = node.get("inputs", {})
                if not isinstance(inputs, dict):
                    continue
                if class_type in {"Efficient Loader", "Eff. Loader SDXL"}:
                    if "positive" in inputs and "negative" in inputs:
                        data["positive_prompt"] = inputs.get("positive")
                        data["negative_prompt"] = inputs.get("negative")
                elif class_type in {"KSampler", "KSamplerAdvanced", "UltimateSDUpscale"}:
                    for key, target in (
                        ("positive", "positive_prompt"),
                        ("negative", "negative_prompt"),
                    ):
                        reference = inputs.get(key)
                        reference_id = reference[0] if isinstance(reference, list) and reference else None
                        source = prompt.get(str(reference_id), {})
                        source_inputs = source.get("inputs", {}) if isinstance(source, dict) else {}
                        text = source_inputs.get("text") if isinstance(source_inputs, dict) else None
                        if text is not None and _valid_prompt_text(text):
                            data[target] = text
    return data


async def _read_job_file(logical_name: str) -> dict[str, Any]:
    assets = _ctx().assets
    if not await assets.exists("output", logical_name):
        return {}
    ref = await assets.resolve("output", logical_name)
    size = await assets.size(ref)
    if size < 0 or size > _MAX_JOB_BYTES:
        raise ValueError("existing job data exceeds 4 MiB")
    raw = await assets.read_bytes(ref)
    if len(raw) != size:
        raise ValueError("existing job data changed while it was read")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


async def _write_job_file(
    logical_name: str,
    timestamp: datetime,
    job_data: dict[str, Any],
) -> None:
    existing = await _read_job_file(logical_name)
    existing[timestamp.strftime("%c")] = job_data
    text = json.dumps(existing, ensure_ascii=False, indent=4)
    if len(text.encode("utf-8")) > _MAX_JOB_BYTES:
        raise ValueError("job data exceeds 4 MiB")
    await _ctx().output.write_text(
        text,
        filename=logical_name,
        folder="output",
        mode="overwrite",
    )


class SaveImageExtended(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "output")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveImageExtended",
            display_name=f"💾 Save Image Extended {VERSION}",
            category="image",
            description=DESCRIPTION,
            inputs=[
                io.Image.Input("images"),
                io.String.Input("filename_prefix", default="ComfyUI", multiline=False),
                io.String.Input(
                    "filename_keys",
                    default="sampler_name, cfg, steps, %F %H-%M-%S",
                    multiline=True,
                ),
                io.String.Input("foldername_prefix", default="", multiline=False),
                io.String.Input("foldername_keys", default="ckpt_name", multiline=True),
                io.String.Input("delimiter", default="-", multiline=False),
                io.Combo.Input(
                    "save_job_data",
                    options=list(SAVE_JOB_OPTIONS),
                    default="disabled",
                ),
                io.Boolean.Input("job_data_per_image", default=False),
                io.String.Input("job_custom_text", default="", multiline=False),
                io.Boolean.Input("save_metadata", default=True),
                io.Int.Input("counter_digits", default=4, min=0, max=8, step=1),
                io.Combo.Input(
                    "counter_position",
                    options=list(COUNTER_POSITIONS),
                    default="last",
                ),
                io.Boolean.Input("one_counter_per_folder", default=True),
                io.Boolean.Input("image_preview", default=True),
                io.Combo.Input(
                    "output_ext",
                    options=list(OUTPUT_EXTENSIONS),
                    default=".webp",
                ),
                io.Int.Input("quality", default=90, min=0, max=100, step=1),
                io.Boolean.Input("named_keys", default=False),
                io.String.Input(
                    "positive_text_opt",
                    optional=True,
                    force_input=True,
                ),
                io.String.Input(
                    "negative_text_opt",
                    optional=True,
                    force_input=True,
                ),
            ],
            outputs=[],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
            not_idempotent=True,
        )

    @classmethod
    async def execute(
        cls,
        images: sdk.ImageRef,
        filename_prefix: str,
        filename_keys: str,
        foldername_prefix: str,
        foldername_keys: str,
        delimiter: str,
        save_job_data: str,
        job_data_per_image: bool,
        job_custom_text: str,
        save_metadata: bool,
        counter_digits: int,
        counter_position: str,
        one_counter_per_folder: bool,
        image_preview: bool,
        output_ext: str,
        quality: int,
        named_keys: bool,
        positive_text_opt: str | None = None,
        negative_text_opt: str | None = None,
        prompt: dict[str, Any] | None = None,
        extra_pnginfo: dict[str, Any] | None = None,
    ) -> io.NodeOutput:
        del one_counter_per_folder, extra_pnginfo
        prompt_data = _prompt_dict(prompt)
        if output_ext not in OUTPUT_EXTENSIONS:
            raise ValueError(f"unsupported output extension {output_ext!r}")
        quality = 90 if int(quality) == 0 else int(quality)
        if not 1 <= quality <= 100:
            raise ValueError("quality must be in [0, 100], where 0 selects 90")
        counter_digits = int(counter_digits)
        if not 0 <= counter_digits <= 8:
            raise ValueError("counter_digits must be in [0, 8]")
        if counter_position not in COUNTER_POSITIONS:
            counter_position = "last"
        delimiter = str(delimiter or "")[:1]

        height, width = await images.spatial_shape()
        batch_size = await images.batch_size()
        resolution = f"{width}x{height}"
        timestamp = datetime.now()
        filename_parts = [item.strip() for item in str(filename_keys).split(",")]
        folder_parts = [item.strip() for item in str(foldername_keys).split(",")]
        custom_folder = generate_custom_name(
            folder_parts,
            str(foldername_prefix),
            delimiter,
            prompt_data,
            resolution,
            timestamp,
            bool(named_keys),
        )
        custom_filename = generate_custom_name(
            filename_parts,
            str(filename_prefix),
            delimiter,
            prompt_data,
            resolution,
            timestamp,
            bool(named_keys),
        )

        filename_path = PurePosixPath(custom_filename)
        nested = "" if str(filename_path.parent) == "." else str(filename_path.parent)
        filename = filename_path.name
        output_folder = _join_logical(custom_folder, nested)
        try:
            catalogue = await _ctx().assets.list(
                "output",
                prefix=output_folder,
                recursive=False,
            )
        except FileNotFoundError:
            catalogue = []
        entries = _directory_entries(catalogue, output_folder)
        counter = get_latest_counter(
            entries,
            filename,
            counter_digits,
            counter_position,
            output_ext,
        )

        logical_names: list[str] = []
        for index in range(batch_size):
            image_name = _image_name(
                filename,
                str(filename_prefix),
                delimiter,
                counter + index,
                counter_digits,
                counter_position,
                output_ext,
            )
            logical_names.append(_join_logical(output_folder, image_name))
        if len(set(logical_names)) != len(logical_names):
            raise ValueError(
                "counter-disabled batch output would overwrite the same image"
            )

        compress_quality = min(quality, 90)
        compress_level = round(compress_quality / 90 * 9)
        image_format = output_ext.removeprefix(".")
        saved = await _ctx().output.save_images(
            images,
            filenames=logical_names,
            compress_level=compress_level,
            save_metadata=bool(save_metadata),
            image_format=image_format,
            quality=quality,
            lossless=(
                quality == 100
                and image_format in {"webp", "avif", "j2k", "jp2"}
            ),
            optimize=image_format in {"webp", "avif", "jpg", "jpeg", "tiff"},
        )

        if save_job_data != "disabled":
            if save_job_data not in SAVE_JOB_OPTIONS:
                raise ValueError(f"unsupported save_job_data option {save_job_data!r}")
            job_data = build_job_data(
                save_job_data,
                prompt_data,
                str(filename_prefix),
                positive_text_opt,
                negative_text_opt,
                str(job_custom_text),
                resolution,
            )
            if job_data_per_image:
                for logical_name in logical_names:
                    path = PurePosixPath(logical_name)
                    await _write_job_file(
                        str(path.with_suffix(".json")), timestamp, job_data
                    )
            else:
                await _write_job_file(
                    _join_logical(output_folder, "jobs.json"), timestamp, job_data
                )

        ui = saved if isinstance(saved, dict) else {"images": []}
        if not image_preview:
            ui = {"images": []}
        return io.NodeOutput(ui=ui)

    @classmethod
    def fingerprint_inputs(cls, **_kwargs):
        return math.nan


NODE_CLASS_MAPPINGS = {"SaveImageExtended": SaveImageExtended}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveImageExtended": f"💾 Save Image Extended {VERSION}",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
