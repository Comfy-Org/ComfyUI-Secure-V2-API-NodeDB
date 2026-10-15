"""Digest-bound audio SafeTensors through public, bounded asset reads.

No host path or full checkpoint copy is created. Verification reads the whole
asset in bounded ranges, then each requested tensor is materialized in the
caller's original parameter order and compared to its verified byte digest.
"""
import hashlib
import json
import math
import re
import struct

MAX_FILE_BYTES = 3 * 1024**3
MAX_HEADER_BYTES = 4 * 1024**2
MAX_TENSOR_BYTES = 128 * 1024**2
CHUNK_BYTES = 8 * 1024**2
DTYPES = {'F64': ('float64', 8), 'F32': ('float32', 4), 'F16': ('float16', 2),
    'BF16': ('bfloat16', 2), 'I64': ('int64', 8), 'I32': ('int32', 4),
    'I16': ('int16', 2), 'I8': ('int8', 1), 'U8': ('uint8', 1), 'BOOL': ('bool', 1),
    'F8_E4M3': ('float8_e4m3fn', 1), 'F8_E5M2': ('float8_e5m2', 1)}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate audio SafeTensors header key')
        result[key] = value
    return result


async def _read(assets, ref, offset, length):
    if type(offset) is not int or type(length) is not int or offset < 0 or not 0 < length <= CHUNK_BYTES:
        raise ValueError('Invalid bounded audio asset range')
    value = await assets.read_range(ref, offset=offset, length=length)
    if type(value) is not bytes or len(value) != length:
        raise ValueError('Audio SafeTensors range was truncated or not bytes')
    return value


def _header(raw, payload_bytes):
    header = json.loads(raw, object_pairs_hook=_unique_object)
    if type(header) is not dict or not 1 <= len(header) <= 50001:
        raise ValueError('Invalid audio SafeTensors header')
    tensors, nonempty = {}, []
    for name, row in header.items():
        if name == '__metadata__':
            if type(row) is not dict or any(type(k) is not str or type(v) is not str for k, v in row.items()):
                raise ValueError('Invalid audio SafeTensors metadata')
            continue
        if type(name) is not str or not name or len(name) > 4096 or type(row) is not dict or set(row) != {'dtype', 'shape', 'data_offsets'}:
            raise ValueError('Invalid audio SafeTensors tensor descriptor')
        dtype, shape, offsets = row['dtype'], row['shape'], row['data_offsets']
        if type(dtype) is not str or dtype not in DTYPES:
            raise ValueError('Unsupported audio SafeTensors dtype')
        if type(shape) is not list or len(shape) > 16 or any(type(v) is not int or not 0 <= v <= 2**63-1 for v in shape):
            raise ValueError('Invalid audio SafeTensors shape')
        if type(offsets) is not list or len(offsets) != 2 or any(type(v) is not int for v in offsets):
            raise ValueError('Invalid audio SafeTensors offsets')
        start, end = offsets
        size = math.prod(shape) * DTYPES[dtype][1]
        if start < 0 or end < start or end > payload_bytes or end-start != size or size > MAX_TENSOR_BYTES:
            raise ValueError('Audio SafeTensors shape/offset/size mismatch')
        tensors[name] = {'dtype': dtype, 'shape': tuple(shape), 'start': start, 'end': end, 'bytes': size}
        if size:
            nonempty.append((start, end, name))
    position = 0
    for start, end, _ in sorted(nonempty):
        if start != position:
            raise ValueError('Audio SafeTensors data contains holes or overlaps')
        position = end
    if position != payload_bytes:
        raise ValueError('Audio SafeTensors header does not cover the whole file')
    return tensors, sorted(nonempty)


class VerifiedAudioSafeTensors:
    """Private per-call materializer; never exported as a graph model recipe."""

    @classmethod
    async def open(cls, assets, ref, expected_bytes, expected_sha256):
        if type(expected_bytes) is not int or not 10 <= expected_bytes <= MAX_FILE_BYTES:
            raise ValueError('Audio SafeTensors exceeds the bounded file domain')
        if type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
            raise ValueError('Audio SafeTensors requires an exact SHA256')
        if await assets.size(ref) != expected_bytes or await assets.digest(ref) != expected_sha256:
            raise ValueError('Audio model resource changed before reading')
        prefix = await _read(assets, ref, 0, 8)
        header_bytes = struct.unpack('<Q', prefix)[0]
        if not 2 <= header_bytes <= MAX_HEADER_BYTES or 8+header_bytes > expected_bytes:
            raise ValueError('Invalid audio SafeTensors header bound')
        raw_header = await _read(assets, ref, 8, header_bytes)
        tensors, spans = _header(raw_header, expected_bytes-8-header_bytes)
        digest = hashlib.sha256(prefix+raw_header)
        hashes = {name: hashlib.sha256() for name in tensors}
        data_offset = 8+header_bytes
        span_index = 0
        # Every payload byte is covered exactly once by the validated sorted
        # ranges. Verify the full file and each tensor without retaining it.
        for offset in range(data_offset, expected_bytes, CHUNK_BYTES):
            raw = await _read(assets, ref, offset, min(CHUNK_BYTES, expected_bytes-offset))
            digest.update(raw)
            start, end = offset-data_offset, offset-data_offset+len(raw)
            while span_index < len(spans) and spans[span_index][1] <= start:
                span_index += 1
            cursor = span_index
            while cursor < len(spans) and spans[cursor][0] < end:
                lower, upper, name = spans[cursor]
                hashes[name].update(memoryview(raw)[max(lower, start)-start:min(upper, end)-start])
                cursor += 1
        if digest.hexdigest() != expected_sha256:
            raise ValueError('Complete audio SafeTensors SHA256 mismatch')
        self = cls()
        self.assets, self.ref = assets, ref
        self.expected_bytes, self.expected_sha256 = expected_bytes, expected_sha256
        self.data_offset, self.tensors = data_offset, tensors
        self.tensor_sha256 = {name: value.hexdigest() for name, value in hashes.items()}
        await self.verify_unchanged()
        return self

    async def verify_unchanged(self):
        if (await self.assets.size(self.ref) != self.expected_bytes
                or await self.assets.digest(self.ref) != self.expected_sha256):
            raise ValueError('Audio model resource changed during reading')

    async def tensor(self, name):
        import torch
        row = self.tensors[name]  # Preserve native missing weight KeyError.
        raw = bytearray(row['bytes'])
        digest = hashlib.sha256()
        for offset in range(0, row['bytes'], CHUNK_BYTES):
            block = await _read(self.assets, self.ref, self.data_offset+row['start']+offset,
                                min(CHUNK_BYTES, row['bytes']-offset))
            raw[offset:offset+len(block)] = block
            digest.update(block)
        if digest.hexdigest() != self.tensor_sha256[name]:
            raise ValueError('Audio weight tensor bytes changed after complete-file verification')
        dtype = getattr(torch, DTYPES[row['dtype']][0])
        if row['bytes'] == 0:
            return torch.empty(row['shape'], dtype=dtype)
        # Torch retains this private bytearray through its storage. A clone
        # would double peak parameter memory without changing tensor values.
        return torch.frombuffer(raw, dtype=dtype).reshape(row['shape'])
