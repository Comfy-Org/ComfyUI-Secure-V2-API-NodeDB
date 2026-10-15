"""Managed output body using explicit metadata, not execution-global capture.

Recipe persistence, automatic ancestry and full user-node wiring stay pending.
"""
from __future__ import annotations

import json
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

from comfy_api.latest import sdk

from .image_factory import require_image_value_factory

from ..secure_algorithms.image_save_parameters import image_parameters
from ..secure_algorithms.image_filename import image_filename
from ..secure_algorithms.image_output_options import image_output_options
from ..secure_algorithms.image_conversion import normalize_native_images, native_frame_image


async def save_image_body(images, *, filename_prefix='ComfyUI', file_format='png', metadata=None,
                          resources=None, workflow=None, lossless_webp=True, quality=100,
                          webp_method=6, jpeg_subsampling=0, embed_workflow=False,
                          save_with_metadata=True, add_counter_to_filename=True,
                          add_loras_to_prompt=False, save_as_recipe=False):
    # Even metadata-disabled legacy saves format the captured dictionary first.
    # Explicit data here is NOT a replacement for the missing provenance owner.
    parameters = image_parameters({} if metadata is None else metadata, resources,
                                  add_loras_to_prompt=add_loras_to_prompt)
    filename_prefix = image_filename(filename_prefix, metadata)
    raw = await images.raw()
    # Raw is already required by native conversion. Derive structural values
    # from that same actual image, without adding an inspect capability.
    physical_shape = getattr(raw, 'shape', None)
    shape = list(physical_shape) if physical_shape is not None else None
    if (shape is None or len(shape) not in (3, 4)
            or any(type(axis) is not int or axis < 1 for axis in shape)):
        raise ValueError('Image save requires a valid HWC/BHWC structural image')
    batch, height, width, channels = [1, *shape] if len(shape) == 3 else shape
    # The canonical writer detaches tensors and squeezes one-channel frames.
    # Native converts before its save-time catch. Preserve those conversion
    # errors through genuine raw access, including grad/bfloat/gray precedence.
    # Actual raw helper tests are retained; native gradient parity remains held.
    first_frame = normalize_native_images(raw)[0]
    native_frame_image(first_frame)
    # These remaining typed/profile guards are explicit source holds, applied
    # after native formatting and first-frame construction, never before them.
    if file_format not in ('png','jpeg','webp'):
        raise ValueError('Unsupported file format: ' + str(file_format))
    for flag in (save_with_metadata,add_counter_to_filename,add_loras_to_prompt,save_as_recipe):
        if type(flag) is not bool:
            raise ValueError('Image save flags must be Boolean')
    # Native ignores options belonging to other encoder branches. Keep active
    # public profiles explicit without making ignored options new PNG failures.
    if file_format == 'webp' and type(lossless_webp) is not bool:
        raise ValueError('Image save flags must be Boolean')
    if file_format in ('png','webp') and type(embed_workflow) is not bool:
        raise ValueError('Image save flags must be Boolean')
    if file_format in ('jpeg','webp') and (type(quality) is not int or not 1 <= quality <= 100):
        raise ValueError('Image quality exceeds bounds')
    if file_format == 'webp' and (type(webp_method) is not int or not 0 <= webp_method <= 6):
        raise ValueError('WebP method exceeds bounds')
    if file_format == 'jpeg' and (type(jpeg_subsampling) is not int or not 0 <= jpeg_subsampling <= 2):
        raise ValueError('JPEG subsampling exceeds bounds')
    if file_format == 'jpeg' and channels in (2, 4):
        # Pillow rejects native LA/RGBA JPEG writes inside the per-frame
        # catch. Run that same failure on a guest-owned memory stream;
        # the public writer would convert to RGB and invent saved outputs.
        # No output authority or normalization factory is needed for a
        # native write which fails before producing a saved-image UI row.
        for frame in normalize_native_images(raw):
            image = native_frame_image(frame)
            try:
                with BytesIO() as stream:
                    image.save(stream, format='JPEG', quality=quality,
                               optimize=True, subsampling=jpeg_subsampling)
            except Exception as error:
                logger.error(f'Error saving image: {error}')
            else:
                raise NotImplementedError('Native alpha JPEG encoder unexpectedly accepted this mode')
        return {'images': []}
    if file_format == 'png':
        # The public explicit-text boundary writes precisely these native PNG
        # chunks even when Core automatic metadata is disabled. It supplies
        # no prompt or workflow that the actual owning snapshot did not carry.
        png_text = {}
        if save_with_metadata and parameters:
            png_text['parameters'] = parameters
        if embed_workflow and workflow is not None:
            try:
                png_text['workflow'] = json.dumps(workflow['workflow'])
            except Exception as error:
                # Original PNG builds/serializes workflow inside the save-time
                # per-frame catch. Preserve its empty saved UI and error logs.
                for frame in normalize_native_images(raw):
                    native_frame_image(frame)
                    logger.error(f'Error saving image: {error}')
                return {'images': []}
    webp_exif_failed = False
    if file_format == 'webp':
        try:
            # Native builds UserComment before workflow EXIF. Preserve that
            # encoding/error order on the actual captured parameter string.
            if save_with_metadata and parameters:
                parameters.encode('utf-16be')
            if embed_workflow and workflow is not None:
                json.dumps(workflow['workflow'])
        except Exception as error:
            # Native catches EXIF construction separately from image saving.
            # Its failed construction sets no EXIF bytes, even if it already
            # assembled UserComment. The public writer must omit those too.
            for frame in normalize_native_images(raw):
                native_frame_image(frame)
                logger.error(f'Error adding EXIF data: {error}')
            webp_exif_failed = True
    writer_images = images
    if len(shape) == 3:
        # Native wraps Torch HWC; the public writer accepts BHWC. Unsqueezing
        # retains tensor storage and leaves the returned original IMAGE alone.
        factory = require_image_value_factory()
        writer_images = await factory(raw.unsqueeze(0))
    if save_as_recipe:
        raise NotImplementedError('Authored recipe owner and persistence remain pending')
    if (embed_workflow and file_format == 'webp' and workflow is not None
            and not webp_exif_failed):
        raise NotImplementedError('Native WebP workflow EXIF representation remains pending')
    if channels == 2 and file_format != 'png':
        raise NotImplementedError('Native LA non-PNG image saving remains pending')
    options = image_output_options(file_format, parameters=parameters,
        quality=quality, lossless_webp=lossless_webp,
        jpeg_subsampling=jpeg_subsampling, webp_method=webp_method,
        save_with_metadata=save_with_metadata,
        add_counter_to_filename=add_counter_to_filename)
    if file_format == 'webp' and webp_exif_failed:
        options['a1111_parameters'] = None
    if file_format == 'png':
        options.pop('a1111_parameters')
        options['png_text'] = png_text
    return await sdk.ctx().output.save_images(writer_images, filename_prefix=filename_prefix, **options)
