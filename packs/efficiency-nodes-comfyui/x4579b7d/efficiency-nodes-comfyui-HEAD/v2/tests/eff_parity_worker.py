"""One side of the efficiency-nodes-comfyui repair-round parity run (to-50% gate container only).

argv: SIDE CASES_JSON OUT_DIR FIXTURES_DIR      SIDE = original | v2

Every case's prompt runs through ComfyUI's real PromptExecutor (core 6257422b at /core, the engine_commit of the
live V2 deployment) with the pack loaded as a custom node: the pristine pack copied to
<OUT>/nodes-root/custom_nodes/efficiency-nodes-comfyui, or /pack/v2 read-only.

Harness facts, both sides:
  * server.PromptServer.instance is a stand-in: an original pack may register HTTP routes and on-prompt handlers at
    import. Routes and handlers are recorded, never served; send_sync is recorded.
  * Test-only nodes (AMY*) produce inputs and probe outputs; core's PreviewAny, ImageBatch, SaveImage and
    EmptyLatentImage are the real ones.
V2 side only:
  * The live guest calls execute without core's hidden holder, so the harness clears cls.hidden before each V2 node's
    execute (hidden values such as UNIQUE_ID never reach a V2 node live).
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
for key, exts in (('checkpoints', {'.safetensors'}), ('loras', {'.safetensors', '.pt'}),
                  ('upscale_models', {'.safetensors'}), ('controlnet', {'.safetensors'}),
                  ('easy_wildcards', {'.txt', '.yaml', '.yml', '.json'})):
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
    if hasattr(value, 'patch_records'):  # LoRA stand-ins: every patch core's loader added, and attachments
        return {'object': type(value).__name__, 'patches': _summary(value.patch_records, depth + 1),
                'attachments': _summary(value.attachments, depth + 1)}
    if hasattr(value, 'weights') and type(value).__module__.startswith('comfy.weight_adapter'):
        return {'adapter': type(value).__name__, 'weights': _summary(list(value.weights), depth + 1)}
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
    """Weightless VAE: the SDK recognises a VAE by encode + decode. encode() is a deterministic, shape- and
    pixel-sensitive stand-in (8x8 mean pool of the RGB channels plus their channel mean), so a different crop,
    channel count or pixel value shows up in the latent."""
    def encode(self, pixels):
        x = pixels.movedim(-1, 1).float()
        pooled = torch.nn.functional.avg_pool2d(x, 8)
        return torch.cat([pooled, pooled.mean(dim=1, keepdim=True)], dim=1)

    def decode(self, samples):
        return samples


# ---- LoRA stand-ins: core's comfy.sd.load_lora_for_models runs for real on both sides; the MODEL and CLIP record
# every patch it adds (keys, strengths, adapter weights) and every attachment, so a different LoRA, strength or order
# shows up in the probe.
import comfy.lora  # noqa: E402

LORA_KEY_MAPS = {
    'unet': {'lora_unet_input_blocks_0_0': 'diffusion_model.input_blocks.0.0.weight',
             'lora_unet_middle_block_1_proj_in': 'diffusion_model.middle_block.1.proj_in.weight'},
    'clip': {'lora_te_text_model_encoder_layers_0_mlp_fc1': 'clip_l.transformer.text_model.encoder.layers.0.mlp.fc1.weight'},
}


class _LoraRecorder:
    def _init_records(self, records=None, attachments=None):
        self.patch_records = list(records or [])
        self.attachments = dict(attachments or {})

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0):
        self.patch_records.append({'keys': sorted(patches), 'strength_patch': strength_patch,
                                   'strength_model': strength_model, 'patches': dict(sorted(patches.items()))})
        return list(patches)

    def set_attachments(self, key, value):
        self.attachments[key] = value


class LoraModel(_LoraRecorder):
    """A MODEL as LoRA loaders use it (model_options + load_device make it a ModelPatcher to the SDK)."""

    def __init__(self, records=None, attachments=None):
        self.model = types.SimpleNamespace(amy_lora_keys=LORA_KEY_MAPS['unet'])
        self.model_options = {}
        self.load_device = 'cpu'
        self._init_records(records, attachments)

    def clone(self):
        return LoraModel(self.patch_records, self.attachments)


class _LoraClipPatcher:
    def __init__(self, owner):
        self.owner = owner
        self.forced_hooks = None

    def set_attachments(self, key, value):
        self.owner.attachments[key] = value


class LoraClip(_LoraRecorder):
    """A CLIP as LoRA loaders use it (tokenize makes it a CLIP to the SDK)."""

    def __init__(self, records=None, attachments=None):
        self.cond_stage_model = types.SimpleNamespace(amy_lora_keys=LORA_KEY_MAPS['clip'])
        self.patcher = _LoraClipPatcher(self)
        self._init_records(records, attachments)

    def tokenize(self, text, **kwargs):
        return {}

    def clone(self):
        return LoraClip(self.patch_records, self.attachments)


def _key_map_unet(model, key_map={}):
    key_map = dict(key_map)
    key_map.update(getattr(model, 'amy_lora_keys', {}))
    return key_map


def _key_map_clip(cond_stage_model, key_map={}):
    key_map = dict(key_map)
    key_map.update(getattr(cond_stage_model, 'amy_lora_keys', {}))
    return key_map


comfy.lora.model_lora_keys_unet = _key_map_unet
comfy.lora.model_lora_keys_clip = _key_map_clip


def _cond(seed):
    generator = torch.Generator().manual_seed(seed)
    return [[torch.rand((1, 4, 8), generator=generator), {'pooled_output': torch.rand((1, 8), generator=generator)}]]


ANY = '*'
STANDINS = {
    'AMYLoraModelClip': _standin('AMYLoraModelClip', lambda self: (LoraModel(), LoraClip()), lambda: {'required': {}},
                                 ('MODEL', 'CLIP')),
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
    pack_dir = OUT / 'nodes-root' / 'custom_nodes' / 'efficiency-nodes-comfyui'
    shutil.copytree('/pack', pack_dir, ignore=shutil.ignore_patterns('v2'))
    pack_path = str(pack_dir)
else:
    pack_path = '/pack/v2'
LOAD_ERROR = None
try:
    loaded = asyncio.run(core_nodes.load_custom_node(pack_path, ignore=set(), module_parent='custom_nodes'))
except Exception as error:  # recorded, never hidden
    loaded, LOAD_ERROR = False, f'{type(error).__name__}: {error}'

# ---- the live host's catalogue menus, V2 side
# The live host builds each V2 node's schema from the manifest and then fills its model and input menus with the
# host catalogue (overlay comfy_secure_nodes/packdb.py: define_schema -> _core_model_menu_choices ->
# _core_input_menu_choices); frozen model combos can be empty sentinel lists until then. The in-process
# loader skips that host step, so the harness applies the overlay's own two functions to every V2 node's schema.
HOST_MENUS = None
if SIDE == 'v2' and loaded:
    sys.path.insert(0, '/overlay')
    try:
        from comfy_secure_nodes import packdb as overlay_packdb
    except Exception as error:  # recorded, never hidden
        HOST_MENUS = f'unavailable: {type(error).__name__}: {error}'
    else:
        wrapped = 0
        for node_id, cls in list(core_nodes.NODE_CLASS_MAPPINGS.items()):
            if not getattr(cls, 'SDK_REFS', False) or '_secure_nodes' not in getattr(cls, '__module__', ''):
                continue
            base = cls.__dict__['define_schema'].__func__

            def define_schema(klass, _base=base):
                schema = _base(klass)
                schema = overlay_packdb._core_model_menu_choices(schema, klass.SDK_PERMISSIONS)
                return overlay_packdb._core_input_menu_choices(schema, klass.SDK_PERMISSIONS)

            cls.define_schema = classmethod(define_schema)
            wrapped += 1
        HOST_MENUS = f'overlay packdb._core_model_menu_choices + _core_input_menu_choices on {wrapped} V2 nodes'

# ---- the guest's call shape, V2 side
# The live guest calls a V2 node's execute on the pack's own class (overlay guest/adapter.py invoke ->
# entry_point -> cls.execute(**inputs)), without core's hidden holder, so the node sees cls.hidden as None there.
# Core's in-process executor fills cls.hidden on a locked per-call class clone instead; the harness runs the node's own
# execute on a subclass of that clone whose hidden is None, so hidden values reach V2 exactly as they do live (not at
# all).
GUEST_HIDDEN = None
if SIDE == 'v2' and loaded:
    cleared = 0
    for node_id, cls in list(core_nodes.NODE_CLASS_MAPPINGS.items()):
        if not getattr(cls, 'SDK_REFS', False) or '_secure_nodes' not in getattr(cls, '__module__', ''):
            continue
        node_execute = cls.__dict__['execute'].__func__

        async def execute(klass, _node_execute=node_execute, **kwargs):
            guest_class = type(klass.__name__, (klass,), {'hidden': None})
            return await _node_execute(guest_class, **kwargs)

        cls.execute = classmethod(execute)
        cleared += 1
    GUEST_HIDDEN = f'execute runs with hidden None on {cleared} V2 nodes (live guest call shape)'


class Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None

    def send_sync(self, event, data, sid=None):
        SENT.append([event, json.loads(json.dumps(data, default=str))])


def describe_file(path):
    data = path.read_bytes()
    root = OUT / ('temp' if (OUT / 'temp') in path.parents else 'output')
    row = {'path': f'{root.name}/{path.relative_to(root)}', 'sha256': hashlib.sha256(data).hexdigest(),
           'bytes': len(data)}
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
        before = {p for root in ('output', 'temp') for p in (OUT / root).rglob('*') if p.is_file()}
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
        files = sorted((p for root in ('output', 'temp') for p in (OUT / root).rglob('*')
                        if p.is_file() and p not in before), key=str)
        result['runs'].append({'success': bool(executor.success), 'errors': errors,
                               'ui': json.loads(json.dumps(history.get('outputs', {}), default=str)),
                               'files': [describe_file(p) for p in files],
                               'sent': [row for row in SENT if row[0] not in ('progress', 'executing')]})
    return result


def main():
    cases = json.loads(Path(CASES).read_text())
    report = {'side': SIDE, 'loaded': bool(loaded), 'load_error': LOAD_ERROR, 'pack_path': pack_path,
              'output_dir': str(OUT / 'output'), 'host_menus': HOST_MENUS, 'guest_hidden': GUEST_HIDDEN,
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
