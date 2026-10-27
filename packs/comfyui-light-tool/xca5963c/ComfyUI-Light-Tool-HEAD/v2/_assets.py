"""Managed asset and output boundaries for the original image codecs."""
import io
import json
import uuid
import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence
from PIL.PngImagePlugin import PngInfo
from itertools import islice
from comfy_api.latest import sdk


async def _bytes(name):
    ref = await sdk.ctx().assets.resolve('input', name)
    return await sdk.ctx().assets.read_bytes(ref)


async def load_image(image, keep_alpha_channel):
    img = Image.open(io.BytesIO(await _bytes(image)))
    output_images, output_masks = [], []
    w, h = None, None
    for i in ImageSequence.Iterator(img):
        i = ImageOps.exif_transpose(i)
        if i.mode == 'I':
            i = i.point(lambda pixel: pixel * (1 / 255))
        image = i.convert('RGBA' if 'A' in i.getbands() and keep_alpha_channel else 'RGB')
        if not output_images:
            w, h = image.size
        if image.size != (w, h):
            continue
        image = torch.from_numpy(np.array(image).astype(np.float32) / 255.0)[None, ]
        if 'A' in i.getbands():
            mask = 1. - torch.from_numpy(np.array(i.getchannel('A')).astype(np.float32) / 255.0)
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device='cpu')
        output_images.append(image)
        output_masks.append(mask.unsqueeze(0))
    if len(output_images) > 1 and img.format not in ['MPO']:
        return torch.cat(output_images, dim=0), torch.cat(output_masks, dim=0)
    return output_images[0], output_masks[0]


async def load_images(directory, image_load_num=0, start_index=0, keep_alpha_channel=False, load_always=False):
    # The directory widget now names an input-catalogue prefix, never a host path.
    if directory.startswith(('/', '\\')) or '\\' in directory or ':' in directory or '..' in directory.split('/'):
        raise ValueError('Select a relative managed input catalogue prefix')
    prefix = directory.rstrip('/')
    prefix = prefix + '/' if prefix else ''
    names = await sdk.ctx().assets.list('input', prefix=prefix, recursive=False)
    if not names:
        raise FileNotFoundError(f"No files in managed input prefix '{directory}'.")
    names = sorted(n for n in names if n.lower().endswith(('.jpg','.jpeg','.png','.webp')))
    names = list(islice(names, start_index, None if image_load_num == 0 else start_index + image_load_num))
    images, masks = [], []
    for name in names:
        with Image.open(io.BytesIO(await _bytes(name))) as original:
            i = ImageOps.exif_transpose(original)
            image = i.convert('RGBA' if 'A' in i.getbands() and keep_alpha_channel else 'RGB')
            images.append(torch.from_numpy(np.array(image).astype(np.float32) / 255.0)[None, ])
            if 'A' in i.getbands():
                mask = 1. - torch.from_numpy(np.array(i.getchannel('A')).astype(np.float32) / 255.0)
            else:
                mask = torch.zeros((64,64), dtype=torch.float32)
            masks.append(mask)
    return images, masks, names


async def save_metadata(image, metadata):
    try:
        # Match the original single-PIL-image quantization and failure on multi-image tensors.
        image = Image.fromarray(np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))
        metadata_dict = json.loads(metadata)
        # Original condition `if "prompt" or "workflow" in metadata_dict` is always true.
        # Preserve original PngInfo.add_text validation before drawing the UUID.
        original_metadata = PngInfo()
        png_text = {}
        for key, value in metadata_dict.items():
            value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            original_metadata.add_text(key, value)
            png_text[key] = value
        filename = str(uuid.uuid4()) + '.png'
        encoded_pixels = np.array(image).astype(np.float32) / 255.0
        if encoded_pixels.ndim == 2:
            # Codec input to save_images is BHWC, including native PIL L images.
            # This node has no IMAGE data output; no native dataflow tensor is reshaped.
            encoded_pixels = encoded_pixels[..., None]
        pixels = torch.from_numpy(encoded_pixels).unsqueeze(0)
        ref = await sdk.ImageRef.from_value(pixels)
        result = await sdk.ctx().output.save_images(ref, filenames=[filename], compress_level=6,
            save_metadata=False, png_text=png_text, overwrite=True)
        return {'ui': result}
    except Exception as e:
        raise Exception(f'SaveMetadata(Light-Tool): Failed to save metadata to image, {e}')
