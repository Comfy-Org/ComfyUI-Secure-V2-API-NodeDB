import asyncio
import fnmatch
import json
import logging
import os
import posixpath
import re
import time
from datetime import datetime
from enum import Enum

from comfy_api.latest import io, sdk

from .. import hook
from .._v2_capture import SAVE_LOCK, bind_loop, bind_snapshot, run_async
from .._v2_refusals import (JPEG, SUBDIR_BACKSLASH, SUBDIR_ESCAPE, SUBDIR_WITH_PREFIX_FOLDER,
                            SecureConversionRefusal)
from ..capture import Capture
from ..trace import Trace
from ..utils.log import print_warning


class OutputFormat(str, Enum):
    PNG = "png"
    PNG_JSON = "png_with_json"
    JPG = "jpg"
    JPG_JSON = "jpg_with_json"
    WEBP = "webp"
    WEBP_JSON = "webp_with_json"


class QualityOption(str, Enum):
    MAX = "max"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MetadataScope(str, Enum):
    FULL = "full"
    DEFAULT = "default"
    PARAMETERS_ONLY = "parameters_only"
    WORKFLOW_ONLY = "workflow_only"
    NONE = "none"


# --- Secure Nodes V2: the guest has no host paths. Every name below is relative to the output root;
# the managed image writer (ctx.output.save_images) publishes the files.

def _compute_vars(input, image_width, image_height):
    # folder_paths.get_save_image_path.compute_vars (core 6257422b, folder_paths.py:536-546)
    input = input.replace("%width%", str(image_width))
    input = input.replace("%height%", str(image_height))
    now = time.localtime()
    input = input.replace("%year%", str(now.tm_year))
    input = input.replace("%month%", str(now.tm_mon).zfill(2))
    input = input.replace("%day%", str(now.tm_mday).zfill(2))
    input = input.replace("%hour%", str(now.tm_hour).zfill(2))
    input = input.replace("%minute%", str(now.tm_min).zfill(2))
    input = input.replace("%second%", str(now.tm_sec).zfill(2))
    return input


def _escapes_output(relative):
    normalized = posixpath.normpath(relative) if relative else ""
    return posixpath.isabs(normalized) or normalized == ".." or normalized.startswith("../")


def _get_save_image_path(filename_prefix, image_width=0, image_height=0):
    """folder_paths.get_save_image_path (core 6257422b, folder_paths.py:525-570), relative to the
    output root. The original only used the counter it computed through find_next_available_filename."""
    if "%" in filename_prefix:
        filename_prefix = _compute_vars(filename_prefix, image_width, image_height)

    subfolder = os.path.dirname(os.path.normpath(filename_prefix))
    filename = os.path.basename(os.path.normpath(filename_prefix))

    full_output_folder = subfolder

    if _escapes_output(full_output_folder):
        err = "**** ERROR: Saving image outside the output folder is not allowed." + \
              "\n full_output_folder: " + full_output_folder + \
              "\n         output_dir: output"
        logging.error(err)
        raise Exception(err)

    counter = 1
    return full_output_folder, filename, counter, subfolder, filename_prefix


def _output_path(folder, name):
    joined = posixpath.join(folder, name) if folder else name
    return posixpath.normpath(joined)


def _exists(path):
    return bool(run_async(sdk.ctx().assets.exists("output", path)))


class _ImageBatch:
    """The IMAGE input as the save loop uses it: its length, its size, one image at a time."""

    def __init__(self, ref, batch_size, height, width):
        self.ref = ref
        self.height = height
        self.width = width
        self._length = batch_size

    def __len__(self):
        return self._length

    def select(self, index):
        return run_async(self.ref.select_batch([index]))


class _PngText:
    """Stands in for PIL's PngInfo: records add_text calls; the managed writer encodes them as PNG text
    chunks in this order (png_text)."""

    def __init__(self):
        self.entries = []

    def add_text(self, key, value, zip=False):
        if isinstance(key, str):
            key.encode("latin-1", "strict")  # PngInfo.add_text raises UnicodeEncodeError here too
        self.entries.append((key, value))

    def as_png_text(self):
        # A repeated keyword is one chunk here: readers (Pillow, the ComfyUI frontend) keep the last value,
        # which this keeps, at the keyword's first position.
        result = {}
        for key, value in self.entries:
            result[key] = value
        return result


def _save(image_ref, path, image_format, **options):
    record = run_async(sdk.ctx().output.save_images(
        image_ref, filenames=[path], image_format=image_format, **options))
    return record["images"][0]


# refer. https://github.com/comfyanonymous/ComfyUI/blob/38b7ac6e269e6ecc5bdd6fefdfb2fb1185b09c9d/nodes.py#L1411
class _Saver:
    """SaveImageWithMetaData.save_images from modules/nodes/node.py; only the file writes go through the SDK."""

    OUTPUT_FORMATS = [e for e in OutputFormat]
    QUALITY_OPTIONS = [e for e in QualityOption]
    METADATA_OPTIONS = [e for e in MetadataScope]
    NEEDS_METADATA_KEYS = {"seed", "width", "height", "pprompt", "nprompt", "model"}

    def __init__(self):
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4

    pattern_format = re.compile(r"(%[^%]+%)") # Pattern to match mask values in the filename

    def parse_output_format(self, output_format: str):
        fmt = OutputFormat(output_format)
        save_workflow_json = fmt.name.endswith("JSON")
        base_format = fmt.replace("_with_json", "")
        return base_format, save_workflow_json

    def get_quality_value(self, quality: str) -> int:
        return {
            QualityOption.MAX: 100,
            QualityOption.HIGH: 80,
            QualityOption.MEDIUM: 60,
            QualityOption.LOW: 30
        }.get(quality, 100)

    def find_next_available_filename(self, folder: str, name: str, ext: str):
        """
        Finds the next available filename by checking existing files in the directory.
        """
        # Secure Nodes V2: the original globbed the folder (Path(folder).glob(f"{name}_*.{ext}")) for the
        # first free number; the catalogue listing gives the same names. When the folder holds more names
        # than the catalogue lists at once, the same first free number is found by probing.
        pattern = f"{name}_*.{ext}"
        directory = posixpath.dirname(_output_path(folder, pattern))
        try:
            listed = run_async(sdk.ctx().assets.list("output", prefix=directory, recursive=False))
        except ValueError:
            listed = None
        if listed is None:
            i = 1
            while _exists(_output_path(folder, f"{name}_{i:05d}.{ext}")):
                i += 1
            return i
        existing = {posixpath.splitext(posixpath.basename(entry))[0] for entry in listed
                    if fnmatch.fnmatchcase(posixpath.basename(entry), posixpath.basename(pattern))}
        i = 1
        while f"{name}_{i:05d}" in existing:
            i += 1
        return i

    @classmethod
    def parse_filename_placeholders(cls, filename: str) -> list[str]:
        """Extracts placeholder segments like %seed%, %pprompt:32%, etc."""
        return re.findall(cls.pattern_format, filename) if "%" in filename else []

    def needs_pnginfo_in_filename(self, segments: list[str]) -> bool:
        for segment in segments:
            parts = segment.strip("%").split(":")
            if parts[0] in self.NEEDS_METADATA_KEYS:
                return True
        return False

    def save_images(self, images, filename_prefix="ComfyUI", subdirectory_name="", prompt=None,
                    extra_pnginfo=None, extra_metadata=None, output_format="png",
                    quality="max", metadata_scope="full",
                    include_batch_num=True, prefer_nearest=True, pnginfo_dict=None):

        extra_metadata = extra_metadata or {}
        base_format, save_workflow_json = self.parse_output_format(output_format)
        pnginfo = _PngText()

        # Parse filename
        filename_prefix = filename_prefix.strip()
        segments = self.parse_filename_placeholders(filename_prefix)

        if metadata_scope in [MetadataScope.FULL, MetadataScope.PARAMETERS_ONLY] or self.needs_pnginfo_in_filename(segments):
            pnginfo_dict = pnginfo_dict or self.gen_pnginfo(prompt, prefer_nearest)

        filename_prefix = self.format_filename(filename_prefix, pnginfo_dict or {}, segments) + self.prefix_append
        subdirectory_name = self.format_filename(subdirectory_name, pnginfo_dict or {})


        full_output_folder, filename, counter, subfolder, filename_prefix = _get_save_image_path(
            filename_prefix, images.width, images.height
        )

        # Handle subdirectory naming and creation
        subdirectory_name = subdirectory_name.strip()
        if subdirectory_name:
            subdirectory_name = self.format_filename(subdirectory_name, pnginfo_dict)
            full_output_folder = subdirectory_name
            filename = filename_prefix
            # Secure Nodes V2: the original joined subdirectory_name to the output folder without a check
            # and created only that folder (os.makedirs) before writing.
            if "\\" in subdirectory_name:
                raise SecureConversionRefusal(SUBDIR_BACKSLASH.format(field="subdirectory_name", name=subdirectory_name))
            if _escapes_output(subdirectory_name):
                raise SecureConversionRefusal(SUBDIR_ESCAPE.format(name=subdirectory_name))
            if "/" in filename:
                raise SecureConversionRefusal(SUBDIR_WITH_PREFIX_FOLDER.format(prefix=filename))
        if "\\" in filename:
            raise SecureConversionRefusal(SUBDIR_BACKSLASH.format(field="filename_prefix", name=filename))

        # The managed writer creates the folder when it publishes the first image.

        results = list()
        images_length = len(images)
        last_image_filename = None

        # Process each image
        for batch_number in range(images_length):
            # Prepare metadata
            metadata = self.prepare_pnginfo(pnginfo, pnginfo_dict, batch_number, images_length, prompt, extra_pnginfo, metadata_scope)
            for key, value in extra_metadata.items():
                metadata.add_text(key, value)

            # Handle filename collision and batch number inclusion
            file = f"{filename}_{batch_number:05d}.{base_format}" if include_batch_num else f"{filename}.{base_format}"
            path = _output_path(full_output_folder, file)

            # Check for filename collision (using next available name)
            if _exists(path):
                count = self.find_next_available_filename(full_output_folder, filename, base_format)
                file = f"{filename}_{count:05d}.{base_format}"
                path = _output_path(full_output_folder, file)

            last_image_filename = file
            quality_value = self.get_quality_value(quality)

            # Save image based on format
            image = images.select(batch_number)
            if base_format == "webp":
                # The original saved the WebP first, then built the EXIF UserComment from
                # Capture.gen_parameters_str(pnginfo_dict) and inserted it (piexif); an error there left
                # the image without EXIF.
                try:
                    parameters, failure = Capture.gen_parameters_str(pnginfo_dict), None
                except Exception as error:
                    parameters, failure = None, error
                saved = _save(image, path, "webp", quality=quality_value, lossless=(quality_value == 100),
                              save_metadata=False, a1111_parameters=parameters)
                if failure is not None:
                    raise failure
            elif base_format == "png":
                saved = _save(image, path, "png", compress_level=self.compress_level,
                              png_text=metadata.as_png_text() if metadata is not None else {})
            else:
                raise SecureConversionRefusal(JPEG.format(fmt=output_format))

            results.append({"filename": file, "subfolder": saved["subfolder"], "type": self.type})

        # Save workflow metadata for the batch
        if save_workflow_json and images_length > 0 and last_image_filename:
            json_filename = last_image_filename.replace(base_format, "json")
            batch_json_file = _output_path(full_output_folder, json_filename)

            # The original opened the file for writing (creating or emptying it) before it read
            # extra_pnginfo["workflow"]; a missing workflow therefore left an empty file.
            run_async(sdk.ctx().output.write_text(
                "", filename=batch_json_file, folder="output", mode="overwrite"))
            run_async(sdk.ctx().output.write_text(
                json.dumps(extra_pnginfo["workflow"]), filename=batch_json_file, folder="output", mode="overwrite"))

        return {"ui": {"images": results}}

    def prepare_pnginfo(self, metadata, pnginfo_dict, batch_number, total_images, prompt, extra_pnginfo, metadata_scope):
        """
        Return final PNG metadata with batch information, parameters, and optional prompt details.
        """
        if metadata_scope == MetadataScope.NONE:
            return None

        if pnginfo_dict:
            pnginfo_copy = pnginfo_dict.copy()

            if total_images > 1:
                pnginfo_copy["Batch index"] = batch_number
                pnginfo_copy["Batch size"] = total_images

            if metadata_scope in [MetadataScope.FULL, MetadataScope.PARAMETERS_ONLY]:
                parameters = Capture.gen_parameters_str(pnginfo_copy)
                if parameters and "Steps" in parameters:
                    metadata.add_text("parameters", parameters)
                    if metadata_scope == MetadataScope.PARAMETERS_ONLY:
                        return metadata

        if prompt is not None and metadata_scope != MetadataScope.WORKFLOW_ONLY:
            metadata.add_text("prompt", json.dumps(prompt))

        if extra_pnginfo is not None:
            for x in extra_pnginfo:
                metadata.add_text(x, json.dumps(extra_pnginfo[x]))

        return metadata

    @classmethod
    def gen_pnginfo(s, prompt, prefer_nearest):
        inputs = Capture.get_inputs()
        trace_tree_from_this_node = Trace.trace(hook.current_save_image_node_id, prompt)
        inputs_before_this_node = Trace.filter_inputs_by_trace_tree(inputs, trace_tree_from_this_node, prefer_nearest)

        sampler_node_id = Trace.find_sampler_node_id(trace_tree_from_this_node)
        if sampler_node_id:
            trace_tree_from_sampler_node = Trace.trace(sampler_node_id, prompt)
            inputs_before_sampler_node = Trace.filter_inputs_by_trace_tree(inputs, trace_tree_from_sampler_node, prefer_nearest)
        else:
            inputs_before_sampler_node = {}

        return Capture.gen_pnginfo_dict(inputs_before_sampler_node, inputs_before_this_node, prompt)

    @classmethod
    def format_filename(cls, filename, pnginfo_dict, segments=None):
        """
        Replaces placeholders in the filename with actual values like date, seed, prompt, etc.
        """
        if "%" not in filename:
            return filename

        segments = segments or re.findall(cls.pattern_format, filename)
        now = datetime.now()
        date_table = {
            "yyyy": f"{now.year}",
            "MM": f"{now.month:02d}",
            "dd": f"{now.day:02d}",
            "hh": f"{now.hour:02d}",
            "mm": f"{now.minute:02d}",
            "ss": f"{now.second:02d}",
        }

        for segment in segments:
            parts = segment.strip("%").split(":")
            key = parts[0]

            if key == "seed":
                seed = pnginfo_dict.get("Seed")
                if seed is None:
                    print_warning("Seed not found in pnginfo_dict!")
                filename = filename.replace(segment, str(seed or ""))

            elif key in {"width", "height"}:
                size = pnginfo_dict.get("Size", "x").split("x")
                if "Size" not in pnginfo_dict:
                    print_warning("Size not found in pnginfo_dict!")
                value = size[0] if key == "width" else size[1]
                filename = filename.replace(segment, value)

            elif key in {"pprompt", "nprompt"}:
                prompt_key = "Positive prompt" if key == "pprompt" else "Negative prompt"
                prompt = pnginfo_dict.get(prompt_key, "")
                if not prompt:
                    print_warning(f"{prompt_key} not found in pnginfo_dict!")
                prompt = prompt.replace("\n", " ")
                length = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                filename = filename.replace(segment, prompt[:length].strip() if length else prompt.strip())

            elif key == "model":
                model = pnginfo_dict.get("Model", "")
                if not model:
                    print_warning("Model not found in pnginfo_dict!")
                model = os.path.splitext(os.path.basename(model))[0]
                length = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                filename = filename.replace(segment, model[:length] if length else model)

            elif key == "date":
                date_format = parts[1] if len(parts) > 1 else "yyyyMMddhhmmss"
                for k, v in date_table.items():
                    date_format = date_format.replace(k, v)
                filename = filename.replace(segment, date_format)

        return filename


class SaveImageWithMetaData(io.ComfyNode):
    OUTPUT_FORMATS = [e for e in OutputFormat]
    QUALITY_OPTIONS = [e for e in QualityOption]
    METADATA_OPTIONS = [e for e in MetadataScope]
    DESCRIPTION = "Saves the input images with metadata to your ComfyUI output directory."
    SDK_REFS = True
    SDK_PERMISSIONS = ("graph.metadata", "assets", "output")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageWithMetaData",
            display_name="Save Image With MetaData",
            category="SaveImage",
            description=cls.DESCRIPTION,
            is_output_node=True,
            inputs=[
                io.Image.Input("images", tooltip="The images to save."),
                io.String.Input("filename_prefix", default="ComfyUI", multiline=None, tooltip="The prefix for the saved file. You can include formatting options like %date:yyyy-MM-dd% or %seed%, and combine them as needed, e.g., %date:hhmmss%_%seed%."),
                io.String.Input("subdirectory_name", default="", multiline=None, tooltip=(
                    "Custom directory to save the images. Leave empty to use the default output "
                    "directory. You can include formatting options like %date:yyyy-MM-dd%."
                )),
                io.Combo.Input("output_format", options=[e.value for e in OutputFormat], tooltip="The format in which the images will be saved."),
                io.Custom("EXTRA_METADATA").Input("extra_metadata", optional=True, tooltip="Additional key-value metadata to include in the image."),
                io.Combo.Input("quality", options=[e.value for e in QualityOption], optional=True, tooltip="Image quality:"
                                "\n'max' / 'lossless WebP' - 100"
                                "\n'high' - 80"
                                "\n'medium' - 60"
                                "\n'low' - 30"
                                "\n\nNote: Lower quality, smaller file size. PNG images ignore this setting."),
                io.Combo.Input("metadata_scope", options=[e.value for e in MetadataScope], optional=True, tooltip="Choose the metadata to save: "
                                "\n'full' - default metadata with additional metadata, "
                                "\n'default' - same as SaveImage node, "
                                "\n'parameters_only' - only A1111-style metadata, "
                                "\n'workflow_only' - workflow metadata only, "
                                "\n'none' - no metadata."),
                io.Boolean.Input("include_batch_num", default=True, optional=True, tooltip="Include batch number in filename."),
                io.Boolean.Input("prefer_nearest", default=True, optional=True, tooltip="Select inputs from closest nodes first if true."),
            ],
            outputs=[],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
        )

    @classmethod
    async def execute(cls, images, filename_prefix="ComfyUI", subdirectory_name="", output_format="png",
                      extra_metadata=None, quality="max", metadata_scope="full",
                      include_batch_num=True, prefer_nearest=True):
        saver = _Saver()
        base_format, _ = saver.parse_output_format(output_format)
        if base_format == "jpg":
            raise SecureConversionRefusal(JPEG.format(fmt=output_format))
        prompt = cls.hidden.prompt
        extra_pnginfo = cls.hidden.extra_pnginfo

        segments = saver.parse_filename_placeholders(filename_prefix.strip())
        needs_capture = (metadata_scope in [MetadataScope.FULL, MetadataScope.PARAMETERS_ONLY]
                         or saver.needs_pnginfo_in_filename(segments))
        # The running prompt and (when the capture needs them) its observed node inputs and outputs come
        # from the broker: what the original read from its executor hooks.
        snapshot = await sdk.ctx().graph.execution_metadata(include_observations=bool(needs_capture))
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        height, width = await images.spatial_shape()
        batch = _ImageBatch(images, int(await images.batch_size()), height, width)
        loop = asyncio.get_running_loop()

        def save():
            with SAVE_LOCK:
                bind_loop(loop)
                bind_snapshot(snapshot, snapshot["node_id"], {"extra_pnginfo": extra_pnginfo})
                return saver.save_images(
                    batch, filename_prefix, subdirectory_name, prompt, extra_pnginfo, extra_metadata,
                    output_format, quality, metadata_scope, include_batch_num, prefer_nearest)

        result = await asyncio.to_thread(save)
        return io.NodeOutput(ui=result["ui"])


class CreateExtraMetaData(io.ComfyNode):
    DESCRIPTION = "Creates custom extra metadata by adding key-value pairs. Empty values are allowed, but unpaired values are not."

    @classmethod
    def define_schema(cls):
        inputs = [io.Custom("EXTRA_METADATA").Input("extra_metadata", optional=True, extra_dict={"forceInput": True})]
        for i in range(1, 5):
            for type in ["key", "value"]:
                inputs.append(io.String.Input(f"{type}{i}", default="", multiline=False, optional=True))
        return io.Schema(
            node_id="CreateExtraMetaData",
            display_name="Create Extra MetaData",
            category="SaveImage",
            description=cls.DESCRIPTION,
            inputs=inputs,
            outputs=[io.Custom("EXTRA_METADATA").Output()],
        )

    @classmethod
    def execute(cls, extra_metadata=None, **keys_values):
        if extra_metadata is None:
            extra_metadata = {}

        for i in range(1, 5):
            key = keys_values.get(f"key{i}", "").strip()
            value = keys_values.get(f"value{i}", "").strip()

            if key:
                extra_metadata[key] = value
            elif value:
                raise ValueError(f"Value provided for 'value{i}' without corresponding 'key{i}'.")

        return io.NodeOutput(extra_metadata)
