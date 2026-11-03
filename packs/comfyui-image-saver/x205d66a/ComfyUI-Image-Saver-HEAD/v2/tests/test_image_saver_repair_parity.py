"""Tier-1 parity for comfyui-image-saver repair rounds: the pristine pack (205d66a9) vs the repaired V2 conversion.

Run in the to-50% gate (DEPS = the pinned piexif wheel, original side only):
  run_in_gate.sh <pack root> <v2/tests> <results> test_image_saver_repair_parity.py [ROUND] [CASE-FILTER]

Two workers execute the same prompts through ComfyUI's real executor (saver_parity_worker.py); the V2 worker runs the
live guest-wire encoder on every V2 node's results and UI. Saved files are compared byte for byte (sha256), and also
by decoded pixels, PNG text chunks (with their order) and the EXIF UserComment of WebP/JPEG.
  EXACT               identical UI, returned values and files
  KNOWN-DIFFERENCE    as SECURE_CONVERSION.md documents (embedded workflow chunk order/format; WebP EXIF layout)
Cases use synthetic inputs only; download_civitai_data is off (no network in the gate).
"""
import copy
import json
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
RESULTS = Path('/results')
WORK = Path('/tmp/amy-saver-parity')
ROUNDS = ['r2']
ROUND = sys.argv[1] if len(sys.argv) > 1 else ROUNDS[-1]
FILTER = sys.argv[2] if len(sys.argv) > 2 else ''
WORKFLOW = {'last_node_id': 21, 'nodes': [{'id': 21, 'type': 'Image Saver Simple', 'widgets_values': []}],
            'links': [], 'version': 0.4}


def n(node_id, class_type, **inputs):
    return {node_id: {'class_type': class_type, 'inputs': inputs}}


def g(*parts):
    out = {}
    for part in parts:
        out.update(part)
    return out


def case(name, prompt, expect='outputs', extra_pnginfo=None, note=''):
    return {'name': name, 'prompt': prompt, 'expect': expect, 'extra_pnginfo': extra_pnginfo, 'note': note}


def image(node_id='2', seed=3, width=96, height=80):
    return n(node_id, 'AMYTestImage', width=width, height=height, batch=1, seed=seed)


def metadata(node_id='20', seed=20261102, **options):
    inputs = dict(additional_hashes='', cfg=2.25, clip_skip=0, custom='fidelity_probe', denoise=0.35,
                  download_civitai_data=False, easy_remix=False, height=80, modelname='', negative='blur',
                  positive='quiet harbor in daylight', sampler_name='euler', scheduler_name='normal', seed_value=seed,
                  steps=2, width=96)
    inputs.update(options)
    return n(node_id, 'Image Saver Metadata', **inputs)


def simple(node_id='21', metadata_node='20', **options):
    inputs = dict(counter=0, embed_workflow=False, extension='png', filename='metadata_primary_seed', images=['2', 0],
                  lossless_webp=True, optimize_png=False, path='fidelity/run', quality_jpeg_or_webp=100,
                  save_workflow_as_json=False, show_preview=True)
    inputs.update(options)
    if metadata_node is not None:
        inputs['metadata'] = [metadata_node, 0]
    return n(node_id, 'Image Saver Simple', **inputs)


def preview(source, node_id):
    return n(node_id, 'PreviewAny', source=source)


R2_CASES = [
    case('simple-png-seed-pair', g(image(), metadata(), simple(),
                                   metadata('baseline_metadata', seed=20261103),
                                   simple('baseline_writer', 'baseline_metadata', filename='metadata_control_seed'),
                                   preview(['21', 1], 'saved_params_probe'), preview(['20', 2], 'metadata_probe'),
                                   preview(['baseline_writer', 1], 'baseline_params')),
         note='live A/B defect: the PNG parameters chunk held the JSON-encoded string'),
    case('simple-png-optimize', g(image(seed=4), metadata(), simple(optimize_png=True))),
    case('simple-png-no-metadata', g(image(seed=5), simple(metadata_node=None, filename='plain'))),
    case('simple-png-multiline-unicode', g(image(seed=6), metadata(positive='a "quoted"\nline two — café 中文',
                                                                   negative='x\ty'), simple())),
    case('simple-png-embed-workflow', g(image(seed=7), metadata(), simple(embed_workflow=True)),
         expect='known:embedded-chunks', extra_pnginfo={'workflow': WORKFLOW}),
    case('simple-webp-lossless', g(image(seed=8), metadata(), simple(extension='webp')), expect='known:exif-layout'),
    case('saver-full-png', g(image(seed=9), n('30', 'Image Saver', images=['2', 0], filename='full_%seed', path='full',
                                              extension='png', steps=2, cfg=2.25, modelname='', sampler_name='euler',
                                              scheduler_name='normal', positive='quiet harbor', negative='blur',
                                              seed_value=11, width=96, height=80, lossless_webp=True,
                                              quality_jpeg_or_webp=100, optimize_png=False, counter=0, denoise=0.35,
                                              clip_skip=0, time_format='%Y-%m-%d-%H%M%S', save_workflow_as_json=False,
                                              embed_workflow=False, additional_hashes='', download_civitai_data=False,
                                              easy_remix=False, show_preview=True, custom=''),
                             preview(['30', 1], 'full_params'))),
]
CASES_BY_ROUND = {'r2': R2_CASES}
CASES = [c for r in ROUNDS[:ROUNDS.index(ROUND) + 1] for c in CASES_BY_ROUND[r]]
if FILTER:
    CASES = [c for c in CASES if FILTER in c['name']]


def run_side(side):
    out = WORK / side
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-I', '-B', str(TESTS / 'saver_parity_worker.py'), side, str(WORK / 'cases.json'),
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


KEYS = ('path', 'sha256', 'pixels_sha256', 'size', 'mode', 'format', 'text', 'text_order', 'user_comment')


def comparable(run):
    ui = {node_id: copy.deepcopy(node_ui) for node_id, node_ui in sorted(run.get('ui', {}).items())}
    files = [{k: f.get(k) for k in KEYS} for f in run['files']]
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
    if err_o or err_c:
        return {**row, 'verdict': 'MISMATCH', 'errors': [err_o, err_c]}
    co, cc = comparable(run_o), comparable(run_c)
    if not co['files']:
        return {**row, 'verdict': 'MISMATCH', 'notes': 'the original saved nothing'}
    if expect.startswith('known:'):
        same_ui = co['ui'] == cc['ui']
        pairs = list(zip(co['files'], cc['files']))
        same_files = len(co['files']) == len(cc['files']) and all(
            a['path'] == b['path'] and a['pixels_sha256'] == b['pixels_sha256'] and a['size'] == b['size']
            for a, b in pairs)
        if expect == 'known:embedded-chunks':
            detail = all(set(a['text']) == set(b['text']) and a['text'].get('parameters') == b['text'].get('parameters')
                         and json.loads(a['text']['workflow']) == json.loads(b['text']['workflow'])
                         and json.loads(a['text']['prompt']) == json.loads(b['text']['prompt']) for a, b in pairs)
            notes = [{'order': [a['text_order'], b['text_order']]} for a, b in pairs]
        else:
            detail = all(a['user_comment'] == b['user_comment'] and a['user_comment'] is not None for a, b in pairs)
            notes = [{'bytes_equal': a['sha256'] == b['sha256']} for a, b in pairs]
        ok = same_ui and same_files and detail
        return {**row, 'verdict': 'KNOWN-DIFFERENCE' if ok else 'MISMATCH', 'notes': notes,
                **({} if ok else {'original': co, 'v2': cc})}
    if co != cc:
        return {**row, 'verdict': 'MISMATCH', 'original': co, 'v2': cc}
    return {**row, 'verdict': 'EXACT', 'observed': co}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (WORK / 'fixtures').mkdir(parents=True, exist_ok=True)
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
    if next((r for r in rows if r['case'] == 'simple-png-seed-pair' and r['verdict'] == 'EXACT'), None):
        spec = next(s for s in CASES if s['name'] == 'simple-png-seed-pair')
        tampered = copy.deepcopy(by_c['simple-png-seed-pair'])
        first = tampered['runs'][-1]['files'][0]
        first['text']['parameters'] = json.dumps(first['text']['parameters'])  # the defect this round fixes
        control = compare(spec, by_o['simple-png-seed-pair'], tampered)
    report = {'pack': 'comfyui-image-saver', 'round': ROUND, 'rounds_run': ROUNDS[:ROUNDS.index(ROUND) + 1],
              'pin': '205d66a9d8035e3ad2ba6c61b7ebf7871664e472', 'host_menus_v2': converted.get('host_menus'),
              'harness': 'ComfyUI core at /core (PromptExecutor, classic cache) on both sides; V2 results and UI '
                         'encoded with the live overlay transport/wire.py; live host catalogue menus on V2 schemas',
              'counts': counts, 'cases': rows,
              'negative_control': {'case': 'simple-png-seed-pair', 'verdict_after_tamper': control['verdict'],
                                   'turned_red': control['verdict'] == 'MISMATCH'}}
    (RESULTS / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'negative_control': report['negative_control'],
                      'not_green': [{k: r.get(k) for k in ('case', 'verdict', 'errors', 'validation', 'notes', 'original', 'v2')}
                                    for r in rows if r['verdict'] not in ('EXACT', 'KNOWN-DIFFERENCE')]},
                     indent=1)[:15000])
    ok = set(counts) <= {'EXACT', 'KNOWN-DIFFERENCE'} and control['verdict'] in ('MISMATCH', 'NOT-RUN')
    sys.exit(0 if ok else 1)


main()
