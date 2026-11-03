"""One side of the WAS Node Suite parity run (gate container only).

argv: SIDE CASES_JSON OUT_DIR FIXTURES_DIR      SIDE = original | v2

Every case's prompt runs through ComfyUI's real PromptExecutor (core 6257422b at /core) with the pack loaded as a
custom node: the pristine fork copied to <OUT>/nodes-root/custom_nodes/was-node-suite-comfyui (with the pinned /deps
wheels, the user directory pointed at <OUT>/user, and the pack's own WAS_BLOCK_AUTO_INSTALL switch set so it never
runs pip), or /pack/v2 read-only. MODEL and CLIP are weightless stand-ins: the CLIP is a comfy.sd.CLIP with the real
SD1 tokenizer and core's real encode_from_tokens_scheduled; both record every LoRA patch comfy.lora.load_lora builds.
The clocks are frozen and the global torch RNG is seeded before every prompt, identically on both sides. An AMYProbe
output node reports what reached it as UI.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time
import types

SIDE, CASES, OUT, FIXTURES = sys.argv[1:5]
OUT = Path(OUT)
sys.path[:0] = ['/core']
if os.path.isdir('/deps') and SIDE == 'original':
    sys.path.insert(0, '/deps')
os.environ['WAS_BLOCK_AUTO_INSTALL'] = '1'
sys.argv = ['main.py', '--cpu']

FIXED_TIME = 1793658605.25  # 2026-11-02 22:30:05 UTC
time.time = lambda: FIXED_TIME
FIXED_LOCAL = time.struct_time((2026, 11, 2, 22, 30, 5, 0, 306, 0))
_real_localtime = time.localtime
time.localtime = lambda *args: FIXED_LOCAL

import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import torch  # noqa: E402
torch.set_num_threads(1)
import folder_paths  # noqa: E402

for name, setter in (('output', folder_paths.set_output_directory), ('temp', folder_paths.set_temp_directory),
                     ('input', folder_paths.set_input_directory), ('user', folder_paths.set_user_directory)):
    (OUT / name).mkdir(parents=True, exist_ok=True)
    setter(str(OUT / name))
for key, exts in (('checkpoints', {'.safetensors'}), ('loras', {'.safetensors'})):
    folder_paths.folder_names_and_paths[key] = ([str(Path(FIXTURES) / key)], exts)
OUTPUT = OUT / 'output'
CWD = OUT / 'cwd'
CWD.mkdir(parents=True, exist_ok=True)
os.chdir(CWD)

import comfy.lora  # noqa: E402
import comfy.sd  # noqa: E402
import comfy.sd1_clip  # noqa: E402
import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402

LORA_KEY_MAPS = {
    'unet': {'lora_unet_input_blocks_0_0': 'diffusion_model.input_blocks.0.0.weight',
             'lora_unet_middle_block_1_proj_in': 'diffusion_model.middle_block.1.proj_in.weight'},
    'clip': {'lora_te_text_model_encoder_layers_0_mlp_fc1': 'clip_l.transformer.text_model.encoder.layers.0.mlp.fc1.weight'},
}


def _summary(value):
    if isinstance(value, torch.Tensor):
        return ['tensor', list(value.shape), str(value.dtype),
                hashlib.sha256(value.detach().contiguous().cpu().numpy().tobytes()).hexdigest()[:16]]
    if isinstance(value, (list, tuple)):
        return [_summary(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _summary(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if hasattr(value, 'weights'):
        return [type(value).__name__, _summary(list(value.weights))]
    if isinstance(value, (int, float, str, bool, type(None))):
        return [type(value).__name__, value]
    return repr(type(value).__name__)


class _Recorder:
    def _init_records(self, records=None, attachments=None):
        self.patch_records = list(records or [])
        self.attachments = dict(attachments or {})

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0):
        self.patch_records.append({'keys': sorted(patches), 'strength_patch': strength_patch,
                                   'strength_model': strength_model,
                                   'patches': {k: _summary(v) for k, v in sorted(patches.items())}})
        return list(patches)

    def set_attachments(self, key, value):
        self.attachments[key] = _summary(value)


class StandinModel(_Recorder):
    def __init__(self, records=None, attachments=None):
        self.model = types.SimpleNamespace(amy_lora_keys=LORA_KEY_MAPS['unet'])
        self.model_options = {}
        self.load_device = 'cpu'
        self._init_records(records, attachments)

    def clone(self):
        return StandinModel(self.patch_records, self.attachments)


class StandinPatcher:
    def __init__(self, owner):
        self.forced_hooks = None
        self.owner = owner

    def set_attachments(self, key, value):
        self.owner.attachments[key] = _summary(value)


_TOKENIZER = None


def _tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = comfy.sd1_clip.SD1Tokenizer(embedding_directory=None, tokenizer_data={})
    return _TOKENIZER


class StandinCLIP(comfy.sd.CLIP, _Recorder):
    def __init__(self, records=None, attachments=None):
        self.tokenizer = _tokenizer()
        self.patcher = StandinPatcher(self)
        self.use_clip_schedule = False
        self.cond_stage_model = types.SimpleNamespace(amy_lora_keys=LORA_KEY_MAPS['clip'])
        self.tokenizer_options = {}
        self._init_records(records, attachments)

    def clone(self):
        return StandinCLIP(self.patch_records, self.attachments)

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0):
        return _Recorder.add_patches(self, patches, strength_patch, strength_model)

    def tokenize(self, text, return_word_ids=False, **kwargs):
        return self.tokenizer.tokenize_with_weights(text, return_word_ids, **kwargs)

    def encode_from_tokens(self, tokens, return_pooled=False, return_dict=False):
        ids = torch.tensor([[float(tok) * float(weight) for tok, weight in chunk] for chunk in tokens['l']])
        cond = torch.stack([ids, ids.flip(-1)], dim=-1).reshape(1, -1, 2) / 1000.0 + 0.001 * len(self.patch_records)
        pooled = cond.mean(dim=1)
        if return_dict:
            return {'cond': cond, 'pooled_output': pooled}
        if return_pooled:
            return cond, pooled
        return cond


def _key_map_unet(model, key_map={}):
    return {**key_map, **model.amy_lora_keys}


def _key_map_clip(cond_stage_model, key_map={}):
    return {**key_map, **cond_stage_model.amy_lora_keys}


comfy.lora.model_lora_keys_unet = _key_map_unet
comfy.lora.model_lora_keys_clip = _key_map_clip


def _standin(name, run, input_types, return_types, output_node=False):
    attrs = {'INPUT_TYPES': classmethod(lambda cls: input_types()), 'RETURN_TYPES': return_types,
             'FUNCTION': 'run', 'CATEGORY': 'amy-test', 'run': run, 'OUTPUT_NODE': output_node}
    return type(f'AMYStandin_{name}', (), attrs)


def _test_image(self, width, height, batch, seed, channels=3):
    generator = torch.Generator().manual_seed(seed)
    return (torch.rand((batch, height, width, channels), generator=generator),)


def _probe(self, label='', **values):
    report = {'label': label}
    for key, value in sorted(values.items()):
        if key in ('model', 'clip') and value is not None:
            report[key] = {'type': type(value).__name__, 'patches': getattr(value, 'patch_records', None),
                           'attachments': getattr(value, 'attachments', None)}
        else:
            report[key] = _summary(value)
    return {'ui': {'probe': [json.dumps(report, sort_keys=True)]}}


STANDINS = {
    'CheckpointLoaderSimple': _standin(
        'CheckpointLoaderSimple', lambda self, ckpt_name: (StandinModel(), StandinCLIP(), object()),
        lambda: {'required': {'ckpt_name': (folder_paths.get_filename_list('checkpoints'),)}},
        ('MODEL', 'CLIP', 'VAE')),
    'AMYTestString': _standin('AMYTestString', lambda self, text: (text,),
                              lambda: {'required': {'text': ('STRING', {'default': '', 'multiline': True})}},
                              ('STRING',)),
    'AMYTestImage': _standin('AMYTestImage', _test_image,
                             lambda: {'required': {'width': ('INT', {'default': 16, 'min': 1, 'max': 512}),
                                                   'height': ('INT', {'default': 12, 'min': 1, 'max': 512}),
                                                   'batch': ('INT', {'default': 1, 'min': 1, 'max': 8}),
                                                   'seed': ('INT', {'default': 0, 'min': 0, 'max': 2 ** 31})},
                                      'optional': {'channels': ('INT', {'default': 3, 'min': 1, 'max': 4})}},
                             ('IMAGE',)),
    'AMYProbe': _standin(
        'AMYProbe', _probe,
        lambda: {'required': {'label': ('STRING', {'default': ''})},
                 'optional': {'text': ('*', {'forceInput': True}), 'number': ('*', {'forceInput': True}),
                              'number_float': ('*', {'forceInput': True}), 'number_int': ('*', {'forceInput': True}),
                              'conditioning': ('CONDITIONING',), 'model': ('MODEL',), 'clip': ('CLIP',),
                              'image': ('IMAGE',), 'latent': ('LATENT',), 'files': ('*', {'forceInput': True})}},
        (), output_node=True),
}
core_nodes.NODE_CLASS_MAPPINGS.update(STANDINS)

# ---- load the pack under test
if SIDE == 'original':
    pack_dir = OUT / 'nodes-root' / 'custom_nodes' / 'was-node-suite-comfyui'
    shutil.copytree('/pack', pack_dir, ignore=shutil.ignore_patterns('v2'))
    pack_path = str(pack_dir)
else:
    pack_path = '/pack/v2'
loaded = asyncio.run(core_nodes.load_custom_node(pack_path, ignore=set(), module_parent='custom_nodes'))
PACK_MODULE = sys.modules[pack_path.replace('.', '_x_')]
PACK_IDS = sorted(PACK_MODULE.NODE_CLASS_MAPPINGS)


def schema_of(node_id):
    cls = core_nodes.NODE_CLASS_MAPPINGS[node_id]

    def plain(value):
        return json.loads(json.dumps(value, default=lambda v: getattr(v, 'value', str(v))))
    try:
        input_types = plain(cls.INPUT_TYPES())
    except Exception as error:
        input_types = {'__error__': f'{type(error).__name__}: {error}'}
    return {'input_types': input_types, 'return_types': plain(list(cls.RETURN_TYPES)),
            'return_names': plain(list(getattr(cls, 'RETURN_NAMES', None) or cls.RETURN_TYPES)),
            'output_node': bool(getattr(cls, 'OUTPUT_NODE', False)), 'category': getattr(cls, 'CATEGORY', None),
            'input_is_list': bool(getattr(cls, 'INPUT_IS_LIST', False)),
            'output_is_list': plain(list(getattr(cls, 'OUTPUT_IS_LIST', None) or [])),
            'description': getattr(cls, 'DESCRIPTION', None)}


def png_chunks(data):
    rows = []
    position = 8
    while position < len(data):
        length, kind = struct.unpack('>I4s', data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        position += 12 + length
        kind = kind.decode('latin-1')
        if kind in ('tEXt', 'iTXt', 'zTXt'):
            keyword, _, rest = body.partition(b'\x00')
            rows.append([kind, keyword.decode('latin-1'), hashlib.sha256(rest).hexdigest()])
        else:
            rows.append([kind, None, hashlib.sha256(body).hexdigest() if kind != 'IDAT' else 'IDAT'])
    return rows


def riff_chunks(data):
    rows = []
    position = 12
    while position + 8 <= len(data):
        kind, size = struct.unpack('<4sI', data[position:position + 8])
        rows.append([kind.decode('latin-1'), size, hashlib.sha256(data[position + 8:position + 8 + size]).hexdigest()])
        position += 8 + size + (size & 1)
    return rows


def describe(path, relative):
    from PIL import Image
    data = path.read_bytes()
    row = {'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    if not data.startswith((b'\x89PNG', b'RIFF', b'GIF8', b'II*\x00', b'MM\x00*', b'BM')):
        row['not_an_image'] = True
        return row
    with Image.open(path) as image:
        image.load()
        row['mode'], row['size'], row['format'] = image.mode, list(image.size), image.format
        row['pixels_sha256'] = hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()
        row['info_keys'] = sorted(str(k) for k in image.info)
        if image.format == 'PNG':
            row['pil_text'] = dict(image.text)
            row['png_chunks'] = png_chunks(data)
        exif = image.getexif()
        row['exif'] = {str(k): str(v) for k, v in sorted(exif.items())}
        if image.format == 'WEBP':
            row['riff_chunks'] = riff_chunks(data)
    return row


def collect():
    rows = []
    for path in sorted(OUTPUT.rglob('*')):
        if path.is_file():
            rows.append(describe(path, path.relative_to(OUTPUT).as_posix()))
    return rows


class Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None

    def send_sync(self, event, data, sid=None):
        pass


def run_case(case):
    for item in list(OUTPUT.iterdir()):
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    for rel, text in (case.get('preexisting') or {}).items():
        target = OUTPUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())
    result = {'name': case['name'], 'runs': []}
    for index in range(case.get('runs', 1)):
        prompt = json.loads(json.dumps(case['prompt']))
        prompt_id = f"{case['name']}-{index}"
        valid = asyncio.run(execution.validate_prompt(prompt_id, prompt, None))
        if not valid[0]:
            result['runs'].append({'validation_error': json.loads(json.dumps(valid[1], default=str)),
                                   'node_errors': json.loads(json.dumps(valid[3], default=str))})
            continue
        torch.manual_seed(20261102)
        executor = execution.PromptExecutor(Server(), cache_type=execution.CacheType.CLASSIC,
                                            cache_args={'lru': 0, 'ram': 0, 'ram_inactive': 0})
        extra = {} if case.get('extra_pnginfo') is None else {'extra_pnginfo': case['extra_pnginfo']}
        executor.execute(prompt, prompt_id, extra, valid[2])
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
    result['files'] = collect()
    return result


def main():
    cases = json.loads(Path(CASES).read_text())
    report = {'side': SIDE, 'loaded': bool(loaded), 'pack_path': pack_path, 'output_dir': str(OUTPUT),
              'pack_ids': PACK_IDS, 'schemas': {node_id: schema_of(node_id) for node_id in PACK_IDS}, 'cases': []}
    for case in cases:
        try:
            report['cases'].append(run_case(case))
        except Exception as error:
            import traceback
            report['cases'].append({'name': case['name'], 'harness_error': f'{type(error).__name__}: {error}',
                                    'traceback': traceback.format_exc()[-3000:]})
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str) + '\n')


main()
