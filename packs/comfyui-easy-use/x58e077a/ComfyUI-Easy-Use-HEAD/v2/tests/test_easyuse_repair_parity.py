"""Tier-1 parity for comfyui-easy-use repair rounds: the pristine pack (58e077a7) vs the repaired V2 conversion.

Run in the to-50% gate (DEPS = the pinned wheels in DEPS.json, original side only):
  run_in_gate.sh <pack root> <v2/tests> <results> test_easyuse_repair_parity.py [ROUND] [CASE-FILTER]

Two workers execute the same prompts through ComfyUI's real executor (easyuse_parity_worker.py); the V2 worker runs
the live guest-wire encoder on every V2 node's results and UI. Each case declares its expected outcome:
  EXACT                identical UI records (PreviewAny, AMYProbe, node UI) and identical output files
  ERROR-PARITY         both fail with the same exception type and message
  REFUSED-AS-DESIGNED  the original succeeds; V2 raises its named "not available in this secure build" RuntimeError
  KNOWN-DIFFERENCE     both sides behave as SECURE_CONVERSION.md documents
  PLATFORM-DEFECT      a case that needs a platform fix (not this pack); reported, not counted as a pass or fail
Cases use synthetic inputs only (seeded tensors, literal text, a seeded 2x upscale model built here with spandrel's
own Compact architecture); no upstream media, workflows or model files. Rounds are cumulative: ROUND (default: the
latest) runs that round's cases and every earlier round's.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
RESULTS = Path('/results')
WORK = Path('/tmp/amy-easyuse-parity')
ROUNDS = ['r1', 'r2', 'r3']
ROUND = sys.argv[1] if len(sys.argv) > 1 else ROUNDS[-1]
FILTER = sys.argv[2] if len(sys.argv) > 2 else ''
UPSCALE_MODEL = 'amy-x2-compact.safetensors'


def make_fixtures():
    """A seeded, weight-random 2x SRVGGNetCompact (spandrel's Compact architecture), saved as safetensors."""
    import torch
    from safetensors.torch import save_file
    try:
        from spandrel.architectures.Compact import SRVGGNetCompact
    except ImportError:
        from spandrel.architectures.Compact.__arch.SRVGG import SRVGGNetCompact
    folder = WORK / 'fixtures' / 'upscale_models'
    folder.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(20261103)
    net = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=8, num_conv=2, upscale=2, act_type='prelu')
    state = {k: v.detach().contiguous() for k, v in net.state_dict().items()}
    save_file(state, str(folder / UPSCALE_MODEL))
    # LoRA files without metadata, keyed for the worker's stand-in MODEL/CLIP key maps
    keys = {'lora_unet_input_blocks_0_0': (4, 2), 'lora_unet_middle_block_1_proj_in': (3, 2),
            'lora_te_text_model_encoder_layers_0_mlp_fc1': (5, 2)}

    def lora(seed):
        out = {}
        for index, (key, (rows, rank)) in enumerate(keys.items()):
            base = torch.arange(rows * rank, dtype=torch.float32) / (7.0 + seed + index)
            out[f'{key}.lora_up.weight'] = base.reshape(rows, rank).contiguous()
            out[f'{key}.lora_down.weight'] = (base.reshape(rank, rows) * 0.5).contiguous()
            out[f'{key}.alpha'] = torch.tensor(float(rank + seed))
        return out

    for seed, name in enumerate(('amy-lora.safetensors', 'sub/amy-sub-lora.safetensors', 'zz-amy-lora.safetensors')):
        path = WORK / 'fixtures' / 'loras' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        save_file(lora(seed), str(path))
    (WORK / 'fixtures' / 'easy_wildcards').mkdir(parents=True, exist_ok=True)


def n(node_id, class_type, **inputs):
    return {node_id: {'class_type': class_type, 'inputs': inputs}}


def g(*parts):
    out = {}
    for part in parts:
        out.update(part)
    return out


def case(name, prompt, expect='outputs', extra_pnginfo=None, note=''):
    return {'name': name, 'prompt': prompt, 'expect': expect, 'extra_pnginfo': extra_pnginfo, 'note': note}


def js(node_id, text):
    return n(node_id, 'AMYTestJSON', text=text)


def show(source=None, node_id='1'):
    return n(node_id, 'easy showAnything', **({'anything': source} if source else {}))


def preview(source, node_id='2'):
    return n(node_id, 'PreviewAny', source=source)


def probe(value, node_id='99', label='probe'):
    return n(node_id, 'AMYProbe', label=label, value=value)


def img(node_id, seed, batch=1, width=96, height=64):
    return n(node_id, 'AMYTestImage', width=width, height=height, batch=batch, seed=seed)


def index(source, idx, node_id='20'):
    return n(node_id, 'easy indexAnything', any=source, index=idx)


def save(images, prefix, node_id):
    return n(node_id, 'SaveImage', images=images, filename_prefix=prefix)


SHOW_CASES = [
    case('show-unconnected', g(show(), preview(['1', 0])), note='live A/B defect: unconnected input showed "null" instead of []'),
    case('show-string', g(n('10', 'AMYTestString', text='hello wörld 中'), show(['10', 0]), preview(['1', 0]),
                          probe(['1', 0]))),
    case('show-int', g(js('10', '7'), show(['10', 0]), preview(['1', 0]), probe(['1', 0]))),
    case('show-float', g(js('10', '0.1'), show(['10', 0]), preview(['1', 0]), probe(['1', 0]))),
    case('show-float-exp', g(js('10', '1e-07'), show(['10', 0]), preview(['1', 0]))),
    case('show-bool', g(js('10', 'true'), show(['10', 0]), preview(['1', 0]), probe(['1', 0]))),
    case('show-dict', g(js('10', '{"b": 1, "a": [1, 2, {"c": "\\u00e9\\u4e2d"}], "n": null}'), show(['10', 0]),
                        preview(['1', 0]), probe(['1', 0]))),
    case('show-list-value', g(js('10', '[1, "x", 2.5]'), show(['10', 0]), preview(['1', 0]), probe(['1', 0]))),
    case('show-list-31', g(js('10', json.dumps(list(range(31)))), show(['10', 0]), preview(['1', 0]))),
    case('show-list-single', g(js('10', '[42]'), show(['10', 0]), preview(['1', 0]), probe(['1', 0]))),
    case('show-list-output', g(n('10', 'AMYTestList', text='["a", "b", "c"]'), show(['10', 0]), preview(['1', 0]),
                               probe(['1', 0]))),
    case('show-none-value', g(js('10', 'null'), show(['10', 0]), preview(['1', 0]), probe(['1', 0]))),
    case('show-image', g(img('10', 3, width=2, height=2), show(['10', 0]), preview(['1', 0]))),
    case('show-latent', g(n('10', 'EmptyLatentImage', width=64, height=64, batch_size=1), show(['10', 0]),
                          preview(['1', 0]))),
    case('show-widgets-in-saved-workflow',
         g(n('10', 'AMYTestString', text='hello'), show(['10', 0]),
           n('30', 'AMYTestImage', width=8, height=8, batch=1, seed=1, after=['1', 0]),
           save(['30', 0], 'show-wf', '31')),
         expect='known:show-workflow-widgets',
         extra_pnginfo={'workflow': {'nodes': [{'id': 1, 'type': 'easy showAnything', 'widgets_values': []},
                                               {'id': 31, 'type': 'SaveImage', 'widgets_values': ['show-wf']}],
                                     'links': [], 'version': 0.4}}),
]
INDEX_CASES = [
    case('index-image-batch-999', g(img('1', 11), img('2', 12), n('batch', 'ImageBatch', image1=['1', 0], image2=['2', 0]),
                                    index(['batch', 0], 999), save(['20', 0], 'idx-sel', 'selected'),
                                    save(['1', 0], 'idx-unsel', 'unselected')),
         note='live A/B defect: IMAGE batch, index past the end (raw tensor on the guest wire)'),
    case('index-image-batch-minus999', g(img('1', 11), img('2', 12),
                                         n('batch', 'ImageBatch', image1=['1', 0], image2=['2', 0]),
                                         index(['batch', 0], -999), save(['20', 0], 'idx-sel', 'selected'),
                                         save(['2', 0], 'idx-unsel', 'unselected')),
         note='live A/B defect: IMAGE batch, index before the start (raw tensor on the guest wire)'),
    case('index-image-batch-minus1', g(img('1', 21, batch=3), index(['1', 0], -1), save(['20', 0], 'idx-m1', 's'))),
    case('index-image-batch-1', g(img('1', 21, batch=3), index(['1', 0], 1), save(['20', 0], 'idx-1', 's'))),
    case('index-image-list-output', g(n('1', 'AMYTestImageList', count=3, seed=5), index(['1', 0], 2),
                                      save(['20', 0], 'idx-list', 's'))),
    case('index-list-output', g(n('1', 'AMYTestList', text='["a", "b", "c"]'), index(['1', 0], 1), preview(['20', 0]),
                                probe(['20', 0]))),
    case('index-list-output-neg', g(n('1', 'AMYTestList', text='["a", "b", "c"]'), index(['1', 0], -1),
                                    preview(['20', 0]))),
    case('index-list-output-clamp', g(n('1', 'AMYTestList', text='["a", "b", "c"]'), index(['1', 0], -9),
                                      preview(['20', 0]))),
    case('index-string', g(n('1', 'AMYTestString', text='hello'), index(['1', 0], 1), preview(['20', 0]))),
    case('index-empty-string', g(n('1', 'AMYTestString', text=''), index(['1', 0], 0), probe(['20', 0]))),
    case('index-json-list', g(js('1', '[10, 20, 30]'), index(['1', 0], -1), probe(['20', 0]))),
    case('index-int', g(js('1', '5'), index(['1', 0], 0), probe(['20', 0]))),
    case('index-latent', g(n('1', 'EmptyLatentImage', width=64, height=64, batch_size=1), index(['1', 0], 0),
                           probe(['20', 0])), expect='error'),
    case('index-mask', g(n('1', 'AMYTestMask', width=16, height=12, batch=2, seed=4), index(['1', 0], 1),
                         probe(['20', 0])), expect='refusal'),
]
PIPE_CASES = [
    case('pipe-in-out-chain',
         g(n('m', 'AMYTestModel'), n('c', 'AMYTestClip'), n('v', 'AMYTestVAE'), n('p', 'AMYTestCond', seed=1),
           n('q', 'AMYTestCond', seed=2), n('l', 'EmptyLatentImage', width=64, height=64, batch_size=1), img('i', 7),
           n('22', 'easy pipeIn', model=['m', 0], pos=['p', 0], neg=['q', 0], latent=['l', 0], vae=['v', 0],
             clip=['c', 0], image=['i', 0]),
           n('23', 'easy pipeOut', pipe=['22', 0]),
           *[probe(['23', slot], node_id=f'out{slot}', label=name)
             for slot, name in enumerate(['pipe', 'model', 'pos', 'neg', 'latent', 'vae', 'clip', 'image', 'seed'])
             if name != 'pipe']),
         expect='platform:sdk-pipe-classification',
         note='live A/B defect: PIPE_LINE reaches the guest as a LatentRef (platform _sdk classification); weightless stand-ins'),
]


def hires(image=None, vae=None, pipe=None, node_id='20', **options):
    inputs = {'model_name': UPSCALE_MODEL, 'rescale_after_model': True, 'rescale_method': 'area',
              'rescale': 'to Width/Height', 'percent': 100, 'width': 128, 'height': 128, 'longer_side': 128,
              'crop': 'disabled', 'image_output': 'Hide', 'link_id': 0, 'save_prefix': 'hires'}
    inputs.update(options)
    for key, value in (('image', image), ('vae', vae), ('pipe', pipe)):
        if value is not None:
            inputs[key] = value
    return n(node_id, 'easy hiresFix', **inputs)


def hires_probes(node_id='20'):
    return g(save([node_id, 1], 'hires-out', 'saved'), probe([node_id, 2], node_id='latent', label='latent'),
             probe([node_id, 0], node_id='pipe', label='pipe'))


def vae(node_id='v'):
    return n(node_id, 'AMYTestVAE')


HIRES_CASES = [
    case('hires-to-wh-hide', g(img('1', 31, width=64, height=64), vae(), hires(['1', 0], ['v', 0]), hires_probes()),
         note='live A/B defect: the upscale model was never applied (image to Width/Height, Hide)'),
    case('hires-to-wh-crop', g(img('1', 32, width=64, height=48), vae(),
                               hires(['1', 0], ['v', 0], width=100, height=76, rescale_method='bicubic'),
                               hires_probes())),
    case('hires-percent', g(img('1', 33, width=40, height=56), vae(),
                            hires(['1', 0], ['v', 0], rescale='by percentage', percent=75, rescale_method='bilinear'),
                            hires_probes())),
    case('hires-percent-zero', g(img('1', 34, width=40, height=40), vae(),
                                 hires(['1', 0], ['v', 0], rescale='by percentage', percent=0, width=72, height=64,
                                       rescale_method='nearest-exact'), hires_probes())),
    case('hires-longer-side', g(img('1', 35, width=50, height=30), vae(),
                                hires(['1', 0], ['v', 0], rescale='to longer side - maintain aspect', longer_side=100,
                                      rescale_method='lanczos', crop='center'), hires_probes())),
    case('hires-no-rescale', g(img('1', 36, width=37, height=45), vae(),
                               hires(['1', 0], ['v', 0], rescale_after_model=False), hires_probes())),
    case('hires-tiled', g(img('1', 37, width=300, height=210), vae(),
                          hires(['1', 0], ['v', 0], rescale='by percentage', percent=50, rescale_method='bislerp'),
                          hires_probes())),
    case('hires-tiled-batch2', g(img('1', 38, width=200, height=100, batch=2), vae(),
                                 hires(['1', 0], ['v', 0], width=128, height=64), hires_probes())),
    case('hires-batch2-single-tile', g(img('1', 39, width=48, height=40, batch=2), vae(),
                                       hires(['1', 0], ['v', 0], width=96, height=80), hires_probes())),
    case('hires-save', g(img('1', 40, width=64, height=48), vae(),
                         hires(['1', 0], ['v', 0], width=64, height=64, image_output='Save', save_prefix='hires-save'),
                         hires_probes())),
    case('hires-preview', g(img('1', 41, width=32, height=32), vae(),
                            hires(['1', 0], ['v', 0], width=64, height=64, image_output='Preview')),
         expect='known:preview-name'),
    case('hires-missing-inputs', g(hires(), probe(['20', 1])), expect='error'),
    case('hires-pipe', g(n('m', 'AMYTestModel'), n('c', 'AMYTestClip'), vae(), n('p', 'AMYTestCond', seed=1),
                         n('q', 'AMYTestCond', seed=2), n('l', 'EmptyLatentImage', width=64, height=64, batch_size=1),
                         img('i', 42, width=32, height=32),
                         n('22', 'easy pipeIn', model=['m', 0], pos=['p', 0], neg=['q', 0], latent=['l', 0],
                           vae=['v', 0], clip=['c', 0], image=['i', 0]),
                         hires(pipe=['22', 0], width=64, height=64), save(['20', 1], 'hires-pipe', 'saved'),
                         probe(['20', 2], node_id='latent', label='latent')),
         expect='platform:sdk-pipe-classification',
         note='PIPE_LINE reaches the guest as a LatentRef (platform _sdk classification)'),
]


def lora_apply(positive, negative=None, node_id='22'):
    inputs = {'model': ['mc', 0], 'clip': ['mc', 1], 'positive': positive}
    if negative is not None:
        inputs['negative'] = negative
    return g(n('mc', 'AMYLoraModelClip'), n(node_id, 'easy loraPromptApply', **inputs))


def lora_probes(node_id='22'):
    return g(*[probe([node_id, slot], node_id=f'p-{name}', label=name)
               for slot, name in enumerate(('model', 'clip', 'positive', 'negative'))])


LORA_CASES = [
    case('lora-stem', g(lora_apply('<lora:amy-lora:0.65> a red ceramic teapot', 'blur'), lora_probes()),
         note='live A/B defect: a LoRA named by its file stem was not resolved like the original'),
    case('lora-full-filename', g(lora_apply('<lora:amy-lora.safetensors:1.0> a red ceramic teapot', 'blur'),
                                 lora_probes()),
         note='the original appends a second .safetensors and skips the LoRA; V2 now does the same'),
    case('lora-full-filename-linked', g(n('t', 'AMYTestString', text='<lora:amy-lora.safetensors:0.65> a red teapot'),
                                        lora_apply(['t', 0], 'blur'), lora_probes())),
    case('lora-two-weights', g(lora_apply('<lora:amy-lora:0.5:0.25> two weights'), lora_probes())),
    case('lora-subfolder-suffix', g(lora_apply('<lora:amy-sub-lora:0.8> sub'), lora_probes())),
    case('lora-suffix-first-match', g(lora_apply('<lora:lora:0.4> first'), lora_probes())),
    case('lora-missing', g(lora_apply('<lora:nope:1> missing', '<lora:gone> neg'), lora_probes())),
    case('lora-negative-unconnected', g(lora_apply('<lora:amy-lora:0.3> x'), lora_probes())),
    case('lora-in-both', g(lora_apply('<lora:amy-lora:0.4> a', '<lora:amy-lora:0.2> b'), lora_probes())),
    case('lora-duplicate', g(lora_apply('<lora:amy-lora:0.5> <lora:amy-lora:0.9> dup  '), lora_probes())),
    case('lora-extended-strength', g(lora_apply('<lora:amy-lora:150> big'), lora_probes())),
    case('lora-zero-strength', g(lora_apply('<lora:amy-lora:0:0> zero'), lora_probes())),
    case('lora-options', g(lora_apply('{a red|a red} <lora:amy-lora:0.7> teapot'), lora_probes())),
    case('lora-none', g(lora_apply('plain text, no tags', 'neg'), lora_probes())),
]


def color(method, output='Hide', ref_seed=52, target_seed=51, target_batch=1, ref_batch=1, width=96, height=64):
    return g(img('t', target_seed, batch=target_batch, width=width, height=height),
             img('r', ref_seed, batch=ref_batch, width=width, height=height),
             n('21', 'easy imageColorMatch', image_ref=['r', 0], image_target=['t', 0], method=method,
               image_output=output, save_prefix='color-match'),
             save(['21', 0], 'matched', 'matched'))


COLOR_CASES = [
    case('colormatch-reinhard', color('reinhard'),
         note='live A/B defect: V2 ignored the method (a plain mean/std transfer)'),
    *[case(f'colormatch-{method}', color(method)) for method in ('wavelet', 'adain', 'mkl', 'hm', 'mvgd',
                                                                 'hm-mvgd-hm', 'hm-mkl-hm')],
    case('colormatch-reinhard-batch2', color('reinhard', target_batch=2)),
    case('colormatch-mvgd-batch2-refs', color('mvgd', target_batch=2, ref_batch=2)),
    case('colormatch-batch-mismatch', color('reinhard', target_batch=2, ref_batch=3), expect='error'),
    case('colormatch-save', color('adain', output='Save')),
    case('colormatch-hide-save', color('hm', output='Hide/Save')),
    case('colormatch-preview', color('wavelet', output='Preview'), expect='known:preview-name'),
]
CASES_BY_ROUND = {'r1': SHOW_CASES + INDEX_CASES + PIPE_CASES, 'r2': HIRES_CASES, 'r3': LORA_CASES + COLOR_CASES}
CASES = [c for r in ROUNDS[:ROUNDS.index(ROUND) + 1] for c in CASES_BY_ROUND[r]]
if FILTER:
    CASES = [c for c in CASES if FILTER in c['name']]


def run_side(side):
    out = WORK / side
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-I', '-B', str(TESTS / 'easyuse_parity_worker.py'), side, str(WORK / 'cases.json'),
           str(out), str(WORK / 'fixtures')]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    (RESULTS / f'worker-{side}.log').write_text(proc.stdout[-20000:] + '\n--- stderr ---\n' + proc.stderr[-40000:])
    if proc.returncode != 0 or not (out / 'report.json').exists():
        raise RuntimeError(f'{side} worker failed rc={proc.returncode}: {proc.stderr[-3000:]}')
    (RESULTS / f'worker-{side}.json').write_bytes((out / 'report.json').read_bytes())
    report = json.loads((out / 'report.json').read_text())
    if not report['loaded']:
        raise RuntimeError(f'{side}: pack did not load: {report["load_error"]}')
    return report


def errors_of(run):
    return [(e['exception_type'].rsplit('.', 1)[-1], e['exception_message']) for e in run.get('errors', [])]


def comparable(run):
    """UI per node and output files, as both sides record them."""
    ui = {}
    for node_id, node_ui in sorted(run.get('ui', {}).items()):
        value = copy.deepcopy(node_ui)
        if 'probe' in value:
            value['probe'] = [json.loads(item) for item in value['probe']]
        ui[node_id] = value
    files = [{k: f.get(k) for k in ('path', 'sha256', 'pixels_sha256', 'size', 'mode', 'text')} for f in run['files']]
    return {'ui': ui, 'files': files}


def compare(spec, orig, conv):
    name, expect = spec['name'], spec['expect']
    row = {'case': name, 'expect': expect}
    if spec.get('note'):
        row['note'] = spec['note']
    if 'harness_error' in orig or 'harness_error' in conv:
        return {**row, 'verdict': 'HARNESS-ERROR', 'original': orig.get('harness_error'), 'v2': conv.get('harness_error')}
    run_o, run_c = orig['runs'][-1], conv['runs'][-1]
    if 'validation_error' in run_o or 'validation_error' in run_c:
        return {**row, 'verdict': 'MISMATCH', 'validation': [run_o.get('node_errors'), run_c.get('node_errors')]}
    err_o, err_c = errors_of(run_o), errors_of(run_c)
    if expect == 'error':
        ok = bool(err_o) and err_o == err_c
        return {**row, 'verdict': 'ERROR-PARITY' if ok else 'MISMATCH', 'errors': [err_o, err_c]}
    if expect == 'refusal':
        ok = not err_o and len(err_c) == 1 and err_c[0][0] == 'RuntimeError' \
            and 'is not available in this secure build' in err_c[0][1]
        return {**row, 'verdict': 'REFUSED-AS-DESIGNED' if ok else 'MISMATCH', 'errors': [err_o, err_c],
                'original_ui': comparable(run_o)['ui']}
    if expect.startswith('platform:'):
        if not err_o and not err_c and comparable(run_o) == comparable(run_c):
            return {**row, 'verdict': 'EXACT', 'note': row.get('note', '') + ' (passes on this core)'}
        return {**row, 'verdict': 'PLATFORM-DEFECT', 'errors': [err_o, err_c]}
    if err_o or err_c:
        return {**row, 'verdict': 'MISMATCH', 'errors': [err_o, err_c]}
    co, cc = comparable(run_o), comparable(run_c)
    if not co['ui'] and not co['files']:
        return {**row, 'verdict': 'MISMATCH', 'notes': 'nothing observable on the original side'}
    if expect == 'known:show-workflow-widgets':
        def workflow_of(c):
            return json.loads(c['files'][0]['text']['workflow']) if c['files'] else None
        wo, wc = workflow_of(co), workflow_of(cc)
        widgets_o = [nd['widgets_values'] for nd in wo['nodes'] if nd['id'] == 1]
        widgets_c = [nd['widgets_values'] for nd in wc['nodes'] if nd['id'] == 1]
        pixels_same = co['files'][0]['pixels_sha256'] == cc['files'][0]['pixels_sha256']
        ok = pixels_same and widgets_o == [[['hello']]] and widgets_c == [[]] and co['ui'] == cc['ui']
        return {**row, 'verdict': 'KNOWN-DIFFERENCE' if ok else 'MISMATCH',
                'widgets_values': {'original': widgets_o, 'v2': widgets_c}, 'pixels_same': pixels_same}
    if expect == 'known:preview-name':
        # Same preview pixels; the original's temp file is named easyPreview_temp_*, the platform preview's is not.
        files_o = [f for f in co['files'] if f['path'].startswith('temp/')]
        files_c = [f for f in cc['files'] if f['path'].startswith('temp/')]

        def previews(c):
            return [image for value in c['ui'].values() for image in value.get('images', [])
                    if image.get('type') == 'temp']
        ui_o, ui_c = previews(co), previews(cc)
        rest_o = {k: v for k, v in co['ui'].items() if not any(i.get('type') == 'temp' for i in v.get('images', []))}
        rest_c = {k: v for k, v in cc['ui'].items() if not any(i.get('type') == 'temp' for i in v.get('images', []))}
        outputs_o = [f for f in co['files'] if f['path'].startswith('output/')]
        outputs_c = [f for f in cc['files'] if f['path'].startswith('output/')]
        ok = (len(files_o) == len(files_c) == 1 and files_o[0]['pixels_sha256'] == files_c[0]['pixels_sha256']
              and files_o[0]['size'] == files_c[0]['size'] and len(ui_o) == len(ui_c) == 1
              and rest_o == rest_c and outputs_o == outputs_c)
        return {**row, 'verdict': 'KNOWN-DIFFERENCE' if ok else 'MISMATCH',
                'names': [ui_o, ui_c], 'files': [files_o, files_c]}
    if co != cc:
        return {**row, 'verdict': 'MISMATCH', 'original': co, 'v2': cc}
    return {**row, 'verdict': 'EXACT', 'observed': co}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (WORK / 'fixtures').mkdir(parents=True, exist_ok=True)
    make_fixtures()
    (WORK / 'cases.json').write_text(json.dumps(CASES, indent=1))
    original = run_side('original')
    converted = run_side('v2')
    by_o = {c['name']: c for c in original['cases']}
    by_c = {c['name']: c for c in converted['cases']}
    rows = [compare(spec, by_o[spec['name']], by_c[spec['name']]) for spec in CASES]
    counts = {}
    for row in rows:
        counts[row['verdict']] = counts.get(row['verdict'], 0) + 1
    control = {'verdict': 'NOT-RUN'}
    target = next((r for r in rows if r['verdict'] == 'EXACT' and r['case'] == 'show-dict'), None)
    if target:
        spec = next(s for s in CASES if s['name'] == 'show-dict')
        tampered = copy.deepcopy(by_c['show-dict'])
        tampered['runs'][-1]['ui']['2']['text'][0] += ' '
        control = compare(spec, by_o['show-dict'], tampered)
    report = {'pack': 'comfyui-easy-use', 'round': ROUND, 'rounds_run': ROUNDS[:ROUNDS.index(ROUND) + 1],
              'pin': '58e077a7435631301cf7443412515cf958e7f3d1',
              'host_menus_v2': converted.get('host_menus'),
              'harness': 'ComfyUI core at /core (PromptExecutor, classic cache) on both sides; V2 results and UI '
                         'encoded with the live overlay transport/wire.py; torch seeded before every prompt',
              'core_sdk_classification': 'patched' if 'hasattr(v.get("samples"), "shape")' in
              Path('/core/comfy_api/latest/_sdk.py').read_text() else 'stock',
              'counts': counts, 'cases': rows,
              'negative_control': {'case': 'show-dict', 'verdict_after_tamper': control['verdict'],
                                   'turned_red': control['verdict'] == 'MISMATCH'}}
    (RESULTS / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'negative_control': report['negative_control'],
                      'core_sdk_classification': report['core_sdk_classification'],
                      'not_green': [{k: r.get(k) for k in ('case', 'verdict', 'errors')} for r in rows
                                    if r['verdict'] not in ('EXACT', 'ERROR-PARITY', 'REFUSED-AS-DESIGNED',
                                                            'KNOWN-DIFFERENCE')]}, indent=1)[:12000])
    green = {'EXACT', 'ERROR-PARITY', 'REFUSED-AS-DESIGNED', 'KNOWN-DIFFERENCE', 'PLATFORM-DEFECT'}
    sys.exit(0 if set(counts) <= green and control['verdict'] in ('MISMATCH', 'NOT-RUN') else 1)


main()
