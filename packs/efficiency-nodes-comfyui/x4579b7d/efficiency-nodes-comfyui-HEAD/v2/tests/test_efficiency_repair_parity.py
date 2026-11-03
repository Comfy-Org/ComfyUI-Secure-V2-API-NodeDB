"""Tier-1 parity for efficiency-nodes-comfyui repair rounds: the pristine pack (4579b7d6) vs the repaired V2 conversion.

Run in the to-50% gate:
  run_in_gate.sh <pack root> <v2/tests> <results> test_efficiency_repair_parity.py [ROUND] [CASE-FILTER]

Two workers execute the same prompts through ComfyUI's real executor (eff_parity_worker.py); the V2 worker runs the
live guest-wire encoder on every V2 node's results and UI, and applies the live host's catalogue menus. Each case
declares its expected outcome (EXACT, ERROR-PARITY, KNOWN-DIFFERENCE). A V2-only check then confirms that the
samplers' normalisers turn each SCRIPT tuple back into exactly the fields their sampling code reads.
Cases use synthetic inputs only; no upstream media, workflows or model files.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
RESULTS = Path('/results')
WORK = Path('/tmp/amy-eff-parity')
ROUNDS = ['r1']
ROUND = sys.argv[1] if len(sys.argv) > 1 else ROUNDS[-1]
FILTER = sys.argv[2] if len(sys.argv) > 2 else ''
CONTROLNET = 'amy-cn.safetensors'


def n(node_id, class_type, **inputs):
    return {node_id: {'class_type': class_type, 'inputs': inputs}}


def g(*parts):
    out = {}
    for part in parts:
        out.update(part)
    return out


def case(name, prompt, expect='outputs', note=''):
    return {'name': name, 'prompt': prompt, 'expect': expect, 'extra_pnginfo': None, 'note': note}


def preview(source, node_id='99'):
    return n(node_id, 'PreviewAny', source=source)


def noise(node_id='1', rng='gpu', cfg_denoiser=False, add_seed_noise=False, seed=0, weight=0.015, script=None):
    inputs = dict(rng_source=rng, cfg_denoiser=cfg_denoiser, add_seed_noise=add_seed_noise, seed=seed, weight=weight)
    if script is not None:
        inputs['script'] = script
    return n(node_id, 'Noise Control Script', **inputs)


def tile(node_id='2', strategy='simple', script=None, **options):
    inputs = dict(upscale_by=1.5, tile_size=256, tiling_strategy=strategy, tiling_steps=2, seed=20261102, denoise=0.35,
                  use_controlnet=False, tile_controlnet=CONTROLNET, strength=1.0)
    inputs.update(options)
    if script is not None:
        inputs['script'] = script
    return n(node_id, 'Tiled Upscaler Script', **inputs)


def xyplot(x=None, y=None, node_id='plot', **options):
    inputs = dict(grid_spacing=4, XY_flip='False', Y_label_orientation='Horizontal', cache_models='True',
                  ksampler_output_image='Images')
    inputs.update(options)
    if x is not None:
        inputs['X'] = x
    if y is not None:
        inputs['Y'] = y
    return n(node_id, 'XY Plot', **inputs)


SEEDS = n('x', 'XY Input: Seeds++ Batch', batch_count=2)
CFG = n('y', 'XY Input: CFG Scale', batch_count=2, first_cfg=6.0, last_cfg=8.0)
STEPS = n('s', 'XY Input: Steps', target_parameter='steps', batch_count=3, first_step=10, last_step=20,
          first_start_step=0, last_start_step=10, first_end_step=10, last_end_step=20, first_refine_step=10,
          last_refine_step=20)

R1_CASES = [
    case('noise-gpu', g(noise(), preview(['1', 0])), note='live A/B defect: the SCRIPT value was a dict with named keys'),
    case('noise-cpu', g(noise(rng='cpu'), preview(['1', 0]))),
    case('noise-flags', g(noise(rng='nv', cfg_denoiser=True, add_seed_noise=True, seed=123, weight=0.5),
                          preview(['1', 0]))),
    case('tile-simple', g(tile(), preview(['2', 0]))),
    case('tile-random-strict', g(tile(strategy='random strict', upscale_by=2.0, tile_size=512, tiling_steps=7,
                                      seed=5, denoise=0.6, strength=0.5), preview(['2', 0]))),
    case('tile-none-unconnected', g(tile(strategy='none'), preview(['2', 0]))),
    case('tile-none-passthrough', g(noise(), tile(strategy='none', script=['1', 0]), preview(['2', 0]))),
    case('noise-then-tile', g(noise(), tile(script=['1', 0]), preview(['2', 0]))),
    case('tile-then-noise', g(tile(), noise(node_id='3', script=['2', 0]), preview(['3', 0]))),
    case('xyplot-seeds-cfg', g(SEEDS, CFG, xyplot(['x', 0], ['y', 0]), preview(['plot', 0])),
         note='live A/B defect: the xyplot value was a dict with named keys'),
    case('xyplot-flip-plot', g(SEEDS, CFG, xyplot(['x', 0], ['y', 0], XY_flip='True', ksampler_output_image='Plot',
                                                  cache_models='False', grid_spacing=0, Y_label_orientation='Vertical'),
                               preview(['plot', 0]))),
    case('xyplot-steps-x-only', g(STEPS, xyplot(['s', 0]), preview(['plot', 0]))),
    case('xyplot-unconnected', g(xyplot(), preview(['plot', 0]))),
    case('xyplot-same-type', g(SEEDS, n('x2', 'XY Input: Seeds++ Batch', batch_count=3), xyplot(['x', 0], ['x2', 0]),
                               preview(['plot', 0]))),
]
CASES_BY_ROUND = {'r1': R1_CASES}
CASES = [c for r in ROUNDS[:ROUNDS.index(ROUND) + 1] for c in CASES_BY_ROUND[r]]
if FILTER:
    CASES = [c for c in CASES if FILTER in c['name']]

UNIT_CHECK = r'''
import asyncio, importlib.util, json, sys
sys.path[:0] = ["/core"]
sys.argv = ["unit", "--cpu"]
import comfy.options
comfy.options.enable_args_parsing()
spec = importlib.util.spec_from_file_location("_amy_eff_v2", "/pack/v2/__init__.py", submodule_search_locations=["/pack/v2"])
package = importlib.util.module_from_spec(spec); sys.modules["_amy_eff_v2"] = package; spec.loader.exec_module(package)
nodes = sys.modules["_amy_eff_v2._secure_nodes"]
checks = {}
# the fields the samplers read before this round (the old producers' dicts), from the new tuples
checks["noise"] = nodes._script_noise(("gpu", True, False, 7, 0.25)) == {
    "rng_source": "gpu", "cfg_denoiser": True, "add_seed_noise": False, "seed": 7, "weight": 0.25}
checks["tile"] = nodes._script_tile((1.5, 256, "simple", 2, 20261102, 0.35, None, 1.0)) == {
    "upscale_by": 1.5, "tile_size": 256, "strategy": "simple", "steps": 2, "seed": 20261102, "denoise": 0.35,
    "control_net": None, "strength": 1.0}
checks["xyplot"] = nodes._script_xyplot(("Seeds++ Batch", [0, 1], "CFG Scale", [6.0, 8.0], 4, "Horizontal", "True",
                                         False, "plot", None)) == {
    "x_type": "Seeds++ Batch", "x_values": [0, 1], "y_type": "CFG Scale", "y_values": [6.0, 8.0], "grid_spacing": 4,
    "y_label_orientation": "Horizontal", "cache_models": True, "plot_as_output": False, "node_id": "plot",
    "dependencies": None}
checks["xyplot-cache-false"] = nodes._script_xyplot(("A", [""], "B", [""], 0, "Vertical", "False", True, "1", None))["cache_models"] is False
checks["dict-passthrough"] = nodes._script_noise({"rng_source": "cpu"}) == {"rng_source": "cpu"} and nodes._script_tile(None) is None
print(json.dumps(checks))
'''


def run_side(side):
    out = WORK / side
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-I', '-B', str(TESTS / 'eff_parity_worker.py'), side, str(WORK / 'cases.json'),
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
    if err_o or err_c:
        return {**row, 'verdict': 'MISMATCH', 'errors': [err_o, err_c]}
    co, cc = comparable(run_o), comparable(run_c)
    if not co['ui'] and not co['files']:
        return {**row, 'verdict': 'MISMATCH', 'notes': 'nothing observable on the original side'}
    if co != cc:
        return {**row, 'verdict': 'MISMATCH', 'original': co, 'v2': cc}
    return {**row, 'verdict': 'EXACT', 'observed': co}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (WORK / 'fixtures' / 'controlnet').mkdir(parents=True, exist_ok=True)
    (WORK / 'fixtures' / 'controlnet' / CONTROLNET).write_bytes(b'AMY-FIXTURE-NOT-LOADED')  # menu entry only
    (WORK / 'cases.json').write_text(json.dumps(CASES, indent=1))
    original = run_side('original')
    converted = run_side('v2')
    by_o = {c['name']: c for c in original['cases']}
    by_c = {c['name']: c for c in converted['cases']}
    rows = [compare(spec, by_o[spec['name']], by_c[spec['name']]) for spec in CASES]
    counts = {}
    for row in rows:
        counts[row['verdict']] = counts.get(row['verdict'], 0) + 1
    unit = subprocess.run([sys.executable, '-I', '-B', '-c', UNIT_CHECK], capture_output=True, text=True, timeout=600)
    try:
        unit_checks = json.loads(unit.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        unit_checks = {'error': unit.stderr[-2000:]}
    control = {'verdict': 'NOT-RUN'}
    if next((r for r in rows if r['case'] == 'noise-gpu' and r['verdict'] == 'EXACT'), None):
        spec = next(s for s in CASES if s['name'] == 'noise-gpu')
        tampered = copy.deepcopy(by_c['noise-gpu'])
        tampered['runs'][-1]['ui']['99']['text'][0] = tampered['runs'][-1]['ui']['99']['text'][0].replace('0.015', '0.016')
        control = compare(spec, by_o['noise-gpu'], tampered)
    report = {'pack': 'efficiency-nodes-comfyui', 'round': ROUND, 'rounds_run': ROUNDS[:ROUNDS.index(ROUND) + 1],
              'pin': '4579b7d6076b2870998a08f5d37883fbc8261ff2', 'host_menus_v2': converted.get('host_menus'),
              'harness': 'ComfyUI core at /core (PromptExecutor, classic cache) on both sides; V2 results and UI '
                         'encoded with the live overlay transport/wire.py; live host catalogue menus on V2 schemas',
              'counts': counts, 'cases': rows, 'v2_normaliser_checks': unit_checks,
              'negative_control': {'case': 'noise-gpu', 'verdict_after_tamper': control['verdict'],
                                   'turned_red': control['verdict'] == 'MISMATCH'}}
    (RESULTS / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'negative_control': report['negative_control'],
                      'v2_normaliser_checks': unit_checks,
                      'not_green': [{k: r.get(k) for k in ('case', 'verdict', 'errors', 'original', 'v2')} for r in rows
                                    if r['verdict'] not in ('EXACT', 'ERROR-PARITY', 'KNOWN-DIFFERENCE')]},
                     indent=1)[:12000])
    ok = (set(counts) <= {'EXACT', 'ERROR-PARITY', 'KNOWN-DIFFERENCE'} and control['verdict'] in ('MISMATCH', 'NOT-RUN')
          and unit_checks and all(v is True for v in unit_checks.values()))
    sys.exit(0 if ok else 1)


main()
