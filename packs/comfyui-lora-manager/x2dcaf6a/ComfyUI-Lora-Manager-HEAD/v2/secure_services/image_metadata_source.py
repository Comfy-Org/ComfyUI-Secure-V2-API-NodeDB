"""Managed image-byte input boundary; full eighteen-output node still pending.

Decode only guest-owned BytesIO, never a path. Preserve the reviewed ordinary
PNG/JPEG/WebP/TIFF metadata precedence; AVIF/JXL Brotli containers stay pending.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from dataclasses import asdict

from PIL import Image
from comfy_api.latest import sdk

from ..secure_algorithms.generation_metadata import extract_generation_metadata
from ..secure_algorithms.bounds import bounded_json, MAX_STRING_BYTES
from .documents import _validate_tree, _preflight_json_depth
from .managed_library import _logical

MAX_ENCODED = 16 * 1024**2
MAX_PIXELS = 16777216
MAX_AXIS = 8192
FIELDS = {'parameters', 'prompt', 'workflow', 'comment'}


def _decode_user_comment(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value[8:].decode('utf-16be', errors='ignore') if value.startswith(b'UNICODE\0') else value.decode('utf-8', errors='ignore')
    return value if isinstance(value, str) else str(value)


def _decode_exif_text(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')
    return value if isinstance(value, str) else str(value)


def fields_from_bytes(data):
    # Imported at point of use so the node module (and its queue validator) load even
    # where the EXIF dependency is absent; decoding still requires it.
    import piexif
    if type(data) is not bytes or not 0 < len(data) <= MAX_ENCODED:
        raise ValueError('Encoded image metadata source exceeds bounds')
    metadata = dict.fromkeys(('parameters', 'prompt', 'workflow', 'comment'))
    with Image.open(BytesIO(data)) as image:
        if image.format not in ('PNG', 'JPEG', 'WEBP', 'TIFF'):
            raise NotImplementedError('Image container metadata branch is still pending')
        width, height = image.size
        if not 1 <= width <= MAX_AXIS or not 1 <= height <= MAX_AXIS or width * height > MAX_PIXELS:
            raise ValueError('Image geometry exceeds predecode bounds')
        if image.format == 'PNG':
            image.load()  # Text after IDAT is populated only after load.
        info = image.info or {}
        for key in ('parameters', 'prompt', 'workflow'):
            if key in info:
                metadata[key] = info[key]
        exif = image.getexif()
        if image.format not in ('JPEG', 'TIFF', 'WEBP') and exif and piexif.ExifIFD.UserComment in exif:
            metadata['comment'] = _decode_user_comment(exif[piexif.ExifIFD.UserComment])
        for tag in (piexif.ImageIFD.Make, piexif.ImageIFD.Model):
            text = _decode_exif_text(exif.get(tag))
            if text:
                for key in ('prompt', 'workflow'):
                    if text.startswith(key + ':') and not metadata[key]:
                        metadata[key] = text[len(key) + 1:].rstrip('\x00')
        try:
            exif_dict = piexif.load(data)  # Content-only equivalent, never filename.
        except Exception:
            exif_dict = {}
        exif_ifd = exif_dict.get('Exif')
        if exif_ifd and piexif.ExifIFD.UserComment in exif_ifd:
            metadata['comment'] = _decode_user_comment(exif_ifd[piexif.ExifIFD.UserComment])
        description = _decode_exif_text((exif_dict.get('0th') or {}).get(piexif.ImageIFD.ImageDescription))
        if description:
            if description.startswith('Workflow:'):
                metadata['workflow'] = description[len('Workflow:'):]
            elif not metadata['prompt']:
                metadata['prompt'] = description
        image_format = image.format
    if not metadata['parameters'] and metadata['comment']:
        metadata['parameters'] = metadata['comment']
    _validate_fields(metadata)
    return {'fields': metadata, 'format': image_format, 'width': width, 'height': height}


def _validate_fields(fields):
    if type(fields) is not dict or set(fields) != FIELDS:
        raise ValueError('Image metadata fields identity is invalid')
    for value in fields.values():
        if value is not None and (type(value) is not str or len(value.encode('utf-8')) > MAX_STRING_BYTES):
            raise ValueError('Image metadata field exceeds text bounds')
        if isinstance(value, str) and value.lstrip().startswith(('{', '[')):
            _preflight_json_depth(value)
    _validate_tree(fields, 4 * MAX_STRING_BYTES)


def extract_fields(fields, sampler_id='', prefer_saved_image_metadata=True):
    _validate_fields(fields)
    bounded_json([sampler_id, prefer_saved_image_metadata])
    # The entire pure interpreter module is byte-identical to pinned source.
    # Embedded graph data is never dispatched or executed.
    result = asdict(extract_generation_metadata(fields, sampler_id, prefer_saved_image_metadata))
    bounded_json(result, allow_tuples=True)
    return result


async def read_image_source(name, sampler_id='', prefer_saved_image_metadata=True, *, interpret=True):
    bounded_json([sampler_id, prefer_saved_image_metadata, interpret])
    if type(prefer_saved_image_metadata) is not bool or type(interpret) is not bool:
        raise ValueError('Image metadata selection flags must be Boolean')
    name = _logical(name)
    if name.lower().endswith(('.avif', '.jxl')):
        raise NotImplementedError('AVIF/JXL Brotli metadata branch is still pending')
    asset = await sdk.ctx().assets.resolve('input', name)
    size = await sdk.ctx().assets.size(asset)
    if type(size) is not int or not 0 < size <= MAX_ENCODED:
        raise ValueError('Encoded image metadata source exceeds bounds')
    digest = await sdk.ctx().assets.digest(asset)
    data = await sdk.ctx().assets.read_range(asset, 0, size)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Image source changed during managed read')
    source = fields_from_bytes(data)
    source.update({'name': name, 'sha256': digest, 'encoded_bytes': size})
    if interpret:
        source['extracted'] = extract_fields(source['fields'], sampler_id, prefer_saved_image_metadata)
    return source
