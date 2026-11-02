"""One side of the comfyui_image_metadata_extension parity run (gate container only).

argv: SIDE CASES_JSON OUT_DIR FIXTURES_DIR      SIDE = original | original-raw | v2

Every case's prompt runs through ComfyUI's real PromptExecutor (core 6257422b at /core) with
the pack loaded as a custom node:
* original / original-raw: the pristine pack copied to <OUT>/nodes-root/custom_nodes/
  comfyui_image_metadata_extension (its import writes a cache folder into the pack);
* v2: /pack/v2, read-only.
"original" adds one harness-only adapter (ADAPTER below); "original-raw" runs the pristine
pack unmodified and is kept as evidence of the core incompatibility.
Model-bearing core nodes are replaced, identically on all sides, by stand-ins with real
INPUT_TYPES/RETURN_TYPES, so the saver sees the same graph and values without loading
weights. Clocks are frozen on all sides.
"""
import asyncio
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time

SIDE, CASES, OUT, FIXTURES = sys.argv[1:5]
OUT = Path(OUT)
sys.path[:0] = ['/core']
if os.path.isdir('/deps') and SIDE.startswith('original'):
    sys.path.insert(0, '/deps')  # piexif for the original (see DEPS.json); v2 does not import it
sys.argv = ['main.py', '--cpu']

FIXED_LOCAL = time.struct_time((2026, 11, 2, 22, 30, 5, 0, 306, 0))
time.localtime = lambda *args: FIXED_LOCAL


class FrozenDatetime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 2, 22, 30, 5)


import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import torch  # noqa: E402
torch.set_num_threads(1)
import folder_paths  # noqa: E402

OUTPUT = OUT / 'output'
for name, setter in (('output', folder_paths.set_output_directory), ('temp', folder_paths.set_temp_directory),
                     ('input', folder_paths.set_input_directory)):
    (OUT / name).mkdir(parents=True, exist_ok=True)
    setter(str(OUT / name))
for key, exts in (('checkpoints', {'.safetensors', '.ckpt'}), ('loras', {'.safetensors'}),
                  ('vae', {'.safetensors'}), ('embeddings', {'.pt', '.safetensors', '.bin'}),
                  ('upscale_models', {'.pth', '.safetensors'}), ('diffusion_models', {'.safetensors'}),
                  ('text_encoders', {'.safetensors'})):
    folder_paths.folder_names_and_paths[key] = ([str(Path(FIXTURES) / key)], exts)

import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402

ADAPTER = None
if SIDE == 'original':
    # Harness-only adapter. The pinned original wraps the executor's output cache in OutputCacheCompat
    # (modules/capture.py:17-41), whose get_cache falls back to the cache's get(); on core 6257422b that
    # get() is async (comfy_execution/caching.py:384), so execution.get_input_data (execution.py:294)
    # receives a coroutine. This restores the synchronous accessor of the ComfyUI releases the original
    # was written for, using get_local (caching.py:390), the synchronous twin of get (no cache
    # providers are configured here); OutputCacheCompat.get_cache finds and uses it.
    from comfy_execution.caching import HierarchicalCache
    HierarchicalCache.get_cache = lambda self, node_id, to_node_id=None: self.get_local(node_id)
    ADAPTER = 'comfy_execution.caching.HierarchicalCache.get_cache = get_local(node_id)'


class _Opaque:
    def __init__(self, label):
        self.label = label


class StandinCLIP:
    """What a CLIP loader returns, minus the weights: the real tokenizer object the capture code
    inspects (py/defs/formatters.py:_extract_embedding_names)."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer


class PlainTokenizer:
    """A tokenizer that is none of the SD1/SD2/SDXL/SD3/Flux tokenizers."""


_TOKENIZERS = {}
TOKENIZER_NOTES = {}


def tokenizer(kind):
    if kind not in _TOKENIZERS:
        import comfy.sd1_clip
        directory = folder_paths.get_folder_paths('embeddings')
        if kind == 'sd1':
            value = comfy.sd1_clip.SD1Tokenizer(embedding_directory=directory, tokenizer_data={})
        elif kind == 'sdxl':
            import comfy.sdxl_clip
            value = comfy.sdxl_clip.SDXLTokenizer(embedding_directory=directory, tokenizer_data={})
        elif kind == 'flux':
            import comfy.text_encoders.flux
            try:
                value = comfy.text_encoders.flux.FluxTokenizer(embedding_directory=directory, tokenizer_data={})
                TOKENIZER_NOTES['flux'] = 'FluxTokenizer constructed normally'
            except Exception as error:  # T5 tokenizer files unavailable: keep the class and its clip_l
                value = object.__new__(comfy.text_encoders.flux.FluxTokenizer)
                value.clip_l = comfy.sd1_clip.SDTokenizer(embedding_directory=directory, tokenizer_data={})
                TOKENIZER_NOTES['flux'] = f'FluxTokenizer without T5 ({type(error).__name__}: {error})'
        elif kind == 'renamed':
            # an SD1Tokenizer subclass pattern used by newer models (clip_name other than "l")
            value = comfy.sd1_clip.SD1Tokenizer(embedding_directory=directory, tokenizer_data={}, clip_name='umt5xxl')
        else:
            value = PlainTokenizer()
        _TOKENIZERS[kind] = StandinCLIP(value)
    return _TOKENIZERS[kind]


def _clip_for_checkpoint(ckpt_name):
    return tokenizer({'sdxl-ckpt.safetensors': 'sdxl', 'renamed-tok.safetensors': 'renamed',
                      'plain-tok.safetensors': 'plain'}.get(ckpt_name, 'sd1'))


class _Flexible(dict):
    """rgthree's FlexibleOptionalInputType: accepts any optional input name."""

    def __init__(self, type_name):
        super().__init__()
        self.type_name = type_name

    def __getitem__(self, key):
        return (self.type_name,)

    def __contains__(self, key):
        return True


def _standin(name, run, input_types=None, return_types=None):
    real = core_nodes.NODE_CLASS_MAPPINGS.get(name)
    attrs = {
        'INPUT_TYPES': classmethod(lambda cls: (input_types or real.INPUT_TYPES)()),
        'RETURN_TYPES': return_types or real.RETURN_TYPES,
        'FUNCTION': 'run', 'CATEGORY': 'amy-test', 'run': run,
    }
    return type(f'AMYStandin_{name.replace(" ", "_")}', (), attrs)


def _cond(*_a, **_k):
    return ([[torch.zeros(1, 77, 768), {'pooled_output': torch.zeros(1, 768)}]],)


def _image_from_latent(samples, vae=None):
    b, _, h, w = samples['samples'].shape
    generator = torch.Generator().manual_seed(1234 + 1000 * h + w)
    return (torch.rand((b, h * 8, w * 8, 3), generator=generator),)


def _ckpt_names():
    return folder_paths.get_filename_list('checkpoints')


SAMPLER_NAMES = ['euler', 'dpmpp_2m', 'ipndm', 'lcm', 'dpmpp_3m_sde']
SCHEDULER_NAMES = ['normal', 'karras', 'exponential', 'sgm_uniform']

STANDINS = {
    'CheckpointLoaderSimple': _standin('CheckpointLoaderSimple',
                                       lambda self, ckpt_name: (_Opaque('model'), _clip_for_checkpoint(ckpt_name), _Opaque('vae'))),
    'CLIPTextEncode': _standin('CLIPTextEncode', lambda self, clip, text: _cond()),
    'KSampler': _standin('KSampler', lambda self, latent_image, **kw: ({'samples': latent_image['samples'].clone()},)),
    'KSamplerAdvanced': _standin('KSamplerAdvanced', lambda self, latent_image, **kw: ({'samples': latent_image['samples'].clone()},)),
    'VAEDecode': _standin('VAEDecode', lambda self, samples, vae: _image_from_latent(samples)),
    'LoraLoader': _standin('LoraLoader', lambda self, model, clip, **kw: (model, clip)),
    'LoraLoaderModelOnly': _standin('LoraLoaderModelOnly', lambda self, model, **kw: (model,)),
    'VAELoader': _standin('VAELoader', lambda self, vae_name: (_Opaque('vae'),)),
    'CLIPSetLastLayer': _standin('CLIPSetLastLayer', lambda self, clip, stop_at_clip_layer: (clip,)),
    'UNETLoader': _standin('UNETLoader', lambda self, unet_name, weight_dtype: (_Opaque('model'),)),
    'DualCLIPLoader': _standin(
        'DualCLIPLoader', lambda self, clip_name1, clip_name2, type, **kw: (tokenizer('flux'),),
        input_types=lambda: {'required': {'clip_name1': (folder_paths.get_filename_list('text_encoders'),),
                                          'clip_name2': (folder_paths.get_filename_list('text_encoders'),),
                                          'type': (['sdxl', 'sd3', 'flux'],)}},
        return_types=('CLIP',)),
    'UpscaleModelLoader': _standin(
        'UpscaleModelLoader', lambda self, model_name: (_Opaque('upscaler'),),
        input_types=lambda: {'required': {'model_name': (folder_paths.get_filename_list('upscale_models'),)}},
        return_types=('UPSCALE_MODEL',)),
    'ImageUpscaleWithModel': _standin(
        'ImageUpscaleWithModel',
        lambda self, upscale_model, image: (image.repeat_interleave(2, dim=1).repeat_interleave(2, dim=2),),
        input_types=lambda: {'required': {'upscale_model': ('UPSCALE_MODEL',), 'image': ('IMAGE',)}},
        return_types=('IMAGE',)),
    'RandomNoise': _standin(
        'RandomNoise', lambda self, noise_seed: (_Opaque('noise'),),
        input_types=lambda: {'required': {'noise_seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff})}},
        return_types=('NOISE',)),
    'KSamplerSelect': _standin(
        'KSamplerSelect', lambda self, sampler_name: (_Opaque('sampler'),),
        input_types=lambda: {'required': {'sampler_name': (SAMPLER_NAMES,)}}, return_types=('SAMPLER',)),
    'BasicScheduler': _standin(
        'BasicScheduler', lambda self, model, scheduler, steps, denoise: (torch.linspace(1, 0, steps + 1),),
        input_types=lambda: {'required': {'model': ('MODEL',), 'scheduler': (SCHEDULER_NAMES,),
                                          'steps': ('INT', {'default': 20, 'min': 1, 'max': 10000}),
                                          'denoise': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 1.0})}},
        return_types=('SIGMAS',)),
    'BasicGuider': _standin(
        'BasicGuider', lambda self, model, conditioning: (_Opaque('guider'),),
        input_types=lambda: {'required': {'model': ('MODEL',), 'conditioning': ('CONDITIONING',)}},
        return_types=('GUIDER',)),
    'FluxGuidance': _standin(
        'FluxGuidance', lambda self, conditioning, guidance: (conditioning,),
        input_types=lambda: {'required': {'conditioning': ('CONDITIONING',),
                                          'guidance': ('FLOAT', {'default': 3.5, 'min': 0.0, 'max': 100.0})}},
        return_types=('CONDITIONING',)),
    'SamplerCustomAdvanced': _standin(
        'SamplerCustomAdvanced',
        lambda self, noise, guider, sampler, sigmas, latent_image: (
            {'samples': latent_image['samples'].clone()}, {'samples': latent_image['samples'].clone()}),
        input_types=lambda: {'required': {'noise': ('NOISE',), 'guider': ('GUIDER',), 'sampler': ('SAMPLER',),
                                          'sigmas': ('SIGMAS',), 'latent_image': ('LATENT',)}},
        return_types=('LATENT', 'LATENT')),
    'Power Lora Loader (rgthree)': _standin(
        'Power Lora Loader (rgthree)', lambda self, model, clip, **kw: (model, clip),
        input_types=lambda: {'required': {'model': ('MODEL',), 'clip': ('CLIP',)}, 'optional': _Flexible('*')},
        return_types=('MODEL', 'CLIP')),
    'Efficient Loader': _standin(
        'Efficient Loader',
        lambda self, ckpt_name, clip_skip, positive, negative, empty_latent_width, empty_latent_height, batch_size, **kw: (
            _Opaque('model'), _cond()[0], _cond()[0],
            {'samples': torch.zeros(batch_size, 4, empty_latent_height // 8, empty_latent_width // 8)},
            _Opaque('vae'), _clip_for_checkpoint(ckpt_name)),
        input_types=lambda: {'required': {
            'ckpt_name': (_ckpt_names(),), 'clip_skip': ('INT', {'default': -1, 'min': -24, 'max': -1}),
            'positive': ('STRING', {'default': '', 'multiline': True}),
            'negative': ('STRING', {'default': '', 'multiline': True}),
            'empty_latent_width': ('INT', {'default': 512, 'min': 64, 'max': 8192, 'step': 8}),
            'empty_latent_height': ('INT', {'default': 512, 'min': 64, 'max': 8192, 'step': 8}),
            'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 64})}},
        return_types=('MODEL', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'VAE', 'CLIP')),
    'KSampler (Efficient)': _standin(
        'KSampler (Efficient)',
        lambda self, model, positive, negative, latent_image, vae, **kw: (
            model, positive, negative, {'samples': latent_image['samples'].clone()}, vae,
            _image_from_latent(latent_image)[0]),
        input_types=lambda: {'required': {
            'model': ('MODEL',), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff}),
            'steps': ('INT', {'default': 20, 'min': 1, 'max': 10000}),
            'cfg': ('FLOAT', {'default': 7.0, 'min': 0.0, 'max': 100.0}),
            'sampler_name': (SAMPLER_NAMES,), 'scheduler': (SCHEDULER_NAMES,),
            'positive': ('CONDITIONING',), 'negative': ('CONDITIONING',), 'latent_image': ('LATENT',),
            'denoise': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 1.0}), 'vae': ('VAE',)}},
        return_types=('MODEL', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'VAE', 'IMAGE')),
    'AMYTestInt': _standin('AMYTestInt', lambda self, value: (value,),
                           input_types=lambda: {'required': {'value': ('INT', {'default': 0, 'min': 0, 'max': 2 ** 63 - 1})}},
                           return_types=('INT',)),
    'AMYTestString': _standin('AMYTestString', lambda self, text: (text,),
                              input_types=lambda: {'required': {'text': ('STRING', {'default': '', 'multiline': True})}},
                              return_types=('STRING',)),
}
core_nodes.NODE_CLASS_MAPPINGS.update(STANDINS)

# ---- load the pack under test
if SIDE.startswith('original'):
    nodes_root = OUT / 'nodes-root'
    pack_dir = nodes_root / 'custom_nodes' / 'comfyui_image_metadata_extension'
    shutil.copytree('/pack', pack_dir, ignore=shutil.ignore_patterns('v2'))
    sys.path.insert(0, str(nodes_root))
    pack_path = str(pack_dir)
else:
    pack_path = '/pack/v2'
loaded = asyncio.run(core_nodes.load_custom_node(pack_path, ignore=set(), module_parent='custom_nodes'))
SAVE = core_nodes.NODE_CLASS_MAPPINGS['SaveImageWithMetaData']
EXTRA = core_nodes.NODE_CLASS_MAPPINGS['CreateExtraMetaData']
sys.modules[SAVE.__module__].datetime = FrozenDatetime


def schema_of(cls, node_id):
    def plain(value):
        return json.loads(json.dumps(value, default=lambda v: getattr(v, 'value', str(v))))
    return {'input_types': plain(cls.INPUT_TYPES()), 'return_types': [str(x) for x in cls.RETURN_TYPES],
            'output_node': bool(getattr(cls, 'OUTPUT_NODE', False)), 'category': getattr(cls, 'CATEGORY', None),
            'description': getattr(cls, 'DESCRIPTION', None),
            'display_name': core_nodes.NODE_DISPLAY_NAME_MAPPINGS.get(node_id)}


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


def _plain_exif(value):
    if isinstance(value, (bytes, bytearray)):
        return 'hex:' + bytes(value).hex()
    if isinstance(value, tuple):
        return [_plain_exif(item) for item in value]
    return value if isinstance(value, (int, float, str)) or value is None else str(value)


def describe(path, relative):
    from PIL import Image
    data = path.read_bytes()
    row = {'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    suffix = path.suffix.lower()
    if suffix in ('.png', '.webp', '.jpg', '.jpeg') and not data.startswith((b'\x89PNG', b'RIFF', b'\xff\xd8')):
        row['not_an_image'] = True  # a pre-existing placeholder file of the case
        return row
    if suffix in ('.png', '.webp', '.jpg', '.jpeg'):
        with Image.open(path) as image:
            image.load()
            row['mode'], row['size'] = image.mode, list(image.size)
            row['pixels_sha256'] = hashlib.sha256(image.tobytes()).hexdigest()
            if suffix == '.png':
                row['pil_text'] = dict(image.text)
                row['png_chunks'] = png_chunks(data)
            else:
                exif = image.getexif()
                row['exif_ifd0'] = {str(k): _plain_exif(v) for k, v in sorted(exif.items()) if k != 0x8769}
                row['exif_ifd0_has_exif_pointer'] = 0x8769 in exif
                row['exif_exif_ifd'] = {str(k): _plain_exif(v) for k, v in sorted(exif.get_ifd(0x8769).items())}
                if suffix == '.webp':
                    row['riff_chunks'] = riff_chunks(data)
    return row


def collect():
    rows, dirs = [], []
    for path in sorted(OUTPUT.rglob('*')):
        if path.is_file():
            rows.append(describe(path, path.relative_to(OUTPUT).as_posix()))
        elif path.is_dir():
            dirs.append(path.relative_to(OUTPUT).as_posix())
    return rows, dirs


class Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None
        self.messages = []

    def send_sync(self, event, data, sid=None):
        self.messages.append((event, data))


KNOWN_TOP = {'output', 'temp', 'input', 'nodes-root', 'report.json'}


def run_case(case):
    for item in list(OUTPUT.iterdir()):
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    for item in list(OUT.iterdir()):
        if item.name not in KNOWN_TOP:
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    for rel, text in (case.get('preexisting') or {}).items():
        target = OUTPUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())
    result = {'name': case['name'], 'runs': []}
    from comfy.cli_args import args as cli_args
    cli_args.disable_metadata = bool(case.get('disable_metadata'))  # the host's --disable-metadata switch
    for index in range(case.get('runs', 1)):
        prompt = json.loads(json.dumps(case['prompt']))
        prompt_id = f"{case['name']}-{index}"
        valid = asyncio.run(execution.validate_prompt(prompt_id, prompt, None))
        if not valid[0]:
            result['runs'].append({'validation_error': json.loads(json.dumps(valid[1], default=str)),
                                   'node_errors': json.loads(json.dumps(valid[3], default=str))})
            continue
        server = Server()
        # as main.py builds it, with the deterministic classic cache (a fresh executor per run)
        executor = execution.PromptExecutor(server, cache_type=execution.CacheType.CLASSIC,
                                            cache_args={'lru': 0, 'ram': 0, 'ram_inactive': 0})
        extra_data = {} if case.get('extra_pnginfo') is None else {'extra_pnginfo': case['extra_pnginfo']}
        executor.execute(prompt, prompt_id, extra_data, valid[2])
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
    cli_args.disable_metadata = False
    result['files'], result['dirs'] = collect()
    result['outside_output'] = sorted(p.name for p in OUT.iterdir() if p.name not in KNOWN_TOP)
    return result


def main():
    cases = json.loads(Path(CASES).read_text())
    report = {'side': SIDE, 'loaded': bool(loaded), 'pack_path': pack_path, 'output_dir': str(OUTPUT),
              'adapter': ADAPTER,
              'schemas': {'SaveImageWithMetaData': schema_of(SAVE, 'SaveImageWithMetaData'),
                          'CreateExtraMetaData': schema_of(EXTRA, 'CreateExtraMetaData')},
              'save_class': f'{SAVE.__module__}.{SAVE.__name__}', 'cases': []}
    for case in cases:
        try:
            report['cases'].append(run_case(case))
        except Exception as error:  # a harness failure is recorded, never hidden
            import traceback
            report['cases'].append({'name': case['name'], 'harness_error': f'{type(error).__name__}: {error}',
                                    'traceback': traceback.format_exc()[-3000:]})
    report['tokenizer_notes'] = TOKENIZER_NOTES
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str) + '\n')


main()
