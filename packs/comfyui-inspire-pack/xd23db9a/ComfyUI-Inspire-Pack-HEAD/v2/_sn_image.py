"""Secure Nodes V2 versions of three Inspire image nodes (pristine inspire/image_util.py, pin d23db9aa).

The value-handling lines are the original's, in the original order. Only these change:
- Listing: `os.path.isdir(directory)` / `os.listdir(directory)` become an SDK listing of a folder inside
  ComfyUI's input/output/temp folder (_sn_dir.py).
- Reading: `Image.open(image_path)` opens the file's bytes, read through the SDK.
- Resizing: `comfy.utils.common_upscale` is a line-for-line copy (_sn_comfy_utils.py), because a guest
  cannot import ComfyUI.
- Refusals: Datetime sorts (no mtime in the SDK) and absolute or '..' directories are refused by name.
Each change is marked "V2:".
"""

import os
import types
from io import BytesIO
import re
import logging

import numpy as np
import torch
from PIL import Image, ImageOps

from comfy_api.latest import io

from . import _sn_comfy_utils, _sn_dir

try:
    import pillow_jxl      # noqa: F401
    jxl = True
except ImportError:
    jxl = False

# V2: only comfy.utils.common_upscale is used; it is the vendored copy.
comfy = types.SimpleNamespace(utils=_sn_comfy_utils)


def extract_first_number(s):
    match = re.search(r'\d+', s)
    return int(match.group()) if match else float('inf')


sort_methods = [
    "None",
    "Alphabetical (ASC)",
    "Alphabetical (DESC)",
    "Numerical (ASC)",
    "Numerical (DESC)",
    "Datetime (ASC)",
    "Datetime (DESC)"
]
DATETIME_METHODS = ("Datetime (ASC)", "Datetime (DESC)")


def sort_by(items, base_path='.', method=None):
    # V2: the Datetime branches are kept as written but cannot run; those methods are refused first.
    def fullpath(x): return os.path.join(base_path, x)

    def get_timestamp(path):
        try:
            return os.path.getmtime(path)
        except FileNotFoundError:
            return float('-inf')

    if method == "Alphabetical (ASC)":
        return sorted(items)
    elif method == "Alphabetical (DESC)":
        return sorted(items, reverse=True)
    elif method == "Numerical (ASC)":
        return sorted(items, key=lambda x: extract_first_number(os.path.splitext(x)[0]))
    elif method == "Numerical (DESC)":
        return sorted(items, key=lambda x: extract_first_number(os.path.splitext(x)[0]), reverse=True)
    elif method == "Datetime (ASC)":
        return sorted(items, key=lambda x: get_timestamp(fullpath(x)))
    elif method == "Datetime (DESC)":
        return sorted(items, key=lambda x: get_timestamp(fullpath(x)), reverse=True)
    else:
        return items


def _refusal(node, directory, sort_method):
    """The V2 refusal message for these inputs, or None."""
    if sort_method in DATETIME_METHODS:
        return _sn_dir.refusal_datetime(node, sort_method)
    if isinstance(directory, str) and directory != "":
        try:
            _sn_dir.locate(node, directory)
        except _sn_dir.DirectoryRefused as error:
            return str(error)
    return None


def _validate(node, directory=None, sort_method=None):
    # Taking sort_method stops core's own menu check for it, so repeat that check here.
    if sort_method is not None and sort_method not in sort_methods:
        return f"Value not in list: sort_method: '{sort_method}' not in {sort_methods}"
    return _refusal(node, directory, sort_method) or True


def _directory_schema(start_index_min):
    return [
        io.String.Input("directory", default=""),
        io.Int.Input("image_load_cap", default=0, min=0, step=1, optional=True),
        io.Int.Input("start_index", default=0, min=start_index_min, max=0xffffffffffffffff, step=1, optional=True),
        io.Boolean.Input("load_always", default=False, label_on="enabled", label_off="disabled", optional=True),
        io.Combo.Input("sort_method", options=sort_methods, optional=True),
    ]


class LoadImagesFromDirBatch(io.ComfyNode):
    NODE = "LoadImagesFromDir //Inspire"
    SDK_REFS = False
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE,
            display_name="Load Image Batch From Dir (Inspire)",
            category="image",
            inputs=_directory_schema(-1),
            outputs=[io.Image.Output(), io.Mask.Output(), io.Int.Output()],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        if 'load_always' in kwargs and kwargs['load_always']:
            return float("NaN")
        else:
            return hash(frozenset(kwargs))

    @classmethod
    def validate_inputs(cls, directory=None, sort_method=None):
        return _validate(cls.NODE, directory, sort_method)

    @classmethod
    async def execute(cls, directory: str, image_load_cap: int = 0, start_index: int = 0, load_always=False, sort_method=None):
        refusal = _refusal(cls.NODE, directory, sort_method)  # V2: linked inputs are checked here
        if refusal:
            raise _sn_dir.DirectoryRefused(refusal)
        # V2: `if not os.path.isdir(directory)` / `os.listdir(directory)`. The original's "No files in
        # directory" check cannot fire: a directory holding no file at all is reported as not found.
        folder = await _sn_dir.open_directory(cls.NODE, directory, f"Directory '{directory} cannot be found.'")
        dir_files = list(folder.names)

        # Filter files by extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if jxl:
            valid_extensions.extend('.jxl')
        dir_files = [f for f in dir_files if any(f.lower().endswith(ext) for ext in valid_extensions)]

        dir_files = sort_by(dir_files, directory, sort_method)
        names = {os.path.join(directory, x): x for x in dir_files}  # V2: path -> listed name
        dir_files = [os.path.join(directory, x) for x in dir_files]

        # start at start_index
        dir_files = dir_files[start_index:]

        images = []
        masks = []

        limit_images = False
        if image_load_cap > 0:
            limit_images = True
        image_count = 0

        has_non_empty_mask = False

        for image_path in dir_files:
            # V2: the original's `if os.path.isdir(image_path) and os.path.ex: continue` cannot apply:
            # only files are listed.
            if limit_images and image_count >= image_load_cap:
                break
            i = Image.open(BytesIO(await folder.read(names[image_path])))  # V2: was Image.open(image_path)
            i = ImageOps.exif_transpose(i)
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
                has_non_empty_mask = True
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            images.append(image)
            masks.append(mask)
            image_count += 1

        if len(images) == 1:
            return io.NodeOutput(images[0], masks[0], 1)

        elif len(images) > 1:
            image1 = images[0]
            mask1 = None

            for image2 in images[1:]:
                if image1.shape[1:] != image2.shape[1:]:
                    image2 = comfy.utils.common_upscale(image2.movedim(-1, 1), image1.shape[2], image1.shape[1], "bilinear", "center").movedim(1, -1)
                image1 = torch.cat((image1, image2), dim=0)

            for mask2 in masks:
                if has_non_empty_mask:
                    if image1.shape[1:3] != mask2.shape:
                        mask2 = torch.nn.functional.interpolate(mask2.unsqueeze(0).unsqueeze(0), size=(image1.shape[1], image1.shape[2]), mode='bilinear', align_corners=False)
                        mask2 = mask2.squeeze(0)
                    else:
                        mask2 = mask2.unsqueeze(0)
                else:
                    mask2 = mask2.unsqueeze(0)

                if mask1 is None:
                    mask1 = mask2
                else:
                    mask1 = torch.cat((mask1, mask2), dim=0)

            return io.NodeOutput(image1, mask1, len(images))

        # V2: with no image left the original returns None, which ComfyUI's V1 output handling
        # rejects with exactly this error, so the node fails. A V3 node returning None would finish
        # with no outputs instead; raise the same error so the outcome stays the same.
        raise TypeError("object of type 'NoneType' has no len()")


class LoadImagesFromDirList(io.ComfyNode):
    NODE = "LoadImageListFromDir //Inspire"
    SDK_REFS = False
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE,
            display_name="Load Image List From Dir (Inspire)",
            category="image",
            inputs=_directory_schema(0),
            outputs=[io.Image.Output(display_name="IMAGE", is_output_list=True),
                     io.Mask.Output(display_name="MASK", is_output_list=True),
                     io.String.Output(display_name="FILE PATH", is_output_list=True)],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        if 'load_always' in kwargs and kwargs['load_always']:
            return float("NaN")
        else:
            return hash(frozenset(kwargs))

    @classmethod
    def validate_inputs(cls, directory=None, sort_method=None):
        return _validate(cls.NODE, directory, sort_method)

    @classmethod
    async def execute(cls, directory: str, image_load_cap: int = 0, start_index: int = 0, load_always=False, sort_method=None):
        refusal = _refusal(cls.NODE, directory, sort_method)  # V2: linked inputs are checked here
        if refusal:
            raise _sn_dir.DirectoryRefused(refusal)
        # V2: `if not os.path.isdir(directory)` / `os.listdir(directory)`; see LoadImagesFromDirBatch.
        folder = await _sn_dir.open_directory(cls.NODE, directory, f"Directory '{directory}' cannot be found.")
        dir_files = list(folder.names)

        # Filter files by extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if jxl:
            valid_extensions.extend('.jxl')
        dir_files = [f for f in dir_files if any(f.lower().endswith(ext) for ext in valid_extensions)]

        dir_files = sort_by(dir_files, directory, sort_method)
        names = {os.path.join(directory, x): x for x in dir_files}  # V2: path -> listed name
        dir_files = [os.path.join(directory, x) for x in dir_files]

        # start at start_index
        dir_files = dir_files[start_index:]

        images = []
        masks = []
        file_paths = []

        limit_images = False
        if image_load_cap > 0:
            limit_images = True
        image_count = 0

        for image_path in dir_files:
            # V2: no directories are listed (see LoadImagesFromDirBatch).
            if limit_images and image_count >= image_load_cap:
                break
            i = Image.open(BytesIO(await folder.read(names[image_path])))  # V2: was Image.open(image_path)
            i = ImageOps.exif_transpose(i)
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]

            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

            images.append(image)
            masks.append(mask)
            file_paths.append(str(image_path))
            image_count += 1

        return io.NodeOutput(images, masks, file_paths)


class ChangeImageBatchSize(io.ComfyNode):
    NODE = "ChangeImageBatchSize //Inspire"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE,
            display_name="Change Image Batch Size (Inspire)",
            category="InspirePack/Util",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("batch_size", default=1, min=1, max=4096, step=1),
                io.Combo.Input("mode", options=["simple"]),
            ],
            outputs=[io.Image.Output()],
        )

    @staticmethod
    def resize_tensor(input_tensor, batch_size, mode):
        if mode == "simple":
            if len(input_tensor) < batch_size:
                last_frame = input_tensor[-1].unsqueeze(0).expand(batch_size - len(input_tensor), -1, -1, -1)
                output_tensor = torch.concat((input_tensor, last_frame), dim=0)
            else:
                output_tensor = input_tensor[:batch_size, :, :, :]
            return output_tensor
        else:
            logging.warning(f"[Inspire Pack] ChangeImage(Latent)BatchSize: Unknown mode `{mode}` - ignored")
            return input_tensor

    @classmethod
    def execute(cls, image, batch_size, mode):
        res = ChangeImageBatchSize.resize_tensor(image, batch_size, mode)
        return io.NodeOutput(res)
