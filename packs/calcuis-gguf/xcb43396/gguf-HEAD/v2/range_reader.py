"""Bounded async GGUF inspection over public asset ranges, never host paths.

Numeric decoding uses the pinned calcuis quantizer. Descriptor parsing checks
all projected work/data spans before fetching or allocating tensor payloads.
Big-endian support is explicit pending, not silently normalized.
"""
from dataclasses import dataclass
import math
import struct
import numpy as np
import torch
from .bounds import state_bounds
from .gguf_math.const import GGML_QUANT_SIZES, GGMLQuantizationType, GGUFValueType
from .gguf_math.quant import dequantize
from .metadata_fields import ReaderField

CHUNK = 1024 * 1024
SCALARS = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}
SCALAR_DTYPES = {0: np.uint8, 1: np.int8, 2: np.uint16, 3: np.int16, 4: np.uint32, 5: np.int32, 6: np.float32, 7: np.bool_, 10: np.uint64, 11: np.int64, 12: np.float64}


@dataclass(frozen=True)
class TensorDescriptor:
    name: str
    shape: tuple
    tensor_type: GGMLQuantizationType
    offset: int
    nbytes: int
    elements: int


class RangeReader:
    def __init__(self, assets=None, ref=None, size=None, *, read_range=None):
        if type(size) is not int or size < 24:
            raise ValueError("invalid GGUF asset size")
        if read_range is None:
            async def read_range(offset, count):
                return await assets.read_range(ref, offset, count)
        self.read_range, self.size = read_range, size
        self.offset = self.metadata_bytes = self.field_work = self.payload_bytes = 0
        self.cache_start, self.cache = -1, b''
        self.fields = []
        self.reader_fields = {}
        self.tensors = []
        self.data_offset = None

    @classmethod
    def from_bytes(cls, data):
        """Parse genuine GGUF bytes without constructing an SDK asset/provider."""
        if type(data) is not bytes:
            raise TypeError('immutable GGUF bytes required')
        async def read_range(offset, count):
            return data[offset:offset + count]
        return cls(size=len(data), read_range=read_range)

    async def take(self, offset, count, *, metadata=True):
        if type(offset) is not int or type(count) is not int or offset < 0 or count < 0 or offset + count > self.size:
            raise ValueError("truncated/out-of-range GGUF read")
        if metadata:
            self.metadata_bytes += count
        else:
            self.payload_bytes += count
        if not count:
            return b''
        if metadata and count <= CHUNK:
            if not self.cache_start <= offset or offset + count > self.cache_start + len(self.cache):
                self.cache_start = offset
                self.cache = await self.read_range(offset, min(CHUNK, self.size - offset))
            if type(self.cache) is not bytes or len(self.cache) < count:
                raise ValueError("short or malformed asset range")
            return self.cache[offset - self.cache_start:offset - self.cache_start + count]
        chunks = []
        for position in range(offset, offset + count, CHUNK):
            length = min(CHUNK, offset + count - position)
            chunk = await self.read_range(position, length)
            if type(chunk) is not bytes or len(chunk) != length:
                raise ValueError("short or malformed asset range")
            chunks.append(chunk)
        return b''.join(chunks)

    async def scalar(self, fmt):
        size = struct.calcsize('<' + fmt)
        value = struct.unpack('<' + fmt, await self.take(self.offset, size))[0]
        self.offset += size
        return value

    async def string(self):
        length = await self.scalar('Q')
        if length > self.size - self.offset:
            raise ValueError("GGUF string span outside asset")
        result = (await self.take(self.offset, length)).decode('utf-8')
        self.offset += length
        return result

    def validate_array_span(self, subtype, count):
        if subtype in SCALARS:
            minimum = struct.calcsize('<' + SCALARS[subtype])
        elif subtype == int(GGUFValueType.STRING):
            minimum = 8
        elif subtype == int(GGUFValueType.ARRAY):
            minimum = 12
        else:
            raise ValueError('unknown GGUF array element type')
        if count > (self.size - self.offset) // minimum:
            raise ValueError('GGUF array elements cannot fit inside asset')

    async def field_value(self, tag, depth=0):
        self.field_work += 1
        if tag in SCALARS:
            return await self.scalar(SCALARS[tag])
        if tag == int(GGUFValueType.STRING):
            return await self.string()
        if tag == int(GGUFValueType.ARRAY):
            subtype = await self.scalar('I')
            count = await self.scalar('Q')
            self.validate_array_span(subtype, count)
            return [await self.field_value(subtype, depth + 1) for _ in range(count)]
        raise ValueError("unknown GGUF metadata value type")

    async def field_parts(self, tag, depth=0):
        """Keep exact pinned ReaderField repr metadata, not JSON-normalized text."""
        self.field_work += 1
        kind = GGUFValueType(tag)
        if tag in SCALARS:
            fmt = SCALARS[tag]
            size = struct.calcsize('<' + fmt)
            raw = await self.take(self.offset, size)
            self.offset += size
            # Match the pinned reader's np.int64 native dtype descriptor,
            # not platform 'q' vs 'l' aliases with different repr text.
            value = np.frombuffer(raw, dtype=SCALAR_DTYPES[tag])
            return [value], [0], [kind]
        if kind == GGUFValueType.STRING:
            length = await self.scalar('Q')
            if length > self.size - self.offset:
                raise ValueError('GGUF string span outside asset')
            raw = await self.take(self.offset, length)
            self.offset += length
            raw.decode('utf-8')
            return [np.array([length], dtype=np.uint64), np.frombuffer(raw, dtype=np.uint8)], [1], [kind]
        if kind == GGUFValueType.ARRAY:
            subtype = await self.scalar('I')
            count = await self.scalar('Q')
            self.validate_array_span(subtype, count)
            parts = [np.array([subtype], dtype=np.uint32), np.array([count], dtype=np.uint64)]
            data, types = [], [kind]
            for index in range(count):
                child_parts, child_data, child_types = await self.field_parts(subtype, depth + 1)
                if index == 0:
                    types += child_types
                data += [len(parts) + item for item in child_data]
                parts += child_parts
            return parts, data, types
        raise ValueError('unknown GGUF metadata value type')

    async def parse(self):
        if await self.take(0, 4) != b'GGUF':
            raise ValueError('GGUF magic invalid')
        self.offset = 4
        version = await self.scalar('I')
        if version not in (2, 3):
            raise ValueError('unsupported GGUF version/endian policy')
        tensor_count, field_count = await self.scalar('Q'), await self.scalar('Q')
        self.reader_fields = {
            'GGUF.version': ReaderField(4, 'GGUF.version', [np.array([version], dtype=np.uint32)], [0], [GGUFValueType.UINT32]),
            'GGUF.tensor_count': ReaderField(8, 'GGUF.tensor_count', [np.array([tensor_count], dtype=np.uint64)], [0], [GGUFValueType.UINT64]),
            'GGUF.kv_count': ReaderField(16, 'GGUF.kv_count', [np.array([field_count], dtype=np.uint64)], [0], [GGUFValueType.UINT64]),
        }
        if tensor_count > self.size // 24 or field_count > self.size // 12:
            raise ValueError("GGUF descriptor counts cannot fit inside asset")
        alignment = 32
        for _ in range(field_count):
            field_offset = self.offset
            name = await self.string()
            tag = await self.scalar('I')
            parts, indices, types = await self.field_parts(tag)
            name_bytes = name.encode('utf-8')
            header = [np.array([len(name_bytes)], dtype=np.uint64), np.frombuffer(name_bytes, dtype=np.uint8), np.array([tag], dtype=np.uint32)]
            field = ReaderField(field_offset, name, header + parts, [3 + index for index in indices], types)
            self.reader_fields[name + ('_' + str(field_offset) if name in self.reader_fields else '')] = field
            value = field.contents()
            self.fields.append((name, tag, value))
            if name == 'general.alignment':
                if tag != int(GGUFValueType.UINT32) or value < 1:
                    raise ValueError("invalid bounded GGUF alignment")
                alignment = value
        names = set()
        descriptors = []
        total_bytes = total_elements = 0
        for _ in range(tensor_count):
            name = await self.string()
            if name in names:
                raise ValueError('duplicated GGUF tensor name')
            names.add(name)
            rank = await self.scalar('I')
            if rank > (self.size - self.offset) // 8:
                raise ValueError("GGUF dimensions cannot fit inside asset")
            dims = tuple([await self.scalar('Q') for _ in range(rank)])
            elements = math.prod(dims)
            qtype = GGMLQuantizationType(await self.scalar('I'))
            relative = await self.scalar('Q')
            block, itemsize = GGML_QUANT_SIZES[qtype]
            if (dims and dims[0] % block) or (not dims and block != 1):
                raise ValueError("quantized row not divisible by block size")
            nbytes = elements // block * itemsize
            total_bytes += nbytes
            total_elements += elements
            descriptors.append(TensorDescriptor(name, tuple(reversed(dims)), qtype, relative, nbytes, elements))
        self.data_offset = (self.offset + alignment - 1) // alignment * alignment
        for desc in descriptors:
            if self.data_offset + desc.offset + desc.nbytes > self.size:
                raise ValueError("GGUF tensor payload span outside asset")
        self.tensors = descriptors
        return self

    def metadata(self):
        # Upstream serializes repr(ReaderField), including memmap's ndarray
        # label/line layout. ndarray.view changes only the guest-memory array
        # subtype; it never calls memmap.__new__, opens a file or maps a path.
        # The resulting arrays have _mmap=None and filename=None.
        return {key: str(ReaderField(field.offset, field.name, [part.view(np.memmap) for part in field.parts], field.data, field.types)) for key, field in self.reader_fields.items()}

    async def fp16_state(self):
        if self.data_offset is None:
            raise ValueError("GGUF descriptors must be validated before payload")
        state = {}
        for desc in self.tensors:
            raw = await self.take(self.data_offset + desc.offset, desc.nbytes, metadata=False)
            if desc.tensor_type == GGMLQuantizationType.F32:
                encoded = np.frombuffer(raw, dtype=np.float32).reshape(desc.shape)
            elif desc.tensor_type == GGMLQuantizationType.F16:
                encoded = np.frombuffer(raw, dtype=np.float16).reshape(desc.shape)
            else:
                block, itemsize = GGML_QUANT_SIZES[desc.tensor_type]
                encoded = np.frombuffer(raw, dtype=np.uint8).reshape((*desc.shape[:-1], desc.shape[-1] // block * itemsize))
            # Exact pinned reverse path: NumPy dequantize.copy -> Torch FP16.
            state[desc.name] = torch.from_numpy(dequantize(encoded, desc.tensor_type).copy()).to(torch.float16)
        return state_bounds(state, output_itemsize=2)
