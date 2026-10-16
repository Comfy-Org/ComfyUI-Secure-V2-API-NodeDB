import asyncio
import ast
import importlib.util
import struct
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent


def load_package(name, path):
    spec = importlib.util.spec_from_file_location(name, path / '__init__.py', submodule_search_locations=[str(path)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load_package('moe_calcuis_draft', V2)
from moe_calcuis_draft import nodes
from moe_calcuis_draft import state_math, encoding_math, range_reader
from moe_calcuis_draft.gguf_math.const import GGMLQuantizationType, GGUFValueType
from moe_calcuis_draft.gguf_math import quant5


def lifted_original(*names):
    tree = ast.parse((PACK / 'pig.py').read_text())
    selected = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    namespace = {'torch': torch, 'GGMLQuantizationType': GGMLQuantizationType, 'quantize': quant5.quantize, 'QuantError': quant5.QuantError, 'QUANTIZATION_THRESHOLD': 1024, 'MAX_TENSOR_NAME_LENGTH': 127}
    class Loading:
        def __call__(self, value):
            return value
        def write(self, message):
            pass
    namespace['loading'] = Loading()
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PACK / 'pig.py'), 'exec'), namespace)
    return namespace


def test_exact13_census_and_schema_static_projection():
    original = ast.parse((PACK / 'pig.py').read_text())
    mapping = next(n.value for n in original.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NODE_CLASS_MAPPINGS' for t in n.targets))
    assert list(nodes.NODE_CLASS_MAPPINGS) == [k.value for k in mapping.keys]
    entry = asyncio.run(sys.modules['moe_calcuis_draft'].comfy_entrypoint())
    assert asyncio.run(entry.get_node_list()) == list(nodes.NODE_CLASS_MAPPINGS.values())
    expected_outputs = ['MODEL', 'CLIP', 'CLIP', 'CLIP', 'CLIP', 'AUDIO_ENCODER', 'MODEL', 'VAE', '', '', '', '', '']
    for (node_id, cls), expected in zip(nodes.NODE_CLASS_MAPPINGS.items(), expected_outputs):
        schema = cls.define_schema()
        assert schema.node_id == node_id and schema.category == 'gguf' and schema.display_name == cls.TITLE
        assert [str(output.io_type) for output in schema.outputs] == ([] if not expected else [expected])
        assert schema.is_output_node == (not expected)
    # Host CLIP options are an independently checked source projection, not
    # the mocked catalogue/type census marker from the historical screen.
    core = ast.parse(Path('/Users/ben/comfy/ComfyUI-secure-nodes/nodes.py').read_text())
    for class_name, options in [('CLIPLoader', nodes.CLIP_TYPES), ('DualCLIPLoader', nodes.DUAL_CLIP_TYPES)]:
        cls = next(n for n in core.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        assert any(isinstance(n, ast.List) and all(isinstance(x, ast.Constant) for x in n.elts) and [x.value for x in n.elts] == options for n in ast.walk(cls))


@pytest.mark.parametrize('dtype', [torch.float16, torch.bfloat16, torch.float32, torch.float64, torch.int32, torch.int64, torch.bool])
def test_boost_pinned_cast_math_and_input_identity(dtype):
    value = torch.arange(24).reshape(4, 6).to(dtype).t()
    before = value.clone()
    result = state_math.boost({'weights': value, 'scalar': torch.tensor(1, dtype=dtype)})
    assert torch.equal(result['weights'], value.to(torch.float32))
    assert result['weights'].shape == value.shape and result['weights'].dtype == torch.float32
    assert torch.equal(value, before)


@pytest.mark.parametrize('values', [[-1000., -240., -.4, 0., .4, 240., 1000.], [0., 0.], [float('inf'), -float('inf'), float('nan')], [1.], [1.01, 1.02, 1.03]])
def test_fp8_formula_exact_ast_and_byte_differential_only_not_cpu_cut(values):
    original = lifted_original('quantize_to_fp8')['quantize_to_fp8']
    pinned_ast = next(n for n in ast.parse((PACK / 'pig.py').read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'quantize_to_fp8')
    converted_ast = next(n for n in ast.parse((V2 / 'state_math.py').read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'quantize_to_fp8')
    assert ast.dump(pinned_ast) == ast.dump(converted_ast)
    value = torch.tensor(values, dtype=torch.bfloat16)
    assert torch.equal(original(value).view(torch.uint8), state_math.quantize_to_fp8(value).view(torch.uint8))


def test_empty_fp8_formula_preserves_native_failure():
    with pytest.raises(RuntimeError):
        state_math.quantize_to_fp8(torch.empty(0, dtype=torch.bfloat16))


@pytest.mark.parametrize('keys', [['plain'], ['net.a', 'net.net.b', 'ignore'], ['model.diffusion_model.a', 'xxmodel.diffusion_model.b', 'model.c'], ['model.a', 'net.b']])
def test_alpha_substring_prefix_quirks(keys):
    namespace = lifted_original('load_state_dict')
    state = {key: torch.tensor(index) for index, key in enumerate(keys)}
    namespace['load_file'] = lambda _: state
    expected = namespace['load_state_dict']('not-a-real-path')
    actual = state_math.alpha_state(state)
    assert list(actual) == list(expected) and all(actual[k] is expected[k] for k in actual)


class RecordingWriter:
    def __init__(self):
        self.tensors = []
    def add_tensor(self, name, data, raw_dtype):
        self.tensors.append((name, data.copy(), raw_dtype))


@pytest.mark.parametrize('dtype', [torch.float32, torch.float16, torch.bfloat16, torch.float64, torch.int32, torch.float8_e4m3fn])
def test_tensor_encoding_pinned_order_dtypes_and_thresholds(dtype):
    state = {'small.weight': torch.linspace(-1, 1, 32).to(dtype), 'big.weight': torch.linspace(-1, 1, 2048).reshape(32, 64).to(dtype), 'time_embedding.x.weight': torch.linspace(-1, 1, 2048).reshape(32, 64).to(dtype)}
    old, new = RecordingWriter(), RecordingWriter()
    original = lifted_original('handle_tensors')['handle_tensors']
    original(None, old, state, 'unused')
    encoding_math.handle_tensors(None, new, state, 'unused')
    assert len(new.tensors) == len(old.tensors) == 3
    for a, b in zip(old.tensors, new.tensors):
        assert a[0] == b[0] and a[2] == b[2] and a[1].dtype == b[1].dtype and a[1].shape == b[1].shape
        assert a[1].tobytes() == b[1].tobytes()


def string(value):
    value = value.encode()
    return struct.pack('<Q', len(value)) + value


def fixture_blob(qtype=GGMLQuantizationType.F32, payload=None, dims=(3, 2), fields=()):
    metadata = b''.join(string(name) + struct.pack('<I', tag) + value for name, tag, value in fields)
    descriptor = string('weights') + struct.pack('<I', len(dims)) + b''.join(struct.pack('<Q', dim) for dim in dims) + struct.pack('<IQ', int(qtype), 0)
    header = b'GGUF' + struct.pack('<IQQ', 3, 1, len(fields)) + metadata + descriptor
    header += b'\0' * ((-len(header)) % 32)
    if payload is None:
        payload = np.arange(6, dtype=np.float32).tobytes()
    return header + payload


class RangeDouble:
    def __init__(self, data):
        self.data, self.calls = data, []
    async def read_range(self, ref, offset, length):
        self.calls.append((offset, length))
        return self.data[offset:offset + length]


@pytest.mark.parametrize('qtype,dtype', [(GGMLQuantizationType.F32, np.float32), (GGMLQuantizationType.F16, np.float16)])
def test_range_reader_exact_pinned_descriptor_and_fp16_decode(qtype, dtype, tmp_path):
    # Pristine memmap executes only on a synthetic scratch file; no host model.
    root = types.ModuleType('moe_pristine_gguf_connector')
    root.__path__ = [str(PACK / 'gguf_connector')]
    sys.modules[root.__name__] = root
    import importlib
    original = importlib.import_module(root.__name__ + '.reader')
    payload = np.array([0., .1, -.3, 240., -240., 1.25], dtype=dtype).tobytes()
    data = fixture_blob(qtype, payload, fields=[('general.architecture', 8, string('pig')), ('custom.list', 9, struct.pack('<IQii', 5, 2, -1, 7))])
    path = tmp_path / 'synthetic.gguf'
    path.write_bytes(data)
    pinned = original.GGUFReader(path)
    service = RangeDouble(data)
    async def run():
        reader = await range_reader.RangeReader(service, 'opaque-ref', len(data)).parse()
        assert reader.data_offset == pinned.data_offset
        desc, expected = reader.tensors[0], pinned.tensors[0]
        assert (desc.name, desc.shape, desc.nbytes, desc.tensor_type, desc.elements) == (expected.name, tuple(reversed(expected.shape)), expected.n_bytes, expected.tensor_type, expected.n_elements)
        state = await reader.fp16_state()
        wanted = torch.from_numpy(quant5.dequantize(expected.data, expected.tensor_type).copy()).to(torch.float16)
        assert torch.equal(state['weights'], wanted)
        assert reader.fields == [(name, tag, pinned.get_field(name).contents()) for name, tag, _ in reader.fields]
        assert reader.metadata() == {key: str(field) for key, field in pinned.fields.items()}
    asyncio.run(run())
    assert service.calls and all(1 <= length <= range_reader.CHUNK for _, length in service.calls)


@pytest.mark.parametrize('failure', ['tensor_count', 'field_count', 'rank', 'string', 'shape', 'span', 'array', 'nested', 'alignment', 'magic', 'version'])
def test_hostile_descriptors_reject_before_tensor_payload(failure):
    data = fixture_blob()
    if failure == 'tensor_count':
        data = data[:8] + struct.pack('<Q', 65537) + data[16:]
    elif failure == 'field_count':
        data = data[:16] + struct.pack('<Q', 65537) + data[24:]
    elif failure == 'rank':
        position = 24 + len(string('weights'))
        data = data[:position] + struct.pack('<I', 9) + data[position+4:]
    elif failure == 'string':
        data = data[:24] + struct.pack('<Q', 4097) + data[32:]
    elif failure == 'shape':
        data = fixture_blob(dims=(1 << 62, 4))
    elif failure == 'span':
        data = data[:-20]
    elif failure == 'array':
        data = fixture_blob(fields=[('array', 9, struct.pack('<IQ', 4, 1_000_001))])
    elif failure == 'nested':
        data = fixture_blob(fields=[('nested', 9, struct.pack('<IQ', 9, 1) * 10)])
    elif failure == 'alignment':
        data = fixture_blob(fields=[('general.alignment', 4, struct.pack('<I', 0))])
    elif failure == 'magic':
        data = b'BAD!' + data[4:]
    elif failure == 'version':
        data = data[:4] + struct.pack('<I', 4) + data[8:]
    service = RangeDouble(data)
    reader = range_reader.RangeReader(service, 'opaque-ref', len(data))
    with pytest.raises((ValueError, UnicodeDecodeError)):
        asyncio.run(reader.parse())
    assert reader.payload_bytes == 0


def test_no_invented_state_or_output_cap_before_native_boost_cast():
    result = state_math.boost({'large_shape': torch.empty(536870913, device='meta')})
    assert result['large_shape'].dtype == torch.float32
    assert result['large_shape'].numel() == 536870913


@pytest.mark.parametrize('name', ['/abs', '../x', 'a/../b', 'a\\..\\b', 'a\0b'])
def test_path_authority_denied(name):
    from moe_calcuis_draft.bounds import logical_name
    with pytest.raises(ValueError):
        logical_name(name)


# Revision 2: VaeGGUF, AudioEncoderLoaderGGUF, GGUFSave and GGUFRun are no longer pending. They use the Phase-1 SDK
# verbs and are differential-tested against the original (see SECURE_CONVERSION.md).
@pytest.mark.parametrize('node_id,arguments', [('LoaderGGUF', {'gguf_name': 'synthetic.gguf'}), ('LoaderGGUFAdvanced', {'gguf_name': 'synthetic.gguf'}), ('ClipLoaderGGUF', {'clip_name': 'synthetic.gguf'}), ('DualClipLoaderGGUF', {'clip_name1': 'a.gguf', 'clip_name2': 'b.gguf', 'type': 'sdxl'}), ('TripleClipLoaderGGUF', {'clip_name1': 'a.gguf', 'clip_name2': 'b.gguf', 'clip_name3': 'c.gguf'}), ('QuadrupleClipLoaderGGUF', {'clip_name1': 'a.gguf', 'clip_name2': 'b.gguf', 'clip_name3': 'c.gguf', 'clip_name4': 'd.gguf'})])
def test_pending_branch_is_not_silent_provider_or_output_substitution(node_id, arguments):
    with pytest.raises(nodes.ConversionPendingError):
        asyncio.run(nodes.NODE_CLASS_MAPPINGS[node_id].execute(**arguments))
