"""Tier-1 parity: nkchocoai ComfyUI-SaveImageWithMetaData (c9a87453) vs its Secure Nodes V2 conversion.

Run in the to-50% gate:
  run_in_gate.sh <pack root> <v2/tests> <results> test_comfyui_saveimagewithmetadata_parity.py

Three workers execute the same prompts through ComfyUI's real executor (nk_parity_worker.py):
original-raw (the pristine pack, unmodified: evidence of the core incompatibility),
original (the pristine pack plus the harness-only cache adapter: the parity reference) and v2.
Every case declares its expected outcome; a case passes only when both sides show it:
  EXACT            both succeed, identical UI records, identical file set, identical bytes
  DECODED-EXACT    as EXACT, but a named container difference is allowed for that case
                   (pixels and decoded metadata identical; see compare_files)
  ERROR-PARITY     both fail with the same exception type and message (and the same files)
  REFUSED-AS-DESIGNED  the original succeeds, V2 raises its named SecureConversionRefusal
  KNOWN-DIFFERENCE both sides behave exactly as SECURE_CONVERSION.md documents
Anything else is MISMATCH; a case expected to write files must write at least one image.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
RESULTS = Path('/results')
WORK = Path('/tmp/amy-nk-parity')
FIXTURES = WORK / 'fixtures'
FIXTURE_FILES = ['checkpoints/test-ckpt.safetensors', 'checkpoints/sdxl-ckpt.safetensors',
                 'checkpoints/renamed-tok.safetensors', 'checkpoints/plain-tok.safetensors',
                 'loras/test-lora.safetensors', 'loras/sub/other-lora.safetensors', 'vae/test-vae.safetensors',
                 'embeddings/test-embedding.pt', 'embeddings/sub/emb2.safetensors',
                 'upscale_models/test-upscaler.pth', 'diffusion_models/test-unet.safetensors',
                 'text_encoders/clip_l.safetensors', 'text_encoders/t5xxl.safetensors']
WORKFLOW = {'last_node_id': 9, 'nodes': [{'id': 1, 'type': 'CheckpointLoaderSimple', 'title': 'Load'}],
            'links': [], 'version': 0.4, 'extra': {'note': 'AMY parity fixture ü'}}


def make_fixtures():
    for rel in FIXTURE_FILES:
        path = FIXTURES / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((b'AMY-FIXTURE:' + rel.encode()) * 97)


def graph(prefix='ComfyUI', method='Farthest', node_id=0, fmt='png', lossless=True, quality=100, save_json=False,
          counter=True, civitai=False, save_wf_image=True, batch=1,
          pos='a red fox in the snow, embedding:test-embedding', neg='blurry, lowres', sampler='dpmpp_2m',
          scheduler='karras', seed=123456789, ckpt='test-ckpt.safetensors', extra=None, extra2=None, lora=False,
          lora_model_only=False, hires=False, vae_loader=False, clip_skip=False, upscale=False, linked_seed=False,
          linked_text=False, second_saver=False, flux=False, rgthree=False, efficiency=False):
    save_inputs = {'filename_prefix': prefix, 'sampler_selection_method': method,
                   'sampler_selection_node_id': node_id, 'file_format': fmt, 'lossless_webp': lossless,
                   'quality': quality, 'save_workflow_json': save_json, 'add_counter_to_filename': counter,
                   'civitai_sampler': civitai, 'save_workflow_image': save_wf_image}
    if flux:
        return {
            '30': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'test-unet.safetensors', 'weight_dtype': 'default'}},
            '31': {'class_type': 'DualCLIPLoader', 'inputs': {'clip_name1': 'clip_l.safetensors',
                                                               'clip_name2': 't5xxl.safetensors', 'type': 'flux'}},
            '32': {'class_type': 'CLIPTextEncode', 'inputs': {'text': pos, 'clip': ['31', 0]}},
            '33': {'class_type': 'FluxGuidance', 'inputs': {'conditioning': ['32', 0], 'guidance': 3.5}},
            '34': {'class_type': 'BasicGuider', 'inputs': {'model': ['30', 0], 'conditioning': ['33', 0]}},
            '35': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': seed}},
            '36': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'euler'}},
            '37': {'class_type': 'BasicScheduler', 'inputs': {'model': ['30', 0], 'scheduler': 'normal', 'steps': 24,
                                                               'denoise': 1.0}},
            '38': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 64, 'height': 48, 'batch_size': batch}},
            '39': {'class_type': 'SamplerCustomAdvanced', 'inputs': {'noise': ['35', 0], 'guider': ['34', 0],
                   'sampler': ['36', 0], 'sigmas': ['37', 0], 'latent_image': ['38', 0]}},
            '40': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'test-vae.safetensors'}},
            '41': {'class_type': 'VAEDecode', 'inputs': {'samples': ['39', 0], 'vae': ['40', 0]}},
            '7': {'class_type': 'SaveImageWithMetaData', 'inputs': {'images': ['41', 0], **save_inputs}},
        }
    if efficiency:
        return {
            '21': {'class_type': 'Efficient Loader', 'inputs': {
                'ckpt_name': ckpt, 'clip_skip': -2, 'positive': pos, 'negative': neg,
                'empty_latent_width': 64, 'empty_latent_height': 64, 'batch_size': batch}},
            '22': {'class_type': 'KSampler (Efficient)', 'inputs': {
                'model': ['21', 0], 'seed': seed, 'steps': 30, 'cfg': 6.5, 'sampler_name': sampler,
                'scheduler': scheduler, 'positive': ['21', 1], 'negative': ['21', 2], 'latent_image': ['21', 3],
                'denoise': 1.0, 'vae': ['21', 4]}},
            '7': {'class_type': 'SaveImageWithMetaData', 'inputs': {'images': ['22', 5], **save_inputs}},
        }
    p = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': ckpt}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': pos, 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': neg, 'clip': ['1', 1]}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 64, 'height': 64, 'batch_size': batch}},
        '5': {'class_type': 'KSampler', 'inputs': {'seed': seed, 'steps': 20, 'cfg': 7.5, 'sampler_name': sampler,
              'scheduler': scheduler, 'denoise': 1.0, 'model': ['1', 0], 'positive': ['2', 0],
              'negative': ['3', 0], 'latent_image': ['4', 0]}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImageWithMetaData', 'inputs': {'images': ['6', 0], **save_inputs}},
    }
    clip_source = ['1', 1]
    model_source = ['1', 0]
    if clip_skip:
        p['9'] = {'class_type': 'CLIPSetLastLayer', 'inputs': {'clip': ['1', 1], 'stop_at_clip_layer': -2}}
        clip_source = ['9', 0]
    if lora:
        p['10'] = {'class_type': 'LoraLoader', 'inputs': {'model': model_source, 'clip': clip_source,
                   'lora_name': 'test-lora.safetensors', 'strength_model': 0.8, 'strength_clip': 0.6}}
        model_source, clip_source = ['10', 0], ['10', 1]
    if lora_model_only:
        p['11'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': model_source,
                   'lora_name': 'sub/other-lora.safetensors', 'strength_model': 0.7}}
        model_source = ['11', 0]
    if rgthree:
        p['20'] = {'class_type': 'Power Lora Loader (rgthree)', 'inputs': {
            'PowerLoraLoaderHeaderWidget': {'type': 'PowerLoraLoaderHeaderWidget'},
            'lora_1': {'on': True, 'lora': 'test-lora.safetensors', 'strength': 0.8},
            'lora_2': {'on': False, 'lora': 'sub/other-lora.safetensors', 'strength': 0.5},
            'lora_3': {'on': True, 'lora': 'sub/other-lora.safetensors', 'strength': 0.25},
            '➕ Add Lora': '', 'model': model_source, 'clip': clip_source}}
        model_source, clip_source = ['20', 0], ['20', 1]
    p['5']['inputs']['model'] = model_source
    p['2']['inputs']['clip'] = clip_source
    p['3']['inputs']['clip'] = clip_source
    if vae_loader:
        p['12'] = {'class_type': 'VAELoader', 'inputs': {'vae_name': 'test-vae.safetensors'}}
        p['6']['inputs']['vae'] = ['12', 0]
    if hires:
        p['13'] = {'class_type': 'LatentUpscaleBy', 'inputs': {'samples': ['5', 0], 'upscale_method': 'nearest-exact',
                   'scale_by': 1.5}}
        p['14'] = {'class_type': 'KSampler', 'inputs': {'seed': seed + 1, 'steps': 12, 'cfg': 5.0,
                   'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 0.5, 'model': model_source,
                   'positive': ['2', 0], 'negative': ['3', 0], 'latent_image': ['13', 0]}}
        p['6']['inputs']['samples'] = ['14', 0]
    if upscale:
        p['15'] = {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': 'test-upscaler.pth'}}
        p['16'] = {'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': ['15', 0], 'image': ['6', 0]}}
        p['7']['inputs']['images'] = ['16', 0]
    if linked_seed:
        p['17'] = {'class_type': 'AMYTestInt', 'inputs': {'value': 987654321}}
        p['5']['inputs']['seed'] = ['17', 0]
    if linked_text:
        p['18'] = {'class_type': 'AMYTestString', 'inputs': {'text': 'linked positive (embedding:test-embedding:0.9)'}}
        p['2']['inputs']['text'] = ['18', 0]
    if extra is not None:
        p['8'] = {'class_type': 'CreateExtraMetaData', 'inputs': dict(extra)}
        p['7']['inputs']['extra_metadata'] = ['8', 0]
        if extra2 is not None:
            p['19'] = {'class_type': 'CreateExtraMetaData', 'inputs': {**extra2, 'extra_metadata': ['8', 0]}}
            p['7']['inputs']['extra_metadata'] = ['19', 0]
    if second_saver:
        p['23'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
        p['24'] = {'class_type': 'SaveImageWithMetaData', 'inputs': {**p['7']['inputs'], 'images': ['23', 0],
                   'filename_prefix': 'first-pass'}}
    return p


def case(name, runs=1, workflow=True, expect='files', allow=(), preexisting=None, disable_metadata=False, **kw):
    return {'name': name, 'prompt': graph(**kw), 'runs': runs, 'expect': expect, 'allow': sorted(allow),
            'extra_pnginfo': {'workflow': WORKFLOW} if workflow else None, 'preexisting': preexisting or {},
            'disable_metadata': disable_metadata}


WEBP = {'DECODED-EXACT-WEBP-EXIF-CONTAINER'}
EXTRA = {'key1': 'Artist', 'value1': 'AMY', 'key2': 'Comment', 'value2': 'parity, ü fixture', 'key3': '',
         'value3': 'dropped', 'key4': 'Empty', 'value4': ''}
EXTRA2 = {'key1': 'Studio', 'value1': 'gate', 'key2': 'Artist', 'value2': 'AMY two'}
EXTRA_DEFAULT_A = {'key1': 'Run', 'value1': 'first'}
EXTRA_DEFAULT_B = {'key1': 'Other', 'value1': 'second'}
CASES = [
    case('png-defaults'),
    case('png-hires-farthest', hires=True, upscale=True),
    case('png-hires-nearest', hires=True, method='Nearest'),
    case('png-by-node-id', hires=True, method='By node ID', node_id=14),
    case('png-by-node-id-missing', method='By node ID', node_id=999, expect='error'),
    case('png-batch2', batch=2),
    case('png-collision-two-runs', runs=2),
    case('png-counter-after-existing', preexisting={'ComfyUI_00041_.png': 'x', 'ComfyUI_00007_.json': 'x',
                                                    'ComfyUI_notcounter.png': 'x', 'ComfyUIx_00099_.png': 'x'}),
    case('png-no-counter', counter=False),
    case('png-no-counter-json-overwrite', counter=False, save_json=True, preexisting={'ComfyUI.json': 'old'}),
    case('png-no-counter-existing', counter=False, preexisting={'ComfyUI.png': 'old'}, expect='refusal'),
    case('png-no-counter-batch2', counter=False, batch=2, expect='refusal'),
    case('png-workflow-json', save_json=True),
    case('png-workflow-json-no-workflow', save_json=True, workflow=False, expect='error'),
    case('png-no-workflow-image', save_wf_image=False, allow={'DECODED-EXACT-PNG-REPEATED-KEYWORD'}),
    case('png-no-workflow-image-no-extra-pnginfo', save_wf_image=False, workflow=False),
    case('png-no-extra-pnginfo', workflow=False),
    case('webp-lossless', fmt='webp', allow=WEBP),
    case('webp-lossy-q80', fmt='webp', lossless=False, quality=80, allow=WEBP),
    case('webp-lossy-json-batch2', fmt='webp', lossless=False, quality=55, save_json=True, batch=2, allow=WEBP),
    case('jpeg-refused', fmt='jpeg', quality=90, expect='refusal'),
    case('civitai-karras', civitai=True),
    case('civitai-unmapped', civitai=True, sampler='ipndm', scheduler='karras'),
    case('civitai-3m-exponential', civitai=True, sampler='dpmpp_3m_sde', scheduler='exponential'),
    case('placeholders', prefix='%seed%_%width%x%height%_%pprompt:12%_%nprompt%_%model:6%_%date:yyyy-MM-dd hhmmss%'),
    case('date-default-and-subfolders', prefix='by-model/%model%/%date:yyyy%/img_%seed%_%date%'),
    case('compute-vars-prefix', prefix='run_%year%%month%/img_%width%_%hour%%minute%', expect='known:stray-dir'),
    case('escape-prefix', prefix='../escape/img', expect='known:escape'),
    case('batch-num-prefix', prefix='img_%batch_num%', expect='refusal'),
    case('empty-prefix', prefix='', expect='refusal'),
    case('prefix-backslash', prefix='.\\CMYK\\image', expect='refusal'),
    case('prefix-backslash-folder', prefix='renders\\img_%seed%', expect='refusal'),
    case('extra-metadata', extra=EXTRA),
    case('extra-metadata-chain', extra=EXTRA, extra2=EXTRA2),
    case('extra-metadata-default-a', extra=EXTRA_DEFAULT_A),
    case('extra-metadata-default-b', extra=EXTRA_DEFAULT_B),
    case('lora-embedding-vae-clipskip', lora=True, vae_loader=True, clip_skip=True),
    case('lora-model-only', lora_model_only=True),
    case('embedding-subfolder-and-weight', pos='portrait embedding:emb2 (embedding:test-embedding:1.2) embedding:sub/emb2'),
    case('embedding-trailing-comma', pos='portrait, embedding:emb2, more', expect='error'),
    case('embedding-missing', pos='portrait, embedding:not-there', expect='error'),
    case('sdxl-tokenizer', ckpt='sdxl-ckpt.safetensors'),
    case('renamed-tokenizer', ckpt='renamed-tok.safetensors', expect='known:v1-tokenizer-crash'),
    case('plain-tokenizer-embedding', ckpt='plain-tok.safetensors', expect='known:v1-tokenizer-crash'),
    case('plain-tokenizer-no-embedding', ckpt='plain-tok.safetensors', pos='a plain prompt'),
    case('linked-seed-and-text', linked_seed=True, linked_text=True),
    case('flux-style', flux=True),
    case('rgthree-power-lora', rgthree=True),
    case('efficiency-loader', efficiency=True),
    case('two-savers', hires=True, second_saver=True),
    case('host-disable-metadata-png', disable_metadata=True, expect='known:disable-metadata'),
    case('host-disable-metadata-webp', disable_metadata=True, fmt='webp', expect='known:disable-metadata'),
]
# The expected error/difference of each non-file case (checked on both sides, exactly).
# (execution.py:878 reports exception_message as "{exception}\n{tips}", tips empty here)
KNOWN = {
    'renamed-tokenizer': {'original': ('AttributeError', "'SD1Tokenizer' object has no attribute 'clip_l'\n")},
    'plain-tokenizer-embedding': {'original': ('AttributeError', "'NoneType' object has no attribute 'embedding_directory'\n")},
}
ESCAPE_FIRST_LINE = '**** ERROR: Saving image outside the output folder is not allowed.'


def run_side(side):
    out = WORK / side
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-I', '-B', str(TESTS / 'nk_parity_worker.py'), side, str(WORK / 'cases.json'),
           str(out), str(FIXTURES)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    (RESULTS / f'worker-{side}.log').write_text(proc.stdout[-20000:] + '\n--- stderr ---\n' + proc.stderr[-40000:])
    if proc.returncode != 0 or not (out / 'report.json').exists():
        raise RuntimeError(f'{side} worker failed rc={proc.returncode}: {proc.stderr[-2000:]}')
    (RESULTS / f'worker-{side}.json').write_bytes((out / 'report.json').read_bytes())
    return json.loads((out / 'report.json').read_text())


def _decoded_png_equal(a, b):
    return a.get('pixels_sha256') == b.get('pixels_sha256') and a.get('pil_text') == b.get('pil_text') \
        and a.get('size') == b.get('size') and a.get('mode') == b.get('mode')


def compare_files(a, b, allow):
    """Return (verdict, notes) for one file present on both sides."""
    if a['sha256'] == b['sha256']:
        return 'EXACT', []
    if a['path'].endswith('.png') and 'DECODED-EXACT-PNG-REPEATED-KEYWORD' in allow and _decoded_png_equal(a, b):
        keywords_a = [row[1] for row in a['png_chunks'] if row[0] in ('tEXt', 'iTXt', 'zTXt')]
        keywords_b = [row[1] for row in b['png_chunks'] if row[0] in ('tEXt', 'iTXt', 'zTXt')]
        if len(keywords_a) != len(set(keywords_a)) and list(dict.fromkeys(keywords_a)) == keywords_b:
            non_text_a = [row for row in a['png_chunks'] if row[0] not in ('tEXt', 'iTXt', 'zTXt')]
            non_text_b = [row for row in b['png_chunks'] if row[0] not in ('tEXt', 'iTXt', 'zTXt')]
            if non_text_a == non_text_b:
                return 'DECODED-EXACT', [f'V1 repeats PNG text keywords {keywords_a}; V2 writes {keywords_b}; '
                                         'decoded text (last value per keyword) and pixels identical']
    if a['path'].endswith('.webp') and 'DECODED-EXACT-WEBP-EXIF-CONTAINER' in allow:
        same = all(a.get(k) == b.get(k) for k in ('pixels_sha256', 'size', 'mode', 'exif_ifd0',
                                                   'exif_ifd0_has_exif_pointer', 'exif_exif_ifd'))
        image_a = [row for row in a['riff_chunks'] if row[0] in ('VP8 ', 'VP8L', 'ALPH')]
        image_b = [row for row in b['riff_chunks'] if row[0] in ('VP8 ', 'VP8L', 'ALPH')]
        if same and image_a == image_b:
            return 'DECODED-EXACT', [f'WebP image chunks identical; EXIF written by piexif (V1) vs Pillow (V2): '
                                     f'V1 RIFF {[(r[0], r[1]) for r in a["riff_chunks"]]} vs V2 '
                                     f'{[(r[0], r[1]) for r in b["riff_chunks"]]}; decoded EXIF identical']
    return 'MISMATCH', ['file content differs']


def _errors(run):
    return [(e['exception_type'].rsplit('.', 1)[-1], e['exception_message']) for e in run.get('errors', [])]


def _ui(run):
    images = []
    for node_ui in run.get('ui', {}).values():
        images.extend(node_ui.get('images', []))
    return images


def _file_set_verdicts(orig, conv, allow, notes):
    files_o = {f['path']: f for f in orig['files']}
    files_c = {f['path']: f for f in conv['files']}
    if set(files_o) != set(files_c):
        notes.append({'original_files': sorted(files_o), 'v2_files': sorted(files_c)})
        return {'__set__': 'MISMATCH'}
    verdicts = {}
    for path in sorted(files_o):
        verdict, why = compare_files(files_o[path], files_c[path], allow)
        verdicts[path] = verdict
        notes.extend(why)
    return verdicts


def compare_case(spec, orig, conv):
    name = spec['name']
    expect = spec['expect']
    allow = set(spec['allow'])
    if 'harness_error' in orig or 'harness_error' in conv:
        return {'case': name, 'verdict': 'HARNESS-ERROR', 'original': orig.get('harness_error'),
                'v2': conv.get('harness_error')}
    notes = []
    verdict = 'MISMATCH'
    runs_o, runs_c = orig['runs'], conv['runs']
    if len(runs_o) != len(runs_c) or any('validation_error' in r for r in runs_o + runs_c):
        notes.append({'validation': [r.get('validation_error') for r in runs_o + runs_c]})
        return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'notes': notes}
    errors_o = [_errors(r) for r in runs_o]
    errors_c = [_errors(r) for r in runs_c]
    ui_o = [_ui(r) for r in runs_o]
    ui_c = [_ui(r) for r in runs_c]
    images_o = [f for f in orig['files']
                if f['path'].endswith(('.png', '.webp', '.jpeg', '.jpg')) and not f.get('not_an_image')]
    if expect == 'files':
        ok = not any(errors_o) and not any(errors_c) and all(r['success'] for r in runs_o + runs_c) \
            and ui_o == ui_c and images_o and orig['dirs'] == conv['dirs'] \
            and orig['outside_output'] == conv['outside_output'] == []
        files = _file_set_verdicts(orig, conv, allow, notes)
        if not ok:
            notes.append({'errors': [errors_o, errors_c], 'ui': [ui_o, ui_c], 'dirs': [orig['dirs'], conv['dirs']],
                          'images_written': len(images_o)})
        elif 'MISMATCH' not in files.values():
            verdict = 'DECODED-EXACT' if 'DECODED-EXACT' in files.values() else 'EXACT'
        return {'case': name, 'expect': expect, 'verdict': verdict, 'files': files, 'ui': ui_c, 'notes': notes[:8]}
    if expect == 'error':
        files = _file_set_verdicts(orig, conv, allow, notes)
        ok = all(errors_o) and errors_o == errors_c and ui_o == ui_c and 'MISMATCH' not in files.values() \
            and orig['dirs'] == conv['dirs']
        if ok:
            verdict = 'ERROR-PARITY'
        else:
            notes.append({'errors': [errors_o, errors_c], 'ui': [ui_o, ui_c]})
        return {'case': name, 'expect': expect, 'verdict': verdict, 'errors': errors_c, 'files': files,
                'notes': notes[:8]}
    if expect == 'refusal':
        refused = all(e and e[-1][0] == 'SecureConversionRefusal' for e in errors_c)
        ok = refused and not any(errors_o) and images_o and not any(ui_c)
        if ok:
            verdict = 'REFUSED-AS-DESIGNED'
        else:
            notes.append({'errors': [errors_o, errors_c], 'original_images': len(images_o)})
        return {'case': name, 'expect': expect, 'verdict': verdict,
                'v2_refusal': errors_c[-1][-1][1] if errors_c and errors_c[-1] else None,
                'original_files': sorted(f['path'] for f in orig['files']),
                'v2_files': sorted(f['path'] for f in conv['files']), 'notes': notes[:8]}
    if expect == 'known:v1-tokenizer-crash':
        want = KNOWN[name]['original']
        ok = all(e == [want] for e in errors_o) and not any(errors_c) and all(r['success'] for r in runs_c) \
            and not orig['files'] and any(f['path'].endswith('.png') for f in conv['files'])
        verdict = 'KNOWN-DIFFERENCE' if ok else 'MISMATCH'
        return {'case': name, 'expect': expect, 'verdict': verdict, 'original_errors': errors_o,
                'v2_files': sorted(f['path'] for f in conv['files'])}
    if expect == 'known:escape':
        first_o = [[(t, m.split('\n')[0]) for t, m in e] for e in errors_o]
        first_c = [[(t, m.split('\n')[0]) for t, m in e] for e in errors_c]
        ok = first_o == first_c == [[('Exception', ESCAPE_FIRST_LINE)]] and not orig['files'] and not conv['files'] \
            and orig['outside_output'] == ['escape'] and conv['outside_output'] == []
        verdict = 'KNOWN-DIFFERENCE' if ok else 'MISMATCH'
        return {'case': name, 'expect': expect, 'verdict': verdict, 'original_errors': errors_o,
                'v2_errors': errors_c, 'original_outside_output': orig['outside_output'],
                'v2_outside_output': conv['outside_output']}
    if expect == 'known:disable-metadata':
        # V1 skips its metadata block under --disable-metadata (py/nodes/node.py:104-115 upstream): no PNG text, and an
        # empty WebP UserComment. A guest cannot read host flags, so V2 writes the metadata as usual.
        files_o = {f['path']: f for f in orig['files']}
        files_c = {f['path']: f for f in conv['files']}
        same_pixels = set(files_o) == set(files_c) and all(
            files_o[p].get('pixels_sha256') == files_c[p].get('pixels_sha256') for p in files_o)
        v1_empty = all((f.get('pil_text') == {}) if f['path'].endswith('.png') else
                       (f.get('exif_exif_ifd') == {'37510': 'hex:' + b'UNICODE\x00'.hex()}) for f in orig['files'])
        v2_full = all(('parameters' in f.get('pil_text', {})) if f['path'].endswith('.png') else
                      (len(f.get('exif_exif_ifd', {}).get('37510', '')) > 40) for f in conv['files'])
        ok = not any(errors_o) and not any(errors_c) and ui_o == ui_c and images_o and same_pixels and v1_empty and v2_full
        verdict = 'KNOWN-DIFFERENCE' if ok else 'MISMATCH'
        return {'case': name, 'expect': expect, 'verdict': verdict, 'v1_metadata_empty': v1_empty,
                'v2_metadata_written': v2_full, 'pixels_identical': same_pixels}
    if expect == 'known:stray-dir':
        files = _file_set_verdicts(orig, conv, allow, notes)
        extra_dirs = sorted(set(orig['dirs']) - set(conv['dirs']))
        ok = not any(errors_o) and not any(errors_c) and ui_o == ui_c and images_o \
            and set(files.values()) == {'EXACT'} and set(conv['dirs']) <= set(orig['dirs']) \
            and extra_dirs == ['run_%year%%month%']
        verdict = 'KNOWN-DIFFERENCE' if ok else 'MISMATCH'
        return {'case': name, 'expect': expect, 'verdict': verdict, 'files': files,
                'original_only_dirs': extra_dirs, 'notes': notes[:8]}
    raise ValueError(expect)


def raw_evidence(raw, reference):
    rows = {}
    for r, ref in zip(raw['cases'], reference['cases']):
        if 'harness_error' in r:
            rows[r['name']] = {'harness_error': r['harness_error']}
            continue
        rows[r['name']] = {'raw_errors': [_errors(run) for run in r['runs']],
                           'reference_errors': [_errors(run) for run in ref.get('runs', [])],
                           'raw_images': sum(1 for f in r['files'] if f['path'].endswith(('.png', '.webp')))}
    return rows


def compare_schemas(orig, conv):
    """INPUT_TYPES as the executor and /object_info see them. Two projection details are normalised:
    a V2 hidden input reads ('PROMPT',) where V1 declared 'PROMPT' (hidden inputs are not rendered), and
    a V1 class without DESCRIPTION is published as '' (server.py:852), which is what V2's '' is."""
    rows = {}
    for node in ('SaveImageWithMetaData', 'CreateExtraMetaData'):
        so, sc = orig['schemas'][node], conv['schemas'][node]
        issues = []
        for group in ('required', 'optional', 'hidden'):
            go, gc = so['input_types'].get(group, {}), sc['input_types'].get(group, {})
            if list(go) != list(gc):
                issues.append(f'{group} names/order differ: {list(go)} vs {list(gc)}')
                continue
            for key in go:
                vo, vc = go[key], gc[key]
                if group == 'hidden':
                    if not (vo == vc or (isinstance(vc, list) and vc == [vo])):
                        issues.append(f'hidden {key}: {vo} vs {vc}')
                    continue
                type_o, type_c = vo[0], vc[0]
                opts_o = vo[1] if len(vo) > 1 else {}
                opts_c = dict(vc[1]) if len(vc) > 1 else {}
                if isinstance(type_o, list):
                    if not (type_c == 'COMBO' and opts_c.pop('options', None) == type_o):
                        issues.append(f'{key}: combo options differ')
                    opts_c.pop('multiselect', None)
                elif type_o != type_c:
                    issues.append(f'{key}: type {type_o} vs {type_c}')
                if opts_o != opts_c:
                    issues.append(f'{key}: options {opts_o} vs {opts_c}')
        for field in ('return_types', 'output_node', 'category', 'description', 'display_name'):
            vo, vc = so[field], sc[field]
            if field == 'description':
                vo, vc = vo if vo is not None else '', vc if vc is not None else ''
            if vo != vc:
                issues.append(f'{field}: {so[field]!r} vs {sc[field]!r}')
        rows[node] = issues or 'EXACT'
    return rows


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    make_fixtures()
    (WORK / 'cases.json').write_text(json.dumps(CASES, indent=2))
    raw = run_side('original-raw')
    original = run_side('original')
    converted = run_side('v2')
    by_name_o = {c['name']: c for c in original['cases']}
    by_name_c = {c['name']: c for c in converted['cases']}
    rows = [compare_case(spec, by_name_o[spec['name']], by_name_c[spec['name']]) for spec in CASES]
    counts = {}
    for row in rows:
        counts[row['verdict']] = counts.get(row['verdict'], 0) + 1
    # negative control: a one-byte change in a converted PNG must turn an EXACT comparison red
    exact = next((r for r in rows if r['verdict'] == 'EXACT'), None)
    if exact is None:
        control = {'verdict': 'NOT-RUN (no EXACT case to perturb)'}
        exact = {'case': None}
    else:
        spec = next(s for s in CASES if s['name'] == exact['case'])
        tampered = copy.deepcopy(by_name_c[exact['case']])
        target = next(f for f in tampered['files'] if f['path'].endswith('.png'))
        target['sha256'] = hashlib.sha256(target['sha256'].encode()).hexdigest()
        target['pil_text'] = {**target['pil_text'], 'parameters': target['pil_text'].get('parameters', '') + 'X'}
        control = compare_case(spec, by_name_o[exact['case']], tampered)
    schemas = compare_schemas(original, converted)
    report = {'pack': 'comfyui-saveimagewithmetadata', 'pin': 'c9a87453bc4257614c87d28a64a5be9c4fdccba9',
              'harness': 'ComfyUI core 6257422b PromptExecutor (classic cache), all sides; stand-ins for '
                         'model-bearing nodes; reference = original + harness-only cache adapter',
              'reference_adapter': original.get('adapter'),
              'nodes': {'SaveImageWithMetaData': {'cases': len(rows), 'verdicts': counts},
                        'CreateExtraMetaData': {'cases': [r['case'] for r in rows if r['case'].startswith('extra-metadata')],
                                                'verdicts': [r['verdict'] for r in rows if r['case'].startswith('extra-metadata')]}},
              'counts': counts, 'cases': rows, 'schemas': schemas,
              'negative_control': {'case': exact['case'], 'verdict_after_tamper': control['verdict'],
                                   'turned_red': control['verdict'] == 'MISMATCH'},
              'unmodified_original_on_core_6257422b': raw_evidence(raw, original),
              'tokenizer_notes': {'original': original.get('tokenizer_notes'), 'v2': converted.get('tokenizer_notes')},
              'original_save_class': original['save_class'], 'v2_save_class': converted['save_class']}
    (RESULTS / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'schemas': schemas, 'negative_control': report['negative_control']}, indent=1))
    ok = control['verdict'] == 'MISMATCH' and set(counts) <= {
        'EXACT', 'DECODED-EXACT', 'ERROR-PARITY', 'REFUSED-AS-DESIGNED', 'KNOWN-DIFFERENCE'} \
        and all(v == 'EXACT' for v in schemas.values())
    sys.exit(0 if ok else 1)


main()
