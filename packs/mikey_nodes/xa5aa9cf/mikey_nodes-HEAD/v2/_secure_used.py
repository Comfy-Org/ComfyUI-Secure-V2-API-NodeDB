"""Secure Nodes V2 classes for mikey_nodes' converted node types (pin a5aa9cf637c4).

Each schema is the original's, frozen in the lane gate (_frozen_schema.py); the two model menus are the host's
catalogues (/models/checkpoints, /models/upscale_models). Each execute runs the original code from
_mikey_upstream.py (verbatim class bodies and helpers) or, where the original touches the host (files, models,
sampling, saving), a line-for-line port whose host steps go through the SDK:
  - value nodes (strings, numbers, file name prefixes, tile sizes, resize): the original methods, unchanged.
  - Wildcard Processor / WildcardOobaPrompt: the original methods; the wildcard files come from the
    `mikey_wildcards` asset kind (the original read <user directory>/wildcards). <llm:...> is refused (network).
  - Empty Latent Ratio Select SDXL: the original method on the pack's own ratios.json.
  - Checkpoint Loader Simple Mikey: the engine loads the checkpoint; ckpt_hash is the file's sha256[:10].
  - MikeySamplerTiledAdvancedBaseOnly: the original steps, with the engine sampling, decoding, encoding and running
    the upscale model; tiling, stitching and resizing are the original's (and Core's) code.
  - Save Images Mikey / Save Images No Display: the original file naming and counters, written by the SDK image
    writer with the original's PNG text chunks.
  - Batch Load Images: refused (it reads an arbitrary host directory).
"""
import datetime
import json
import os
import re

import numpy as np
import torch
from comfy_api.latest import io, sdk

from . import _core_upscale
from . import _mikey_upstream as up
from . import _mikey_wildcards
from ._frozen_schema import schema_for

PACK = "mikey_nodes"
WILDCARD_KIND = "mikey_wildcards"
WILDCARD_TOKEN = re.compile(r'((\d+)\$\$)?__(!|\+|-|\*)?((?:[^|_]+_)*[^|_]+)((?:\|[^|]+)*)__')  # the original's regex


class NotConvertedError(RuntimeError):
    """The node (or the requested feature) is not converted to Secure Nodes V2."""


class WildcardsUnavailableError(RuntimeError):
    """The prompt uses a wildcard, but the host has no mikey_wildcards asset kind."""


def _hidden(cls, name):
    hidden = getattr(cls, "hidden", None)
    return getattr(hidden, name, None) if hidden is not None else None


async def _load_wildcards(node_id, texts):
    """Fill the wildcard tree from the asset kind. Without the kind, a prompt that names a wildcard is refused
    (the original would read the file or, if it is missing, drop the token); one without wildcards runs unchanged."""
    assets = sdk.ctx().assets
    try:
        names = await assets.list(WILDCARD_KIND, recursive=True)
    except PermissionError:
        raise
    except Exception as exc:
        if any(WILDCARD_TOKEN.search(str(text or "")) for text in texts):
            raise WildcardsUnavailableError(
                f"{PACK}/{node_id}: the prompt uses a wildcard, but the host has no {WILDCARD_KIND} asset kind "
                f"({type(exc).__name__}: {exc}). The original read wildcard files from the user directory's "
                "wildcards folder.") from exc
        _mikey_wildcards.load_tree({})
        return
    files = {}
    for name in names:
        if name.endswith(".txt"):
            files[name] = await assets.read_bytes(await assets.resolve(WILDCARD_KIND, name))
    _mikey_wildcards.load_tree(files)


def _remote_combo(schema, input_id, route):
    for item in schema.inputs:
        if item.id == input_id:
            item.remote = io.RemoteOptions(route=route, refresh_button=True)
            return schema
    raise KeyError(input_id)


# ---------------------------------------------------------------- value nodes (original methods)
class Int_to_String(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Int to String")

    @classmethod
    async def execute(cls, int_, use_commas):
        return io.NodeOutput(*up.INTtoSTRING().convert(int_, use_commas))


class Range_Integer(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Range Integer")

    @classmethod
    async def execute(cls, start, end, step, seed):
        value, text = up.RangeInteger().generate(start, end, step, seed)
        # The original returns numpy's int64; the guest wire carries the same value as a Python int.
        return io.NodeOutput(int(value), text)


class Seed_String(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Seed String")

    @classmethod
    async def execute(cls, seed):
        return io.NodeOutput(*up.IntegerAndString().output(seed))


class TextConcat(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("TextConcat")

    @classmethod
    async def execute(cls, delimiter, **kwargs):
        return io.NodeOutput(*up.TextConcat().concat(delimiter, **kwargs))


class RemoveTextBetween(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("RemoveTextBetween")

    @classmethod
    async def execute(cls, text, **kwargs):
        return io.NodeOutput(*up.RemoveTextBetween().remove(text, **kwargs))


class FileNamePrefix(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("FileNamePrefix")

    @classmethod
    async def execute(cls, date, date_directory, custom_directory, custom_text):
        return io.NodeOutput(*up.FileNamePrefix().get_filename_prefix(
            date, date_directory, custom_directory, custom_text,
            prompt=_hidden(cls, "prompt"), extra_pnginfo=_hidden(cls, "extra_pnginfo")))


class FileNamePrefixDateDirFirst(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("FileNamePrefixDateDirFirst")

    @classmethod
    async def execute(cls, date, date_directory, custom_directory, custom_text):
        return io.NodeOutput(*up.FileNamePrefixDateDirFirst().get_filename_prefix(
            date, date_directory, custom_directory, custom_text,
            prompt=_hidden(cls, "prompt"), extra_pnginfo=_hidden(cls, "extra_pnginfo")))


class Upscale_Tile_Calculator(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Upscale Tile Calculator")

    @classmethod
    async def execute(cls, image, tile_resolution):
        return io.NodeOutput(*up.UpscaleTileCalculator().calculate(image, tile_resolution))


class Resize_Image_for_SDXL(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Resize Image for SDXL")

    @classmethod
    async def execute(cls, image, upscale_method, crop):
        return io.NodeOutput(*up.ResizeImageSDXL().resize(image, upscale_method, crop))


class Empty_Latent_Ratio_Select_SDXL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)  # LatentRef.from_value stores a guest tensor (the host's refs.store needs "raw")

    @classmethod
    def define_schema(cls):
        return schema_for("Empty Latent Ratio Select SDXL")

    @classmethod
    async def execute(cls, ratio_selected, batch_size=1):
        node = up.EmptyLatentRatioSelector
        node.INPUT_TYPES()  # the original reads ratios.json here (class attributes ratio_sizes / ratio_dict)
        (latent,) = node().generate(ratio_selected, batch_size)
        return io.NodeOutput(await sdk.LatentRef.from_value(latent))


# ---------------------------------------------------------------- wildcards
class Wildcard_Processor(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return schema_for("Wildcard Processor")

    @classmethod
    async def execute(cls, prompt, seed):
        await _load_wildcards("Wildcard Processor", [prompt])
        return io.NodeOutput(*up.WildcardProcessor().process(
            prompt, seed, prompt_=_hidden(cls, "prompt"), extra_pnginfo=_hidden(cls, "extra_pnginfo")))


class WildcardOobaPrompt(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return schema_for("WildcardOobaPrompt")

    @classmethod
    async def execute(cls, input_prompt, seed):
        await _load_wildcards("WildcardOobaPrompt", [input_prompt])
        # The original also writes the result into the hidden prompt dict (prompt[unique_id].inputs.output_text) for
        # later nodes' metadata; this guest's copy of the prompt is not shared with other nodes.
        return io.NodeOutput(*up.WildcardOobaPrompt().process(
            input_prompt, seed, prompt=_hidden(cls, "prompt"), unique_id=_hidden(cls, "unique_id"),
            extra_pnginfo=_hidden(cls, "extra_pnginfo")))


# ---------------------------------------------------------------- refused
class Batch_Load_Images(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    REASON = ("it loads every image in a directory path typed into the node, anywhere on the host's file system, "
              "and a Secure Nodes V2 guest can read only the host's catalogued folders")

    @classmethod
    def define_schema(cls):
        return schema_for("Batch Load Images")

    @classmethod
    def validate_inputs(cls, image_directory=None, subdirectories=None):
        return f"{PACK}/Batch Load Images is not yet converted to Secure Nodes V2: {cls.REASON}"

    @classmethod
    async def execute(cls, **kwargs):
        raise NotConvertedError(f"{PACK}/Batch Load Images is not yet converted to Secure Nodes V2: {cls.REASON}")


# ---------------------------------------------------------------- models and sampling (ported; the engine runs them)
class Checkpoint_Loader_Simple_Mikey(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models", "assets")

    @classmethod
    def define_schema(cls):
        return _remote_combo(schema_for("Checkpoint Loader Simple Mikey"), "ckpt_name", "/models/checkpoints")

    @classmethod
    async def execute(cls, ckpt_name):
        # mikey_nodes.py CheckpointLoaderSimpleMikey.load_checkpoint:
        context = sdk.ctx()
        model, clip, vae = await context.models.load_checkpoint(ckpt_name)
        # get_file_hash: the first 10 hex digits of the file's sha256 (the original caches it by base name)
        asset = await context.assets.resolve("checkpoints", ckpt_name)
        hash = (await context.assets.digest(asset, algorithm="sha256"))[:10]
        ckpt_name = os.path.basename(ckpt_name)
        return io.NodeOutput(model, clip, vae, ckpt_name, hash)


async def _image_value(value):
    return value if isinstance(value, torch.Tensor) else await value.raw()


async def _ksample(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent, start_step=None,
                   last_step=None, force_full_denoise=False):
    """nodes.common_ksampler (denoise 1.0, noise on), run by the engine."""
    options = {}
    if start_step is not None:
        options["start_step"] = start_step
    if last_step is not None:
        options["last_step"] = last_step
    return await sdk.ctx().sample(latent=latent, steps=steps, model=model, positive=positive, negative=negative,
                                  cfg=cfg, seed=seed, sampler_name=sampler_name, scheduler=scheduler, denoise=1.0,
                                  force_full_denoise=force_full_denoise, **options)


async def _upscale_with_model(model_name, pixels):
    """UpscaleModelLoader().load_model + ImageUpscaleWithModel().upscale, run by the engine."""
    upscale_model = await sdk.ctx().models.load_upscale_model(model_name)
    return await _image_value(await upscale_model.upscale(await sdk.ImageRef.from_value(pixels)))


class MikeySamplerTiledAdvancedBaseOnly(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "sample", "models")

    @classmethod
    def define_schema(cls):
        return _remote_combo(schema_for("MikeySamplerTiledAdvancedBaseOnly"), "model_name", "/models/upscale_models")

    # mikey_nodes.py MikeySamplerTiledAdvancedBaseOnly (L3114-3194), ported line for line.
    @staticmethod
    async def phase_one(base_model, samples, positive_cond_base, negative_cond_base,
                        upscale_by, model_name, seed, vae, denoise_image,
                        steps, cfg, sampler_name, scheduler):
        image_scaler = _core_upscale.ImageScale()
        # step 1 run base model
        start_step = int(steps - (steps * denoise_image))
        sample1 = await _ksample(base_model, seed, steps, cfg, sampler_name, scheduler, positive_cond_base,
                                 negative_cond_base, samples, start_step=start_step, last_step=steps,
                                 force_full_denoise=False)
        # step 3 upscale image using a simple AI image upscaler
        pixels = await _image_value(await vae.decode(sample1))
        org_width, org_height = pixels.shape[2], pixels.shape[1]
        img = await _upscale_with_model(model_name, pixels)
        upscaled_width, upscaled_height = int(org_width * upscale_by // 8 * 8), int(org_height * upscale_by // 8 * 8)
        img = image_scaler.upscale(img, 'nearest-exact', upscaled_width, upscaled_height, 'center')[0]
        return img, upscaled_width, upscaled_height

    @staticmethod
    async def upscale_image(samples, vae, upscale_by, model_name):
        image_scaler = _core_upscale.ImageScale()
        # step 3 upscale image using a simple AI image upscaler
        pixels = await _image_value(await vae.decode(samples))
        org_width, org_height = pixels.shape[2], pixels.shape[1]
        img = await _upscale_with_model(model_name, pixels)
        upscaled_width, upscaled_height = int(org_width * upscale_by // 8 * 8), int(org_height * upscale_by // 8 * 8)
        img = image_scaler.upscale(img, 'nearest-exact', upscaled_width, upscaled_height, 'center')[0]
        return img, upscaled_width, upscaled_height

    @classmethod
    async def execute(cls, seed, base_model, vae, samples, positive_cond_base, negative_cond_base,
                      model_name, upscale_by=2.0, tiler_denoise=0.4, tile_size=1024,
                      denoise_image=1.0, steps=30, cfg=6.5,
                      sampler_name='dpmpp_sde_gpu', scheduler='karras', image_optional=None):
        # if image not none replace samples with decoded image
        if image_optional is not None:
            samples = await vae.encode(image_optional)
        if denoise_image > 0:
            # phase 1: run base, refiner, then upscaler model
            img, upscaled_width, upscaled_height = await cls.phase_one(
                base_model, samples, positive_cond_base, negative_cond_base, upscale_by, model_name, seed, vae,
                denoise_image, steps, cfg, sampler_name, scheduler)
            img = up.tensor2pil(img)
        else:
            img = await cls.upscale_image(samples, vae, upscale_by, model_name)
            img = up.tensor2pil(img)  # the original passes the (image, width, height) tuple here and fails
        # phase 2: run tiler
        tiled_image = await cls.run_tiler_for_steps(img, base_model, vae, seed, cfg, sampler_name, scheduler,
                                                    positive_cond_base, negative_cond_base, steps, tiler_denoise,
                                                    tile_size)
        return io.NodeOutput(await sdk.ImageRef.from_value(tiled_image))

    # mikey_nodes.py run_tiler_for_steps (L2956-2969) and ai_upscale_adv (L2930-2941), ported line for line.
    @staticmethod
    async def ai_upscale_adv(tile, base_model, vae, seed, cfg, sampler_name, scheduler, positive_cond_base,
                             negative_cond_base, start_step=11, end_step=20):
        """Upscale a tile using the AI model."""
        tile = up.pil2tensor(tile)
        encoded_tile = await vae.encode(await sdk.ImageRef.from_value(tile))
        tile = await _ksample(base_model, seed, end_step, cfg, sampler_name, scheduler,
                              positive_cond_base, negative_cond_base, encoded_tile,
                              start_step=start_step, force_full_denoise=True)
        tile = await _image_value(await vae.decode(tile))
        return tile

    @classmethod
    async def run_tiler_for_steps(cls, enlarged_img, base_model, vae, seed, cfg, sampler_name, scheduler,
                                  positive_cond_base, negative_cond_base, steps=20, denoise=0.25, tile_size=1024):
        # Split the enlarged image into overlapping tiles
        tiles = up.split_image(enlarged_img, tile_size=tile_size)

        # Resample each tile using the AI model
        start_step = int(steps - (steps * denoise))
        end_step = steps
        resampled_tiles = [(coords, await cls.ai_upscale_adv(tile, base_model, vae, seed, cfg, sampler_name,
                                                             scheduler, positive_cond_base, negative_cond_base,
                                                             start_step, end_step)) for coords, tile in tiles]

        # Stitch the tiles to get the final upscaled image
        result = up.stitch_images(enlarged_img.size, resampled_tiles)

        return result


# ---------------------------------------------------------------- saving (ported; the SDK image writer saves)
class DuplicatePngTextError(ValueError):
    """The original writes duplicate PNG text chunks, which the V2 image writer cannot store."""


def _png_text(prompt, extra_pnginfo, extra_metadata, node_id):
    """The original's PngInfo.add_text calls (SaveImagesMikeyML.save_images, L1584-1601), in order."""
    pairs = []
    if prompt is not None:
        pairs.append(("prompt", json.dumps(prompt)))
    if extra_pnginfo is not None:
        for x in extra_pnginfo:
            if x == 'parameters':
                # encode text as utf-8
                text = extra_pnginfo[x].encode('utf-8').decode('utf-8')
                pairs.append((x, text))
            elif x == 'workflow':
                pairs.append((x, json.dumps(extra_pnginfo[x])))
            elif x == 'prompt':
                pairs.append((x, json.dumps(extra_pnginfo[x])))
            else:
                pairs.append((x, json.dumps(extra_pnginfo[x], ensure_ascii=False)))
    if extra_metadata:
        pairs.append(("extra_metadata", extra_metadata))
    text = {}
    for key, value in pairs:
        if key in text:
            raise DuplicatePngTextError(
                f"{PACK}/{node_id}: PNG text key {key!r} occurs more than once (the prompt, extra_pnginfo and "
                "extra_metadata keys); the original writes duplicate text chunks, which the V2 image writer cannot "
                "store.")
        text[key] = value
    return text


async def _save_images_mikey(node_id, images, sub_directory, filename_text_1, filename_text_2, filename_text_3,
                             filename_separator, timestamp, counter_type,
                             filename_text_1_pos, filename_text_2_pos, filename_text_3_pos,
                             timestamp_pos, timestamp_type, counter_pos, extra_metadata,
                             prompt=None, extra_pnginfo=None):
    """mikey_nodes.py SaveImagesMikeyML.save_images (L1536-1623), ported line for line: the directory listing and
    existence checks go through the SDK's output assets, and the SDK image writer saves each file."""
    self = up.SaveImagesMikeyML()
    assets = sdk.ctx().assets
    positions = [filename_text_1_pos, filename_text_2_pos, filename_text_3_pos, timestamp_pos, counter_pos]
    if len(positions) != len(set(positions)):
        raise ValueError("Duplicate position numbers detected. Please ensure all position numbers are unique.")
    sub_directory = up.search_and_replace(sub_directory, extra_pnginfo, prompt)
    # replace only characters that are not allowed in filenames
    sub_directory = re.sub(r'[<>:"|?*]', '', sub_directory)
    # remove non ascii characters
    sub_directory = sub_directory.encode('ascii', 'ignore').decode('ascii')
    # os.path.join(output_dir, sub_directory): an absolute sub_directory leaves the output directory, which the V2
    # image writer never does; ".." is refused by the SDK's confinement check.
    if sub_directory.startswith("/"):
        raise ValueError(f"{PACK}/{node_id}: sub_directory {sub_directory!r} is an absolute path outside the output "
                         "directory; the V2 image writer writes only inside it")
    logical_dir = "/".join(part for part in sub_directory.replace("\\", "/").split("/") if part not in ("", "."))

    filename_texts = self._prepare_filename_texts(filename_text_1, filename_text_2, filename_text_3, extra_pnginfo,
                                                  prompt)

    if timestamp == 'true':
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    else:
        ts = ''

    elements = {
        filename_text_1_pos: filename_texts[0],
        filename_text_2_pos: filename_texts[1],
        filename_text_3_pos: filename_texts[2],
        timestamp_pos: ts,
        counter_pos: 'counter' if counter_type != 'none' else None
    }

    # Construct initial filename without the counter
    sorted_elements = [elem for _, elem in sorted(elements.items()) if elem]
    filename_base = filename_separator.join(sorted_elements).replace('counter', '{counter}')

    # Get initial counter value (os.listdir of the output sub-directory: its files, by name)
    listed = await assets.list("output", prefix=logical_dir, recursive=False)
    files = [name[len(logical_dir) + 1:] if logical_dir else name for name in listed]
    if counter_type != 'none':
        counter = self._get_initial_counter(files, None, counter_type, filename_separator, counter_pos,
                                            filename_texts)
    else:
        counter = 0

    batch = await _image_value(images)
    text = _png_text(prompt, extra_pnginfo, extra_metadata, node_id)
    results = list()
    for ix, image in enumerate(batch):
        # Check and get the next available counter (_get_next_counter, over the output assets)
        if counter_type != 'none':
            while await assets.exists("output", "/".join(p for p in (logical_dir, filename_base.format(
                    counter=f"{counter:05}") + ".png") if p)):
                counter += 1
            current_filename = filename_base.format(counter=f"{counter:05}")
        else:
            current_filename = filename_base
        if timestamp_type == 'save_time' and timestamp == 'true':
            current_timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
            current_filename = current_filename.replace(ts, current_timestamp)
            ts = current_timestamp
        if ix > 0 and counter_type == 'none':
            current_filename = current_filename.replace(ts, ts + f'_{ix:02}')
        logical = "/".join(p for p in (logical_dir, f"{current_filename}.png") if p)
        try:
            saved = await sdk.ctx().output.save_images(
                await sdk.ImageRef.from_value(image.unsqueeze(0)), filenames=[logical], compress_level=4,
                save_metadata=False, png_text=text)
        except Exception as error:
            if "an exact output image already exists" in str(error):
                raise FileExistsError(
                    f"{PACK}/{node_id}: {logical} already exists. The original overwrites it, but the V2 image "
                    "writer never overwrites files; use a timestamp or a counter in the file name.") from error
            raise
        results.append({
            "filename": f"{current_filename}.png",
            "subfolder": sub_directory,
            "type": "output",
        })
        if counter_type != 'none':
            counter += 1

    return results


class Save_Images_Mikey(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets", "output")

    @classmethod
    def define_schema(cls):
        return schema_for("Save Images Mikey")

    @classmethod
    async def execute(cls, images, **kwargs):
        results = await _save_images_mikey("Save Images Mikey", images, **kwargs, prompt=_hidden(cls, "prompt"),
                                           extra_pnginfo=_hidden(cls, "extra_pnginfo"))
        return io.NodeOutput(ui={"images": results})


class Save_Images_No_Display(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets", "output")

    @classmethod
    def define_schema(cls):
        return schema_for("Save Images No Display")

    @classmethod
    async def execute(cls, images, **kwargs):
        await _save_images_mikey("Save Images No Display", images, **kwargs, prompt=_hidden(cls, "prompt"),
                                 extra_pnginfo=_hidden(cls, "extra_pnginfo"))
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {
    "Batch Load Images": Batch_Load_Images,
    "Checkpoint Loader Simple Mikey": Checkpoint_Loader_Simple_Mikey,
    "Empty Latent Ratio Select SDXL": Empty_Latent_Ratio_Select_SDXL,
    "FileNamePrefix": FileNamePrefix,
    "FileNamePrefixDateDirFirst": FileNamePrefixDateDirFirst,
    "Int to String": Int_to_String,
    "MikeySamplerTiledAdvancedBaseOnly": MikeySamplerTiledAdvancedBaseOnly,
    "Range Integer": Range_Integer,
    "RemoveTextBetween": RemoveTextBetween,
    "Resize Image for SDXL": Resize_Image_for_SDXL,
    "Save Images Mikey": Save_Images_Mikey,
    "Save Images No Display": Save_Images_No_Display,
    "Seed String": Seed_String,
    "TextConcat": TextConcat,
    "Upscale Tile Calculator": Upscale_Tile_Calculator,
    "Wildcard Processor": Wildcard_Processor,
    "WildcardOobaPrompt": WildcardOobaPrompt,
}
