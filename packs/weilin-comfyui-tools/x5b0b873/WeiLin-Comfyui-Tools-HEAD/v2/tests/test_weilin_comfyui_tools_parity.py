"""Tier-1 parity: weilin-comfyui-tools (5b0b8730) vs its Secure Nodes V2 conversion.

Run in the to-50% gate:
  run_in_gate.sh <pack root> <v2/tests> <results> test_weilin_comfyui_tools_parity.py

Two workers execute the same prompts through ComfyUI's real executor (weilin_parity_worker.py): the
pristine pack (with harness stand-ins for its two import-time side effects only) and V2. An AMYProbe
output node reports each prompt node's text, CONDITIONING tensors, and the MODEL/CLIP LoRA patches as UI.
Every case declares its expected outcome:
  EXACT            identical UI records (texts, conditioning tensors, every LoRA patch and strength)
  ERROR-PARITY     both fail with the same exception type and message
  KNOWN-DIFFERENCE both sides behave exactly as SECURE_CONVERSION.md documents
Anything else is MISMATCH.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
RESULTS = Path('/results')
WORK = Path('/tmp/amy-weilin-parity')
FIXTURES = WORK / 'fixtures'
NODE_IDS = ('WeiLinPromptUI', 'WeiLinPromptUIWithoutLora', 'WeiLinPromptUIOnlyLoraStack')
LORA_KEYS = {'lora_unet_input_blocks_0_0': (4, 2), 'lora_unet_middle_block_1_proj_in': (3, 2),
             'lora_te_text_model_encoder_layers_0_mlp_fc1': (5, 2)}


def make_fixtures():
    import torch
    from safetensors.torch import save_file

    (FIXTURES / 'checkpoints').mkdir(parents=True, exist_ok=True)
    (FIXTURES / 'checkpoints' / 'test-ckpt.safetensors').write_bytes(b'AMY-FIXTURE' * 50)

    def tensors(seed):
        out = {}
        for index, (key, (rows, rank)) in enumerate(LORA_KEYS.items()):
            base = torch.arange(rows * rank, dtype=torch.float32) / (7.0 + seed + index)
            out[f'{key}.lora_up.weight'] = base.reshape(rows, rank).contiguous()
            out[f'{key}.lora_down.weight'] = (base.reshape(rank, rows) * 0.5).contiguous()
            out[f'{key}.alpha'] = torch.tensor(float(rank + seed))
        return out

    loras = {
        'tagged-lora_v2.safetensors': {'ss_tag_frequency': json.dumps(
            {'10_sks': {'1girl': 30, 'sks style': 25, 'masterpiece': 40, 'red scarf': 25}, '5_other': {'sks style': 3}}),
            'ss_output_name': 'tagged-lora-v2'},
        'named-lora-v3.safetensors': {'ss_output_name': 'MyStyle-v3'},
        'plain_lora_12.safetensors': None,
        'common-only.safetensors': {'ss_tag_frequency': json.dumps({'b': {'solo': 5, '1girl': 9}})},
        'sub/other-lora.safetensors': None,
    }
    for seed, (name, metadata) in enumerate(loras.items()):
        path = FIXTURES / 'loras' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        save_file(tensors(seed), str(path), metadata=metadata)
    torch.save(tensors(9), str(FIXTURES / 'loras' / 'legacy-lora.pt'))


def lora_item(name, weight, text_weight, trigger=None):
    item = {'lora': name, 'weight': weight, 'text_encoder_weight': text_weight}
    if trigger is not None:
        item['trigger_weight'] = trigger
    return item


def prompt_ui(positive, lora_str='', auto_random=False, random_template='', model=True, clip=True, opt_text=None):
    p = {'1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'test-ckpt.safetensors'}},
         '2': {'class_type': 'WeiLinPromptUI', 'inputs': {
             'positive': positive, 'auto_random': auto_random, 'lora_str': lora_str, 'temp_str': '',
             'temp_lora_str': '', 'random_template': random_template}},
         '3': {'class_type': 'AMYProbe', 'inputs': {'label': 'ui', 'text': ['2', 0], 'conditioning': ['2', 1],
                                                    'clip': ['2', 2], 'model': ['2', 3]}}}
    if clip:
        p['2']['inputs']['opt_clip'] = ['1', 1]
    if model:
        p['2']['inputs']['opt_model'] = ['1', 0]
    if opt_text is not None:
        p['4'] = {'class_type': 'AMYTestString', 'inputs': {'text': opt_text}}
        p['2']['inputs']['opt_text'] = ['4', 0]
    return p


def prompt_without(positive, auto_random=False, random_template='', clip=True, opt_text=None):
    p = {'1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'test-ckpt.safetensors'}},
         '2': {'class_type': 'WeiLinPromptUIWithoutLora', 'inputs': {
             'positive': positive, 'auto_random': auto_random, 'temp_str': '', 'random_template': random_template}},
         '3': {'class_type': 'AMYProbe', 'inputs': {'label': 'without', 'text': ['2', 0], 'conditioning': ['2', 1],
                                                    'clip': ['2', 2]}}}
    if clip:
        p['2']['inputs']['opt_clip'] = ['1', 1]
    if opt_text is not None:
        p['4'] = {'class_type': 'AMYTestString', 'inputs': {'text': opt_text}}
        p['2']['inputs']['opt_text'] = ['4', 0]
    return p


def prompt_stack(lora_str):
    return {'1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'test-ckpt.safetensors'}},
            '2': {'class_type': 'WeiLinPromptUIOnlyLoraStack', 'inputs': {
                'clip': ['1', 1], 'model': ['1', 0], 'lora_str': lora_str, 'temp_lora_str': ''}},
            '3': {'class_type': 'AMYProbe', 'inputs': {'label': 'stack', 'clip': ['2', 0], 'model': ['2', 1]}}}


def case(name, prompt, expect='outputs', runs=1):
    return {'name': name, 'prompt': prompt, 'expect': expect, 'runs': runs}


TWO = json.dumps([lora_item('tagged-lora_v2.safetensors', 0.8, 0.6, 1.2), lora_item('named-lora-v3.safetensors', 0.5, 0.4)])
CASES = [
    case('without-plain', prompt_without('a red fox in the snow, (masterpiece:1.2)')),
    case('without-json-and-opt-text', prompt_without(json.dumps({'prompt': 'from json', 'lora': [lora_item('plain_lora_12.safetensors', 1, 1)]}),
                                                     opt_text='linked text')),
    case('without-no-clip', prompt_without('no clip here', clip=False)),
    case('without-auto-random-no-template', prompt_without('random off template', auto_random=True)),
    case('without-auto-random-template', prompt_without('x', auto_random=True, random_template='my-template'),
         expect='known:random-template'),
    case('without-encode-error', prompt_without('AMY-RAISE in the text')),
    case('ui-plain-no-model', prompt_ui('portrait of a cat', model=False)),
    case('ui-lora-str-no-model', prompt_ui('lora ignored without a model', lora_str=TWO, model=False)),
    case('ui-lora-str-with-model', prompt_ui('portrait of a cat', lora_str=TWO)),
    case('ui-wlr-tags', prompt_ui('city at night, <wlr:plain_lora_12:0.7:0.3:1.1>, <wlr:sub/other-lora:0.5:0.25>, neon')),
    case('ui-json-lora-plus-wlr-dedupe', prompt_ui(json.dumps({'prompt': 'json prompt <wlr:common-only:0.4:0.2:0.8>, <wlr:tagged-lora_v2:0.9:0.9>',
                                                                'lora': [lora_item('tagged-lora_v2.safetensors', 0.3, 0.2)]}))),
    # an old-format tag followed by a new-format one: the original's new-format pattern spans both tags
    case('ui-wlr-old-then-new', prompt_ui('a <wlr:tagged-lora_v2:0.9:0.9> <wlr:common-only:0.4:0.2:0.8>'), expect='error'),
    case('ui-missing-lora', prompt_ui('x', lora_str=json.dumps([lora_item('not-there.safetensors', 1, 1)])), expect='error'),
    case('ui-lora-no-clip', prompt_ui('model only', lora_str=TWO, clip=False)),
    case('ui-zero-strength', prompt_ui('zero', lora_str=json.dumps([lora_item('plain_lora_12.safetensors', 0, 0)]))),
    case('ui-extended-strength', prompt_ui('big', lora_str=json.dumps([lora_item('named-lora-v3.safetensors', 150, -120)]))),
    case('ui-pt-lora', prompt_ui('legacy', lora_str=json.dumps([lora_item('legacy-lora.pt', 0.6, 0.6)]))),
    case('ui-common-tags-only', prompt_ui('common', lora_str=json.dumps([lora_item('common-only.safetensors', 1, 1)]))),
    case('ui-auto-random-no-template', prompt_ui('keep me', auto_random=True)),
    case('ui-auto-random-template', prompt_ui('x', auto_random=True, random_template='my-template'),
         expect='known:random-template'),
    case('ui-bad-json-lora-str', prompt_ui('x', lora_str='{not json'), expect='error'),
    case('ui-encode-error-with-lora', prompt_ui('AMY-RAISE after loras', lora_str=TWO)),
    case('ui-opt-text', prompt_ui('base prompt', opt_text='prefix from link')),
    case('ui-repeat-run', prompt_ui('again', lora_str=TWO), runs=2),
    case('stack-two-loras', prompt_stack(json.dumps([lora_item('plain_lora_12.safetensors', 1.0, 0.5),
                                                      lora_item('sub/other-lora.safetensors', 0.25, 0.75)]))),
    case('stack-metadata-lora', prompt_stack(TWO)),
    case('stack-empty', prompt_stack('')),
    case('stack-missing', prompt_stack(json.dumps([lora_item('gone.safetensors', 1, 1)])), expect='error'),
]


def run_side(side):
    out = WORK / side
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-I', '-B', str(TESTS / 'weilin_parity_worker.py'), side, str(WORK / 'cases.json'),
           str(out), str(FIXTURES)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    (RESULTS / f'worker-{side}.log').write_text(proc.stdout[-20000:] + '\n--- stderr ---\n' + proc.stderr[-40000:])
    if proc.returncode != 0 or not (out / 'report.json').exists():
        raise RuntimeError(f'{side} worker failed rc={proc.returncode}: {proc.stderr[-2000:]}')
    (RESULTS / f'worker-{side}.json').write_bytes((out / 'report.json').read_bytes())
    return json.loads((out / 'report.json').read_text())


def _errors(run):
    return [(e['exception_type'].rsplit('.', 1)[-1], e['exception_message']) for e in run.get('errors', [])]


def _probe_and_ui(run, strip_attachments=False):
    """Per node: its UI; the probe UI parsed. Optionally without the MODEL/CLIP attachments."""
    out = {}
    for node_id, node_ui in sorted(run.get('ui', {}).items()):
        if 'probe' in node_ui:
            report = json.loads(node_ui['probe'][0])
            if strip_attachments:
                for key in ('model', 'clip'):
                    if report.get(key):
                        report[key] = {k: v for k, v in report[key].items() if k != 'attachments'}
            out[node_id] = {'probe': report}
        else:
            out[node_id] = node_ui
    return out


def _attachments(run):
    found = {}
    for node_ui in run.get('ui', {}).values():
        if 'probe' in node_ui:
            report = json.loads(node_ui['probe'][0])
            for key in ('model', 'clip'):
                if report.get(key):
                    found[key] = sorted(report[key].get('attachments', {}))
    return found


def compare_case(spec, orig, conv):
    name, expect = spec['name'], spec['expect']
    if 'harness_error' in orig or 'harness_error' in conv:
        return {'case': name, 'verdict': 'HARNESS-ERROR', 'original': orig.get('harness_error'),
                'v2': conv.get('harness_error')}
    runs_o, runs_c = orig['runs'], conv['runs']
    if len(runs_o) != len(runs_c) or any('validation_error' in r for r in runs_o + runs_c):
        return {'case': name, 'expect': expect, 'verdict': 'MISMATCH',
                'notes': [r.get('validation_error') for r in runs_o + runs_c]}
    errors_o = [_errors(r) for r in runs_o]
    errors_c = [_errors(r) for r in runs_c]
    if expect == 'outputs':
        if any(errors_o) or any(errors_c):
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'errors': [errors_o, errors_c]}
        full_o = [_probe_and_ui(r) for r in runs_o]
        full_c = [_probe_and_ui(r) for r in runs_c]
        if not all(any('probe' in v for v in ui.values()) for ui in full_o):
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'notes': ['no probe output (vacuous)']}
        if full_o == full_c:
            return {'case': name, 'expect': expect, 'verdict': 'EXACT', 'probe': full_c[-1]}
        stripped_o = [_probe_and_ui(r, True) for r in runs_o]
        stripped_c = [_probe_and_ui(r, True) for r in runs_c]
        attach_o = [_attachments(r) for r in runs_o]
        attach_c = [_attachments(r) for r in runs_c]
        only_metadata = all(not any(a.values()) for a in attach_o) and all(
            set(v) == {'lora_metadata'} for a in attach_c for v in a.values() if v)
        if stripped_o == stripped_c and only_metadata:
            return {'case': name, 'expect': expect, 'verdict': 'KNOWN-DIFFERENCE', 'probe': stripped_c[-1],
                    'difference': 'V2 (core comfy.sd.load_lora_for_models) attaches the LoRA file metadata as '
                                  "'lora_metadata' to the patched MODEL/CLIP; the original's own loader did not",
                    'attachments': {'original': attach_o, 'v2': attach_c}}
        return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'original': full_o, 'v2': full_c}
    if expect == 'error':
        ok = all(errors_o) and errors_o == errors_c
        return {'case': name, 'expect': expect, 'verdict': 'ERROR-PARITY' if ok else 'MISMATCH',
                'errors': [errors_o, errors_c]}
    if expect == 'known:random-template':
        # The original looks the template up as a file kept by its web editor; with no such file its
        # go_run_node_auto_random_tag returns "" and the node fails indexing it. V2 refuses by name.
        ok = all(e == [('TypeError', "string indices must be integers, not 'str'\n")] for e in errors_o) \
            and all(e and e[-1][0] == 'SecureConversionRefusal' for e in errors_c)
        return {'case': name, 'expect': expect, 'verdict': 'KNOWN-DIFFERENCE' if ok else 'MISMATCH',
                'errors': [errors_o, errors_c]}
    raise ValueError(expect)


def compare_schemas(orig, conv):
    """INPUT_TYPES as the executor and /object_info see them (hidden-type projection and DESCRIPTION None/''
    normalised as in core server.py:852)."""
    rows = {}
    for node in NODE_IDS:
        so, sc = orig['schemas'][node], conv['schemas'][node]
        issues = []
        for group in ('required', 'optional', 'hidden'):
            go, gc = so['input_types'].get(group, {}), sc['input_types'].get(group, {})
            if group == 'hidden' and so['output_node']:
                # V3 appends hidden prompt/extra_pnginfo to every output node (comfy_api/latest/_io.py:1826-1830)
                gc = {k: v for k, v in gc.items() if k in go or k not in ('prompt', 'extra_pnginfo')}
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
                if type_o != type_c:
                    issues.append(f'{key}: type {type_o} vs {type_c}')
                if opts_o != opts_c:
                    issues.append(f'{key}: options {opts_o} vs {opts_c}')
        for field in ('return_types', 'return_names', 'output_node', 'category', 'description', 'display_name'):
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
    original = run_side('original')
    converted = run_side('v2')
    by_name_o = {c['name']: c for c in original['cases']}
    by_name_c = {c['name']: c for c in converted['cases']}
    rows = [compare_case(spec, by_name_o[spec['name']], by_name_c[spec['name']]) for spec in CASES]
    counts = {}
    for row in rows:
        counts[row['verdict']] = counts.get(row['verdict'], 0) + 1
    # negative control: perturb one recorded LoRA strength in an EXACT case with patches; it must turn red
    target = next((r for r in rows if r['verdict'] == 'EXACT' and 'with-model' in r['case']), None) \
        or next((r for r in rows if r['verdict'] == 'EXACT'), None)
    if target is None:
        control = {'verdict': 'NOT-RUN (no EXACT case to perturb)'}
        target = {'case': None}
    else:
        spec = next(s for s in CASES if s['name'] == target['case'])
        tampered = copy.deepcopy(by_name_c[target['case']])
        for node_ui in tampered['runs'][-1]['ui'].values():
            if 'probe' in node_ui:
                report = json.loads(node_ui['probe'][0])
                report['text'] = (report.get('text') or '') + 'X'
                node_ui['probe'] = [json.dumps(report, sort_keys=True)]
        control = compare_case(spec, by_name_o[target['case']], tampered)
    schemas = compare_schemas(original, converted)
    report = {'pack': 'weilin-comfyui-tools', 'pin': '5b0b8730193d498432e2fc43549b42edcb498c63',
              'harness': 'ComfyUI core 6257422b PromptExecutor (classic cache), both sides; stand-in MODEL/CLIP '
                         'record every LoRA patch; the original loads with harness stand-ins for its pip installer '
                         'and its web-editor server module only',
              'original_harness_stubs': original.get('harness_stubs'),
              'nodes': {node: [r['verdict'] for r in rows if (
                  ('ui-' in r['case'] and node == 'WeiLinPromptUI')
                  or ('without-' in r['case'] and node == 'WeiLinPromptUIWithoutLora')
                  or ('stack-' in r['case'] and node == 'WeiLinPromptUIOnlyLoraStack'))] for node in NODE_IDS},
              'counts': counts, 'cases': rows, 'schemas': schemas,
              'negative_control': {'case': target['case'], 'verdict_after_tamper': control['verdict'],
                                   'turned_red': control['verdict'] == 'MISMATCH'},
              'original_cwd_files': sorted({f for c in original['cases'] for f in c.get('cwd_files', [])}),
              'v2_cwd_files': sorted({f for c in converted['cases'] for f in c.get('cwd_files', [])})}
    (RESULTS / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'schemas': schemas, 'negative_control': report['negative_control'],
                      'cwd': [report['original_cwd_files'], report['v2_cwd_files']]}, indent=1))
    ok = control['verdict'] == 'MISMATCH' and set(counts) <= {'EXACT', 'ERROR-PARITY', 'KNOWN-DIFFERENCE'} \
        and all(v == 'EXACT' for v in schemas.values())
    sys.exit(0 if ok else 1)


main()
