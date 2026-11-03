"""One side of the comfyui-easy-use repair-round parity run (to-50% gate container only).

argv: SIDE CASES_JSON OUT_DIR FIXTURES_DIR      SIDE = original | v2

Every case's prompt runs through ComfyUI's real PromptExecutor (core 6257422b at /core, the engine_commit of the
live V2 deployment) with the pack loaded as a custom node: the pristine pack copied to
<OUT>/nodes-root/custom_nodes/ComfyUI-Easy-Use (with /deps, pinned wheels, on sys.path), or /pack/v2 read-only.

Harness facts, both sides:
  * server.PromptServer.instance is a stand-in: the original registers HTTP routes and an on-prompt handler at
    import (py/routes.py, py/server.py:170). Routes and handlers are recorded, never served; send_sync is recorded.
  * Test-only nodes (AMY*) produce inputs and probe outputs; core's PreviewAny, ImageBatch, SaveImage and
    EmptyLatentImage are the real ones.
V2 side only:
  * The live runtime runs V2 nodes out of process: each result and UI crosses the guest wire, whose encoder refuses
    anything but refs, JSON scalars and containers (overlay comfy_secure_nodes/transport/wire.py encode()). The
    in-process SDK of core never encodes, so the harness runs that same encode() (loaded read-only from the overlay
    mount) on every V2 node's results and UI before core resolves them (_sdk.unwrap_outputs). A value the live
    wire refuses fails here with the live error.
"""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import types

SIDE, CASES, OUT, FIXTURES = sys.argv[1:5]
OUT = Path(OUT)
sys.path[:0] = ['/core']
if SIDE == 'original' and os.path.isdir('/deps'):
    sys.path.append('/deps')
sys.argv = ['main.py', '--cpu']

import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import torch  # noqa: E402
torch.set_num_threads(1)
import folder_paths  # noqa: E402

for name, setter in (('output', folder_paths.set_output_directory), ('temp', folder_paths.set_temp_directory),
                     ('input', folder_paths.set_input_directory), ('user', folder_paths.set_user_directory)):
    (OUT / name).mkdir(parents=True, exist_ok=True)
    setter(str(OUT / name))
for key, exts in (('checkpoints', {'.safetensors'}), ('loras', {'.safetensors', '.pt'})):
    folder_paths.folder_names_and_paths[key] = ([str(Path(FIXTURES) / key)], exts)
CWD = OUT / 'cwd'
CWD.mkdir(parents=True, exist_ok=True)
os.chdir(CWD)

# ---- PromptServer stand-in (the original registers routes and an on-prompt handler at import)
from aiohttp import web  # noqa: E402
import server  # noqa: E402

SENT = []


class StubPromptServer:
    def __init__(self):
        self.routes = web.RouteTableDef()
        self.client_id = None
        self.last_node_id = None
        self.on_prompt_handlers = []
        self.supports = []

    def send_sync(self, event, data, sid=None):
        SENT.append([event, json.loads(json.dumps(data, default=str))])

    def add_on_prompt_handler(self, handler):
        self.on_prompt_handlers.append(handler)

    def __getattr__(self, name):  # anything else the pack touches at import
        raise AttributeError(f'harness PromptServer stand-in has no {name}')


server.PromptServer.instance = StubPromptServer()

import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402
from comfy_extras.nodes_preview_any import PreviewAny  # noqa: E402

core_nodes.NODE_CLASS_MAPPINGS['PreviewAny'] = PreviewAny


# ---- test-only nodes
def _summary(value, depth=0):
    """Deterministic, comparable description of any value a node returns."""
    if isinstance(value, torch.Tensor):
        data = value.detach().contiguous().cpu()
        return {'tensor': list(data.shape), 'dtype': str(data.dtype),
                'sha256': hashlib.sha256(data.numpy().tobytes()).hexdigest()}
    if isinstance(value, dict):
        return {'dict': {str(k): _summary(v, depth + 1) for k, v in value.items()}}
    if isinstance(value, (list, tuple)):
        return {type(value).__name__: [_summary(v, depth + 1) for v in value]}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return {type(value).__name__: value}
    return {'object': type(value).__name__}


def _standin(name, run, input_types, return_types, output_node=False, output_is_list=None, input_is_list=False):
    attrs = {'INPUT_TYPES': classmethod(lambda cls: input_types()), 'RETURN_TYPES': return_types,
             'FUNCTION': 'run', 'CATEGORY': 'amy-test', 'run': run, 'OUTPUT_NODE': output_node,
             'INPUT_IS_LIST': input_is_list}
    if output_is_list is not None:
        attrs['OUTPUT_IS_LIST'] = output_is_list
    return type(f'AMYStandin_{name}', (), attrs)


def _image(width, height, batch, seed, channels=3):
    generator = torch.Generator().manual_seed(seed)
    return torch.rand((batch, height, width, channels), generator=generator, dtype=torch.float32)


def _probe(self, label, value=None, after=None):
    items = value if isinstance(value, list) else [value]
    return {'ui': {'probe': [json.dumps({'label': label[0] if isinstance(label, list) else label,
                                         'items': [_summary(item) for item in items]}, sort_keys=True)]}}


class StandinModel:
    """Weightless MODEL: the SDK recognises a ModelPatcher by model_options + load_device."""
    def __init__(self):
        self.model_options = {}
        self.load_device = 'cpu'


class StandinCLIP:
    """Weightless CLIP: the SDK recognises a CLIP by tokenize/encode_from_tokens."""
    def tokenize(self, text):
        return {}


class StandinVAE:
    """Weightless VAE: the SDK recognises a VAE by encode + decode."""
    def encode(self, pixels):
        return pixels

    def decode(self, samples):
        return samples


def _cond(seed):
    generator = torch.Generator().manual_seed(seed)
    return [[torch.rand((1, 4, 8), generator=generator), {'pooled_output': torch.rand((1, 8), generator=generator)}]]


ANY = '*'
STANDINS = {
    'AMYTestModel': _standin('AMYTestModel', lambda self: (StandinModel(),), lambda: {'required': {}}, ('MODEL',)),
    'AMYTestClip': _standin('AMYTestClip', lambda self: (StandinCLIP(),), lambda: {'required': {}}, ('CLIP',)),
    'AMYTestVAE': _standin('AMYTestVAE', lambda self: (StandinVAE(),), lambda: {'required': {}}, ('VAE',)),
    'AMYTestCond': _standin('AMYTestCond', lambda self, seed: (_cond(seed),),
                            lambda: {'required': {'seed': ('INT', {'default': 0})}}, ('CONDITIONING',)),
    'AMYTestString': _standin('AMYTestString', lambda self, text: (text,),
                              lambda: {'required': {'text': ('STRING', {'default': '', 'multiline': True})}},
                              ('STRING',)),
    'AMYTestJSON': _standin('AMYTestJSON', lambda self, text: (json.loads(text),),
                            lambda: {'required': {'text': ('STRING', {'default': 'null', 'multiline': True})}},
                            (ANY,)),
    'AMYTestList': _standin('AMYTestList', lambda self, text: (json.loads(text),),
                            lambda: {'required': {'text': ('STRING', {'default': '[]', 'multiline': True})}},
                            (ANY,), output_is_list=(True,)),
    'AMYTestImage': _standin('AMYTestImage', lambda self, width, height, batch, seed, after=None:
                             (_image(width, height, batch, seed),),
                             lambda: {'required': {'width': ('INT', {'default': 16}), 'height': ('INT', {'default': 12}),
                                                   'batch': ('INT', {'default': 1}), 'seed': ('INT', {'default': 0})},
                                      'optional': {'after': (ANY,)}},
                             ('IMAGE',)),
    'AMYTestImageList': _standin('AMYTestImageList', lambda self, count, seed:
                                 ([_image(8 + i, 6, 1, seed + i) for i in range(count)],),
                                 lambda: {'required': {'count': ('INT', {'default': 3}), 'seed': ('INT', {'default': 0})}},
                                 ('IMAGE',), output_is_list=(True,)),
    'AMYTestMask': _standin('AMYTestMask', lambda self, width, height, batch, seed:
                            (_image(width, height, batch, seed)[..., 0],),
                            lambda: {'required': {'width': ('INT', {'default': 16}), 'height': ('INT', {'default': 12}),
                                                  'batch': ('INT', {'default': 2}), 'seed': ('INT', {'default': 0})}},
                            ('MASK',)),
    'AMYProbe': _standin('AMYProbe', _probe,
                         lambda: {'required': {'label': ('STRING', {'default': ''})},
                                  'optional': {'value': (ANY,), 'after': (ANY,)}},
                         (), output_node=True, input_is_list=True),
}
core_nodes.NODE_CLASS_MAPPINGS.update(STANDINS)

# ---- the live guest wire, V2 side
WIRE = None
if SIDE == 'v2':
    from comfy_api.latest import _sdk as comfy_sdk
    spec = importlib.util.spec_from_file_location('amy_overlay_wire',
                                                  '/overlay/comfy_secure_nodes/transport/wire.py')
    WIRE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(WIRE)
    _unwrap_outputs = comfy_sdk.unwrap_outputs

    async def unwrap_outputs_across_wire(resolver, node_output):
        if getattr(node_output, 'result', None):
            WIRE.encode(list(node_output.result), preserve_tuples=True)
        if getattr(node_output, 'ui', None) is not None:
            WIRE.encode(node_output.ui, preserve_tuples=True)
        return await _unwrap_outputs(resolver, node_output)

    comfy_sdk.unwrap_outputs = unwrap_outputs_across_wire

# ---- load the pack under test
if SIDE == 'original':
    pack_dir = OUT / 'nodes-root' / 'custom_nodes' / 'ComfyUI-Easy-Use'
    shutil.copytree('/pack', pack_dir, ignore=shutil.ignore_patterns('v2'))
    pack_path = str(pack_dir)
else:
    pack_path = '/pack/v2'
LOAD_ERROR = None
try:
    loaded = asyncio.run(core_nodes.load_custom_node(pack_path, ignore=set(), module_parent='custom_nodes'))
except Exception as error:  # recorded, never hidden
    loaded, LOAD_ERROR = False, f'{type(error).__name__}: {error}'


class Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None

    def send_sync(self, event, data, sid=None):
        SENT.append([event, json.loads(json.dumps(data, default=str))])


def describe_file(path):
    data = path.read_bytes()
    row = {'path': str(path.relative_to(OUT / 'output')), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    if path.suffix.lower() == '.png':
        from PIL import Image
        import numpy as np
        with Image.open(path) as im:
            row.update({'size': list(im.size), 'mode': im.mode, 'text': dict(getattr(im, 'text', {}) or {}),
                        'pixels_sha256': hashlib.sha256(np.asarray(im.convert('RGBA')).tobytes()).hexdigest()})
    return row


def run_case(case):
    result = {'name': case['name'], 'runs': []}
    for index in range(case.get('runs', 1)):
        torch.manual_seed(20261102)
        prompt = json.loads(json.dumps(case['prompt']))
        prompt_id = f"{case['name']}-{index}"
        before = {p for p in (OUT / 'output').rglob('*') if p.is_file()}
        SENT.clear()
        valid = asyncio.run(execution.validate_prompt(prompt_id, prompt, None))
        if not valid[0]:
            result['runs'].append({'validation_error': json.loads(json.dumps(valid[1], default=str)),
                                   'node_errors': json.loads(json.dumps(valid[3], default=str))})
            continue
        executor = execution.PromptExecutor(Server(), cache_type=execution.CacheType.CLASSIC,
                                            cache_args={'lru': 0, 'ram': 0, 'ram_inactive': 0})
        extra = {'extra_pnginfo': case['extra_pnginfo']} if case.get('extra_pnginfo') else {}
        executor.execute(prompt, prompt_id, json.loads(json.dumps(extra)), valid[2])
        errors = []
        for event, data in executor.status_messages:
            if event == 'execution_error':
                errors.append({'node_id': data.get('node_id'), 'node_type': data.get('node_type'),
                               'exception_type': data.get('exception_type'),
                               'exception_message': data.get('exception_message'),
                               'traceback_tail': ''.join(data.get('traceback') or [])[-1500:]})
        history = getattr(executor, 'history_result', None) or {}
        files = sorted((p for p in (OUT / 'output').rglob('*') if p.is_file() and p not in before), key=str)
        result['runs'].append({'success': bool(executor.success), 'errors': errors,
                               'ui': json.loads(json.dumps(history.get('outputs', {}), default=str)),
                               'files': [describe_file(p) for p in files],
                               'sent': [row for row in SENT if row[0] not in ('progress', 'executing')]})
    return result


def main():
    cases = json.loads(Path(CASES).read_text())
    report = {'side': SIDE, 'loaded': bool(loaded), 'load_error': LOAD_ERROR, 'pack_path': pack_path,
              'output_dir': str(OUT / 'output'),
              'wire': None if WIRE is None else '/overlay/comfy_secure_nodes/transport/wire.py encode()',
              'routes': len(server.PromptServer.instance.routes), 'cases': []}
    if loaded:
        for case in cases:
            try:
                report['cases'].append(run_case(case))
            except Exception as error:  # a harness failure is recorded, never hidden
                import traceback
                report['cases'].append({'name': case['name'], 'harness_error': f'{type(error).__name__}: {error}',
                                        'traceback': traceback.format_exc()[-3000:]})
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str) + '\n')


main()
