"""Lora Info routes: the original's notes, description and save calls, over read-only assets and pack storage.

Original (ComfyUI-Lora-Manager 2dcaf6a):
- GET  /api/lm/loras/get-notes?name=   handler model_handlers.py:1414, lookup base_model_service.py:1049
- GET  /api/lm/loras/metadata?file_path= handler model_handlers.py:1530, base_model_service.py:1181 + filter_civitai_data
- POST /api/lm/loras/save-metadata     handler model_handlers.py:932 (the widget sends {file_path, notes})
- sidecars: utils/metadata_manager.py:27 load_metadata, utils/models.py BaseModelMetadata.from_dict

Platform replacements (deliberate differences, recorded in SECURE_CONVERSION.md):
- The LoRA is named by its logical catalogue name; no host path is accepted or returned.
- Sidecars are read through read-only assets in the default 'alongside' layout. Nothing is written to model folders:
  saved notes go to a pack-owned storage record, which is shown in place of the sidecar notes when it exists.
- The description response carries only the fields the widget reads (description, model.description).
"""
from __future__ import annotations

import hashlib
import json
import posixpath

from comfy_api.latest import sdk

from .managed_library import _logical

FOLDER = 'loras'
# The original LoRA scanner caches '.safetensors' files only (services/lora_scanner.py:19), matched in any case
# (model_scanner.py:414), and skips hidden folders (model_scanner.py:410).
LORA_EXTENSIONS = ('.safetensors',)
SIDECAR_SUFFIX = '.metadata.json'
SIDECAR_READ_MAX = 16 * 1024 * 1024        # one assets.read_range
REQUEST_BODY_MAX = 1024 * 1024             # the host's route request bound
NOTES_KEY_PREFIX = 'lora_info.notes.'      # + sha256(logical name): at most 80 bytes (storage keys <= 128)
NOTES_FORMAT = 'loramanager.lora-info-notes.v1'
NOTES_VALUE_MAX = 1024 * 1024              # host PackStorage value bound
# BaseModelMetadata fields without a default: from_dict raises without them, load_metadata returns
# (None, should_skip=True) and the scanner leaves the model out of its cache (metadata_manager.py:54-57).
REQUIRED_FIELDS = ('file_name', 'model_name', 'file_path', 'size', 'modified', 'sha256', 'base_model', 'preview_url')


def _json(status, data):
    return {'status': status, 'content_type': 'application/json',
            'body': json.dumps(data, ensure_ascii=False, allow_nan=False)}


def _text(status, text):
    return {'status': status, 'content_type': 'text/plain', 'body': text}


def _request(request, method):
    if (type(request) is not dict or set(request) != {'method', 'path', 'query', 'body'}
            or str(request['method']).upper() != method or type(request['query']) is not dict
            or type(request['body']) is not str):
        raise ValueError('invalid route request')
    return request['query']


def _model_extension(name):
    lowered = name.lower()
    return next((extension for extension in LORA_EXTENSIONS if lowered.endswith(extension)), None)


def _hidden(name):
    return any(part.startswith('.') for part in name.split('/')[:-1])


def _stem(name):
    extension = _model_extension(name)
    return name[:-len(extension)] if extension else name


def _is_logical(name):
    try:
        _logical(name)
        return True
    except ValueError:
        return False


async def _existing(file):
    """A confined logical file present in the LoRA folders.

    The original's description and save calls take any model path (no cache, no extension check); here the file is
    named logically and must be inside the 'loras' roots.
    """
    return type(file) is str and _is_logical(file) and await sdk.ctx().assets.exists(FOLDER, file)


async def find_lora(name):
    """The logical name of the LoRA the original's get_model_notes would match, or None.

    The original walks its scanner cache and takes the first model whose file_name (the stem) equals the name, or
    that the name ends with after '/' or '\\'. Here: the exact relative path first, then the first match in sorted
    catalogue order (the original's cache order is not reproducible; see the recorded difference).
    """
    if _is_logical(name) and not _hidden(name):
        for extension in LORA_EXTENSIONS:
            candidate = name + extension
            if await sdk.ctx().assets.exists(FOLDER, candidate):
                return candidate
    for candidate in await sdk.ctx().assets.list(FOLDER):
        if not _model_extension(candidate) or _hidden(candidate):
            continue
        file_name = _stem(candidate).rsplit('/', 1)[-1]
        if file_name == name or name.endswith('/' + file_name) or name.endswith('\\' + file_name):
            return candidate
    return None


async def read_sidecar(logical):
    """('absent'|'corrupt'|'ok', mapping|None) for the LoRA's alongside sidecar, as load_metadata decides it."""
    sidecar = posixpath.splitext(logical)[0] + SIDECAR_SUFFIX  # get_metadata_path: splitext of the model file
    if not await sdk.ctx().assets.exists(FOLDER, sidecar):
        return 'absent', None
    ref = await sdk.ctx().assets.resolve(FOLDER, sidecar)
    size = await sdk.ctx().assets.size(ref)
    if size > SIDECAR_READ_MAX:
        raise ValueError(f'sidecar metadata exceeds {SIDECAR_READ_MAX} bytes')
    data = await sdk.ctx().assets.read_range(ref, 0, size) if size else b''
    try:
        document = json.loads(bytes(data).decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return 'corrupt', None
    if type(document) is not dict or any(field not in document for field in REQUIRED_FIELDS):
        return 'corrupt', None
    return 'ok', document


def notes_key(logical):
    return NOTES_KEY_PREFIX + hashlib.sha256(logical.encode('utf-8')).hexdigest()


async def read_saved_notes(logical):
    """The pack-owned record's notes for this logical name, or None when no record exists."""
    value = await sdk.ctx().storage.get(notes_key(logical))
    if value is None:
        return None
    record = json.loads(value)
    if (type(record) is not dict or set(record) != {'format', 'name', 'notes'} or record['format'] != NOTES_FORMAT
            or record['name'] != logical or type(record['notes']) is not str):
        raise ValueError('corrupt Lora Info notes record')
    return record['notes']


async def get_notes(request):
    """GET get-notes?name=: {success, notes, file} like the original's {success, notes, file_path}."""
    query = _request(request, 'GET')
    name = query.get('name')
    if not name:
        return _text(400, 'Lora file name is required')
    logical = await find_lora(name)
    if logical is None:
        return _json(404, {'success': False, 'error': 'Lora not found in cache'})
    state, document = await read_sidecar(logical)
    # The original's scanner leaves out a model whose sidecar is corrupt (metadata_manager.py:54-57) or marked
    # 'exclude' (model_scanner.py:2654), so get-notes cannot find it.
    if state == 'corrupt' or (state == 'ok' and document.get('exclude', False)):
        return _json(404, {'success': False, 'error': 'Lora not found in cache'})
    saved = await read_saved_notes(logical)
    notes = saved if saved is not None else ('' if document is None else document.get('notes', ''))
    return _json(200, {'success': True, 'notes': notes, 'file': logical})


async def get_metadata(request):
    """GET metadata?file=: the description fields of the original's filtered CivitAI data."""
    query = _request(request, 'GET')
    file = query.get('file')
    if not file:
        return _text(400, 'File path is required')
    if not await _existing(file):
        return _json(404, {'success': False, 'error': 'Lora not found or no CivitAI metadata available'})
    state, document = await read_sidecar(file)
    if state != 'ok':
        return _json(404, {'success': False, 'error': 'Lora not found or no CivitAI metadata available'})
    civitai = document.get('civitai') or {}
    metadata = {}
    if type(civitai) is dict:
        if 'description' in civitai:
            metadata['description'] = civitai['description']
        model = civitai.get('model')
        if 'model' in civitai:
            metadata['model'] = {'description': model.get('description')} if type(model) is dict and 'description' in model else {}
    return _json(200, {'success': True, 'metadata': metadata})


async def save_notes(request):
    """POST save-metadata {file, notes}: notes go to the pack-owned record (last write wins, as the sidecar write)."""
    _request(request, 'POST')
    body = request['body']
    if len(body.encode('utf-8')) > REQUEST_BODY_MAX:
        return _text(413, 'request body is too large')
    try:
        data = json.loads(body)
    except ValueError:
        return _text(400, 'invalid JSON body')
    if type(data) is not dict:
        return _text(400, 'invalid JSON body')
    file = data.get('file')
    if not file:
        return _text(400, 'File path is required')
    if set(data) != {'file', 'notes'} or type(data['notes']) is not str:
        return _text(400, 'only {file, notes} with string notes can be saved')
    if not await _existing(file):
        return _text(500, f'Lora not found: {file}')
    value = json.dumps({'format': NOTES_FORMAT, 'name': file, 'notes': data['notes']}, ensure_ascii=False)
    if len(value.encode('utf-8')) > NOTES_VALUE_MAX:
        return _text(413, f'notes exceed the {NOTES_VALUE_MAX}-byte storage record limit')
    await sdk.ctx().storage.set(notes_key(file), value)
    return _json(200, {'success': True})
