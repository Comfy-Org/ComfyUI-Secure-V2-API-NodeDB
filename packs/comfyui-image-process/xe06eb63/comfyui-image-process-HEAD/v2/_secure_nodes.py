"""comfyui-image-process for Secure Nodes V2: every node the pack registers, with the original's schema.

The docstrings and define_schema methods are the original's (image_process.py at e06eb63e), copied verbatim by the
converter's build script; the one edit is LoadICCProfile's profile list (see there).
- SaveImageBMP is converted: it saves through the SDK's image writer.
- SaveImageJPG's body is ready, but the node is refused until the SDK's JPEG writer can write what the original
  writes (see _JPEG_WRITER_OPTIONS).
- Every other node is registered and refused by name (REFUSALS).
This module imports only the standard library, numpy, Pillow, the SDK and the pack's define.py. It never imports
image_process.py or image_helper.py, which import scipy, scikit-image, piexif and ComfyUI's folder_paths.
"""

import re
from datetime import datetime

import numpy as np
from PIL import Image

from comfy_api.latest import io, sdk

from .define import define

PACK = "comfyui-image-process"

REFUSALS = {
    'ColorPatchFlatten': (
        'its colour maths needs scikit-image (rgb2hsv, hsv2rgb), which the V2 guest does not have; no '
        'dependency profile is declared for this pack'
    ),
    'ColorPatchMerge': (
        'its colour maths needs scipy (ndimage), scikit-image (rgb2lab) and OpenCV, which the V2 guest does '
        'not have; no dependency profile is declared for this pack'
    ),
    'AchromaticStabilizer': (
        'its filters need scipy (ndimage), which the V2 guest does not have; no dependency profile is '
        'declared for this pack'
    ),
    'LoadICCProfile': (
        'it reads ICC profile files from a models/icc_profiles folder that the original registers at import; '
        'V2 has no catalogue for that folder'
    ),
    'SaveImageAdvancedCustom': (
        'its formats and options (ICC profiles, dpi, TIFF compression, TGA, AVIF speed, EXIF and TIFF '
        'metadata, saving into the input folder) need image-writer options the SDK does not declare'
    ),
    'SaveImageJPG': (
        "the SDK's JPEG writer always uses 4:4:4 chroma subsampling and has no dpi option; the original saves"
        " with Pillow's default 4:2:0 subsampling at 72 dpi, so the file and its decoded pixels would differ"
    ),
    'SaveImageAdvancedJPG': (
        "it has SaveImageJPG's JPEG writer gap (chroma subsampling, dpi), and its EXIF metadata and saving "
        'into the input folder need image-writer options the SDK does not declare'
    ),
    'SaveImageAdvancedBMP': (
        'its options (32-bit BMP with a joined alpha mask, dpi, saving into the input folder) need '
        'image-writer options the SDK does not declare'
    ),
    'SaveImageTIFF': (
        "it joins optional alpha masks (Lanczos-resized) and shows temporary PNG previews, and the SDK's TIFF"
        ' writer has no dpi option; it is not converted in this pass'
    ),
    'SaveImageAdvancedTIFF': (
        'its options (TIFF compression, dpi, alpha masks, TIFF metadata, saving into the input folder) need '
        'image-writer options the SDK does not declare'
    ),
    'SaveImageTGA': (
        "the SDK's image writer has no TGA format"
    ),
    'SaveImageAdvancedTGA': (
        "the SDK's image writer has no TGA format"
    ),
    'SaveImageAVIF': (
        "the SDK's AVIF writer has no speed or dpi option (the original encodes with speed 6 at 72 dpi), so "
        'the lossy file would differ'
    ),
    'SaveImageAdvancedAVIF': (
        "the SDK's AVIF writer has no speed or dpi option, and its alpha masks and saving into the input "
        'folder need image-writer options the SDK does not declare'
    ),
    'SaveImageICO': (
        "the SDK's image writer has no ICO format"
    ),
    'SaveImageAdvancedICO': (
        "the SDK's image writer has no ICO format"
    ),
    'ICOPacker': (
        'it only prepares input for SaveImageAdvancedICO, which needs an ICO writer the SDK does not have'
    ),
}


def _refusal(node_id: str) -> str:
    return f"{PACK}/{node_id} is not yet converted to Secure Nodes V2: {REFUSALS[node_id]}"


class NotConvertedError(RuntimeError):
    """A registered node that V2 cannot run yet; the message names the node and the reason."""


# SaveImageJPG's switch. The original saves with Pillow's defaults: 4:2:0 chroma subsampling, plus dpi=(72, 72).
# The SDK's JPEG writer always uses 4:4:4 and declares neither option, so the node is refused while this is None.
# Once the writer declares them, set them here (for example {"<subsampling option>": <4:2:0>, "<dpi option>": (72, 72)});
# that one line turns the node on.
_JPEG_WRITER_OPTIONS = None


class ImageSaveHelperExt:
    # image_helper.py ImageSaveHelperExt.resolve_filename_prefix, verbatim.
    @staticmethod
    def resolve_filename_prefix(
        prefix: str, image_width: int = 0, image_height: int = 0
    ) -> str:
        """
        Resolve template tokens in a filename prefix string.
        """
        if "%" not in prefix:
            return prefix

        now = datetime.now()

        def _replace_date(m: re.Match) -> str:
            fmt = m.group(1)
            # Replace longest tokens first to avoid partial matches (e.g. yy
            # inside yyyy, or mm inside MM).
            fmt = fmt.replace("yyyy", now.strftime("%Y"))
            fmt = fmt.replace("yy", now.strftime("%y"))
            fmt = fmt.replace("MM", now.strftime("%m"))
            fmt = fmt.replace("dd", now.strftime("%d"))
            fmt = fmt.replace("HH", now.strftime("%H"))
            fmt = fmt.replace("hh", now.strftime("%I"))
            fmt = fmt.replace("mm", now.strftime("%M"))
            fmt = fmt.replace("ss", now.strftime("%S"))
            return fmt

        prefix = re.sub(r"%date:([^%]+)%", _replace_date, prefix)

        prefix = prefix.replace("%year%", now.strftime("%Y"))
        prefix = prefix.replace("%month%", now.strftime("%m"))
        prefix = prefix.replace("%day%", now.strftime("%d"))
        prefix = prefix.replace("%hour%", now.strftime("%H"))
        prefix = prefix.replace("%minute%", now.strftime("%M"))
        prefix = prefix.replace("%second%", now.strftime("%S"))
        prefix = prefix.replace("%width%", str(image_width))
        prefix = prefix.replace("%height%", str(image_height))

        return prefix


async def _save_rgb_images(node_id, images, filename_prefix, **writer_options):
    """The original's save loop for its RGB savers (ImageSaveHelperExt.get_save_image_path + get_save_result with
    convert_mode "RGB" and no mask), through the SDK's image writer.

    Names: the pack's own filename tokens are resolved here, then the writer runs Core's get_save_image_path and
    names each file <name>_<counter:05>_.<ext> with %batch_num% replaced, as the original does.
    Pixels: the original saves Image.fromarray(np.clip(255 * image, 0, 255).astype(np.uint8)).convert("RGB"); the
    writer quantizes the same way. Pillow decides what convert("RGB") does with the channel count, as in the
    original: 3 channels go to the writer unchanged, 4 (RGBA) as their first three (convert drops alpha), and counts
    Pillow can't read raise Pillow's own TypeError. 2 channels (grey + alpha) are refused (see below).
    """
    shape = (await images.describe())["shape"]  # [batch, height, width, channels]; no pixels move
    height, width, channels = int(shape[1]), int(shape[2]), int(shape[3])
    mode = Image.fromarray(np.zeros((1, 1, channels), np.uint8)).mode
    if mode == "RGBA":
        images = await images.rgb()
    elif mode != "RGB":
        raise ValueError(
            f"{PACK}/{node_id}: a {channels}-channel IMAGE (mode {mode}) is not supported in Secure Nodes V2. The "
            "original saves its grey channel as RGB; the SDK's image writer has no grey-to-RGB conversion.")
    filename_prefix = ImageSaveHelperExt.resolve_filename_prefix(filename_prefix, width, height)
    return await sdk.ctx().output.save_images(
        images, filename_prefix=filename_prefix, save_metadata=False, **writer_options)


class ColorPatchFlatten(io.ComfyNode):
    """
    Flatten HSV values across a color patch within a given tolerance.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ColorPatchFlatten",
            display_name="Color Patch Flatten",
            category=define.author,
            is_experimental=True,
            description="Flatten HSV values across a color patch within a given tolerance.",
            inputs=[
                io.Image.Input(
                    id="image",
                    display_name="Image",
                    tooltip="The image to be processed.",
                ),
                io.Mask.Input(
                    id="mask",
                    display_name="Alpha Mask",
                    tooltip="Optional alpha channel mask.",
                    optional=True,
                ),
                io.Float.Input(
                    id="flatten_tolerance",
                    display_name="Flatten Tolerance",
                    tooltip="How different colors can be conisdered as a same color patch.\nLarger number means weaker flattening effect.",
                    step=0.01,
                    round=0.01,
                    default=0.05,
                    max=1.0,
                    min=0.00,
                ),
                io.Boolean.Input(id="flatten_hue", display_name="H", default=True),
                io.Boolean.Input(
                    id="flatten_saturation", display_name="S", default=True
                ),
                io.Boolean.Input(
                    id="flatten_brightness", display_name="V", default=True
                ),
            ],
            outputs=[
                io.Image.Output(id="output", display_name="OUTPUT"),
                io.Mask.Output(id="mask", display_name="ALPHA"),
            ],
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("ColorPatchFlatten")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("ColorPatchFlatten"))


class ColorPatchMerge(io.ComfyNode):
    """
    Groups similar colors and replaces them with their local average.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ColorPatchMerge",
            display_name="Color Patch Merge",
            category=define.author,
            is_experimental=True,
            description="Groups similar colors and replaces them with their local averages.",
            inputs=[
                io.Image.Input(
                    id="image",
                    display_name="Image",
                    tooltip="The image to be processed.",
                ),
                io.Mask.Input(
                    id="mask",
                    display_name="Alpha Mask",
                    tooltip="Optional alpha channel mask.",
                    optional=True,
                ),
                io.Float.Input(
                    id="merge_tolerance",
                    display_name="Merge Tolerance",
                    tooltip="How different colors can be to stay in the same group.",
                    step=0.01,
                    round=0.01,
                    default=0.05,
                    max=1.0,
                    min=0.00,
                ),
                io.Int.Input(
                    id="neighborhood",
                    display_name="Neighborhood",
                    tooltip="The neighborhood size (diameter) for the bilateral filter.\nUsed for 'Smooth' merging solution.",
                    step=1,
                    default=3,
                    max=31,
                    min=3,
                ),
                io.Int.Input(
                    id="min_area",
                    display_name="Minimal Area",
                    tooltip="The minimum area size for color patches.\nUsed for 'Unify' merging solution.",
                    step=1,
                    default=20,
                    max=1024,
                    min=2,
                ),
                io.Int.Input(
                    id="iterations",
                    display_name="Iterations",
                    tooltip="Number of growth iterations for color patches.\nMore iterations result in larger, more uniform color regions.\nUsed for 'Unify' merging solution.",
                    step=1,
                    default=2,
                    max=16,
                    min=1,
                ),
                io.Boolean.Input(
                    id="use_lab",
                    display_name="Use Lab Colors",
                    tooltip="Convert RGB space to Lab colors.",
                    default=True,
                ),
                io.Combo.Input(
                    id="merge_solution",
                    display_name="Merge Solution",
                    tooltip="How to handle the color merging.",
                    options=["Smooth", "Unify"],
                    default="Smooth",
                ),
            ],
            outputs=[
                io.Image.Output(id="output", display_name="OUTPUT"),
                io.Mask.Output(id="mask", display_name="ALPHA"),
            ],
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("ColorPatchMerge")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("ColorPatchMerge"))


class AchromaticStabilizer(io.ComfyNode):
    """
    Fix achromatic color instability from AI-generated images.

    Pixels with near-zero saturation have their hue snapped to 0
    and their saturation zeroed out, then optionally smoothed.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="AchromaticStabilizer",
            display_name="Achromatic Stabilizer",
            category=define.author,
            is_experimental=True,
            description="Fix achromatic color instability across the image."
            "Pixels with near-zero saturation have their hue snapped to 0 and their saturation zeroed out, then optionally smoothed.",
            inputs=[
                io.Image.Input(
                    id="image",
                    display_name="Image",
                    tooltip="The image to be processed.",
                ),
                io.Mask.Input(
                    id="mask",
                    display_name="Alpha Mask",
                    tooltip="Optional alpha channel mask.\nIf provided and preserve_alpha is True, this mask will be used as the alpha channel.",
                    optional=True,
                ),
                io.Boolean.Input(
                    id="smooth",
                    display_name="Smooth Transitions",
                    tooltip="Whether to apply a smoothing filter to the corrected areas.",
                    default=True,
                ),
                io.Float.Input(
                    id="sat_threshold",
                    display_name="Saturation Threshold",
                    tooltip="The saturation level below which pixels are considered artifacts.",
                    step=0.01,
                    round=0.01,
                    default=0.08,
                    max=1.0,
                    min=0.0,
                ),
                io.Int.Input(
                    id="kernel_size",
                    display_name="Smoothing Kernel Size",
                    tooltip="The size of the smoothing kernel to apply.",
                    default=3,
                    max=15,
                    min=1,
                ),
                io.Boolean.Input(
                    id="preserve_alpha",
                    display_name="Preserve Alpha",
                    tooltip="Whether to preserve the alpha channel during processing.",
                    default=True,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel before saving.",
                    default=False,
                ),
            ],
            outputs=[
                io.Image.Output(id="output", display_name="OUTPUT"),
                io.Mask.Output(id="mask", display_name="ALPHA"),
            ],
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("AchromaticStabilizer")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("AchromaticStabilizer"))


class LoadICCProfile(io.ComfyNode):
    """
    Loads an ICC color profile from the models/icc_profiles folder.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LoadICCProfile",
            display_name="Load ICC Profile",
            category=define.author,
            inputs=[
                io.Combo.Input(
                    id="profile",
                    display_name="Profile",
                    # V2: the original lists the readable profiles in models/icc_profiles here (none on a fresh
                    # install). The node is refused, so the list is empty.
                    options=[],
                )
            ],
            outputs=[
                io.Custom("ICC_PROFILE").Output(
                    id="icc_profile", display_name="ICC_PROFILE"
                ),
                io.String.Output(id="icc_profile_info", display_name="ICC_INFO"),
            ],
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("LoadICCProfile")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("LoadICCProfile"))


class SaveImageAdvancedCustom(io.ComfyNode):
    """
    Saves images to disk with additional options for metadata and compression.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedCustom",
            display_name="Save Image Advanced",
            category=define.author,
            description="Saves image to disk with additional options for metadata and compression.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Mask.Input(
                    id="masks",
                    display_name="Alpha Masks",
                    tooltip="Optional alpha channel masks to clip the saved images. If provided, these masks will be applied to the corresponding images before saving.",
                    optional=True,
                ),
                io.Custom("ICC_PROFILE").Input(
                    id="icc_profile",
                    display_name="ICC Profile",
                    tooltip="Optional ICC color profile to embed into the saved images.",
                    optional=True,
                ),
                io.Boolean.Input(
                    id="disable_metadata",
                    display_name="Disable Metadata",
                    tooltip="Whether to include the metadata to the saved image.",
                    default=True,
                ),
                io.Boolean.Input(
                    id="join_alpha",
                    display_name="Join Alpha Channel",
                    tooltip="Clip the image with the provided mask.\nPlease note this does not work on JPG format.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel before saving.",
                    default=False,
                ),
                io.Int.Input(
                    id="dpi",
                    display_name="DPI",
                    tooltip="The DPI to use when saving images.",
                    default=define.printing_dpi,
                    min=1,
                    max=600,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Int.Input(
                    id="compress_level",
                    display_name="Compression Level",
                    tooltip="The compression level to use when saving images as PNG (0-9).",
                    default=4,
                    min=0,
                    max=9,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Int.Input(
                    id="quality",
                    display_name="Quality",
                    tooltip="The quality to use when saving images as JPEG or WebP (1-100).",
                    default=90,
                    min=1,
                    max=100,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Combo.Input(
                    id="tiff_compression",
                    display_name="TIFF Compression",
                    tooltip="The compression to use when saving images as TIFF.",
                    options=[
                        "none",
                        "tiff_lzw",
                        "tiff_deflate",
                        "tiff_adobe_deflate",
                        "packbits",
                        "jpeg",
                        "tiff_jpeg",
                        "tiff_ccitt",
                    ],
                    default="none",
                ),
                io.Boolean.Input(
                    id="tga_rle",
                    display_name="TGA RLE Compression",
                    tooltip="Whether to use RLE compression when saving as TGA.",
                    default=True,
                ),
                io.Combo.Input(
                    id="format",
                    display_name="Format",
                    tooltip="The format to save the image in.",
                    options=["png", "jpg", "webp", "tiff", "bmp", "tga", "avif"],
                    default="png",
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedCustom")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedCustom"))


class SaveImageJPG(io.ComfyNode):
    """
    Saves images to disk as JPG files.
    """

    SDK_REFS = True
    # inspect: describe() reads the batch's shape (no pixels); output: the image writer.
    SDK_PERMISSIONS = ("inspect", "output")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageJPG",
            display_name="Save Image (JPG)",
            category=define.author,
            description="Saves images to disk as JPG files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        if _JPEG_WRITER_OPTIONS is None:
            return _refusal("SaveImageJPG")
        return True

    @classmethod
    async def execute(
        cls,
        images,
        filename_prefix: str = define.default_file_name,
        **kwargs,
    ) -> io.NodeOutput:
        if _JPEG_WRITER_OPTIONS is None:
            raise NotConvertedError(_refusal("SaveImageJPG"))
        # The original: RGB JPEG, quality=95, optimize=True, dpi=(72, 72), no EXIF and no ICC profile.
        return io.NodeOutput(ui=await _save_rgb_images(
            "SaveImageJPG", images, filename_prefix, image_format="jpg", quality=95, optimize=True,
            **_JPEG_WRITER_OPTIONS))


class SaveImageAdvancedJPG(io.ComfyNode):
    """
    Saves images to disk as JPG files with additional options.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedJPG",
            display_name="Save Image Advanced (JPG)",
            category=define.author,
            description="Saves images to disk as JPG files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Boolean.Input(
                    id="disable_metadata",
                    display_name="Disable Metadata",
                    tooltip="Disable embedding EXIF data into the saved images.\nEmbed into `UserComment`.",
                    default=False,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Int.Input(
                    id="dpi",
                    display_name="DPI",
                    tooltip="The DPI to use when saving images.",
                    default=define.printing_dpi,
                    min=1,
                    max=600,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Int.Input(
                    id="quality",
                    display_name="Quality",
                    tooltip="The quality of the saved images.",
                    default=95,
                    min=1,
                    max=100,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedJPG")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedJPG"))


class SaveImageBMP(io.ComfyNode):
    """
    Saves images to disk as BMP files.
    """

    SDK_REFS = True
    # inspect: describe() reads the batch's shape (no pixels); output: the image writer.
    SDK_PERMISSIONS = ("inspect", "output")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageBMP",
            display_name="Save Image (BMP)",
            category=define.author,
            description="Saves images to disk as BMP files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        images,
        filename_prefix: str = define.default_file_name,
        **kwargs,
    ) -> io.NodeOutput:
        # The original: RGB BMP, dpi=(72, 72), no metadata. The SDK's writer has no dpi option, so the BMP header
        # records Pillow's default 96 dpi; the pixels are the original's (SECURE_CONVERSION.md, known differences).
        return io.NodeOutput(ui=await _save_rgb_images("SaveImageBMP", images, filename_prefix, image_format="bmp"))


class SaveImageAdvancedBMP(io.ComfyNode):
    """
    Saves images to disk as BMP files with additional options.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedBMP",
            display_name="Save Image Advanced (BMP)",
            category=define.author,
            description="Saves images to disk as BMP files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Mask.Input(
                    id="masks",
                    display_name="Alpha Masks",
                    tooltip="Optional alpha channel masks to clip the saved images. If provided, these masks will be applied to the corresponding images before saving.",
                    optional=True,
                ),
                io.Combo.Input(
                    id="bit_depth",
                    display_name="Bit Depth",
                    tooltip="The bit depth to use when saving images as BMP.\n32bit supports alpha channel.",
                    options=["24bit", "32bit"],
                    default="24bit",
                ),
                io.Boolean.Input(
                    id="join_alpha",
                    display_name="Join Alpha Channel",
                    tooltip="Clip the image with the provided mask.\nPlease note this only works on 32bit bit depth.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel before saving.",
                    default=False,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Int.Input(
                    id="dpi",
                    display_name="DPI",
                    tooltip="The DPI to use when saving images.",
                    default=define.printing_dpi,
                    min=1,
                    max=600,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedBMP")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedBMP"))


class SaveImageTIFF(io.ComfyNode):
    """
    Saves images to disk as TIFF files.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageTIFF",
            display_name="Save Image (TIFF)",
            category=define.author,
            description="Saves images to disk as TIFF files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Mask.Input(
                    id="masks",
                    display_name="Alpha Masks",
                    tooltip="Optional alpha channel masks to clip the saved images. If provided, these masks will be applied to the corresponding images before saving.",
                    optional=True,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageTIFF")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageTIFF"))


class SaveImageAdvancedTIFF(io.ComfyNode):
    """
    Saves images to disk as TIFF files with additional options.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedTIFF",
            display_name="Save Image Advanced (TIFF)",
            category=define.author,
            description="Saves images to disk as TIFF files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Mask.Input(
                    id="masks",
                    display_name="Alpha Masks",
                    tooltip="Optional alpha channel masks to clip the saved images. If provided, these masks will be applied to the corresponding images before saving.",
                    optional=True,
                ),
                io.Boolean.Input(
                    id="disable_metadata",
                    display_name="Disable Metadata",
                    tooltip="Disable embedding EXIF data into the saved images.\nEmbed into `UserComment`.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="join_alpha",
                    display_name="Join Alpha Channel",
                    tooltip="Clip the image with the provided mask.\nPlease note this does not work on JPG format.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel before saving.",
                    default=False,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Int.Input(
                    id="dpi",
                    display_name="DPI",
                    tooltip="The DPI to use when saving images.",
                    default=define.printing_dpi,
                    min=1,
                    max=600,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Combo.Input(
                    id="tiff_compression",
                    display_name="Compression",
                    tooltip="The compression to use when saving images as TIFF.",
                    options=[
                        "none",
                        "tiff_lzw",
                        "tiff_deflate",
                        "tiff_adobe_deflate",
                        "packbits",
                        "jpeg",
                        "tiff_jpeg",
                        "tiff_ccitt",
                    ],
                    default="none",
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedTIFF")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedTIFF"))


class SaveImageTGA(io.ComfyNode):
    """
    Saves images to disk as TGA files.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageTGA",
            display_name="Save Image (TGA)",
            category=define.author,
            description="Saves images to disk as TGA files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageTGA")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageTGA"))


class SaveImageAdvancedTGA(io.ComfyNode):
    """
    Saves images to disk as TGA files with additional options.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedTGA",
            display_name="Save Image Advanced (TGA)",
            category=define.author,
            description="Saves images to disk as TGA files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Mask.Input(
                    id="masks",
                    display_name="Alpha Masks",
                    tooltip="Optional alpha channel masks to clip the saved images. If provided, these masks will be applied to the corresponding images before saving.",
                    optional=True,
                ),
                io.Boolean.Input(
                    id="rle",
                    display_name="RLE Compression",
                    tooltip="Whether to use RLE compression when saving as TGA.",
                    default=True,
                ),
                io.Boolean.Input(
                    id="join_alpha",
                    display_name="Join Alpha Channel",
                    tooltip="Clip the image with the provided mask.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel before saving.",
                    default=False,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedTGA")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedTGA"))


class SaveImageAVIF(io.ComfyNode):
    """
    Saves images to disk as AVIF files.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAVIF",
            display_name="Save Image (AVIF)",
            category=define.author,
            description="Saves images to disk as AVIF files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAVIF")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAVIF"))


class SaveImageAdvancedAVIF(io.ComfyNode):
    """
    Saves images to disk as AVIF files with additional options.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedAVIF",
            display_name="Save Image Advanced (AVIF)",
            category=define.author,
            description="Saves images to disk as AVIF files.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be saved.",
                ),
                io.Mask.Input(
                    id="masks",
                    display_name="Alpha Masks",
                    tooltip="Optional alpha channel masks to clip the saved images. If provided, these masks will be applied to the corresponding images before saving.",
                    optional=True,
                ),
                io.Boolean.Input(
                    id="join_alpha",
                    display_name="Join Alpha Channel",
                    tooltip="Clip the image with the provided mask.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel before saving.",
                    default=False,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Int.Input(
                    id="dpi",
                    display_name="DPI",
                    tooltip="The DPI to use when saving images.",
                    default=define.printing_dpi,
                    min=1,
                    max=600,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Int.Input(
                    id="quality",
                    display_name="Quality",
                    tooltip="The quality of the saved images (0-100).",
                    default=80,
                    min=0,
                    max=100,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Int.Input(
                    id="speed",
                    display_name="Speed",
                    tooltip="AVIF encoding speed (0-10). 0 is slowest/best, 10 is fastest.",
                    default=6,
                    min=0,
                    max=10,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedAVIF")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedAVIF"))


class SaveImageICO(io.ComfyNode):
    """
    Save multiple images to disk as a bundled ICO file.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageICO",
            display_name="Save Image (ICO)",
            category=define.author,
            description="Save the image batch to disk as a single bundled ICO file.\nImages must be square and one of the standard ICO sizes\n(16, 24, 32, 48, 64, 128, 256).\nInvalid images are optionally saved as fallback PNGs.",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="Images",
                    tooltip="The images to be bundled into a single ICO file.\nEach image must be square and match a valid ICO size\n(16, 24, 32, 48, 64, 128, or 256 px).",
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Boolean.Input(
                    id="save_invalid_as_png",
                    display_name="Save Invalid as PNG",
                    tooltip="When enabled, images that fail ICO validation are saved as\nindividual PNG files with an `_INVALID` suffix.\nWhen disabled, invalid images are silently discarded.",
                    default=True,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageICO")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageICO"))


class SaveImageAdvancedICO(io.ComfyNode):
    """
    Save multiple images to disk as a bundled ICO file with explicit size choices.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveImageAdvancedICO",
            display_name="Save Image Advanced (ICO)",
            category=define.author,
            description="Save images from an ICO Packer node to disk as a single bundled ICO file.\nEach packed size must match its image dimensions (e.g. 32×32 for size 32).\nInvalid images are optionally saved as fallback PNGs.",
            inputs=[
                io.Custom("ICO_PACKER").Input(
                    id="ico_packer",
                    display_name="ICO Packer",
                    tooltip="Connect an ICO Packer node output.\nContains per-size images and optional masks.",
                ),
                io.Combo.Input(
                    id="color_depth",
                    display_name="Color Depth",
                    tooltip="The color depth of the images.",
                    options=["8bit", "16bit", "32bit"],
                    default="8bit",
                ),
                io.Combo.Input(
                    id="compression",
                    display_name="Compression",
                    tooltip="The compression of the images.",
                    options=["none", "RLE", "ZIP"],
                    default="none",
                ),
                io.Boolean.Input(
                    id="join_alpha",
                    display_name="Join Alpha Channel",
                    tooltip="Whether to join the alpha channel of the images.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="invert_alpha",
                    display_name="Invert Alpha",
                    tooltip="Whether to invert the alpha channel of the images.",
                    default=False,
                ),
                io.String.Input(
                    id="filename_prefix",
                    display_name="Filename Prefix",
                    tooltip="The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes.",
                    default=define.default_file_name,
                ),
                io.Boolean.Input(
                    id="save_to_input_folder",
                    display_name="Save to Input Folder",
                    tooltip="Whether to sync the image to the input folder.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="sort_by_size",
                    display_name="Sort by Size",
                    tooltip="When enabled, the images will be sorted by size before being bundled into the ICO file.",
                    default=False,
                ),
                io.Boolean.Input(
                    id="save_invalid_as_png",
                    display_name="Save Invalid as PNG",
                    tooltip="When enabled, images that fail ICO validation are saved as\nindividual PNG files with an `_INVALID` suffix.\nWhen disabled, invalid images are silently discarded.",
                    default=True,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("SaveImageAdvancedICO")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("SaveImageAdvancedICO"))


class ICOPacker(io.ComfyNode):
    """
    Prepare the info to be packed into an ICO file.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ICOPacker",
            display_name="ICO Packer",
            category=define.author,
            description="Pack multiple images into a single ICO file.\nUse the node menu to add image/mask pairs per ICO size.",
            inputs=[
                io.Boolean.Input(
                    id="crop_images",
                    display_name="Crop Images",
                    tooltip="When enabled, images (and masks) larger than the slot size are cropped to that size before packing.",
                    default=False,
                ),
                io.Combo.Input(
                    id="crop_reference_point",
                    display_name="Reference Point",
                    tooltip="When Crop Images is enabled, choose the anchor for the crop window.",
                    options=["center", "top-left"],
                    default="center",
                ),
            ],
            outputs=[
                io.Custom("ICO_PACKER").Output(
                    id="ico_packer",
                )
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            accept_all_inputs=True,
        )

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _refusal("ICOPacker")

    @classmethod
    def execute(cls, **kwargs):
        raise NotConvertedError(_refusal("ICOPacker"))
