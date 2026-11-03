"""One side of the weilin-comfyui-tools parity run (gate container only).

argv: SIDE CASES_JSON OUT_DIR FIXTURES_DIR      SIDE = original | v2

Every case's prompt runs through ComfyUI's real PromptExecutor (core 6257422b at /core) with the pack
loaded as a custom node: the pristine pack copied to <OUT>/nodes-root/custom_nodes/weilin-comfyui-tools,
or /pack/v2 read-only.

The original's __init__.py runs two import-time side effects that the gate must not run, so the harness
registers stand-in modules for them before loading the pristine pack (HARNESS_STUBS below):
  .install_request            install_requirements() -> no-op (the original pip-installs missing requirements)
  .app.server.prompt_server   HTTP routes, a local database and a worker for its web editor; the node code
                              takes only folder_paths and go_run_node_auto_random_tag from it. The stand-in
                              returns "" from go_run_node_auto_random_tag, which is what the real function
                              returns when the named template file does not exist (prompt_server.py:1474-1479).
The node classes, their helpers and app/server/prompt_api/trigger_words.py run unmodified.

MODEL and CLIP are stand-ins (no weights): the CLIP is a comfy.sd.CLIP whose tokenizer is the real SD1
tokenizer and whose encode_from_tokens is deterministic, so core's encode_from_tokens_scheduled
(comfy/sd.py:340-350) runs for real; MODEL/CLIP clone() and add_patches() record every LoRA patch
comfy.lora.load_lora builds (the LoRA key maps of the stand-ins come from LORA_KEY_MAPS). An AMYProbe
output node reports the resulting text, conditioning tensors, patches and attachments as its UI.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import types

SIDE, CASES, OUT, FIXTURES = sys.argv[1:5]
OUT = Path(OUT)
sys.path[:0] = ['/core']
sys.argv = ['main.py', '--cpu']

import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import torch  # noqa: E402
torch.set_num_threads(1)
import folder_paths  # noqa: E402

for name, setter in (('output', folder_paths.set_output_directory), ('temp', folder_paths.set_temp_directory),
                     ('input', folder_paths.set_input_directory)):
    (OUT / name).mkdir(parents=True, exist_ok=True)
    setter(str(OUT / name))
for key, exts in (('checkpoints', {'.safetensors'}), ('loras', {'.safetensors', '.pt'})):
    folder_paths.folder_names_and_paths[key] = ([str(Path(FIXTURES) / key)], exts)
CWD = OUT / 'cwd'
CWD.mkdir(parents=True, exist_ok=True)
os.chdir(CWD)  # the original's trigger-word cache file is ./loras_tags.json

import comfy.lora  # noqa: E402
import comfy.sd  # noqa: E402
import comfy.sd1_clip  # noqa: E402
import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402

# ---- stand-in MODEL / CLIP
LORA_KEY_MAPS = {
    'unet': {'lora_unet_input_blocks_0_0': 'diffusion_model.input_blocks.0.0.weight',
             'lora_unet_middle_block_1_proj_in': 'diffusion_model.middle_block.1.proj_in.weight'},
    'clip': {'lora_te_text_model_encoder_layers_0_mlp_fc1': 'clip_l.transformer.text_model.encoder.layers.0.mlp.fc1.weight'},
}


def _summary_tensor(value):
    if isinstance(value, torch.Tensor):
        return ['tensor', list(value.shape), str(value.dtype), hashlib.sha256(value.detach().contiguous().cpu().numpy().tobytes()).hexdigest()[:16]]
    if isinstance(value, (list, tuple)):
        return [_summary_tensor(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _summary_tensor(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if hasattr(value, 'weights'):  # comfy.weight_adapter adapters
        return [type(value).__name__, _summary_tensor(list(value.weights))]
    return repr(value) if not isinstance(value, (int, float, str, bool, type(None))) else value


class _Recorder:
    def _init_records(self, records=None, attachments=None):
        self.patch_records = list(records or [])
        self.attachments = dict(attachments or {})

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0):
        self.patch_records.append({'keys': sorted(patches), 'strength_patch': strength_patch,
                                   'strength_model': strength_model,
                                   'patches': {k: _summary_tensor(v) for k, v in sorted(patches.items())}})
        return list(patches)

    def set_attachments(self, key, value):
        self.attachments[key] = _summary_tensor(value)


class StandinModel(_Recorder):
    """A MODEL as the LoRA loaders use it: .model for the key map, clone(), add_patches(), set_attachments()."""

    def __init__(self, label='model', records=None, attachments=None):
        self.label = label
        self.model = types.SimpleNamespace(amy_lora_keys=LORA_KEY_MAPS['unet'])
        self.model_options = {}  # with load_device: what the SDK recognises as a MODEL (ModelPatcher)
        self.load_device = 'cpu'
        self._init_records(records, attachments)

    def clone(self):
        return StandinModel(self.label, self.patch_records, self.attachments)


class StandinPatcher:
    def __init__(self, owner):
        self.forced_hooks = None
        self.owner = owner

    def set_attachments(self, key, value):
        self.owner.attachments[key] = _summary_tensor(value)


_TOKENIZER = None


def _tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = comfy.sd1_clip.SD1Tokenizer(embedding_directory=None, tokenizer_data={})
    return _TOKENIZER


class StandinCLIP(comfy.sd.CLIP, _Recorder):
    """comfy.sd.CLIP without weights: real tokenize() and encode_from_tokens_scheduled(), deterministic
    encode_from_tokens(), recorded clone()/add_patches()."""

    def __init__(self, records=None, attachments=None):  # comfy.sd.CLIP.__init__ would build the text model
        self.tokenizer = _tokenizer()
        self.patcher = StandinPatcher(self)
        self.use_clip_schedule = False
        self.cond_stage_model = types.SimpleNamespace(amy_lora_keys=LORA_KEY_MAPS['clip'])
        self.tokenizer_options = {}
        self._init_records(records, attachments)

    def clone(self):
        return StandinCLIP(self.patch_records, self.attachments)

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0):  # not comfy.sd.CLIP's (patcher-backed)
        return _Recorder.add_patches(self, patches, strength_patch, strength_model)

    def tokenize(self, text, return_word_ids=False, **kwargs):
        if 'AMY-RAISE' in text:
            raise RuntimeError('stand-in CLIP tokenize failure')
        return self.tokenizer.tokenize_with_weights(text, return_word_ids, **kwargs)

    def encode_from_tokens(self, tokens, return_pooled=False, return_dict=False):
        ids = torch.tensor([[float(tok) * float(weight) for tok, weight in chunk] for chunk in tokens['l']])
        cond = torch.stack([ids, ids.flip(-1)], dim=-1).reshape(1, -1, 2) / 1000.0
        cond = cond + 0.001 * len(self.patch_records)  # patched CLIPs encode differently
        pooled = cond.mean(dim=1)
        if return_dict:
            return {'cond': cond, 'pooled_output': pooled}
        if return_pooled:
            return cond, pooled
        return cond


def _key_map_unet(model, key_map={}):
    key_map = dict(key_map)
    key_map.update(model.amy_lora_keys)
    return key_map


def _key_map_clip(cond_stage_model, key_map={}):
    key_map = dict(key_map)
    key_map.update(cond_stage_model.amy_lora_keys)
    return key_map


comfy.lora.model_lora_keys_unet = _key_map_unet
comfy.lora.model_lora_keys_clip = _key_map_clip


def _standin(name, run, input_types, return_types, output_node=False):
    attrs = {'INPUT_TYPES': classmethod(lambda cls: input_types()), 'RETURN_TYPES': return_types,
             'FUNCTION': 'run', 'CATEGORY': 'amy-test', 'run': run, 'OUTPUT_NODE': output_node}
    return type(f'AMYStandin_{name}', (), attrs)


def _probe(self, text=None, conditioning=None, model=None, clip=None, label=''):
    def describe_model(value):
        if value is None:
            return None
        return {'type': type(value).__name__, 'patches': value.patch_records, 'attachments': value.attachments}

    report = {'label': label, 'text': text,
              'conditioning': None if conditioning is None else _summary_tensor(conditioning),
              'model': describe_model(model), 'clip': describe_model(clip)}
    return {'ui': {'probe': [json.dumps(report, sort_keys=True)]}}


STANDINS = {
    'CheckpointLoaderSimple': _standin(
        'CheckpointLoaderSimple', lambda self, ckpt_name: (StandinModel(), StandinCLIP(), object()),
        lambda: {'required': {'ckpt_name': (folder_paths.get_filename_list('checkpoints'),)}},
        ('MODEL', 'CLIP', 'VAE')),
    'AMYTestString': _standin('AMYTestString', lambda self, text: (text,),
                              lambda: {'required': {'text': ('STRING', {'default': '', 'multiline': True})}},
                              ('STRING',)),
    'AMYProbe': _standin(
        'AMYProbe', _probe,
        lambda: {'required': {'label': ('STRING', {'default': ''})},
                 'optional': {'text': ('STRING', {'forceInput': True}), 'conditioning': ('CONDITIONING',),
                              'model': ('MODEL',), 'clip': ('CLIP',)}},
        (), output_node=True),
}
core_nodes.NODE_CLASS_MAPPINGS.update(STANDINS)

# ---- load the pack under test
HARNESS_STUBS = []
if SIDE == 'original':
    pack_dir = OUT / 'nodes-root' / 'custom_nodes' / 'weilin-comfyui-tools'
    shutil.copytree('/pack', pack_dir, ignore=shutil.ignore_patterns('v2'))
    package = str(pack_dir).replace('.', '_x_')  # nodes.load_custom_node's module name for a directory
    install_stub = types.ModuleType(package + '.install_request')
    install_stub.install_requirements = lambda: None
    server_stub = types.ModuleType(package + '.app.server.prompt_server')
    server_stub.folder_paths = folder_paths
    server_stub.go_run_node_auto_random_tag = lambda name: ""
    sys.modules[install_stub.__name__] = install_stub
    sys.modules[server_stub.__name__] = server_stub
    HARNESS_STUBS = [install_stub.__name__.rsplit('.', 1)[-1], 'app.server.prompt_server']
    pack_path = str(pack_dir)
else:
    pack_path = '/pack/v2'
loaded = asyncio.run(core_nodes.load_custom_node(pack_path, ignore=set(), module_parent='custom_nodes'))
NODE_IDS = ('WeiLinPromptUI', 'WeiLinPromptUIWithoutLora', 'WeiLinPromptUIOnlyLoraStack')


def schema_of(node_id):
    cls = core_nodes.NODE_CLASS_MAPPINGS[node_id]

    def plain(value):
        return json.loads(json.dumps(value, default=lambda v: getattr(v, 'value', str(v))))
    return {'input_types': plain(cls.INPUT_TYPES()), 'return_types': [str(x) for x in cls.RETURN_TYPES],
            'return_names': [str(x) for x in (getattr(cls, 'RETURN_NAMES', None) or cls.RETURN_TYPES)],
            'output_node': bool(getattr(cls, 'OUTPUT_NODE', False)), 'category': getattr(cls, 'CATEGORY', None),
            'description': getattr(cls, 'DESCRIPTION', None),
            'display_name': core_nodes.NODE_DISPLAY_NAME_MAPPINGS.get(node_id)}


class Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None

    def send_sync(self, event, data, sid=None):
        pass


def run_case(case):
    result = {'name': case['name'], 'runs': []}
    for index in range(case.get('runs', 1)):
        prompt = json.loads(json.dumps(case['prompt']))
        prompt_id = f"{case['name']}-{index}"
        valid = asyncio.run(execution.validate_prompt(prompt_id, prompt, None))
        if not valid[0]:
            result['runs'].append({'validation_error': json.loads(json.dumps(valid[1], default=str)),
                                   'node_errors': json.loads(json.dumps(valid[3], default=str))})
            continue
        executor = execution.PromptExecutor(Server(), cache_type=execution.CacheType.CLASSIC,
                                            cache_args={'lru': 0, 'ram': 0, 'ram_inactive': 0})
        executor.execute(prompt, prompt_id, {}, valid[2])
        errors = []
        for event, data in executor.status_messages:
            if event == 'execution_error':
                errors.append({'node_id': data.get('node_id'), 'node_type': data.get('node_type'),
                               'exception_type': data.get('exception_type'),
                               'exception_message': data.get('exception_message'),
                               'traceback_tail': ''.join(data.get('traceback') or [])[-1500:]})
        history = getattr(executor, 'history_result', None) or {}
        result['runs'].append({'success': bool(executor.success), 'errors': errors,
                               'ui': json.loads(json.dumps(history.get('outputs', {}), default=str))})
    result['cwd_files'] = sorted(p.name for p in CWD.iterdir())
    return result


def main():
    cases = json.loads(Path(CASES).read_text())
    report = {'side': SIDE, 'loaded': bool(loaded), 'pack_path': pack_path, 'harness_stubs': HARNESS_STUBS,
              'schemas': {node_id: schema_of(node_id) for node_id in NODE_IDS}, 'cases': []}
    for case in cases:
        try:
            report['cases'].append(run_case(case))
        except Exception as error:  # a harness failure is recorded, never hidden
            import traceback
            report['cases'].append({'name': case['name'], 'harness_error': f'{type(error).__name__}: {error}',
                                    'traceback': traceback.format_exc()[-3000:]})
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str) + '\n')


main()
