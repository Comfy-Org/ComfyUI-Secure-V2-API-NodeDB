"""Secure Nodes 2.0 implementation of Ultimate SD Upscale.

This module is a port of the pack's own tile pipeline:
- usdu_nodes.py and the usdu_patch.py sizing and batching patches;
- modules/processing.py, modules/upscaler.py, modules/images.py and the
  usdu_utils.py helpers;
- the bundled ultimate-upscale.py script.

Their PIL operations are unchanged: crop regions from the drawn tile masks,
Lanczos resizes, the Gaussian mask blur, the gradient seam masks, alpha
compositing and the 8-bit image round trips. A tile is therefore cut, blended
and pasted exactly as the original does it.

The functions are async because the model-owned steps cross the Secure Nodes
2.0 SDK as opaque references: upscale-model inference, VAE encode/decode,
diffusion sampling, and the spatial crops of conditioning and model patches.
Comments of the form "file:line" point at the pinned upstream source.
"""
from __future__ import annotations

import logging
import math
from enum import Enum
from typing import Any, Callable, List, Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from ._secure_runtime import SCHEMAS, bind_node, sdk


logger = logging.getLogger(__name__)

# Upper bound on the working canvas (batch x width x height) in a sandboxed
# guest. The original has no limit; an image this large exhausts memory there.
_MAX_PIXELS = 67_108_864


# --------------------------------------------------------------------------- #
# SDK boundary
# --------------------------------------------------------------------------- #
def _ctx():
    return sdk.ctx()


async def _image_ref(pixels):
    return await sdk.ImageRef.from_value(pixels)


async def _release(refs):
    released = set()
    for ref in reversed(refs):
        if ref is not None and ref.id not in released:
            released.add(ref.id)
            await ref.release()


async def _upscale_with_model(upscale_model, image):
    # modules/upscaler.py:17-21: ImageUpscaleWithModel(upscale_model, image),
    # i.e. ComfyUI's tiled runner (512-pixel tiles, 32-pixel overlap, output
    # clamped to [0, 1]) on the node's original IMAGE.
    upscaled = await upscale_model.upscale(image, tile_size=512)
    try:
        return torch.as_tensor(await upscaled.raw())
    finally:
        await upscaled.release()


async def _crop_cond(cond, regions, init_size, canvas_size, tile_size, created):
    """usdu_utils.py:558-569 (crop_cond).

    Rows without area, mask, GLIGEN, ControlNet or reference-latent metadata
    pass through unchanged, as in the original. Rows with such metadata are
    cropped by the host's spatial conditioning crop for the first region.
    """
    if cond is None:
        return None
    if not await cond.has_spatial_metadata():
        return cond
    region = regions if isinstance(regions, tuple) else regions[0]
    init_width, init_height = init_size
    canvas_width, canvas_height = canvas_size
    source_width = max(1, math.ceil(init_width / 8))
    source_height = max(1, math.ceil(init_height / 8))
    left, top, right, bottom = region
    x = max(0, min(source_width - 1, math.floor(
        left * source_width / canvas_width)))
    y = max(0, min(source_height - 1, math.floor(
        top * source_height / canvas_height)))
    crop_right = max(x + 1, min(source_width, math.ceil(
        right * source_width / canvas_width)))
    crop_bottom = max(y + 1, min(source_height, math.ceil(
        bottom * source_height / canvas_height)))
    cropped = await cond.spatial_crop(
        x=x, y=y, width=crop_right - x, height=crop_bottom - y,
        source_width=source_width, source_height=source_height,
        target_width=max(1, math.ceil(tile_size[0] / 8)),
        target_height=max(1, math.ceil(tile_size[1] / 8)),
    )
    created.append(cropped)
    return cropped


async def sample(model, seed, steps, cfg, sampler_name, scheduler, positive,
                 negative, latent, denoise, custom_sampler, custom_sigmas):
    """processing.py:156-182: choose the way to sample based on given inputs."""

    # Custom sampler and sigmas: SamplerCustom(model, add_noise=True,
    # noise_seed=seed, cfg, positive, negative, sampler, sigmas, latent).
    if custom_sampler is not None and custom_sigmas is not None:
        return await _ctx().sample(
            latent=latent, steps=max(1, int(steps)), model=model,
            positive=positive, negative=negative, cfg=float(cfg),
            seed=int(seed), sampler_name=str(sampler_name),
            scheduler=str(scheduler), sampler=custom_sampler,
            sigmas=custom_sigmas,
        )

    # Default: common_ksampler(model, seed, steps, cfg, sampler_name,
    # scheduler, positive, negative, latent, denoise=denoise).
    return await _ctx().sample(
        latent=latent, steps=int(steps), model=model, positive=positive,
        negative=negative, cfg=float(cfg), seed=int(seed),
        sampler_name=str(sampler_name), scheduler=str(scheduler),
        denoise=float(denoise),
    )


async def _generate(p, batched_tiles, crop_regions, canvas_size, tile_size):
    """The model-owned middle of process_images() and process_batch_tiles().

    processing.py:256-283 and :384-413: VAEEncode, crop_cond and
    crop_model_cond, sample() or sample_with_guider(), then VAEDecode or
    VAEDecodeTiled. Returns the decoded IMAGE tensor.
    """
    created = []
    try:
        pixels = await _image_ref(batched_tiles)
        created.append(pixels)
        latent = await p.vae.encode(pixels)
        created.append(latent)
        regions = crop_regions if isinstance(crop_regions, list) else [crop_regions]
        crop = dict(
            regions=[tuple(int(value) for value in region) for region in regions],
            source_width=int(canvas_size[0]),
            source_height=int(canvas_size[1]),
            target_width=int(tile_size[0]),
            target_height=int(tile_size[1]),
        )
        if p.guider is not None:
            # Guider-based sampling: crop_model_cond(...) + sample_with_guider().
            guider = await p.guider.spatial_crop_inputs(**crop)
            created.append(guider)
            samples = await _ctx().sample(
                latent=latent, steps=1, guider=guider,
                sampler=p.custom_sampler, sigmas=p.custom_sigmas,
                seed=int(p.seed),
            )
        else:
            # Crop conditioning
            positive_cropped = await _crop_cond(
                p.positive, crop_regions, p.init_size, canvas_size, tile_size,
                created)
            negative_cropped = await _crop_cond(
                p.negative, crop_regions, p.init_size, canvas_size, tile_size,
                created)
            model = await p.model.spatial_crop_inputs(**crop)
            created.append(model)
            # Generate samples
            samples = await sample(
                model, p.seed, p.steps, p.cfg, p.sampler_name, p.scheduler,
                positive_cropped, negative_cropped, latent, p.denoise,
                p.custom_sampler, p.custom_sigmas)
        created.append(samples)

        # Decode the sample
        if not p.tiled_decode:
            decoded = await p.vae.decode(samples)
        else:
            decoded = await p.vae.decode_tiled(samples, 512)  # Default tile size is 512
        created.append(decoded)
        images = torch.as_tensor(await decoded.raw())
        if images.ndim == 5:  # nodes.VAEDecode: combine batches
            images = images.reshape(
                -1, images.shape[-3], images.shape[-2], images.shape[-1])
        return images
    finally:
        await _release(created)


async def _progress(p, tiles):
    # The original updates its per-tile progress bar here.
    p.tiles_done += tiles
    await _ctx().progress.update(p.tiles_done, max(p.tiles_total, p.tiles_done))


# --------------------------------------------------------------------------- #
# usdu_utils.py
# --------------------------------------------------------------------------- #
def tensor_to_pil(img_tensor, batch_index=0):
    # Takes a batch of images in the form of a tensor of shape [batch_size, height, width, channels]
    # and returns an RGB PIL Image. Assumes channels=3
    safe_tensor = torch.nan_to_num(img_tensor[batch_index])
    return Image.fromarray((255 * safe_tensor.cpu().numpy()).astype(np.uint8))


def pil_to_tensor(image):
    # Takes a PIL image and returns a tensor of shape [1, height, width, channels]
    image = np.array(image).astype(np.float32) / 255.0
    image = torch.from_numpy(image).unsqueeze(0)
    if len(image.shape) == 3:  # If the image is grayscale, add a channel dimension
        image = image.unsqueeze(-1)
    return image


def get_crop_region(mask, pad=0):
    # Takes a black and white PIL image in 'L' mode and returns the coordinates of the white rectangular mask region
    # Should be equivalent to the get_crop_region function from https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/master/modules/masking.py
    coordinates = mask.getbbox()
    if coordinates is not None:
        x1, y1, x2, y2 = coordinates
    else:
        x1, y1, x2, y2 = mask.width, mask.height, 0, 0
    # Apply padding
    x1 = max(x1 - pad, 0)
    y1 = max(y1 - pad, 0)
    x2 = min(x2 + pad, mask.width)
    y2 = min(y2 + pad, mask.height)
    return fix_crop_region((x1, y1, x2, y2), (mask.width, mask.height))


def fix_crop_region(region, image_size):
    # Remove the extra pixel added by the get_crop_region function
    image_width, image_height = image_size
    x1, y1, x2, y2 = region
    if x2 < image_width:
        x2 -= 1
    if y2 < image_height:
        y2 -= 1
    return x1, y1, x2, y2


def expand_crop(region, width, height, target_width, target_height):
    '''
    Expands a crop region to a specified target size.
    :param region: A tuple of the form (x1, y1, x2, y2) denoting the upper left and the lower right points
        of the rectangular region. Expected to have x2 > x1 and y2 > y1.
    :param width: The width of the image the crop region is from.
    :param height: The height of the image the crop region is from.
    :param target_width: The desired width of the crop region.
    :param target_height: The desired height of the crop region.
    '''
    x1, y1, x2, y2 = region
    actual_width = x2 - x1
    actual_height = y2 - y1
    # target_width = math.ceil(actual_width / 8) * 8
    # target_height = math.ceil(actual_height / 8) * 8

    # Try to expand region to the right of half the difference
    width_diff = target_width - actual_width
    x2 = min(x2 + width_diff // 2, width)
    # Expand region to the left of the difference including the pixels that could not be expanded to the right
    width_diff = target_width - (x2 - x1)
    x1 = max(x1 - width_diff, 0)
    # Try the right again
    width_diff = target_width - (x2 - x1)
    x2 = min(x2 + width_diff, width)

    # Try to expand region to the bottom of half the difference
    height_diff = target_height - actual_height
    y2 = min(y2 + height_diff // 2, height)
    # Expand region to the top of the difference including the pixels that could not be expanded to the bottom
    height_diff = target_height - (y2 - y1)
    y1 = max(y1 - height_diff, 0)
    # Try the bottom again
    height_diff = target_height - (y2 - y1)
    y2 = min(y2 + height_diff, height)

    return (x1, y1, x2, y2), (target_width, target_height)


# --------------------------------------------------------------------------- #
# modules/images.py, modules/shared.py
# --------------------------------------------------------------------------- #
def flatten(img, bgcolor):
    # Replace transparency with bgcolor
    if img.mode in ("RGB"):
        return img
    return Image.alpha_composite(Image.new("RGBA", img.size, bgcolor), img).convert("RGB")


class Options:
    img2img_background_color = "#ffffff"  # Set to white for now


class State:
    interrupted = False

    def begin(self):
        pass

    def end(self):
        pass


class Shared:
    """modules/shared.py, held per node call rather than as module globals."""

    def __init__(self):
        self.opts = Options()
        self.state = State()
        # Will only ever hold 1 upscaler
        self.sd_upscalers = [None]
        # The upscaler usable by ComfyUI nodes
        self.actual_upscaler = None
        # Batch of images to upscale
        self.batch = []
        self.batch_as_tensor = None


# --------------------------------------------------------------------------- #
# modules/upscaler.py
# --------------------------------------------------------------------------- #
class Upscaler:

    def __init__(self, shared):
        self.shared = shared

    async def upscale(self, img: Image, scale, selected_model: str = None):
        shared = self.shared
        if scale == 1.0:
            return img
        if (shared.actual_upscaler is None):
            return img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
        upscaled = await _upscale_with_model(shared.actual_upscaler, shared.batch_as_tensor)
        shared.batch = [tensor_to_pil(upscaled, i) for i in range(len(upscaled))]
        return shared.batch[0]


class UpscalerData:
    name = ""
    data_path = ""

    def __init__(self, shared):
        self.scaler = Upscaler(shared)


# --------------------------------------------------------------------------- #
# modules/processing.py
# --------------------------------------------------------------------------- #
class USDUMode(Enum):
    LINEAR = 0
    CHESS = 1
    NONE = 2


class USDUSFMode(Enum):
    NONE = 0
    BAND_PASS = 1
    HALF_TILE = 2
    HALF_TILE_PLUS_INTERSECTIONS = 3


class StableDiffusionProcessing:

    def __init__(
        self,
        shared,
        init_img,
        model,
        positive,
        negative,
        vae,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        upscale_by,
        uniform_tile_mode,
        tiled_decode,
        tile_width,
        tile_height,
        redraw_mode,
        seam_fix_mode,
        custom_sampler=None,
        custom_sigmas=None,
        batch_size=1,
        guider=None,
    ):
        self.shared = shared
        # Variables used by the USDU script
        self.init_images = [init_img]
        self.image_mask = Image.new('L', init_img.size, 0)  # Placeholder mask
        self.mask_blur = 0
        self.inpaint_full_res_padding = 0
        self.width = init_img.width * upscale_by
        self.height = init_img.height * upscale_by
        self.rows = round(self.height / tile_height)
        self.cols = round(self.width / tile_width)

        # Guider-based sampling (guider encapsulates model + conditioning + cfg)
        self.guider = guider

        # ComfyUI Sampler inputs. With a guider, its own models are cropped per
        # tile (crop_model_cond on guider.model_patcher in the original).
        self.model = model
        self.positive = positive
        self.negative = negative
        self.vae = vae
        self.seed = seed
        self.steps = steps
        self.cfg = cfg
        self.sampler_name = sampler_name
        self.scheduler = scheduler
        self.denoise = denoise

        # Optional custom sampler and sigmas
        self.custom_sampler = custom_sampler
        self.custom_sigmas = custom_sigmas

        if guider is None and (custom_sampler is not None) ^ (custom_sigmas is not None):
            logger.warning("Both custom sampler and custom sigmas must be provided, defaulting to widget sampler and sigmas")

        # Variables used only by this script
        self.init_size = init_img.width, init_img.height
        self.upscale_by = upscale_by
        self.uniform_tile_mode = uniform_tile_mode
        self.tiled_decode = tiled_decode
        self.batch_size = batch_size

        # Other required A1111 variables for the USDU script that is currently unused in this script
        self.extra_generation_params = {}

        # Progress for the entire process, one step per tile
        self.tiles_done = 0
        self.tiles_total = 1


class Processed:

    def __init__(self, p: StableDiffusionProcessing, images: list, seed: int, info: str):
        self.images = images
        self.seed = seed
        self.info = info

    def infotext(self, p: StableDiffusionProcessing, index):
        return None


def fix_seed(p: StableDiffusionProcessing):
    pass


async def process_images(p: StableDiffusionProcessing) -> Processed:
    # Where the main image generation happens in A1111
    shared = p.shared

    # Setup
    image_mask = p.image_mask.convert('L')
    init_image = p.init_images[0]

    # Locate the white region of the mask outlining the tile and add padding
    crop_region = get_crop_region(image_mask, p.inpaint_full_res_padding)

    if p.uniform_tile_mode:
        # Expand the crop region to match the processing size ratio and then resize it to the processing size
        x1, y1, x2, y2 = crop_region
        crop_width = x2 - x1
        crop_height = y2 - y1
        crop_ratio = crop_width / crop_height
        p_ratio = p.width / p.height
        if crop_ratio > p_ratio:
            target_width = crop_width
            target_height = round(crop_width / p_ratio)
        else:
            target_width = round(crop_height * p_ratio)
            target_height = crop_height
        crop_region, _ = expand_crop(crop_region, image_mask.width, image_mask.height, target_width, target_height)
        tile_size = p.width, p.height
    else:
        # Uses the minimal size that can fit the mask, minimizes tile size but may lead to image sizes that the model is not trained on
        x1, y1, x2, y2 = crop_region
        crop_width = x2 - x1
        crop_height = y2 - y1
        target_width = math.ceil(crop_width / 8) * 8
        target_height = math.ceil(crop_height / 8) * 8
        crop_region, tile_size = expand_crop(crop_region, image_mask.width,
                                             image_mask.height, target_width, target_height)

    # Blur the mask
    if p.mask_blur > 0:
        image_mask = image_mask.filter(ImageFilter.GaussianBlur(p.mask_blur))

    # Crop the images to get the tiles that will be used for generation
    tiles = [img.crop(crop_region) for img in shared.batch]

    # Assume the same size for all images in the batch
    initial_tile_size = tiles[0].size

    # Resize if necessary
    for i, tile in enumerate(tiles):
        if tile.size != tile_size:
            tiles[i] = tile.resize(tile_size, Image.Resampling.LANCZOS)

    # Encode the image, sample and decode
    batched_tiles = torch.cat([pil_to_tensor(tile) for tile in tiles], dim=0)
    decoded = await _generate(p, batched_tiles, crop_region, init_image.size, tile_size)

    # Update the progress bar
    await _progress(p, 1)

    # Convert the sample to a PIL image
    tiles_sampled = [tensor_to_pil(decoded, i) for i in range(len(decoded))]

    for i, tile_sampled in enumerate(tiles_sampled):
        init_image = shared.batch[i]

        # Resize back to the original size
        if tile_sampled.size != initial_tile_size:
            tile_sampled = tile_sampled.resize(initial_tile_size, Image.Resampling.LANCZOS)

        # Put the tile into position
        image_tile_only = Image.new('RGBA', init_image.size)
        image_tile_only.paste(tile_sampled, crop_region[:2])

        # Add the mask as an alpha channel
        # Must make a copy due to the possibility of an edge becoming black
        temp = image_tile_only.copy()
        temp.putalpha(image_mask)
        image_tile_only.paste(temp, image_tile_only)

        # Add back the tile to the initial image according to the mask in the alpha channel
        result = init_image.convert('RGBA')
        result.alpha_composite(image_tile_only)

        # Convert back to RGB
        result = result.convert('RGB')

        shared.batch[i] = result

    processed = Processed(p, [shared.batch[0]], p.seed, "")
    return processed


async def process_batch_tiles(
    p: StableDiffusionProcessing,
    tiles_coords: List[Tuple[int, int]],
    images: List[Image.Image],
    calc_rectangle_fn: Callable,
) -> List[Image.Image]:
    """Encode, sample and decode a batch of tiles and composite them back into *images*.

    Unlike process_images() which operates on a single pre-built mask, this function
    builds per-tile masks from *calc_rectangle_fn* and handles every (tile, image)
    combination in one batched encode → sample → decode pass.
    """
    if not tiles_coords or not images:
        return images

    batch_tiles: List[Tuple[Image.Image, Tuple[int, int]]] = []
    batch_masks: List[Image.Image] = []
    batch_crop_regions: List[Tuple[int, int, int, int]] = []
    batch_tile_sizes: List[Tuple[int, int]] = []

    for image in images:
        for tx, ty in tiles_coords:
            tile_mask = Image.new("L", (image.width, image.height), "black")
            tile_draw = ImageDraw.Draw(tile_mask)
            tile_draw.rectangle(calc_rectangle_fn(tx, ty), fill="white")

            crop_region = get_crop_region(tile_mask, p.inpaint_full_res_padding)

            if p.uniform_tile_mode:
                x1, y1, x2, y2 = crop_region
                crop_w = x2 - x1
                crop_h = y2 - y1
                crop_ratio = crop_w / crop_h if crop_h != 0 else 1.0
                p_ratio = p.width / p.height if p.height != 0 else 1.0
                if crop_ratio > p_ratio:
                    target_w = crop_w
                    target_h = round(crop_w / p_ratio)
                else:
                    target_w = round(crop_h * p_ratio)
                    target_h = crop_h
                crop_region, _ = expand_crop(crop_region, tile_mask.width, tile_mask.height, target_w, target_h)
                tile_size: Tuple[int, int] = (p.width, p.height)
            else:
                x1, y1, x2, y2 = crop_region
                crop_w = x2 - x1
                crop_h = y2 - y1
                target_w = math.ceil(crop_w / 8) * 8
                target_h = math.ceil(crop_h / 8) * 8
                crop_region, tile_size = expand_crop(crop_region, tile_mask.width, tile_mask.height, target_w, target_h)

            if p.mask_blur > 0:
                tile_mask = tile_mask.filter(ImageFilter.GaussianBlur(p.mask_blur))

            cropped_tile = image.crop(crop_region)
            initial_tile_size = cropped_tile.size
            if cropped_tile.size != tile_size:
                cropped_tile = cropped_tile.resize(tile_size, Image.Resampling.LANCZOS)

            batch_tiles.append((cropped_tile, initial_tile_size))
            batch_masks.append(tile_mask)
            batch_crop_regions.append(crop_region)
            batch_tile_sizes.append(tile_size)

    # Encode all tiles into a single latent batch, sample and decode
    batched_tensors = torch.cat([pil_to_tensor(tile) for tile, _ in batch_tiles], dim=0)
    first_tile_size = batch_tile_sizes[0]
    decoded = await _generate(p, batched_tensors, batch_crop_regions, images[0].size, first_tile_size)

    # Update progress bar once per batch call (one step per tile coord)
    await _progress(p, len(tiles_coords))

    # Composite each decoded tile back onto its source image
    result_imgs = list(images)
    for i, result_img in enumerate(result_imgs):
        for j in range(len(tiles_coords)):
            idx = i * len(tiles_coords) + j
            tile_sampled = tensor_to_pil(decoded, idx)
            initial_tile_size = batch_tiles[idx][1]
            crop_region = batch_crop_regions[idx]
            tile_mask = batch_masks[idx]

            if tile_sampled.size != initial_tile_size:
                tile_sampled = tile_sampled.resize(initial_tile_size, Image.Resampling.LANCZOS)

            image_tile_only = Image.new('RGBA', result_img.size)
            image_tile_only.paste(tile_sampled, crop_region[:2])

            temp = image_tile_only.copy()
            temp.putalpha(tile_mask)
            image_tile_only.paste(temp, image_tile_only)

            result = result_img.convert('RGBA')
            result.alpha_composite(image_tile_only)
            result_img = result.convert('RGB')
            result_imgs[i] = result_img

    return result_imgs


# --------------------------------------------------------------------------- #
# repositories/ultimate_sd_upscale/scripts/ultimate-upscale.py with the
# usdu_patch.py patches applied in place
# --------------------------------------------------------------------------- #
def round_length(length: int, multiple: int = 8) -> int:
    """Round length to nearest multiple (default 8)."""
    return round(length / multiple) * multiple


class USDUpscaler():

    def __init__(self, p, image, upscaler_index:int, save_redraw, save_seams_fix, tile_width, tile_height) -> None:
        # usdu_patch.py:52-54 (patch_usdu_upscaler_init)
        p.width = round_length(image.width * p.upscale_by)
        p.height = round_length(image.height * p.upscale_by)
        if p.width * p.height * max(1, len(p.shared.batch)) > _MAX_PIXELS:
            raise ValueError("Ultimate SD Upscale target exceeds the pixel limit")
        self.p:StableDiffusionProcessing = p
        self.image:Image = image
        self.scale_factor = math.ceil(max(p.width, p.height) / max(image.width, image.height))
        self.upscaler = p.shared.sd_upscalers[upscaler_index]
        self.redraw = USDURedraw()
        self.redraw.save = save_redraw
        self.redraw.tile_width = tile_width if tile_width > 0 else tile_height
        self.redraw.tile_height = tile_height if tile_height > 0 else tile_width
        self.seams_fix = USDUSeamsFix()
        self.seams_fix.save = save_seams_fix
        self.seams_fix.tile_width = tile_width if tile_width > 0 else tile_height
        self.seams_fix.tile_height = tile_height if tile_height > 0 else tile_width
        self.initial_info = None
        self.rows = math.ceil(self.p.height / self.redraw.tile_height)
        self.cols = math.ceil(self.p.width / self.redraw.tile_width)

    def get_factor(self, num):
        # Its just return, don't need elif
        if num == 1:
            return 2
        if num % 4 == 0:
            return 4
        if num % 3 == 0:
            return 3
        if num % 2 == 0:
            return 2
        return 0

    def get_factors(self):
        scales = []
        current_scale = 1
        current_scale_factor = self.get_factor(self.scale_factor)
        while current_scale_factor == 0:
            self.scale_factor += 1
            current_scale_factor = self.get_factor(self.scale_factor)
        while current_scale < self.scale_factor:
            current_scale_factor = self.get_factor(self.scale_factor // current_scale)
            scales.append(current_scale_factor)
            current_scale = current_scale * current_scale_factor
            if current_scale_factor == 0:
                break
        self.scales = enumerate(scales)

    async def upscale(self):
        # Log info
        print(f"Canva size: {self.p.width}x{self.p.height}")
        print(f"Image size: {self.image.width}x{self.image.height}")
        print(f"Scale factor: {self.scale_factor}")
        # Check upscaler is not empty
        if self.upscaler.name == "None":
            self.image = self.image.resize((self.p.width, self.p.height), resample=Image.LANCZOS)
        else:
            # Get list with scale factors
            self.get_factors()
            # Upscaling image over all factors
            for index, value in self.scales:
                print(f"Upscaling iteration {index+1} with scale factor {value}")
                self.image = await self.upscaler.scaler.upscale(self.image, value, self.upscaler.data_path)
            # Resize image to set values
            self.image = self.image.resize((self.p.width, self.p.height), resample=Image.LANCZOS)
        # usdu_patch.py:91-97 (patch_usdu_upscale_method): keep shared.batch
        # consistent with the upscaling width/height for subsequent processing.
        shared = self.p.shared
        shared.batch = [self.image] + [
            img.resize((self.p.width, self.p.height), resample=Image.LANCZOS)
            for img in shared.batch[1:]
        ]

    def setup_redraw(self, redraw_mode, padding, mask_blur):
        self.redraw.mode = USDUMode(redraw_mode)
        self.redraw.enabled = self.redraw.mode != USDUMode.NONE
        self.redraw.padding = padding
        self.p.mask_blur = mask_blur

    def setup_seams_fix(self, padding, denoise, mask_blur, width, mode):
        self.seams_fix.padding = padding
        self.seams_fix.denoise = denoise
        self.seams_fix.mask_blur = mask_blur
        self.seams_fix.width = width
        self.seams_fix.mode = USDUSFMode(mode)
        self.seams_fix.enabled = self.seams_fix.mode != USDUSFMode.NONE

    def calc_jobs_count(self):
        redraw_job_count = (self.rows * self.cols) if self.redraw.enabled else 0
        seams_job_count = 0
        if self.seams_fix.mode == USDUSFMode.BAND_PASS:
            seams_job_count = self.rows + self.cols - 2
        elif self.seams_fix.mode == USDUSFMode.HALF_TILE:
            seams_job_count = self.rows * (self.cols - 1) + (self.rows - 1) * self.cols
        elif self.seams_fix.mode == USDUSFMode.HALF_TILE_PLUS_INTERSECTIONS:
            seams_job_count = self.rows * (self.cols - 1) + (self.rows - 1) * self.cols + (self.rows - 1) * (self.cols - 1)

        self.p.shared.state.job_count = redraw_job_count + seams_job_count

    def print_info(self):
        print(f"Tile size: {self.redraw.tile_width}x{self.redraw.tile_height}")
        print(f"Tiles amount: {self.rows * self.cols}")
        print(f"Grid: {self.rows}x{self.cols}")
        print(f"Redraw enabled: {self.redraw.enabled}")
        print(f"Seams fix mode: {self.seams_fix.mode.name}")

    def add_extra_info(self):
        self.p.extra_generation_params["Ultimate SD upscale upscaler"] = self.upscaler.name
        self.p.extra_generation_params["Ultimate SD upscale tile_width"] = self.redraw.tile_width
        self.p.extra_generation_params["Ultimate SD upscale tile_height"] = self.redraw.tile_height
        self.p.extra_generation_params["Ultimate SD upscale mask_blur"] = self.p.mask_blur
        self.p.extra_generation_params["Ultimate SD upscale padding"] = self.redraw.padding

    async def process(self):
        state = self.p.shared.state
        state.begin()
        self.calc_jobs_count()
        self.p.tiles_total = max(1, state.job_count)
        self.result_images = []
        if self.redraw.enabled:
            self.image = await self.redraw.start(self.p, self.image, self.rows, self.cols)
            self.initial_info = self.redraw.initial_info
        self.result_images.append(self.image)

        if self.seams_fix.enabled:
            self.image = await self.seams_fix.start(self.p, self.image, self.rows, self.cols)
            self.initial_info = self.seams_fix.initial_info
            self.result_images.append(self.image)
        state.end()


class USDURedraw():

    def init_draw(self, p, width, height):
        p.inpaint_full_res = True
        p.inpaint_full_res_padding = self.padding
        p.width = math.ceil((self.tile_width+self.padding) / 64) * 64
        p.height = math.ceil((self.tile_height+self.padding) / 64) * 64
        mask = Image.new("L", (width, height), "black")
        draw = ImageDraw.Draw(mask)
        # usdu_patch.py:66-69 (patch_usdu_redraw_init)
        p.width = round_length(self.tile_width + self.padding)
        p.height = round_length(self.tile_height + self.padding)
        return mask, draw

    def calc_rectangle(self, xi, yi):
        x1 = xi * self.tile_width
        y1 = yi * self.tile_height
        x2 = xi * self.tile_width + self.tile_width
        y2 = yi * self.tile_height + self.tile_height

        return x1, y1, x2, y2

    async def linear_process(self, p, image, rows, cols):
        state = p.shared.state
        # usdu_patch.py:179-209 (new_linear_process)
        batch_size = getattr(p, 'batch_size', 1)
        if batch_size <= 1:
            # ultimate-upscale.py:171-189 (linear_process)
            mask, draw = self.init_draw(p, image.width, image.height)
            for yi in range(rows):
                for xi in range(cols):
                    if state.interrupted:
                        break
                    draw.rectangle(self.calc_rectangle(xi, yi), fill="white")
                    p.init_images = [image]
                    p.image_mask = mask
                    processed = await process_images(p)
                    draw.rectangle(self.calc_rectangle(xi, yi), fill="black")
                    if (len(processed.images) > 0):
                        image = processed.images[0]

            p.width = image.width
            p.height = image.height
            self.initial_info = processed.infotext(p, 0)

            return image

        # Batch mode
        mask_template, draw_template = self.init_draw(p, image.width, image.height)
        tiles_to_process: List[Tuple[int, int]] = []
        batch_count = 0

        for yi in range(rows):
            for xi in range(cols):
                if state.interrupted:
                    break

                tiles_to_process.append((xi, yi))

                if len(tiles_to_process) >= batch_size or (yi == rows - 1 and xi == cols - 1):
                    batch_count += 1
                    p.shared.batch = await process_batch_tiles(p, tiles_to_process, p.shared.batch, self.calc_rectangle)
                    tiles_to_process = []

        p.width = image.width
        p.height = image.height
        return image

    async def chess_process(self, p, image, rows, cols):
        state = p.shared.state
        # usdu_patch.py:211-252 (new_chess_process)
        batch_size = getattr(p, 'batch_size', 1)
        if batch_size <= 1:
            # ultimate-upscale.py:191-240 (chess_process)
            mask, draw = self.init_draw(p, image.width, image.height)
            tiles = []
            # calc tiles colors
            for yi in range(rows):
                for xi in range(cols):
                    if state.interrupted:
                        break
                    if xi == 0:
                        tiles.append([])
                    color = xi % 2 == 0
                    if yi > 0 and yi % 2 != 0:
                        color = not color
                    tiles[yi].append(color)

            for yi in range(len(tiles)):
                for xi in range(len(tiles[yi])):
                    if state.interrupted:
                        break
                    if not tiles[yi][xi]:
                        tiles[yi][xi] = not tiles[yi][xi]
                        continue
                    tiles[yi][xi] = not tiles[yi][xi]
                    draw.rectangle(self.calc_rectangle(xi, yi), fill="white")
                    p.init_images = [image]
                    p.image_mask = mask
                    processed = await process_images(p)
                    draw.rectangle(self.calc_rectangle(xi, yi), fill="black")
                    if (len(processed.images) > 0):
                        image = processed.images[0]

            for yi in range(len(tiles)):
                for xi in range(len(tiles[yi])):
                    if state.interrupted:
                        break
                    if not tiles[yi][xi]:
                        continue
                    draw.rectangle(self.calc_rectangle(xi, yi), fill="white")
                    p.init_images = [image]
                    p.image_mask = mask
                    processed = await process_images(p)
                    draw.rectangle(self.calc_rectangle(xi, yi), fill="black")
                    if (len(processed.images) > 0):
                        image = processed.images[0]

            p.width = image.width
            p.height = image.height
            self.initial_info = processed.infotext(p, 0)

            return image

        mask_template, draw_template = self.init_draw(p, image.width, image.height)

        # Determine tile "white/black" order
        tile_colors = []
        for yi in range(rows):
            row_colors = []
            for xi in range(cols):
                color = xi % 2 == 0
                if yi > 0 and yi % 2 != 0:
                    color = not color
                row_colors.append(color)
            tile_colors.append(row_colors)

        # Helper to iterate tiles in chess order: white first, then black
        def chess_order_iter(white: bool):
            for yi in range(rows):
                for xi in range(cols):
                    if tile_colors[yi][xi] == white:
                        yield (xi, yi)

        # Process white tiles then black tiles
        for color in (True, False):
            tiles_to_process: List[Tuple[int, int]] = []
            for tx, ty in chess_order_iter(color):
                if state.interrupted:
                    break
                tiles_to_process.append((tx, ty))
                if len(tiles_to_process) >= batch_size:
                    p.shared.batch = await process_batch_tiles(p, tiles_to_process, p.shared.batch, self.calc_rectangle)
                    tiles_to_process = []
            if tiles_to_process:
                p.shared.batch = await process_batch_tiles(p, tiles_to_process, p.shared.batch, self.calc_rectangle)

        p.width = image.width
        p.height = image.height
        return image

    async def start(self, p, image, rows, cols):
        self.initial_info = None
        if self.mode == USDUMode.LINEAR:
            return await self.linear_process(p, image, rows, cols)
        if self.mode == USDUMode.CHESS:
            return await self.chess_process(p, image, rows, cols)


class USDUSeamsFix():

    def init_draw(self, p):
        self.initial_info = None
        p.width = math.ceil((self.tile_width+self.padding) / 64) * 64
        p.height = math.ceil((self.tile_height+self.padding) / 64) * 64
        # usdu_patch.py:78-81 (patch_usdu_seams_fix_init)
        p.width = round_length(self.tile_width + self.padding)
        p.height = round_length(self.tile_height + self.padding)

    async def half_tile_process(self, p, image, rows, cols):
        state = p.shared.state

        self.init_draw(p)
        processed = None

        gradient = Image.linear_gradient("L")
        row_gradient = Image.new("L", (self.tile_width, self.tile_height), "black")
        row_gradient.paste(gradient.resize(
            (self.tile_width, self.tile_height//2), resample=Image.BICUBIC), (0, 0))
        row_gradient.paste(gradient.rotate(180).resize(
                (self.tile_width, self.tile_height//2), resample=Image.BICUBIC),
                (0, self.tile_height//2))
        col_gradient = Image.new("L", (self.tile_width, self.tile_height), "black")
        col_gradient.paste(gradient.rotate(90).resize(
            (self.tile_width//2, self.tile_height), resample=Image.BICUBIC), (0, 0))
        col_gradient.paste(gradient.rotate(270).resize(
            (self.tile_width//2, self.tile_height), resample=Image.BICUBIC), (self.tile_width//2, 0))

        # The original sets denoising_strength, which its sampler never reads:
        # seam passes sample with the main denoise (p.denoise). Kept for parity.
        p.denoising_strength = self.denoise
        p.mask_blur = self.mask_blur

        for yi in range(rows-1):
            for xi in range(cols):
                if state.interrupted:
                    break
                p.width = self.tile_width
                p.height = self.tile_height
                p.inpaint_full_res = True
                p.inpaint_full_res_padding = self.padding
                mask = Image.new("L", (image.width, image.height), "black")
                mask.paste(row_gradient, (xi*self.tile_width, yi*self.tile_height + self.tile_height//2))

                p.init_images = [image]
                p.image_mask = mask
                processed = await process_images(p)
                if (len(processed.images) > 0):
                    image = processed.images[0]

        for yi in range(rows):
            for xi in range(cols-1):
                if state.interrupted:
                    break
                p.width = self.tile_width
                p.height = self.tile_height
                p.inpaint_full_res = True
                p.inpaint_full_res_padding = self.padding
                mask = Image.new("L", (image.width, image.height), "black")
                mask.paste(col_gradient, (xi*self.tile_width+self.tile_width//2, yi*self.tile_height))

                p.init_images = [image]
                p.image_mask = mask
                processed = await process_images(p)
                if (len(processed.images) > 0):
                    image = processed.images[0]

        p.width = image.width
        p.height = image.height
        if processed is not None:
            self.initial_info = processed.infotext(p, 0)

        return image

    async def half_tile_process_corners(self, p, image, rows, cols):
        state = p.shared.state
        fixed_image = await self.half_tile_process(p, image, rows, cols)
        processed = None
        self.init_draw(p)
        gradient = Image.radial_gradient("L").resize(
            (self.tile_width, self.tile_height), resample=Image.BICUBIC)
        gradient = ImageOps.invert(gradient)
        p.denoising_strength = self.denoise
        #p.mask_blur = 0
        p.mask_blur = self.mask_blur

        for yi in range(rows-1):
            for xi in range(cols-1):
                if state.interrupted:
                    break
                p.width = self.tile_width
                p.height = self.tile_height
                p.inpaint_full_res = True
                p.inpaint_full_res_padding = 0
                mask = Image.new("L", (fixed_image.width, fixed_image.height), "black")
                mask.paste(gradient, (xi*self.tile_width + self.tile_width//2,
                                      yi*self.tile_height + self.tile_height//2))

                p.init_images = [fixed_image]
                p.image_mask = mask
                processed = await process_images(p)
                if (len(processed.images) > 0):
                    fixed_image = processed.images[0]

        p.width = fixed_image.width
        p.height = fixed_image.height
        if processed is not None:
            self.initial_info = processed.infotext(p, 0)

        return fixed_image

    async def band_pass_process(self, p, image, cols, rows):
        state = p.shared.state

        self.init_draw(p)
        processed = None

        p.denoising_strength = self.denoise
        p.mask_blur = 0

        gradient = Image.linear_gradient("L")
        mirror_gradient = Image.new("L", (256, 256), "black")
        mirror_gradient.paste(gradient.resize((256, 128), resample=Image.BICUBIC), (0, 0))
        mirror_gradient.paste(gradient.rotate(180).resize((256, 128), resample=Image.BICUBIC), (0, 128))

        row_gradient = mirror_gradient.resize((image.width, self.width), resample=Image.BICUBIC)
        col_gradient = mirror_gradient.rotate(90).resize((self.width, image.height), resample=Image.BICUBIC)

        for xi in range(1, rows):
            if state.interrupted:
                    break
            p.width = self.width + self.padding * 2
            p.height = image.height
            p.inpaint_full_res = True
            p.inpaint_full_res_padding = self.padding
            mask = Image.new("L", (image.width, image.height), "black")
            mask.paste(col_gradient, (xi * self.tile_width - self.width // 2, 0))

            p.init_images = [image]
            p.image_mask = mask
            processed = await process_images(p)
            if (len(processed.images) > 0):
                image = processed.images[0]
        for yi in range(1, cols):
            if state.interrupted:
                    break
            p.width = image.width
            p.height = self.width + self.padding * 2
            p.inpaint_full_res = True
            p.inpaint_full_res_padding = self.padding
            mask = Image.new("L", (image.width, image.height), "black")
            mask.paste(row_gradient, (0, yi * self.tile_height - self.width // 2))

            p.init_images = [image]
            p.image_mask = mask
            processed = await process_images(p)
            if (len(processed.images) > 0):
                image = processed.images[0]

        p.width = image.width
        p.height = image.height
        if processed is not None:
            self.initial_info = processed.infotext(p, 0)

        return image

    async def start(self, p, image, rows, cols):
        if USDUSFMode(self.mode) == USDUSFMode.BAND_PASS:
            return await self.band_pass_process(p, image, rows, cols)
        elif USDUSFMode(self.mode) == USDUSFMode.HALF_TILE:
            return await self.half_tile_process(p, image, rows, cols)
        elif USDUSFMode(self.mode) == USDUSFMode.HALF_TILE_PLUS_INTERSECTIONS:
            return await self.half_tile_process_corners(p, image, rows, cols)
        else:
            return image


async def script_run(p, _, tile_width, tile_height, mask_blur, padding, seams_fix_width, seams_fix_denoise, seams_fix_padding,
                     upscaler_index, save_upscaled_image, redraw_mode, save_seams_fix_image, seams_fix_mask_blur,
                     seams_fix_type, target_size_type, custom_width, custom_height, custom_scale):
    """usdu_patch.py:112-164 (patched_script_run, which replaces Script.run)."""
    preserved_batch_size = getattr(p, 'batch_size', 1)

    # Init (matching original code)
    fix_seed(p)

    # Keep original file-saving flags as in original code
    p.do_not_save_grid = True
    p.do_not_save_samples = True
    p.inpaint_full_res = False

    p.inpainting_fill = 1
    p.n_iter = 1
    p.batch_size = preserved_batch_size

    seed = p.seed

    # Init image
    init_img = p.init_images[0]
    if init_img is None:
        return Processed(p, [], seed, "Empty image")
    init_img = flatten(init_img, p.shared.opts.img2img_background_color)

    # Override size by user choice
    if target_size_type == 1:
        p.width = custom_width
        p.height = custom_height
    elif target_size_type == 2:
        p.width = math.ceil((init_img.width * custom_scale) / 64) * 64
        p.height = math.ceil((init_img.height * custom_scale) / 64) * 64

    # Create and run upscaler
    upscaler = USDUpscaler(p, init_img, upscaler_index, save_upscaled_image, save_seams_fix_image, tile_width, tile_height)
    await upscaler.upscale()

    # Drawing & seams fix setup
    upscaler.setup_redraw(redraw_mode, padding, mask_blur)
    upscaler.setup_seams_fix(seams_fix_padding, seams_fix_denoise, seams_fix_mask_blur, seams_fix_width, seams_fix_type)
    upscaler.print_info()
    upscaler.add_extra_info()
    await upscaler.process()
    result_images = upscaler.result_images

    return Processed(p, result_images, seed, upscaler.initial_info or "")


# --------------------------------------------------------------------------- #
# usdu_nodes.py
# --------------------------------------------------------------------------- #
# The modes available for Ultimate SD Upscale
MODES = {
    "Linear": USDUMode.LINEAR,
    "Chess": USDUMode.CHESS,
    "None": USDUMode.NONE,
}
# The seam fix modes
SEAM_FIX_MODES = {
    "None": USDUSFMode.NONE,
    "Band Pass": USDUSFMode.BAND_PASS,
    "Half Tile": USDUSFMode.HALF_TILE,
    "Half Tile + Intersections": USDUSFMode.HALF_TILE_PLUS_INTERSECTIONS,
}


async def _upscale_images(image, model, positive, negative, vae, upscale_by, seed,
                          steps, cfg, sampler_name, scheduler, denoise, upscale_model,
                          mode_type, tile_width, tile_height, mask_blur, tile_padding,
                          seam_fix_mode, seam_fix_denoise, seam_fix_mask_blur,
                          seam_fix_width, seam_fix_padding, force_uniform_tiles, tiled_decode, batch_size=1,
                          custom_sampler=None, custom_sigmas=None, guider=None):
    """usdu_nodes.py:122-174 (UltimateSDUpscale.upscale) and :282-324 (the guider node)."""
    redraw_mode = MODES[mode_type]
    seam_fix_mode = SEAM_FIX_MODES[seam_fix_mode]

    #
    # Set up A1111 patches
    #
    shared = Shared()

    # Upscaler
    # An object that the script works with
    shared.sd_upscalers[0] = UpscalerData(shared)
    # Where the actual upscaler is stored, will be used when the script upscales using the Upscaler in UpscalerData
    shared.actual_upscaler = upscale_model

    # Set the batch of images
    pixels = torch.as_tensor(await image.raw())
    if pixels.ndim == 4 and int(pixels.shape[0] * pixels.shape[1] * pixels.shape[2]) > _MAX_PIXELS:
        raise ValueError("Ultimate SD Upscale input exceeds the pixel limit")
    shared.batch = [tensor_to_pil(pixels, i) for i in range(len(pixels))]
    # The model upscale runs host-side on the node's original IMAGE.
    shared.batch_as_tensor = image

    assert batch_size == 1 or force_uniform_tiles, "batch_size greater than 1 requires force_uniform_tiles to be True; all tiles in the batch must be the same size."

    # Processing
    sdprocessing = StableDiffusionProcessing(
        shared, shared.batch[0], model, positive, negative, vae,
        seed, steps, cfg, sampler_name, scheduler, denoise, upscale_by, force_uniform_tiles, tiled_decode,
        tile_width, tile_height, redraw_mode, seam_fix_mode,
        custom_sampler, custom_sigmas, batch_size,
        guider=guider,
    )

    #
    # Running the script
    #
    await script_run(p=sdprocessing, _=None, tile_width=tile_width, tile_height=tile_height,
                     mask_blur=mask_blur, padding=tile_padding, seams_fix_width=seam_fix_width,
                     seams_fix_denoise=seam_fix_denoise, seams_fix_padding=seam_fix_padding,
                     upscaler_index=0, save_upscaled_image=False, redraw_mode=redraw_mode,
                     save_seams_fix_image=False, seams_fix_mask_blur=seam_fix_mask_blur,
                     seams_fix_type=seam_fix_mode, target_size_type=2,
                     custom_width=None, custom_height=None, custom_scale=upscale_by)

    # Return the resulting images
    images = [pil_to_tensor(img) for img in shared.batch]
    tensor = torch.cat(images, dim=0)
    return await _image_ref(tensor)


async def _upscale(**kwargs: Any):
    return (await _upscale_images(**kwargs),)


async def _no_upscale(upscaled_image: Any, **kwargs: Any):
    # usdu_nodes.py:191-204
    upscale_by = 1.0
    return (await _upscale_images(
        image=upscaled_image, upscale_by=upscale_by, upscale_model=None, **kwargs),)


async def _custom(upscale_model: Any = None, custom_sampler: Any = None,
                  custom_sigmas: Any = None, **kwargs: Any):
    # usdu_nodes.py:222-234
    return (await _upscale_images(
        upscale_model=upscale_model, custom_sampler=custom_sampler,
        custom_sigmas=custom_sigmas, **kwargs),)


async def _guider(image: Any, guider: Any, sampler: Any, sigmas: Any, vae: Any,
                  upscale_by: Any, seed: Any, upscale_model: Any, **kwargs: Any):
    # usdu_nodes.py:282-324: StableDiffusionProcessing(shared.batch[0], None,
    # None, None, vae, seed, 0, 0, None, None, 0, upscale_by, ...,
    # custom_sampler=sampler, custom_sigmas=sigmas, guider=guider)
    return (await _upscale_images(
        image=image, model=None, positive=None, negative=None, vae=vae,
        upscale_by=upscale_by, seed=seed, steps=0, cfg=0, sampler_name=None,
        scheduler=None, denoise=0, upscale_model=upscale_model,
        custom_sampler=sampler, custom_sigmas=sigmas, guider=guider,
        **kwargs),)


NODE_CLASS_MAPPINGS = {
    "UltimateSDUpscale": bind_node(
        "UltimateSDUpscale", _upscale, permissions=("raw", "sample")),
    "UltimateSDUpscaleNoUpscale": bind_node(
        "UltimateSDUpscaleNoUpscale", _no_upscale,
        permissions=("raw", "sample")),
    "UltimateSDUpscaleCustomSample": bind_node(
        "UltimateSDUpscaleCustomSample", _custom,
        permissions=("raw", "sample")),
    "UltimateSDUpscaleGuider": bind_node(
        "UltimateSDUpscaleGuider", _guider,
        permissions=("raw", "sample")),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UltimateSDUpscale": "Ultimate SD Upscale",
    "UltimateSDUpscaleNoUpscale": "Ultimate SD Upscale (No Upscale)",
    "UltimateSDUpscaleCustomSample": "Ultimate SD Upscale (Custom Sample)",
    "UltimateSDUpscaleGuider": "Ultimate SD Upscale (Guider)",
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SCHEMAS"]
