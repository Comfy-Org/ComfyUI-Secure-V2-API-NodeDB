"""Bounded managed-byte image decode, pinned to core 6257422 LoadImage.

This ports only the image frame conversion from VideoFromFile, followed by
LoadImage's animated-WebP Pillow fallback. No paths, audio, video selectors,
Comfy internals, or model operations enter this module.
"""
from io import BytesIO
import hashlib

from comfy_api.latest import sdk
from .image_metadata_source import MAX_AXIS, MAX_ENCODED, MAX_PIXELS

MAX_FRAMES = 256
FORMATS = ('PNG', 'JPEG', 'WEBP', 'TIFF', 'GIF', 'AVIF')


def _geometry(width, height, frames=1):
    if not (1 <= width <= MAX_AXIS and 1 <= height <= MAX_AXIS
            and 1 <= frames <= MAX_FRAMES and width * height * frames <= MAX_PIXELS):
        raise ValueError('Image batch exceeds managed decode bounds')


def decode_pixels(data):
    """Return CPU BHWC RGB and BHW inverted alpha with core's precision.

    Bounds apply to the complete batch. Crossing a bound raises rather than
    silently returning a prefix of an animation.
    """
    import av
    import numpy as np
    import torch
    from PIL import Image, ImageOps, ImageSequence

    if type(data) is not bytes or not 0 < len(data) <= MAX_ENCODED:
        raise ValueError('Encoded image exceeds managed decode bounds')
    with Image.open(BytesIO(data)) as header:
        if header.format not in FORMATS:
            raise NotImplementedError('Image container pixel branch is still pending')
        _geometry(*header.size)

    frames, alphas = [], None
    decoded_pixels = 0
    image_format, integer_format, align_graph = None, False, None
    with av.open(BytesIO(data), mode='r') as container:
        stream = next((item for item in container.streams if item.type == 'video'), None)
        if stream is None:
            raise ValueError('Managed image has no decodable image stream')
        # Animated WebP has an undecoded 0x0 AV stream. Its Pillow header
        # was checked above; validate real frame dimensions if AV yields any.
        if stream.width > 0 and stream.height > 0:
            _geometry(stream.width, stream.height)
        stream.thread_type = 'AUTO'
        for packet in container.demux(stream):
            try:
                for frame in packet.decode():
                    if frame.pts < 0:
                        continue
                    _geometry(frame.width, frame.height, len(frames) + 1)
                    decoded_pixels += frame.width * frame.height
                    if decoded_pixels > MAX_PIXELS:
                        raise ValueError('Image batch exceeds managed decode bounds')
                    if image_format is None:
                        has_alpha = any(component.is_alpha or frame.format.name == 'pal8'
                                        for component in frame.format.components)
                        alphas = [] if has_alpha else None
                        integer_format = frame.format.name in (
                            'yuvj420p', 'yuvj422p', 'yuvj444p', 'rgb24', 'rgba', 'pal8')
                        image_format = (('rgba' if has_alpha else 'rgb24') if integer_format
                                        else ('gbrapf32le' if has_alpha else 'gbrpf32le'))
                    # Match the pinned core's deterministic swscale alignment.
                    if image_format in ('gbrpf32le', 'gbrapf32le') and frame.width % 32:
                        if align_graph is None:
                            pad_w = ((frame.width + 31) // 32) * 32
                            pad_h = ((frame.height + 31) // 32) * 32
                            graph = av.filter.Graph()
                            source = graph.add_buffer(width=frame.width, height=frame.height,
                                                      format=frame.format.name, time_base=stream.time_base)
                            pad = graph.add('pad', f'{pad_w}:{pad_h}:0:0')
                            fill = graph.add('fillborders',
                                f'left=0:right={pad_w-frame.width}:top=0:bottom={pad_h-frame.height}:mode=smear')
                            sink = graph.add('buffersink')
                            source.link_to(pad)
                            pad.link_to(fill)
                            fill.link_to(sink)
                            graph.configure()
                            align_graph = (graph, source, sink)
                        align_graph[1].push(frame)
                        array = np.ascontiguousarray(align_graph[2].pull().to_ndarray(
                            format=image_format)[:frame.height, :frame.width])
                    else:
                        array = frame.to_ndarray(format=image_format)
                    rotation = int(round(frame.rotation // 90)) % 4 if frame.rotation else 0
                    if rotation:
                        array = np.rot90(array, k=rotation, axes=(0, 1)).copy()
                    frames.append(torch.from_numpy(array if alphas is None else array[..., :-1]))
                    if alphas is not None:
                        alphas.append(torch.from_numpy(array[..., -1:]))
            except av.error.InvalidDataError:
                # Pinned core skips invalid packets, including all packets of an
                # animated WebP, then uses Pillow when no frame was decoded.
                continue
    if frames:
        images = torch.stack(frames)
        if integer_format:
            images = images.float() / 255.0
        if alphas is None:
            masks = torch.zeros((len(frames), 64, 64), dtype=torch.float32)
        else:
            alpha = torch.stack(alphas)
            if integer_format:
                alpha = alpha.float() / 255.0
            masks = 1.0 - alpha[..., -1]
        return images, masks

    # Pinned LoadImage's fallback for animated WebP only when PyAV yielded no
    # frames. It skips differently sized pages and respects EXIF orientation.
    masks = []
    first_size = None
    with Image.open(BytesIO(data)) as source:
        for index, page in enumerate(ImageSequence.Iterator(source)):
            if index >= MAX_FRAMES:
                raise ValueError('Image batch exceeds managed decode bounds')
            _geometry(*page.size)
            page = ImageOps.exif_transpose(page)
            rgb = page.convert('RGB')
            if first_size is None:
                first_size = rgb.size
            if rgb.size != first_size:
                continue
            _geometry(*rgb.size, len(frames) + 1)
            frames.append(torch.from_numpy(np.array(rgb).astype(np.float32) / 255.0))
            if 'A' in page.getbands():
                alpha = np.array(page.getchannel('A')).astype(np.float32) / 255.0
                masks.append(1.0 - torch.from_numpy(alpha))
            else:
                masks.append(torch.zeros((64, 64), dtype=torch.float32))
    if not frames:
        raise ValueError('Managed image has no decodable frames')
    return torch.stack(frames), torch.stack(masks)


async def load_managed_pixels(asset, expected_digest):
    size = await sdk.ctx().assets.size(asset)
    if type(size) is not int or not 0 < size <= MAX_ENCODED:
        raise ValueError('Encoded image exceeds managed decode bounds')
    data = await sdk.ctx().assets.read_range(asset, 0, size)
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError('Image source changed during managed decoding')
    pixels, mask = decode_pixels(data)
    return await sdk.ImageRef.from_value(pixels), await sdk.MaskRef._from_raw(mask)
