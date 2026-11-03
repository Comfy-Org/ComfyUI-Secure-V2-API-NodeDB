"""comfy_mtb (pin b35b5d8a): the converted node types.

Each schema is the original's, frozen in the lane gate (_frozen_schemas.json). Each body runs the original's own
code from _mtb_upstream.py (verbatim copies); what differs is how values cross the boundary:
- most nodes take and return plain values (SDK_REFS = False): tensors, numbers and strings, as the original's;
- Vae Decode asks the host to decode (the VAE stays on the host), with the original's tiling;
- Load Image Sequence reads its file through the SDK's assets, from ComfyUI's input, output or temp folder.
Inputs the original accepts but V2 cannot honour are refused by name.
"""

import io as _bytes_io
import re

from comfy_api.latest import io, sdk

from . import _mtb_upstream as upstream
from ._frozen_schema import schema_for

PACK = "comfy-mtb"
_DRIVE = re.compile(r"^[A-Za-z]:")


def _refused(node_id, reason):
    return ValueError(f"{PACK}/{node_id}: {reason}")


async def _mask_output(mask):
    """A MASK tensor made in the guest, handed back unchanged.

    The runtime publishes a plain-values output declared MASK only as [B, H, W] or [B, 1, H, W] (production guests'
    patch; a bare base guest wraps every tensor as IMAGE). The original's single-frame loader returns [H, W], and
    a picked mask has whatever shape its input had. This SDK base has no public MASK constructor, so the mask
    crosses as a VALUE: the host stores exactly this tensor as the node's output, as the original returns it.
    """
    return None if mask is None else await sdk.ValueRef.from_value(mask)


class Any_To_String__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Any To String (mtb)")

    @classmethod
    def execute(cls, input):
        # A model, VAE, CLIP or other live host object cannot cross as a value: the runtime refuses it before this
        # body runs ("input 'input' is a OpaqueRef ..."). The original prints the object itself (its repr).
        if isinstance(input, sdk.Ref):
            raise _refused("Any To String (mtb)", f"a {input.kind} value is a host object in Secure Nodes V2, so "
                           "its text (the original prints the object itself) cannot be reproduced")
        return io.NodeOutput(*upstream.MTB_AnyToString().do_str(input))


class String_Replace__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("String Replace (mtb)")

    @classmethod
    def execute(cls, string, old, new, use_regex):
        return io.NodeOutput(*upstream.MTB_StringReplace().replace_str(string, old, new, use_regex))


class Int_To_Number__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Int To Number (mtb)")

    @classmethod
    def execute(cls, int):  # noqa: A002 (the original's input name)
        return io.NodeOutput(*upstream.MTB_IntToNumber().int_to_number(int))


class Pick_From_Batch__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Pick From Batch (mtb)")

    @classmethod
    async def execute(cls, image, from_direction, count, mask=None):
        picked, picked_mask = upstream.MTB_PickFromBatch().pick_from_batch(image, from_direction, count, mask)
        if picked.shape[0] == 0 or (picked_mask is not None and picked_mask.shape[0] == 0):
            # The original returns an empty batch here (e.g. count 0 from the start); V2 cannot pass one on.
            raise _refused("Pick From Batch (mtb)", f"count {count} from the {from_direction} picks no images; the "
                           "original returns an empty IMAGE batch, which Secure Nodes V2 cannot pass between nodes")
        return io.NodeOutput(picked, await _mask_output(picked_mask))


class Color_Correct__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Color Correct (mtb)")

    @classmethod
    def execute(cls, image, clamp, gamma=1.0, contrast=1.0, exposure=0.0, offset=0.0, hue=0.0, saturation=1.0,
                value=1.0, mask=None):
        return io.NodeOutput(*upstream.MTB_ColorCorrect().correct(
            image, clamp, gamma, contrast, exposure, offset, hue, saturation, value, mask))


class Image_Compare__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Image Compare (mtb)")

    @classmethod
    def execute(cls, imageA, imageB, mode):
        return io.NodeOutput(*upstream.MTB_ImageCompare().compare(imageA, imageB, mode))


class Sharpen__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Sharpen (mtb)")

    @classmethod
    def execute(cls, image, sharpen_radius, sigma_x, sigma_y, alpha):
        return io.NodeOutput(*upstream.MTB_Sharpen().do_sharp(image, sharpen_radius, sigma_x, sigma_y, alpha))


class Uncrop__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Uncrop (mtb)")

    @classmethod
    def execute(cls, image, crop_image, bbox, border_blending=0.25):
        return io.NodeOutput(*upstream.MTB_Uncrop().do_uncrop(image, crop_image, bbox, border_blending))


class Vae_Decode__mtb_(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Vae Decode (mtb)")

    @classmethod
    async def execute(cls, vae, samples, seamless_model, use_tiling_decoder=True, tile_size=512):
        # The original (nodes/model.py MTB_VaeDecode.decode):
        #   tiled:  vae.decode_tiled(samples["samples"], tile_x=tile_size // 8, tile_y=tile_size // 8), with Core's
        #           default overlap (16 latent pixels);
        #   plain:  vae.decode(samples["samples"]).
        # The host's tiled decode is Core's VAEDecodeTiled: tile and overlap in pixels, divided by the VAE's own
        # compression, and the overlap shrinks to tile_size // 4 below 512. With an 8x image VAE, tile_size >= 512
        # and overlap 128 that is the original's call exactly; other cases are refused by name.
        if seamless_model:
            raise _refused("Vae Decode (mtb)", "seamless_model is not supported in Secure Nodes V2: the original "
                           "switches the VAE's convolutions to circular padding in place, which changes the shared "
                           "host VAE for every later node")
        if use_tiling_decoder:
            layout = await vae.latent_layout()
            if layout["spatial_compression"] != 8 or layout["temporal_compression"] is not None:
                raise _refused("Vae Decode (mtb)", "the tiling decoder is supported in Secure Nodes V2 only for "
                               "image VAEs with 8x compression (the original divides tile_size by 8 for every VAE); "
                               "turn use_tiling_decoder off")
            if tile_size < 512:
                raise _refused("Vae Decode (mtb)", f"tile_size {tile_size} is not supported in Secure Nodes V2: "
                               "below 512 the host's tiled decode narrows the tile overlap, where the original "
                               "keeps 16 latent pixels; use 512 or more, or turn use_tiling_decoder off")
            return io.NodeOutput(await vae.decode_tiled(samples, tile_size=tile_size, overlap=128))
        return io.NodeOutput(await vae.decode(samples))


def _input_file(node_id, name):
    """(folder, logical name) for the original's folder_paths.get_annotated_filepath(name): a trailing
    " [output]", " [input]" or " [temp]" picks that folder, otherwise the input folder."""
    folder = "input"
    for suffix, managed in (("[output]", "output"), ("[input]", "input"), ("[temp]", "temp")):
        if name.endswith(suffix):
            folder, name = managed, name[:-(len(suffix) + 1)]
            break
    text = name.replace("\\", "/")
    if text.startswith("/") or _DRIVE.match(text) or ".." in text.split("/"):
        raise _refused(node_id, f"Secure Nodes V2 loads images only from inside ComfyUI's input, output or temp "
                       f"folder; '{name}' is outside it. Put the frames in a sub-folder of the input folder.")
    return folder, text


class Load_Image_Sequence__mtb_(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return schema_for("Load Image Sequence (mtb)")

    @staticmethod
    def _all_frames_refusal():
        return _refused("Load Image Sequence (mtb)", "loading all frames (current_frame -1) or a range is not "
                        "supported in Secure Nodes V2: the original finds the frames with glob on the server's "
                        "file system, relative to its working folder; load one frame at a time from the input "
                        "folder instead")

    @classmethod
    async def fingerprint_inputs(cls, path="", current_frame=0, range=""):  # noqa: A002 (the original's names)
        # The original's IS_CHANGED: the sha256 of the frame's bytes, or "NONE" when the file does not exist.
        if range or current_frame == -1:
            return float("nan")
        folder, name = _input_file("Load Image Sequence (mtb)", upstream.resolve_path(path, current_frame))
        ctx = sdk.ctx()
        if not await ctx.assets.exists(folder, name):
            return "NONE"
        return await ctx.assets.digest(await ctx.assets.resolve(folder, name), algorithm="sha256")

    @classmethod
    async def execute(cls, path=None, current_frame=0, range=""):  # noqa: A002 (the original's names)
        if range or current_frame == -1:
            raise cls._all_frames_refusal()
        total_frames = 1
        folder, name = _input_file("Load Image Sequence (mtb)", upstream.resolve_path(path, current_frame))
        ctx = sdk.ctx()
        data = await ctx.assets.read_bytes(await ctx.assets.resolve(folder, name))
        image, mask = upstream.img_from_path(_bytes_io.BytesIO(data))
        return io.NodeOutput(image, await _mask_output(mask), current_frame, total_frames)


NODE_CLASS_MAPPINGS = {
    "Any To String (mtb)": Any_To_String__mtb_,
    "Color Correct (mtb)": Color_Correct__mtb_,
    "Image Compare (mtb)": Image_Compare__mtb_,
    "Int To Number (mtb)": Int_To_Number__mtb_,
    "Load Image Sequence (mtb)": Load_Image_Sequence__mtb_,
    "Pick From Batch (mtb)": Pick_From_Batch__mtb_,
    "Sharpen (mtb)": Sharpen__mtb_,
    "String Replace (mtb)": String_Replace__mtb_,
    "Uncrop (mtb)": Uncrop__mtb_,
    "Vae Decode (mtb)": Vae_Decode__mtb_,
}
