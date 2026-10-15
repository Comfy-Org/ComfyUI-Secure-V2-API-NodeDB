import asyncio
import importlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import types

import numpy as np
import pytest
import torch
from safetensors.torch import save

V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location('moe_gguf_bounds', V2 / '__init__.py', submodule_search_locations=[str(V2)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from moe_gguf_bounds.safetensor_preflight import validate_header, validate_header_length, unique_object, header_ranges, append_header_chunk, MAX_HEADER_BYTES
from moe_gguf_bounds.range_reader import RangeReader


def decode_header(data):
    length=struct.unpack('<Q',data[:8])[0]
    validate_header_length(len(data),length)
    buffer=bytearray()
    for offset,count in header_ranges(length):
        append_header_chunk(buffer,data[offset:offset+count],count)
    return validate_header(json.loads(buffer,object_pairs_hook=unique_object),len(data),length,4)


def test_safetensors_preflight_valid_scalars_empty_and_nonfinite():
    state = {'scalar': torch.tensor(1, dtype=torch.int64), 'empty': torch.empty(0, 2), 'nonfinite': torch.tensor([float('nan'), float('inf')])}
    data = save(state)
    header = decode_header(data)
    assert set(header) == set(state)


@pytest.mark.parametrize('failure', ['native_header_limit', 'shape', 'duplicate', 'offset', 'dtype'])
def test_safetensors_native_layout_denial_before_state_loader(failure):
    descriptor = {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}
    header = {'weights': descriptor}
    if failure == 'shape':
        descriptor['shape'] = [1 << 62]
    elif failure == 'offset':
        descriptor['data_offsets'] = [0, 9]
    elif failure == 'dtype':
        descriptor['dtype'] = 'EXECUTABLE'
    raw = json.dumps(header).encode()
    if failure == 'duplicate':
        raw = b'{"x":{},"x":{}}'
    data = struct.pack('<Q', len(raw)) + raw + b'\0' * 4
    if failure == 'native_header_limit':
        data = struct.pack('<Q', MAX_HEADER_BYTES + 1) + data[8:]
    with pytest.raises(ValueError):
        decode_header(data)


def string(value):
    value = value.encode()
    return struct.pack('<Q', len(value)) + value


def test_all_metadata_scalar_types_array_strings_and_memmap_repr_without_mapping(tmp_path, monkeypatch):
    fields = [
        ('u8', 0, struct.pack('<B', 255)), ('i8', 1, struct.pack('<b', -127)),
        ('u16', 2, struct.pack('<H', 65535)), ('i16', 3, struct.pack('<h', -32767)),
        ('u32', 4, struct.pack('<I', 123)), ('i32', 5, struct.pack('<i', -123)),
        ('f32', 6, struct.pack('<f', .25)), ('boolean', 7, struct.pack('<?', True)),
        ('u64', 10, struct.pack('<Q', 1 << 48)), ('i64', 11, struct.pack('<q', -(1 << 48))),
        ('f64', 12, struct.pack('<d', float('nan'))),
        ('utf8', 8, string('日本語 array(not replaced) memmap(no path) ' * 4)),
        ('strings', 9, struct.pack('<IQ', 8, 2) + string('a') + string('日本語')),
        ('empty', 9, struct.pack('<IQ', 4, 0)),
    ]
    data = b'GGUF' + struct.pack('<IQQ', 3, 0, len(fields)) + b''.join(string(name) + struct.pack('<I', tag) + raw for name, tag, raw in fields)
    data += b'\0' * ((-len(data)) % 32)
    path = tmp_path / 'metadata-only.gguf'
    path.write_bytes(data)
    root = types.ModuleType('moe_metadata_pristine')
    root.__path__ = [str(PACK / 'gguf_connector')]
    sys.modules[root.__name__] = root
    original = importlib.import_module(root.__name__ + '.reader').GGUFReader(path)
    expected = {key: str(field) for key, field in original.fields.items()}
    def fail_file_mapping(*args, **kwargs):
        pytest.fail('range parser/metadata rendering must not construct a memmap or open a path')
    monkeypatch.setattr(np.memmap, '__new__', fail_file_mapping)
    reader = asyncio.run(RangeReader.from_bytes(data).parse())
    assert reader.metadata() == expected
    for field in reader.reader_fields.values():
        for part in field.parts:
            mapped_label_only = part.view(np.memmap)
            assert mapped_label_only.filename is None and mapped_label_only._mmap is None
