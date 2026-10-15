"""Calcuis Alpha/Zero GGUF v3 output, streamed without output-path authority.

Only the native converter's F32/F16/BF16 encoding family is supported. The
Caller limits, when supplied, remain enforced; host admission grants capacity.
The managed publication operation is deliberately outside this module.
"""
from dataclasses import dataclass
from math import prod
import struct
import sys


def _string(value):
    encoded = value.encode('utf-8')
    return struct.pack('<Q', len(encoded)) + encoded


def _padding(size):
    return bytes((-size) % 32)


@dataclass(frozen=True)
class EncodedTensor:
    name: str
    shape: tuple
    qtype: int
    data: memoryview


class BinaryWriter:
    """One non-sharded native little-endian GGUF artifact."""
    def __init__(self, architecture, *, max_bytes=None, max_tensors=None, max_elements=None):
        if type(architecture) is not str or not architecture:
            raise ValueError('nonempty architecture required')
        if any(value is not None and (type(value) is not int or value <= 0) for value in (max_bytes, max_tensors, max_elements)):
            raise ValueError('supplied resource-policy limits must be positive')
        self.max_bytes = max_bytes
        self.max_tensors = max_tensors
        self.max_elements = max_elements
        self.kv = {'general.architecture': struct.pack('<I', 8) + _string(architecture)}
        self.tensors = {}
        self.state = 'open'
        self._elements = 0
        self._data_bytes = 0
        self._prefix_bytes = 24 + len(_string('general.architecture')) + len(self.kv['general.architecture'])
        self._check_size(self._prefix_bytes)

    def _open(self):
        if self.state != 'open':
            raise ValueError('writer is sealed or disposed')

    def _check_size(self, size):
        if self.max_bytes is not None and size > self.max_bytes:
            raise ValueError('GGUF output exceeds supplied resource policy')

    def _uint32(self, key, value):
        self._open()
        encoded = struct.pack('<II', 4, value)
        previous = self.kv.get(key)
        projected = self._prefix_bytes + len(encoded) - (len(previous) if previous is not None else 0)
        if previous is None:
            projected += len(_string(key))
        self._check_size(projected + len(_padding(projected)) + self._data_bytes)
        self.kv[key] = encoded
        self._prefix_bytes = projected

    def add_quantization_version(self, value):
        self._uint32('general.quantization_version', value)

    def add_file_type(self, value):
        self._uint32('general.file_type', value)

    def add_encoded_tensor(self, name, shape, qtype, payload):
        self._open()
        if type(name) is not str:
            raise ValueError('string tensor name required')
        if name in self.tensors:
            raise ValueError(f'Duplicated tensor name {name!r}')
        shape = tuple(shape)
        if any(type(dim) is not int or dim < 0 for dim in shape):
            raise ValueError('nonnegative tensor shape required')
        if type(qtype) is not int or qtype not in (0, 1, 30):
            raise ValueError('Alpha/Zero F32/F16/BF16 encoding required')
        if type(payload) is not bytes:
            raise ValueError('immutable encoded tensor bytes required')
        data = memoryview(payload)
        width = 4 if qtype == 0 else 2
        elements = prod(shape)
        if len(data) != elements * width:
            raise ValueError('encoded bytes disagree with tensor shape/type')
        if (self.max_tensors is not None and len(self.tensors) + 1 > self.max_tensors) or (self.max_elements is not None and self._elements + elements > self.max_elements):
            raise ValueError('tensor count/elements exceed supplied resource policy')
        prefix_size = self._prefix_bytes + len(_string(name)) + 4 + 8 * len(shape) + 4 + 8
        data_size = self._data_bytes + len(data) + len(_padding(len(data)))
        self._check_size(prefix_size + len(_padding(prefix_size)) + data_size)
        self.tensors[name] = EncodedTensor(name, shape, qtype, data.toreadonly())
        self._prefix_bytes = prefix_size
        self._data_bytes = data_size
        self._elements += elements

    def add_tensor(self, name, tensor, raw_shape=None, raw_dtype=None, tensor_endianess=None):
        """Real native handle_tensors adapter; tensor is its actual NumPy result."""
        self._open()
        if raw_dtype is None:
            raise ValueError('native converter must declare its encoded dtype')
        qtype = int(raw_dtype)
        shape = tuple(int(dim) for dim in (tensor.shape if raw_shape is None else raw_shape))
        source_endian = sys.byteorder if tensor_endianess is None else ('big' if int(tensor_endianess) else 'little')
        if source_endian != 'little':
            tensor = tensor.byteswap(inplace=False)
        if tensor.dtype.name == 'uint8':
            # Native quant_shape_from_byte_shape: these three types have block=1.
            width = 4 if qtype == 0 else 2
            if not shape or shape[-1] % width:
                raise ValueError('quantized tensor bytes per row disagree with type size')
            shape = (*shape[:-1], shape[-1] // width)
        self.add_encoded_tensor(name, shape, qtype, tensor.tobytes(order='C'))

    @property
    def total_bytes(self):
        return self._prefix_bytes + len(_padding(self._prefix_bytes)) + self._data_bytes

    def iter_chunks(self):
        """Emit header/KV/directory/aligned weights once; close disposes buffers."""
        self._open()
        self.state = 'streaming'
        try:
            yield struct.pack('<IIQQ', 1179993927, 3, len(self.tensors), len(self.kv))
            for key, value in self.kv.items():
                yield _string(key)
                yield value
            offset = 0
            for tensor in self.tensors.values():
                yield _string(tensor.name)
                yield struct.pack('<I', len(tensor.shape))
                for dimension in reversed(tensor.shape):
                    yield struct.pack('<Q', dimension)
                yield struct.pack('<IQ', tensor.qtype, offset)
                offset += len(tensor.data) + len(_padding(len(tensor.data)))
            yield _padding(self._prefix_bytes)
            for tensor in self.tensors.values():
                yield tensor.data
                yield _padding(len(tensor.data))
        finally:
            self.close()

    def close(self):
        self.tensors.clear()
        self.kv.clear()
        self.state = 'closed'
