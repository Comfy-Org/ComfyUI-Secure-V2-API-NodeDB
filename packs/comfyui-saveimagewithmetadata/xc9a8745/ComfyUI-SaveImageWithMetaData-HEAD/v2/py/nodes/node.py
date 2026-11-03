import asyncio
import json
import os
import posixpath
import re
import time

from datetime import datetime

from comfy_api.latest import io, sdk

from ..capture import Capture
from .. import hook
from ..trace import Trace
from .._v2_capture import SAVE_LOCK, bind_loop, bind_snapshot, run_async
from .._v2_refusals import (BACKSLASH, BATCH_NUM, DOT_NAME, JPEG, OVERWRITE, OVERWRITE_BATCH,
                            SecureConversionRefusal)

from ..defs.combo import SAMPLER_SELECTION_METHOD


# --- Secure Nodes V2: the guest has no host paths. Every name below is relative to the
# output root; the managed image writer (ctx.output.save_images) publishes the files.

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
    """folder_paths.get_save_image_path (core 6257422b, folder_paths.py:525-570) relative to the
    output root. The counter is left to the managed writer, which runs the core function."""
    if "%" in filename_prefix:
        filename_prefix = _compute_vars(filename_prefix, image_width, image_height)

    subfolder = os.path.dirname(os.path.normpath(filename_prefix))
    filename = os.path.basename(os.path.normpath(filename_prefix))

    full_output_folder = subfolder

    if _escapes_output(full_output_folder):
        err = "**** ERROR: Saving image outside the output folder is not allowed." + \
              "\n full_output_folder: " + full_output_folder + \
              "\n         output_dir: output"
        raise Exception(err)

    counter = None
    return full_output_folder, filename, counter, subfolder, filename_prefix


def _output_path(folder, name):
    return posixpath.join(folder, name) if folder else name


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
    """Stands in for PIL's PngInfo: records add_text calls; the managed writer encodes them
    as PNG text chunks in this order (png_text)."""

    def __init__(self):
        self.entries = []

    def add_text(self, key, value, zip=False):
        if isinstance(key, str):
            key.encode("latin-1", "strict")  # PngInfo.add_text raises UnicodeEncodeError here too
        self.entries.append((key, value))

    def as_png_text(self):
        # A repeated keyword is one chunk here: readers (Pillow, the ComfyUI frontend) keep the
        # last value, which this keeps, at the keyword's first position.
        result = {}
        for key, value in self.entries:
            result[key] = value
        return result


def _save(image_ref, file_format, **options):
    record = run_async(sdk.ctx().output.save_images(image_ref, image_format=file_format, **options))
    return record["images"][0]


# refer. https://github.com/comfyanonymous/ComfyUI/blob/38b7ac6e269e6ecc5bdd6fefdfb2fb1185b09c9d/nodes.py#L1411
class _Saver:
    """SaveImageWithMetaData from py/nodes/node.py; only the file writes go through the SDK."""

    def __init__(self):
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4

    pattern_format = re.compile(r"(%[^%]+%)")

    def save_images(
        self,
        images,
        filename_prefix="ComfyUI",
        sampler_selection_method=SAMPLER_SELECTION_METHOD[0],
        sampler_selection_node_id=0,
        file_format="png",
        lossless_webp=True,
        quality=100,
        save_workflow_json=False,
        add_counter_to_filename=True,
        civitai_sampler=False,
        extra_metadata={},
        prompt=None,
        extra_pnginfo=None,
        save_workflow_image=True,
    ):
        pnginfo_dict_src = self.gen_pnginfo(
            sampler_selection_method, sampler_selection_node_id, civitai_sampler
        )
        for k, v in extra_metadata.items():
            if k and v:
                pnginfo_dict_src[k] = v.replace(",", "/")

        results = list()
        for index in range(len(images)):
            pnginfo_dict = pnginfo_dict_src.copy()
            if len(images) >= 2:
                pnginfo_dict["Batch index"] = index
                pnginfo_dict["Batch size"] = len(images)

            # Secure Nodes V2: the original skipped this block when the host ran with
            # --disable-metadata (comfy.cli_args.args); a guest cannot read host flags.
            metadata = _PngText()
            parameters = Capture.gen_parameters_str(pnginfo_dict)
            if pnginfo_dict:
                metadata.add_text("parameters", parameters)
            if prompt is not None and save_workflow_image:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))
            if save_workflow_image == False:
                metadata.add_text("workflow", "")

            filename_prefix = self.format_filename(filename_prefix, pnginfo_dict)
            # Secure Nodes V2: the original created the prefix's folder here (os.makedirs);
            # the managed writer creates it when it publishes the image.
            (
                full_output_folder,
                filename,
                counter,
                subfolder,
                filename_prefix,
            ) = _get_save_image_path(
                filename_prefix, images.width, images.height
            )
            if filename in ("", ".", ".."):
                raise SecureConversionRefusal(DOT_NAME.format(prefix=filename_prefix))
            if "\\" in filename_prefix:
                raise SecureConversionRefusal(BACKSLASH.format(prefix=filename_prefix))
            image = images.select(index)
            if file_format == "png":
                options = {"compress_level": self.compress_level, "png_text": metadata.as_png_text()}
            else:
                options = {"quality": quality, "lossless": lossless_webp, "optimize": True,
                           "save_metadata": False, "a1111_parameters": parameters}
            if add_counter_to_filename:
                if "%batch_num%" in filename:
                    raise SecureConversionRefusal(BATCH_NUM)
                # The writer runs folder_paths.get_save_image_path for this prefix: the same
                # counter, and the name f"{filename}_{counter:05}_.{file_format}".
                saved = _save(image, file_format, filename_prefix=_output_path(subfolder, filename), **options)
                file = saved["filename"]
                subfolder = saved["subfolder"]
                base_filename = file[: -len("." + file_format)]
            else:
                base_filename = filename
                file = base_filename + "." + file_format
                if len(images) >= 2:
                    raise SecureConversionRefusal(OVERWRITE_BATCH.format(count=len(images), name=_output_path(subfolder, file)))
                if run_async(sdk.ctx().assets.exists("output", _output_path(subfolder, file))):
                    raise SecureConversionRefusal(OVERWRITE.format(name=_output_path(subfolder, file)))
                saved = _save(image, file_format, filenames=[_output_path(subfolder, file)], **options)

            if save_workflow_json:
                file_path_workflow = _output_path(full_output_folder, f"{base_filename}.json")
                # The original opened the file for writing (creating or emptying it) before it read
                # extra_pnginfo["workflow"]; a missing workflow therefore left an empty file.
                run_async(sdk.ctx().output.write_text(
                    "", filename=file_path_workflow, folder="output", mode="overwrite"))
                run_async(sdk.ctx().output.write_text(
                    json.dumps(extra_pnginfo["workflow"]), filename=file_path_workflow, folder="output",
                    mode="overwrite"))

            results.append(
                {"filename": file, "subfolder": subfolder, "type": self.type}
            )

        return {"ui": {"images": results}}

    @classmethod
    def gen_pnginfo(
        cls, sampler_selection_method, sampler_selection_node_id, save_civitai_sampler
    ):
        # get all node inputs
        inputs = Capture.get_inputs()

        # get sampler node before this node
        trace_tree_from_this_node = Trace.trace(
            hook.current_save_image_node_id, hook.current_prompt
        )
        inputs_before_this_node = Trace.filter_inputs_by_trace_tree(
            inputs, trace_tree_from_this_node
        )
        sampler_node_id = Trace.find_sampler_node_id(
            trace_tree_from_this_node,
            sampler_selection_method,
            sampler_selection_node_id,
        )

        # get inputs before sampler node
        trace_tree_from_sampler_node = Trace.trace(sampler_node_id, hook.current_prompt)
        inputs_before_sampler_node = Trace.filter_inputs_by_trace_tree(
            inputs, trace_tree_from_sampler_node
        )

        # generate PNGInfo from inputs
        pnginfo_dict = Capture.gen_pnginfo_dict(
            inputs_before_sampler_node, inputs_before_this_node, save_civitai_sampler
        )
        return pnginfo_dict

    @classmethod
    def format_filename(cls, filename, pnginfo_dict):
        result = re.findall(cls.pattern_format, filename)
        for segment in result:
            parts = segment.replace("%", "").split(":")
            key = parts[0]
            if key == "seed":
                filename = filename.replace(segment, str(pnginfo_dict.get("Seed", "")))
            elif key == "width":
                w = pnginfo_dict.get("Size", "x").split("x")[0]
                filename = filename.replace(segment, str(w))
            elif key == "height":
                w = pnginfo_dict.get("Size", "x").split("x")[1]
                filename = filename.replace(segment, str(w))
            elif key == "pprompt":
                prompt = pnginfo_dict.get("Positive prompt", "").replace("\n", " ")
                if len(parts) >= 2:
                    length = int(parts[1])
                    prompt = prompt[:length]
                filename = filename.replace(segment, prompt.strip())
            elif key == "nprompt":
                prompt = pnginfo_dict.get("Negative prompt", "").replace("\n", " ")
                if len(parts) >= 2:
                    length = int(parts[1])
                    prompt = prompt[:length]
                filename = filename.replace(segment, prompt.strip())
            elif key == "model":
                model = pnginfo_dict.get("Model", "")
                model = os.path.splitext(os.path.basename(model))[0]
                if len(parts) >= 2:
                    length = int(parts[1])
                    model = model[:length]
                filename = filename.replace(segment, model)
            elif key == "date":
                now = datetime.now()
                date_table = {
                    "yyyy": now.year,
                    "MM": now.month,
                    "dd": now.day,
                    "hh": now.hour,
                    "mm": now.minute,
                    "ss": now.second,
                }
                if len(parts) >= 2:
                    date_format = parts[1]
                    for k, v in date_table.items():
                        date_format = date_format.replace(k, str(v).zfill(len(k)))
                    filename = filename.replace(segment, date_format)
                else:
                    date_format = "yyyyMMddhhmmss"
                    for k, v in date_table.items():
                        date_format = date_format.replace(k, str(v).zfill(len(k)))
                    filename = filename.replace(segment, date_format)

        return filename


class SaveImageWithMetaData(io.ComfyNode):
    SAVE_FILE_FORMATS = ["png", "jpeg", "webp"]
    SDK_REFS = True
    SDK_PERMISSIONS = ("graph.metadata", "assets", "output")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageWithMetaData",
            display_name="Save Image With Metadata",
            category="SaveImage",
            is_output_node=True,
            inputs=[
                io.Image.Input("images"),
                io.String.Input("filename_prefix", default="ComfyUI", multiline=None),
                io.Combo.Input("sampler_selection_method", options=SAMPLER_SELECTION_METHOD),
                io.Int.Input("sampler_selection_node_id", default=0, min=0, max=999999999, step=1),
                io.Combo.Input("file_format", options=cls.SAVE_FILE_FORMATS),
                io.Boolean.Input("lossless_webp", default=True, optional=True),
                io.Int.Input("quality", default=100, min=1, max=100, optional=True),
                io.Boolean.Input("save_workflow_json", default=False, optional=True),
                io.Boolean.Input("add_counter_to_filename", default=True, optional=True),
                io.Boolean.Input("civitai_sampler", default=False, optional=True),
                io.Custom("EXTRA_METADATA").Input("extra_metadata", optional=True),
                io.Boolean.Input("save_workflow_image", default=True, optional=True),
            ],
            outputs=[],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
        )

    @classmethod
    async def execute(
        cls,
        images,
        filename_prefix="ComfyUI",
        sampler_selection_method=SAMPLER_SELECTION_METHOD[0],
        sampler_selection_node_id=0,
        file_format="png",
        lossless_webp=True,
        quality=100,
        save_workflow_json=False,
        add_counter_to_filename=True,
        civitai_sampler=False,
        extra_metadata={},
        save_workflow_image=True,
    ):
        if file_format == "jpeg":
            raise SecureConversionRefusal(JPEG)
        prompt = cls.hidden.prompt
        extra_pnginfo = cls.hidden.extra_pnginfo
        # The running prompt and its observed node inputs and outputs come from the broker:
        # what the original read from its executor hooks.
        snapshot = await sdk.ctx().graph.execution_metadata(include_observations=True)
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        height, width = await images.spatial_shape()
        batch = _ImageBatch(images, int(await images.batch_size()), height, width)
        loop = asyncio.get_running_loop()

        def save():
            with SAVE_LOCK:
                bind_loop(loop)
                bind_snapshot(snapshot, snapshot["node_id"], {"extra_pnginfo": extra_pnginfo})
                return _Saver().save_images(
                    batch, filename_prefix, sampler_selection_method, sampler_selection_node_id,
                    file_format, lossless_webp, quality, save_workflow_json, add_counter_to_filename,
                    civitai_sampler, extra_metadata, prompt, extra_pnginfo, save_workflow_image)

        result = await asyncio.to_thread(save)
        return io.NodeOutput(ui=result["ui"])


class CreateExtraMetaData(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="CreateExtraMetaData",
            display_name="Create Extra MetaData",
            category="SaveImage",
            inputs=[
                io.String.Input("key1", default="", multiline=False),
                io.String.Input("value1", default="", multiline=False),
                io.String.Input("key2", default="", multiline=False, optional=True),
                io.String.Input("value2", default="", multiline=False, optional=True),
                io.String.Input("key3", default="", multiline=False, optional=True),
                io.String.Input("value3", default="", multiline=False, optional=True),
                io.String.Input("key4", default="", multiline=False, optional=True),
                io.String.Input("value4", default="", multiline=False, optional=True),
                io.Custom("EXTRA_METADATA").Input("extra_metadata", optional=True),
            ],
            outputs=[io.Custom("EXTRA_METADATA").Output()],
        )

    @classmethod
    def execute(
        cls,
        extra_metadata={},
        key1="",
        value1="",
        key2="",
        value2="",
        key3="",
        value3="",
        key4="",
        value4="",
    ):
        extra_metadata.update(
            {
                key1: value1,
                key2: value2,
                key3: value3,
                key4: value4,
            }
        )
        return io.NodeOutput(extra_metadata)
