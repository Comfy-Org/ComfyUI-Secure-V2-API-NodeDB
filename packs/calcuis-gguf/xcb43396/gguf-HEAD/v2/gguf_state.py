"""calcuis load_gguf_sd + load_gguf_clip semantics for VAE/audio GGUFs, as a guest-built table for the host-owned
GGUF storage views (sdk assets.gguf_tensor_state). Parsing and name rules stay here; payload bytes never cross
the guest, and no host path is exposed.

Mirrors pinned pig.py (cb433968):
- load_gguf_sd: 'model.diffusion_model.' prefix kept/stripped only when any tensor carries it; general.architecture
  (absent -> PIG_ARCH_LIST[0]; unknown -> ValueError); comfy.gguf.orig_shape.<name> (ARRAY of INT32) else reversed
  dims, with the sdxl proj_in/proj_out trailing-1 squeeze; F32/F16 viewed to shape, BF16 non-2-D dequantized to F16
  and the rest wrapped (done host-side by the published tensor_state).
- load_gguf_clip: 'pig' (pig_work) and the final `else: pass` are identity. Branches that transform keys or tensor
  data (t5/llama family/gemma/ideogram/cat/cow) are outside the VAE/audio constructor scope and refuse explicitly.
"""
import json
from pathlib import Path

from .gguf_math.const import GGML_QUANT_SIZES, GGMLQuantizationType, GGUFValueType
from .range_reader import RangeReader

ARRAYS = json.loads(Path(__file__).with_name('version.json').read_text())[0]
PIG_ARCH_LIST = ARRAYS['PIG_ARCH_LIST']
TXT_ARCH_LIST = ARRAYS['TXT_ARCH_LIST']
HANDLE_PREFIX = 'model.diffusion_model.'
TRANSFORMING = frozenset({'t5', 't5encoder', 'llama', 'qwen2vl', 'qwen3vl', 'qwen2', 'qwen3', 'gemma3', 'mistral3', 'dog',
                          'gemma2', 'ideogram', 'ideogram4', 'cat', 'cow'})
TABLE_FORMAT = 'gguf-tensor-table/1'


class GGUFScopeError(RuntimeError):
    """Explicit calcuis branch outside this constructor's exact scope; never approximated."""


def _architecture(reader):
    field = reader.reader_fields.get('general.architecture')
    if field is None:
        return PIG_ARCH_LIST[0]  # pig.py: accept gguf without any metadata
    if field.types != [GGUFValueType.STRING]:
        raise TypeError('general.architecture must be a GGUF string')
    arch = field.contents()
    if arch not in PIG_ARCH_LIST and arch not in TXT_ARCH_LIST:
        raise ValueError(f'Unknown architecture: {arch!r}')
    return arch


def _orig_shape(reader, name):
    key = f'comfy.gguf.orig_shape.{name}'
    field = reader.reader_fields.get(key)
    if field is None:
        return None
    if len(field.types) != 2 or field.types[0] != GGUFValueType.ARRAY or field.types[1] != GGUFValueType.INT32:
        raise TypeError(f'Bad original shape metadata for {key}: Expected ARRAY of INT32, got {field.types}')
    return tuple(int(v) for v in field.contents())


def build_table(reader):
    """The exact load_gguf_sd key/shape/storage decisions for every selected tensor (requires a parsed reader)."""
    arch = _architecture(reader)
    if arch in TRANSFORMING:
        raise GGUFScopeError(f'calcuis {arch!r} GGUF applies text-encoder key/data transforms; outside the VAE/audio constructor scope')
    return arch, _table(_entries(reader, arch))


def build_diffusion_table(reader):
    """pig.py LoaderGGUF: load_gguf_sd only; no load_gguf_clip branch applies, so no architecture is refused here."""
    arch = _architecture(reader)
    return arch, _table(_entries(reader, arch))


def build_text_table(reader):
    """pig.py load_gguf_clip for the CLIP loaders: identity branches, plus the t5 branches that only rename keys.

    tensor_swap applies every (old, new) pair of the T5/B5 map with str.replace, in map order, and a later key
    that lands on an existing name replaces its value in place (dict semantics). Branches that synthesize
    tokenizers or change tensor data stay refused with their exact reason.
    """
    arch = _architecture(reader)
    entries = _entries(reader, arch)
    if arch in ('t5', 't5encoder'):
        token = next((entry['shape'] for entry in entries if entry['name'] == 'token_embd.weight'), None)
        if token in ([256384, 4096], [256384, 768]):
            raise GGUFScopeError(f'calcuis {arch!r} GGUF with a 256384-row token embedding synthesizes spiece_model from GGUF tokenizer metadata; not expressible as file byte ranges')
        key_map = ARRAYS['B5'] if token == [32128, 768] else ARRAYS['T5']
        renamed = {}
        for entry in entries:
            name = entry['name']
            for old, new in key_map.items():
                name = name.replace(old, new)
            renamed[name] = dict(entry, name=name)
        entries = list(renamed.values())
    elif arch in TRANSFORMING:
        raise GGUFScopeError(f'calcuis {arch!r} GGUF applies text-encoder data transforms (dequantization, permutation, norm offsets, tokenizer synthesis or paired files); not expressible as file byte ranges')
    return arch, _table(entries)


def _table(entries):
    return {'format': TABLE_FORMAT, 'byteorder': 'little', 'tensors': entries}


def gguf_metadata(reader):
    """pig.py get_gguf_metadata: single-typed STRING/INT32/F32/BOOL fields by reader key; others and failures skipped."""
    metadata = {}
    for field_name, field in reader.reader_fields.items():
        try:
            if len(field.types) == 1:
                if field.types[0] == GGUFValueType.STRING:
                    metadata[field_name] = str(field.parts[field.data[-1]], 'utf-8')
                elif field.types[0] == GGUFValueType.INT32:
                    metadata[field_name] = int(field.parts[field.data[-1]])
                elif field.types[0] == GGUFValueType.F32:
                    metadata[field_name] = float(field.parts[field.data[-1]])
                elif field.types[0] == GGUFValueType.BOOL:
                    metadata[field_name] = bool(field.parts[field.data[-1]])
        except Exception:  # pig.py: bare except -> continue
            continue
    return metadata


def _entries(reader, arch):
    has_prefix = any(desc.name.startswith(HANDLE_PREFIX) for desc in reader.tensors)
    entries = []
    for desc in reader.tensors:
        key = desc.name
        if has_prefix:
            if not key.startswith(HANDLE_PREFIX):
                continue
            key = key[len(HANDLE_PREFIX):]
        shape = _orig_shape(reader, desc.name)
        if shape is None:
            shape = tuple(desc.shape)  # RangeReader stores reversed GGUF dims (torch order)
            if arch == 'sdxl' and desc.name.endswith(('.proj_in.weight', '.proj_out.weight')):
                while len(shape) > 2 and shape[-1] == 1:
                    shape = shape[:-1]
        if desc.tensor_type in (GGMLQuantizationType.F32, GGMLQuantizationType.F16):
            storage = tuple(desc.shape)
        else:
            block, itemsize = GGML_QUANT_SIZES[desc.tensor_type]
            storage = (*desc.shape[:-1], desc.shape[-1] // block * itemsize)
        entries.append({'name': key, 'offset': reader.data_offset + desc.offset, 'tensor_type': int(desc.tensor_type),
                        'shape': list(shape), 'storage_shape': list(storage)})
    return entries


async def gguf_state(assets, asset):
    """Host-owned tensor state ref for a confined GGUF asset (its byte size bounds the mapping)."""
    size = await assets.size(asset)
    reader = await RangeReader(assets, asset, size).parse()
    _, table = build_table(reader)
    return await assets.gguf_tensor_state(asset, table, max_bytes=size)


async def gguf_diffusion_state(assets, asset):
    """LoaderGGUF: (state ref, scalar GGUF metadata) exactly as load_gguf_sd(..., is_extra=True) selects them."""
    size = await assets.size(asset)
    reader = await RangeReader(assets, asset, size).parse()
    _, table = build_diffusion_table(reader)
    return await assets.gguf_tensor_state(asset, table, max_bytes=size), gguf_metadata(reader)


async def gguf_text_state(assets, asset):
    """CLIP loaders: state ref for a GGUF text encoder (identity and rename-only load_gguf_clip branches)."""
    size = await assets.size(asset)
    reader = await RangeReader(assets, asset, size).parse()
    _, table = build_text_table(reader)
    return await assets.gguf_tensor_state(asset, table, max_bytes=size)


async def rechunk(parts, size=1024 * 1024):
    """Byte-exact re-chunking of a writer stream into 1..size non-empty pieces (save_binary's contract)."""
    buffer = bytearray()
    for part in parts:
        if part:
            buffer += part
            while len(buffer) >= size:
                yield bytes(buffer[:size])
                del buffer[:size]
    if buffer:
        yield bytes(buffer)
