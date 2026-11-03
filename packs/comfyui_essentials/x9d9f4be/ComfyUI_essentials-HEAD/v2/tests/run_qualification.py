"""Finite synthetic original/default/actual-Guest qualification. Gate only."""
from __future__ import annotations

import argparse
import ast
import asyncio
import builtins
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import traceback
import types

if not Path('/pack/image.py').is_file() or not Path('/tests/guest_common.lock').is_file():
    raise SystemExit('This driver may execute pack Python only in the bounded run_in_gate container.')
sys.dont_write_bytecode = True
sys.path[:0] = ['/core', '/overlay', '/tests']
from comfy.cli_args import args as core_args
core_args.cpu = True
import torch
import comfy.utils
from comfy_api.latest import io, _sdk as sdk
from comfy_secure_nodes import packdb, packmanifest
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
import guest_lock
import schema_source
import byte_reader_checks

ARGS = argparse.ArgumentParser()
ARGS.add_argument('--phase', choices=('guest-batch-size',), default='guest-batch-size')
ARGS.add_argument('--negative-control', action='store_true')
ARGS.add_argument('--pack-root', default='/pack')
OPTIONS = ARGS.parse_args()
PACK = Path(OPTIONS.pack_root).resolve()
if PACK != Path('/pack'):
    assert str(PACK).startswith('/tmp/essentials-r8-package-')
    assert PACK.parts[-5:] == ('stage', 'packs', 'comfyui_essentials', 'x9d9f4be', 'ComfyUI_essentials-HEAD')
V2 = PACK / 'v2'
RESULTS = Path('/results')
CASES = json.loads(Path('/tests/cases.json').read_text())
FROZEN = json.loads((V2 / '_schemas.json').read_text())
BASELINE = json.loads(Path('/tests/baseline-secure-nodes.json').read_text())
SELECTED = ('ImageBatchMultiple+', 'GetImageSize+')
FOCUSED_GUEST_NODES = ('ImageBatchMultiple+', 'GetImageSize+')
FOCUSED_GUEST = OPTIONS.phase == 'guest-batch-size'
if FOCUSED_GUEST:
    focused_counts = {node_id: sum(case['node'] == node_id for case in CASES) for node_id in FOCUSED_GUEST_NODES}
    assert focused_counts == {'ImageBatchMultiple+': 86, 'GetImageSize+': 32}, focused_counts
NEGATIVE_CASE_INDEX = 245
if OPTIONS.negative_control:
    assert CASES[NEGATIVE_CASE_INDEX]['node'] == 'ImageBatchMultiple+'
    assert CASES[NEGATIVE_CASE_INDEX]['label'] == 'all-five/nearest-exact'
GUEST_NAMESPACE = 'custom_nodes.essentials_recovery_guest'
BASE = Path('/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages')
RECEIPT = {'status': 'RUNNING', 'evidence': 'gate, B13 sources 38f28c98',
    'core': '6257422b', 'engine_sdk': '038019fa', 'overlay': '6f58bcec/e4d93d0d',
    'guest_base': '0cd9adec', 'upstream_commit': '9d9f4bedfc9f0321c19faf71855e228c93bd0dc9',
    'timeout_seconds': 360, 'phase': OPTIONS.phase, 'expected_negative': OPTIONS.negative_control,
    'host_pid': os.getpid(), 'scheduled_cases': 1 if OPTIONS.negative_control else 118, 'nodes': {}, 'failures': [],
    'qualification': 'CPU development sandbox_kind=none is not live B13 deployment or OS isolation evidence',
    'output_checks': ['declared IMAGE wire kind', 'dtype', 'shape', 'logical bytes including signed zero', 'stride', 'storage offset', 'no-op host identity', 'input unchanged'],
}
if FOCUSED_GUEST:
    RECEIPT['case_selection'] = {
        'phase': 'guest-batch-size', 'nodes': list(FOCUSED_GUEST_NODES),
        'positive_fixture_inventory': focused_counts, 'input_corpus_cases': len(CASES),
        'original_case_indices': [NEGATIVE_CASE_INDEX] if OPTIONS.negative_control else [index for index, case in enumerate(CASES) if case['node'] in FOCUSED_GUEST_NODES],
        'held_nodes': {'ImageResize+': 'ActualGuest stride mismatch in attempt-06-r6; registered only as a whole-node named refusal'},
        'default_cases_in_this_attempt': 0,
    }
RECEIPT['pack_root'] = str(PACK)
signal.signal(signal.SIGALRM, lambda number, frame: (_ for _ in ()).throw(TimeoutError('finite Essentials driver exceeded 360 seconds')))
signal.alarm(360)


def save():
    (RESULTS / 'qualification.json').write_text(json.dumps(RECEIPT, indent=2, sort_keys=True) + '\n')


def tensor_bytes(value):
    packed = value.detach().reshape(-1).clone(memory_format=torch.contiguous_format)
    return packed.view(torch.uint8).numpy().tobytes()


def equivalent(actual, expected, path='result'):
    if isinstance(expected, torch.Tensor):
        assert isinstance(actual, torch.Tensor), (path, type(actual))
        assert actual.dtype == expected.dtype, (path, actual.dtype, expected.dtype)
        assert actual.shape == expected.shape, (path, actual.shape, expected.shape)
        assert tuple(actual.stride()) == tuple(expected.stride()), (path, 'stride', actual.stride(), expected.stride())
        assert actual.storage_offset() == expected.storage_offset(), (path, 'storage_offset', actual.storage_offset(), expected.storage_offset())
        assert tensor_bytes(actual) == tensor_bytes(expected), (path, 'bytes')
    else:
        assert type(actual) is type(expected), (path, type(actual), type(expected))
        if isinstance(expected, (tuple, list)):
            assert len(actual) == len(expected), path
            for index, (a, e) in enumerate(zip(actual, expected, strict=True)):
                equivalent(a, e, f'{path}/{index}')
        elif isinstance(expected, dict):
            assert actual.keys() == expected.keys(), path
            for key in expected:
                equivalent(actual[key], expected[key], f'{path}/{key}')
        elif isinstance(expected, float):
            assert actual.hex() == expected.hex(), (path, actual, expected)
        else:
            assert actual == expected, (path, actual, expected)


def fixture(value):
    if not isinstance(value, dict):
        return value
    if value.get('fixture') != 'image':
        return {key: fixture(item) for key, item in value.items()}
    batch, height, width, channels = value['shape']
    view = value['view']
    storage_shape = (batch, height, width, channels)
    if view == 'permute': storage_shape = (batch, channels, height, width)
    elif view == 'rgba_rgb':
        assert channels == 3
        storage_shape = (batch, height, width, 4)
    elif view == 'slice': storage_shape = (batch, height, width * 2, channels)
    elif view == 'transpose': storage_shape = (batch, width, height, channels)
    elif view == 'offset': storage_shape = (batch, height, width + 1, channels)
    elif view == 'expand': storage_shape = (1, height, width, channels)
    count = math.prod(storage_shape)
    raw = ((torch.arange(count, dtype=torch.float64) * 37 + value['seed']) % 257) / 256
    if value['values'] == 'out-of-range':
        raw = raw * 4 - 1
        if count: raw[0] = -0.0
    if value['values'] == 'nan' and count: raw[0] = float('nan')
    raw = raw.to(getattr(torch, value['dtype'])).reshape(storage_shape)
    if view == 'permute': raw = raw.permute(0, 2, 3, 1)
    elif view == 'rgba_rgb': raw = raw[..., :3]
    elif view == 'slice': raw = raw[:, :, ::2, :]
    elif view == 'transpose': raw = raw.transpose(1, 2)
    elif view == 'offset': raw = raw[:, :, 1:, :]
    elif view == 'expand': raw = raw.expand(batch, -1, -1, -1)
    assert tuple(raw.shape) == tuple(value['shape'])
    return raw


def original_classes():
    source = (PACK / 'image.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in {FROZEN[node_id]['class'] for node_id in SELECTED}]
    assert len(selected) == 2
    module = types.ModuleType('essentials_pinned_original_selected')
    module.__dict__.update(torch=torch, F=torch.nn.functional, comfy=comfy, MAX_RESOLUTION=io.MAX_RESOLUTION)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PACK / 'image.py'), 'exec'), module.__dict__)
    return {node_id: getattr(module, FROZEN[node_id]['class']) for node_id in SELECTED}


def baseline(node_id, fields, originals):
    calls = []
    real_lanczos, real_upscale = comfy.utils.lanczos, comfy.utils.common_upscale
    def lanczos(*args, **kwargs):
        calls.append('lanczos')
        return real_lanczos(*args, **kwargs)
    def common_upscale(*args, **kwargs):
        calls.append('common_upscale')
        return real_upscale(*args, **kwargs)
    comfy.utils.lanczos, comfy.utils.common_upscale = lanczos, common_upscale
    try:
        try: return originals[node_id]().execute(**fields), None, calls
        except Exception as error: return None, error, calls
    finally:
        comfy.utils.lanczos, comfy.utils.common_upscale = real_lanczos, real_upscale


def import_v2():
    spec = importlib.util.spec_from_file_location('essentials_recovery_default', V2 / '__init__.py', submodule_search_locations=[str(V2)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def structured_difference(before, after, path=''):
    differences = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child_path = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in before:
                differences.append({'path': child_path, 'before_present': False, 'after_present': True, 'after': after[key]})
            elif key not in after:
                differences.append({'path': child_path, 'before_present': True, 'after_present': False, 'before': before[key]})
            else:
                differences.extend(structured_difference(before[key], after[key], child_path))
    elif isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            child_path = path + '/' + str(index)
            if index >= len(before):
                differences.append({'path': child_path, 'before_present': False, 'after_present': True, 'after': after[index]})
            elif index >= len(after):
                differences.append({'path': child_path, 'before_present': True, 'after_present': False, 'before': before[index]})
            else:
                differences.extend(structured_difference(before[index], after[index], child_path))
    elif type(before) is not type(after) or before != after:
        differences.append({'path': path, 'before_present': True, 'after_present': True, 'before': before, 'after': after,
            'before_type': type(before).__name__, 'after_type': type(after).__name__})
    return differences


def diagnose_schemas(module):
    # Collect every raw and encoded row before asserting any difference. This
    # path never classifies codec defaults or enters parity/Guest execution.
    source = schema_source.schemas(PACK, io)
    raw_differences = {node_id: structured_difference(FROZEN[node_id], source[node_id]) for node_id in FROZEN
        if structured_difference(FROZEN[node_id], source[node_id])}
    actual_rows = {}
    old_manifest_differences = {}
    for node_id, cls in module.NODE_CLASS_MAPPINGS.items():
        schema = cls.GET_SCHEMA()
        schema.validate()
        methods = {name: name in cls.__dict__ for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')}
        row = {'module': cls.__module__.removeprefix(module.__name__ + '.'), 'class': cls.__name__,
            'sdk_refs': True, 'permissions': list(cls.SDK_PERMISSIONS), 'methods': methods,
            'schema': packmanifest.encode_schema(schema)}
        if methods['validate_inputs']:
            row['validation_inputs'] = packmanifest.encode_validation_inputs(cls)
        actual_rows[node_id] = row
        differences = structured_difference(BASELINE['nodes'][node_id]['schema'], row['schema'])
        if differences:
            old_manifest_differences[node_id] = differences
    artifacts = {'source-schemas.json': source, 'source-schema-differences.json': raw_differences,
        'actual-encoded-rows.json': actual_rows, 'encoded-schema-differences.json': old_manifest_differences}
    hashes = {}
    for name, data in artifacts.items():
        text = json.dumps(data, indent=2, sort_keys=True) + '\n'
        (RESULTS / name).write_text(text)
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()
    RECEIPT['schema_diagnostic'] = {'raw_source_rows': len(source), 'actual_encoded_rows': len(actual_rows),
        'raw_source_difference_nodes': len(raw_differences), 'old_manifest_difference_nodes': len(old_manifest_differences),
        'old_manifest_difference_fields': sum(len(rows) for rows in old_manifest_differences.values()),
        'encoder': packmanifest.__file__, 'artifacts': hashes,
        'comparison_policy': 'Exact structured old-manifest schema comparison; no catalogue normalization, codec classification, or default waiver in this diagnostic.',
        'parity_cases': 0, 'guest_startups': 0}
    save()
    assert set(actual_rows) == set(source) == set(FROZEN) == set(BASELINE['nodes']) and len(actual_rows) == 85
    assert not raw_differences, f'Original raw schema differences: {list(raw_differences)}'
    assert not old_manifest_differences, f'Encoded schema diagnostic retained differences for {len(old_manifest_differences)} nodes'
    return RECEIPT['schema_diagnostic']


def encode_and_check(module):
    assert set(module.NODE_CLASS_MAPPINGS) == set(FROZEN) and len(FROZEN) == 85
    assert set(module.IMAGE_CLASS_MAPPINGS) == set(SELECTED)
    assert set(module.REFUSAL_CLASS_MAPPINGS) == set(FROZEN) - set(SELECTED)
    resize = module.NODE_CLASS_MAPPINGS['ImageResize+']
    assert resize is module.REFUSAL_CLASS_MAPPINGS['ImageResize+']
    assert resize.__module__ == module.__name__ + '._refusals'
    assert resize.SDK_PERMISSIONS == ()
    image_module = sys.modules[module.__name__ + '.image']
    assert all(cls is not image_module.ImageResize for cls in module.NODE_CLASS_MAPPINGS.values())
    source_schemas = schema_source.schemas(PACK, io)
    source_differences = {node_id: {'source': source_schemas[node_id], 'frozen': FROZEN[node_id]} for node_id in FROZEN if source_schemas[node_id] != FROZEN[node_id]}
    (RESULTS / 'source-schemas.json').write_text(json.dumps(source_schemas, indent=2, sort_keys=True) + '\n')
    (RESULTS / 'source-schema-differences.json').write_text(json.dumps(source_differences, indent=2, sort_keys=True) + '\n')
    assert not source_differences, f'Original schema drift: {list(source_differences)}'
    assert getattr(module, 'WEB_DIRECTORY', None) is None, 'legacy frontend must remain held'
    manifest = {'format': packmanifest.FORMAT, 'runtime': manifest_declaration(V2), 'nodes': {},
        'web_directory': getattr(module, 'WEB_DIRECTORY', None), 'frontend_permissions': []}
    validation_refusals = set()
    for node_id, cls in module.NODE_CLASS_MAPPINGS.items():
        schema = cls.GET_SCHEMA()
        schema.validate()
        encoded = packmanifest.encode_schema(schema)
        reference = BASELINE['nodes'][node_id]['schema']
        # The selected Core adds one sampler to three original dynamic schemas.
        # Invert exactly that independently source-proved addition, then require
        # every encoded field to match the retained old manifest byte-for-value.
        preserved = copy.deepcopy(encoded)
        assert 'loop_boundary' not in reference['attrs']
        assert 'loop_boundary' in preserved['attrs'] and preserved['attrs']['loop_boundary'] is None
        del preserved['attrs']['loop_boundary']
        choice = 'cfgpp_ud10_ab'
        combo_inputs = {'KSamplerVariationsStochastic+': 'sampler', 'KSamplerVariationsWithNoise+': 'sampler_name'}
        if node_id in combo_inputs:
            target = combo_inputs[node_id]
            new_input = next(row for row in preserved['inputs'] if row['attrs']['id'] == target)
            old_input = next(row for row in reference['inputs'] if row['attrs']['id'] == target)
            old_options = old_input['attrs']['options']
            position = old_options.index('deis') + 1
            assert new_input['attrs']['options'] == old_options[:position] + [choice] + old_options[position:]
            new_input['attrs']['options'].pop(position)
        elif node_id == 'SamplerSelectHelper+':
            old_inputs = reference['inputs']
            position = next(index for index, row in enumerate(old_inputs) if row['attrs']['id'] == 'deis') + 1
            added = copy.deepcopy(old_inputs[position - 1])
            assert added['io_type'] == 'BOOLEAN' and added['attrs']['default'] is False
            added['attrs']['id'] = choice
            assert preserved['inputs'] == old_inputs[:position] + [added] + old_inputs[position:]
            preserved['inputs'].pop(position)
        assert json.dumps(preserved, sort_keys=True, separators=(',', ':')) == json.dumps(reference, sort_keys=True, separators=(',', ':')), f'85-schema preservation drift beyond the verified catalogue/codec deltas: {node_id}'
        methods = {name: name in cls.__dict__ for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')}
        row = {'module': cls.__module__.removeprefix(module.__name__ + '.'), 'class': cls.__name__, 'sdk_refs': True,
            'permissions': list(cls.SDK_PERMISSIONS), 'methods': methods, 'schema': encoded}
        if methods['validate_inputs']:
            row['validation_inputs'] = packmanifest.encode_validation_inputs(cls)
            assert cls.validate_inputs() == f'comfyui_essentials/{node_id} is not yet converted to Secure Nodes V2'
            validation_refusals.add(node_id)
        manifest['nodes'][node_id] = row
    assert validation_refusals == set(FROZEN) - set(SELECTED) and len(validation_refusals) == 83
    assert manifest['nodes']['ImageResize+']['module'] == '_refusals'
    text = json.dumps(manifest, indent=2, sort_keys=True) + '\n'
    (RESULTS / 'secure-nodes.json').write_text(text)
    return {'registered': 85, 'source_schema_exact': 85, 'retained_manifest_schema_exact_after_verified_deltas': 85,
        'catalogue_unchanged_rows': 82, 'verified_host_codec_default': {'loop_boundary': None, 'rows': 85},
        'frontend_held': manifest['web_directory'] is None,
        'source_proved_core_catalogue_refresh': ['KSamplerVariationsStochastic+', 'KSamplerVariationsWithNoise+', 'SamplerSelectHelper+'],
        'bytes': len(text.encode()), 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'encoder': packmanifest.__file__,
        'unqualified_validation_refusals': len(validation_refusals), 'resize_registration': 'WHOLE_NODE_REFUSAL_ONLY'}


def plan_for(node_id, cls, fields, method='execute'):
    return sdk.ExecutionPlan(prompt_id='essentials-finite', node_id='17', node_type=cls.__name__,
        node_module=cls.__module__, inputs=fields, method=method, permissions=tuple(cls.SDK_PERMISSIONS))


async def in_runtime(plan, operation):
    refs = sdk.InProcessRefResolver()
    ctx = sdk.InProcessCtxProvider().build(plan)
    try:
        with sdk.bind_runtime(refs, ctx, sdk.InProcessOps()):
            return await operation(refs)
    finally:
        refs.clear()


async def verify_empty_boundary(originals, module):
    cases = [case for case in CASES if case['node'] == 'ImageResize+' and case['label'] == 'multiple/512']
    assert len(cases) == 1 and cases[0].get('public_boundary_refusal') is True
    fields = {key: fixture(value) for key, value in cases[0]['fields'].items()}
    expected = originals['ImageResize+']().execute(**fields)
    assert tuple(expected[0].shape) == (1, 0, 0, 3) and expected[1:] == (0, 0)
    source_path = BASE / 'comfy_api/latest/_sdk.py'
    source_text = source_path.read_text()
    tree = ast.parse(source_text)
    bounds = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_image_buffer_shape')
    message = 'IMAGE requires a bounded non-empty BHWC buffer with 1..4 channels'
    assert any(isinstance(node, ast.Constant) and node.value == message for node in ast.walk(bounds))
    assert any(isinstance(node, ast.Compare) and any(isinstance(operator, ast.Lt) for operator in node.ops)
        and any(isinstance(comparator, ast.Constant) and comparator.value == 1 for comparator in node.comparators)
        for node in ast.walk(bounds))
    from comfy_api.latest import sdk as public_sdk
    async def refused(refs):
        try:
            await public_sdk.ImageRef.from_value(expected[0])
        except ValueError as error:
            assert str(error) == message
            return
        raise AssertionError('selected public IMAGE factory accepted empty original output')
    cls = module.NODE_CLASS_MAPPINGS['ImageResize+']
    await in_runtime(plan_for('ImageResize+', cls, fields), refused)
    return {'case': 'ImageResize+/multiple/512', 'original_shape': list(expected[0].shape),
        'original_dtype': str(expected[0].dtype), 'original_stride': list(expected[0].stride()),
        'original_storage_offset': expected[0].storage_offset(), 'original_returned_dimensions': list(expected[1:]),
        'host_public_factory': 'ValueError: ' + message,
        'guest_base_factory_source': str(source_path), 'guest_base_factory_source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'guest_base_bounds_line': bounds.lineno, 'production_compute_changed': False}


async def read_outputs(output):
    values = []
    for value in output.args:
        if isinstance(value, sdk.TensorRef):
            assert value.kind == 'IMAGE', ('wrong wire kind', value.kind)
            values.append(await value.raw())
        else:
            values.append(value)
    assert output.ui is None
    return tuple(values)


async def compare(case, phase, module, originals, session=None, guest_classes=None):
    node_id = case['node']
    fields = {key: fixture(value) for key, value in case['fields'].items()}
    snapshots = {key: (str(value.dtype), tuple(value.shape), tuple(value.stride()), value.storage_offset(), tensor_bytes(value)) for key, value in fields.items() if isinstance(value, torch.Tensor)}
    expected, expected_error, engine_calls = baseline(node_id, fields, originals)
    cls = (guest_classes or module.NODE_CLASS_MAPPINGS)[node_id]
    named_refusal = bool(engine_calls) or case.get('public_boundary_refusal', False) and expected_error is None
    async def run(refs):
        wrapped = await sdk.wrap_inputs(refs, fields)
        for key, value in wrapped.items():
            if isinstance(fields[key], torch.Tensor):
                assert value.kind == 'IMAGE', (key, 'input kind', value.kind)
        try:
            if session is None:
                got = await cls.execute(**wrapped)
            else:
                got = await session.execute(plan_for(node_id, cls, wrapped), sdk.current_runtime(), capabilities=tuple(cls.SDK_PERMISSIONS), tenant='essentials-finite')
                assert session.last_guest_pid != os.getpid()
                RECEIPT['guest_pid'] = session.last_guest_pid
            if named_refusal:
                raise AssertionError('documented unsupported branch returned successfully')
            if expected_error:
                raise AssertionError(f'original raised {type(expected_error).__name__}: {expected_error}; conversion returned')
            values = await read_outputs(got)
            if case.get('identity'):
                assert got.args[0].kind == 'IMAGE'
                assert got.args[0].id == wrapped['image_1'].id, 'no-op lost host-issued ref identity'
                assert values[0] is fields['image_1'], 'no-op lost host tensor identity'
            equivalent(values, expected)
            return 'EXACT'
        except Exception as error:
            name, message = type(error).__name__, str(error)
            if isinstance(error, wire.WireError):
                name, message = getattr(error, 'remote_type', name), getattr(error, 'remote_message', message)
            if named_refusal:
                assert name == 'EssentialsPurposeRefusal', (name, message)
                assert f'comfyui_essentials/{node_id}' in message, message
                if engine_calls:
                    assert ('lanczos' in message if node_id == 'ImageResize+' else 'common_upscale' in message), message
                else:
                    assert 'public IMAGE boundary' in message, message
                return 'REFUSED-AS-DESIGNED'
            if expected_error is not None:
                assert name == type(expected_error).__name__ and message == str(expected_error), (name, message, type(expected_error).__name__, str(expected_error))
                return 'EXACT-ERROR'
            raise
    verdict = await in_runtime(plan_for(node_id, cls, fields), run)
    for key, before in snapshots.items():
        value = fields[key]
        assert before == (str(value.dtype), tuple(value.shape), tuple(value.stride()), value.storage_offset(), tensor_bytes(value)), f'input mutated: {key}'
    return verdict


class LockedSession(GuestSession):
    def _guest_command(self, python):
        return [python, '/tests/_essentials_guest_entry.py']

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env['COMFY_GUEST_API_ROOT'] = str(BASE / 'comfy_api')
        env['ESSENTIALS_GUARD_ROOT'] = str(self.guest_runtime_root)
        env['ESSENTIALS_GUARD_NAMESPACE'] = GUEST_NAMESPACE
        env['ESSENTIALS_GUARD_DENIALS'] = '/results/guest-import-denials.jsonl'
        env['ESSENTIALS_GUARD_REPORT'] = '/results/guest-import-guard.json'


PROBE = '''from comfy_api.latest import io, sdk
from .image import NODE_CLASS_MAPPINGS as images
from ._refusals import NODE_CLASS_MAPPINGS as refusals
class SchemaProbe(io.ComfyNode):
 SDK_REFS = True
 SDK_PERMISSIONS = ()
 @classmethod
 async def execute(cls, **kwargs):
  assert set(images) == {'ImageBatchMultiple+', 'GetImageSize+'}
  assert len(refusals) == 83 and 'ImageResize+' in refusals
  assert refusals['ImageResize+'].__module__.endswith('._refusals')
  for node_id, node in refusals.items():
   assert node.validate_inputs() == f'comfyui_essentials/{node_id} is not yet converted to Secure Nodes V2'
  for node in {**images, **refusals}.values():
   node.GET_SCHEMA().validate()
  return io.NodeOutput(len(images) + len(refusals), sdk.__file__)
class ImportProbe(io.ComfyNode):
 SDK_REFS = True
 SDK_PERMISSIONS = ()
 @classmethod
 async def execute(cls, **kwargs):
  import scipy
  return io.NodeOutput()
'''


async def guest_probe(session, cls, expected_denial=False):
    async def call(refs):
        try:
            output = await session.execute(plan_for(cls.__name__, cls, {}), sdk.current_runtime(), capabilities=(), tenant='essentials-finite')
        except wire.WireError as error:
            if expected_denial:
                assert error.remote_type == 'ModuleNotFoundError' and "sealed guest lock excludes 'scipy'" in error.remote_message
                return 'DENIED'
            raise
        assert not expected_denial, 'undeclared import escaped child guard'
        assert output.args[0] == 85 and str(output.args[1]).startswith(str(BASE))
        return '85_SCHEMAS_VALIDATED_ON_SELECTED_GUEST_BASE'
    return await in_runtime(plan_for(cls.__name__, cls, {}), call)


async def phase_cases(phase, module, originals, session=None, classes=None):
    selected_cases = list(enumerate(CASES))
    if FOCUSED_GUEST:
        selected_cases = [(index, case) for index, case in selected_cases if case['node'] in FOCUSED_GUEST_NODES]
        assert phase == 'guest' and len(selected_cases) == 118
    if OPTIONS.negative_control:
        selected_cases = [(index, case) for index, case in selected_cases if index == NEGATIVE_CASE_INDEX]
        assert len(selected_cases) == 1
    for index, case in selected_cases:
        key = phase + '/' + case['node']
        row = RECEIPT['nodes'].setdefault(key, {})
        try:
            verdict = await compare(case, phase, module, originals, session, classes)
            row[verdict] = row.get(verdict, 0) + 1
        except Exception as error:
            row['MISMATCH'] = row.get('MISMATCH', 0) + 1
            RECEIPT['failures'].append({'phase': phase, 'index': index, 'node': case['node'], 'label': case['label'],
                'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc(),
                'guest_stderr': session.last_stderr if session else None})
            save()
            if OPTIONS.negative_control:
                RECEIPT['negative_control_observed'] = (
                    phase == 'guest' and isinstance(error, AssertionError) and str(error) == "('result/0', 'bytes')"
                    and RECEIPT.get('guest_pid') not in (None, os.getpid())
                )
                raise
            if len(RECEIPT['failures']) >= 8:
                raise AssertionError('finite stop after eight mismatches')


async def main():
    guest_temp_root = None
    for root in (PACK, V2):
        files = [path for path in root.rglob('*.py') if root != PACK or not path.is_relative_to(V2)]
        for path in files: compile(path.read_bytes(), str(path), 'exec')
        RECEIPT['compile_' + ('original' if root == PACK else 'v2')] = len(files)
    denials = []
    metadata, active, restore = guest_lock.install(V2, 'essentials_recovery_default', denials.append)
    try:
        module = import_v2()
        if OPTIONS.phase == 'schemas':
            RECEIPT['schemas'] = diagnose_schemas(module)
            active()
            assert not denials, denials
            RECEIPT['status'] = 'PASS'
            return
        RECEIPT['schemas'] = encode_and_check(module)
        RECEIPT['default_import_guard'] = metadata
        originals = original_classes()
        RECEIPT['byte_reader_controls'] = byte_reader_checks.run_checks(tensor_bytes, fixture)
        if OPTIONS.phase in ('all', 'default'):
            await phase_cases('default', module, originals)
            active()
            assert not denials, denials
        if OPTIONS.phase in ('all', 'guest', 'guest-batch-size'):
            with tempfile.TemporaryDirectory(prefix='essentials-qualified-') as temp:
                root = Path(temp) / 'v2'
                guest_temp_root = root
                shutil.copytree(V2, root)
                if OPTIONS.negative_control:
                    mutant = Path('/tests/negative-overlay/image.py')
                    shutil.copyfile(mutant, root / 'image.py')
                    RECEIPT['negative_control_overlay'] = {
                        'classification': 'actual Guest wrong-output witness; no host output mutation',
                        'source': str(mutant), 'sha256': hashlib.sha256(mutant.read_bytes()).hexdigest(),
                        'node': 'ImageBatchMultiple+', 'case_index': NEGATIVE_CASE_INDEX,
                        'expected_assertion': "('result/0', 'bytes')", 'publishing_assembly_modified': False,
                    }
                (root / '__init__.py').write_text("raise AssertionError('package __init__ executed in namespace guest')\n")
                (root / '_qualification_probe.py').write_text(PROBE)
                classes = {}
                for node_id in FROZEN:
                    relative = 'image' if node_id in SELECTED else '_refusals'
                    loaded = packdb.load(GUEST_NAMESPACE, root, relative)
                    classes[node_id] = getattr(loaded, FROZEN[node_id]['class'])
                probes = packdb.load(GUEST_NAMESPACE, root, '_qualification_probe')
                session = await asyncio.wait_for(LockedSession('essentials-finite', guest_runtime_root=root).start(), 45)
                try:
                    RECEIPT['sandbox_kind'] = session.sandbox_kind
                    RECEIPT['namespace_init_sentinel'] = True
                    RECEIPT['guest_schemas'] = await guest_probe(session, probes.SchemaProbe)
                    RECEIPT['guest_import_control_before'] = await guest_probe(session, probes.ImportProbe, True)
                    await phase_cases('guest', module, originals, session, classes)
                    execution_refusals = 0
                    for node_id, cls in classes.items():
                        if node_id in SELECTED: continue
                        async def refused(refs):
                            try:
                                await session.execute(plan_for(node_id, cls, {}), sdk.current_runtime(), capabilities=(), tenant='essentials-finite')
                            except wire.WireError as error:
                                assert error.remote_type == 'EssentialsPurposeRefusal'
                                assert error.remote_message == f'comfyui_essentials/{node_id} is not yet converted to Secure Nodes V2'
                                return
                            raise AssertionError(f'unqualified node executed: {node_id}')
                        await in_runtime(plan_for(node_id, cls, {}), refused)
                        execution_refusals += 1
                    assert execution_refusals == 83
                    RECEIPT['guest_unqualified_execution_refusals'] = execution_refusals
                    RECEIPT['guest_import_control_after'] = await guest_probe(session, probes.ImportProbe, True)
                    RECEIPT['guest_pid'] = session.last_guest_pid
                    assert session.last_guest_pid != os.getpid()
                    report = json.loads((RESULTS / 'guest-import-guard.json').read_text())
                    assert report['pid'] == session.last_guest_pid and report['lock_sha256'] == metadata['lock_sha256']
                    assert report['sdk_file'].startswith(str(BASE))
                    RECEIPT['guest_guard'] = report
                finally:
                    await session.kill()
                    RECEIPT['guest_killed'] = True
            RECEIPT['temporary_namespace_removed'] = not root.exists()
        active()
        RECEIPT['status'] = 'PASS' if not RECEIPT['failures'] else 'FAIL'
    finally:
        if guest_temp_root is not None:
            RECEIPT['temporary_namespace_removed'] = not guest_temp_root.exists()
        restore()


try:
    asyncio.run(main())
except BaseException as error:
    RECEIPT['status'] = 'FAIL'
    RECEIPT['terminal_error'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
finally:
    signal.alarm(0)
    save()
    print(json.dumps({key: value for key, value in RECEIPT.items() if key not in {'failures', 'default_import_guard', 'guest_guard'}}, indent=2, sort_keys=True), flush=True)
if RECEIPT['status'] != 'PASS':
    raise SystemExit(1)
