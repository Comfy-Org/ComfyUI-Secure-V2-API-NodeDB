"""Tier-1 parity: WAS Node Suite fork (44de7058) vs its Secure Nodes V2 conversion.

Run in the to-50% gate (DEPS = the pinned wheels in DEPS.json, for the original side only):
  run_in_gate.sh <pack root> <v2/tests> <results> test_was_node_suite_parity.py

Two workers execute the same prompts through ComfyUI's real executor (was_parity_worker.py). Every case declares
its expected outcome; a case passes only when both sides show it:
  EXACT              identical UI records (AMYProbe summaries, Image Save previews) and identical output files
  DECODED-EXACT      as EXACT, with a named container difference allowed for that case (see compare_files)
  ERROR-PARITY       both fail with the same exception type and message
  REFUSED-AS-DESIGNED  the original succeeds, V2 raises its named SecureConversionRefusal (or refuses at validation)
  KNOWN-DIFFERENCE   both sides behave exactly as SECURE_CONVERSION.md documents
Also: every declared node's schema (V1 INPUT_TYPES/RETURN_TYPES vs the V2 projection), and a refused node.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
RESULTS = Path('/results')
WORK = Path('/tmp/amy-was-parity')
FIXTURES = WORK / 'fixtures'
LORA_KEYS = {'lora_unet_input_blocks_0_0': (4, 2), 'lora_unet_middle_block_1_proj_in': (3, 2),
             'lora_te_text_model_encoder_layers_0_mlp_fc1': (5, 2)}
WORKFLOW = {'last_node_id': 3, 'nodes': [{'id': 1, 'type': 'AMYTestImage'}], 'links': [], 'version': 0.4}


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

    for seed, (name, metadata) in enumerate({'test-lora.safetensors': None,
                                             'sub/meta-lora.safetensors': {'ss_output_name': 'meta'}}.items()):
        path = FIXTURES / 'loras' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        save_file(tensors(seed), str(path), metadata=metadata)


def text(node_id, value):
    return {node_id: {'class_type': 'AMYTestString', 'inputs': {'text': value}}}


def probe(**links):
    return {'99': {'class_type': 'AMYProbe', 'inputs': {'label': 'probe', **links}}}


def probe_at(node_id, **links):
    return {node_id: {'class_type': 'AMYProbe', 'inputs': {'label': f'probe {node_id}', **links}}}


def g(*parts):
    out = {}
    for part in parts:
        out.update(part)
    return out


def node(node_id, class_type, **inputs):
    return {node_id: {'class_type': class_type, 'inputs': inputs}}


def ckpt():
    return node('1', 'CheckpointLoaderSimple', ckpt_name='test-ckpt.safetensors')


def image(batch=1, width=16, height=12, seed=7):
    return node('2', 'AMYTestImage', width=width, height=height, batch=batch, seed=seed)


def save(**options):
    inputs = {'images': ['2', 0], 'output_path': '[time(%Y-%m-%d)]', 'filename_prefix': 'ComfyUI',
              'filename_delimiter': '_', 'filename_number_padding': 4, 'filename_number_start': 'false',
              'extension': 'png', 'dpi': 300, 'quality': 100, 'optimize_image': 'true', 'lossless_webp': 'false',
              'overwrite_mode': 'false', 'show_history': 'false', 'show_history_by_prefix': 'true',
              'embed_workflow': 'true', 'show_previews': 'true'}
    inputs.update(options)
    return node('3', 'Image Save', **inputs)


def case(name, prompt, expect='outputs', allow=(), runs=1, preexisting=None, workflow=True):
    return {'name': name, 'prompt': prompt, 'expect': expect, 'allow': sorted(allow), 'runs': runs,
            'preexisting': preexisting or {}, 'extra_pnginfo': {'workflow': WORKFLOW} if workflow else None}


PNG = {'DECODED-EXACT-PNG-PHYS'}
WEBP = {'DECODED-EXACT-WEBP-EMPTY-EXIF'}
FILTERS = dict(brightness=0.0, contrast=1.0, saturation=1.0, sharpness=1.0, blur=0, gaussian_blur=0.0,
               edge_enhance=0.0, detail_enhance='false')
CASES = [
    case('text-to-string', g(text('10', 'hello  world'), node('11', 'Text to String', text=['10', 0]),
                             probe(text=['11', 0]))),
    case('string-to-text', g(text('10', 'a\nb'), node('11', 'String to Text', string=['10', 0]), probe(text=['11', 0]))),
    case('text-to-number-int', g(text('10', '42'), node('11', 'Text to Number', text=['10', 0]),
                                 node('12', 'Number to Int', number=['11', 0]),
                                 probe(number=['11', 0], number_int=['12', 0]))),
    case('text-to-number-float', g(text('10', '3.75'), node('11', 'Text to Number', text=['10', 0]),
                                   node('12', 'Number to Int', number=['11', 0]),
                                   probe(number=['11', 0], number_int=['12', 0]))),
    case('text-to-number-error', g(text('10', 'abc'), node('11', 'Text to Number', text=['10', 0]),
                                   probe(number=['11', 0])), expect='error'),
    case('text-concatenate', g(text('10', '  alpha '), text('13', ''), text('14', ' gamma'),
                               node('11', 'Text Concatenate', delimiter=', ', clean_whitespace='true',
                                    text_a=['10', 0], text_b=['13', 0], text_c=['14', 0]),
                               probe(text=['11', 0]))),
    case('text-concatenate-newline-raw', g(text('10', ' x '), text('13', 'y'),
                                           node('11', 'Text Concatenate', delimiter='\\n', clean_whitespace='false',
                                                text_a=['10', 0], text_d=['13', 0]),
                                           probe(text=['11', 0]))),
    case('find-replace', g(text('10', 'a1b22c333'), node('11', 'Text Find and Replace', text=['10', 0],
                                                        find='[0-9]+', replace='#'),
                           probe(text=['11', 0], number=['11', 1], number_float=['11', 2], number_int=['11', 3]))),
    case('find-replace-bad-regex', g(text('10', 'abc'), node('11', 'Text Find and Replace', text=['10', 0],
                                                            find='(', replace=''),
                                     probe(text=['11', 0])), expect='error'),
    case('text-multiline-tokens', g(node('11', 'Text Multiline',
                                         text='# a comment\nshot at [time] on [time(%Y-%m-%d %H:%M)]\n  # indented\nlast line'),
                                    probe(text=['11', 0]))),
    case('text-multiline-hostname', g(node('11', 'Text Multiline', text='made on [hostname]'), probe(text=['11', 0])),
         expect='refusal'),
    case('text-to-conditioning', g(ckpt(), text('10', 'a (red:1.2) fox'),
                                   node('11', 'Text to Conditioning', clip=['1', 1], text=['10', 0]),
                                   probe(conditioning=['11', 0]))),
    case('load-lora', g(ckpt(), node('11', 'Load Lora', model=['1', 0], clip=['1', 1], lora_name='test-lora.safetensors',
                                     strength_model=0.8, strength_clip=0.6),
                        probe(model=['11', 0], clip=['11', 1], text=['11', 2]))),
    case('lora-loader-alias-subfolder', g(ckpt(), node('11', 'Lora Loader', model=['1', 0], clip=['1', 1],
                                                       lora_name='sub/meta-lora.safetensors', strength_model=-1.5,
                                                       strength_clip=0.0),
                                          probe(model=['11', 0], clip=['11', 1], text=['11', 2])),
         expect='known:lora-metadata'),
    case('load-lora-zero', g(ckpt(), node('11', 'Load Lora', model=['1', 0], clip=['1', 1],
                                          lora_name='test-lora.safetensors', strength_model=0.0, strength_clip=0.0),
                             probe(model=['11', 0], clip=['11', 1]))),
    case('load-lora-none-name', g(ckpt(), node('11', 'Load Lora', model=['1', 0], clip=['1', 1], lora_name='None',
                                               strength_model=1.0, strength_clip=1.0),
                                  probe(model=['11', 0])), expect='error'),
    case('load-lora-unknown-name', g(ckpt(), node('11', 'Load Lora', model=['1', 0], clip=['1', 1],
                                                  lora_name='gone.safetensors', strength_model=1.0,
                                                  strength_clip=1.0),
                                     probe(model=['11', 0])), expect='validation'),
    case('image-filters-neutral', g(image(), node('11', 'Image Filter Adjustments', image=['2', 0], **FILTERS),
                                    probe(image=['11', 0]))),
    case('image-filters-all', g(image(), node('11', 'Image Filter Adjustments', image=['2', 0], brightness=0.1,
                                              contrast=1.3, saturation=1.7, sharpness=2.0, blur=2, gaussian_blur=1.5,
                                              edge_enhance=0.4, detail_enhance='true'),
                                probe(image=['11', 0]))),
    case('image-filters-batch2', g(image(batch=2), node('11', 'Image Filter Adjustments', image=['2', 0],
                                                        **{**FILTERS, 'saturation': 0.5, 'blur': 1}),
                                   probe(image=['11', 0]))),
    case('latent-noise', g(node('20', 'EmptyLatentImage', width=64, height=64, batch_size=1),
                           node('11', 'Latent Noise Injection', samples=['20', 0], noise_std=0.3),
                           probe(latent=['11', 0]))),
    case('save-png-default', g(image(), save(), probe(files=['3', 1])), allow=PNG),
    case('save-png-plain', g(image(), save(embed_workflow='false', optimize_image='false', dpi=72,
                                           output_path='renders/run1'), probe(files=['3', 1])), allow=PNG),
    case('save-png-batch-after-existing', g(image(batch=2), save(output_path=''), probe(files=['3', 1])),
         allow=PNG, preexisting={'ComfyUI_0007.png': 'x', 'other_0099.png': 'x'}),
    case('save-number-start', g(image(), save(filename_number_start='true', filename_number_padding=3,
                                              filename_delimiter='-', filename_prefix='shot [time]'),
                                probe(files=['3', 1])), allow=PNG),
    case('save-no-previews', g(image(), save(show_previews='false'), probe(files=['3', 1])), allow=PNG),
    case('save-gif', g(image(), save(extension='gif'), probe(files=['3', 1]))),
    case('save-tiff', g(image(), save(extension='tiff', optimize_image='false'), probe(files=['3', 1]))),
    case('save-bmp', g(image(), save(extension='bmp'), probe(files=['3', 1]))),
    case('save-webp-lossy', g(image(), save(extension='webp', embed_workflow='false', quality=80),
                              probe(files=['3', 1])), allow=WEBP),
    case('save-webp-lossless', g(image(), save(extension='webp', embed_workflow='false', lossless_webp='true'),
                                 probe(files=['3', 1])), allow=WEBP),
    case('save-prefix-as-filename-new', g(image(), save(overwrite_mode='prefix_as_filename', output_path='fixed'),
                                          probe(files=['3', 1])), allow=PNG),
    case('save-jpg-refused', g(image(), save(extension='jpg')), expect='refusal'),
    case('save-webp-embed-refused', g(image(), save(extension='webp')), expect='refusal'),
    case('save-history-refused', g(image(), save(show_history='true')), expect='refusal'),
    case('save-absolute-path-refused', g(image(), save(output_path='/tmp/amy-was-parity/abs-out')),
         expect='refusal-outside'),
    case('save-windows-path-refused', g(image(), save(output_path='C:\\Users\\someone\\out')), expect='refusal'),
    case('save-overwrite-refused', g(image(), save(overwrite_mode='prefix_as_filename', output_path='')),
         expect='refusal', preexisting={'ComfyUI.png': 'x'}),
    case('save-host-token-refused', g(image(), save(filename_prefix='[user]-img')), expect='refusal'),
    case('refused-node-integer-place-counter', g(node('11', 'Integer place counter', int_input=5),
                                                 probe(number=['11', 0])), expect='not-converted'),
    # Number PI has no inputs, so core never calls validate_inputs for it: its refusal is raised when it runs.
    case('refused-node-number-pi-at-run', g(node('11', 'Number PI'), probe(number=['11', 0])),
         expect='not-converted-at-run'),
]

# ---- phase B batch 1 (r2): value, switch, list and token nodes
NUMBER_OUTS = dict(number=0, number_float=1, number_int=2)
OPERATIONS = ['addition', 'subtraction', 'division', 'floor division', 'multiplication', 'exponentiation', 'modulus',
              'greater-than', 'greater-than or equals', 'less-than', 'less-than or equals', 'equals', 'does not equal']


def outs(node_id, **slots):
    return {key: [node_id, index] for key, index in slots.items()}


def numbers(a, b, type_a='float', type_b='integer'):
    return g(node('20', 'Constant Number', number_type=type_a, number=a),
             node('21', 'Constant Number', number_type=type_b, number=b))


CASES += [
    case('seed', g(node('11', 'Seed', seed=123456789012345),
                   probe(**outs('11', number=0, text=1, number_float=2, number_int=3)))),
    case('constant-number-integer', g(node('11', 'Constant Number', number_type='integer', number=7.6),
                                      probe(**outs('11', **NUMBER_OUTS)))),
    case('constant-number-float', g(node('11', 'Constant Number', number_type='float', number=-2.25),
                                    probe(**outs('11', **NUMBER_OUTS)))),
    case('constant-number-bool', g(node('11', 'Constant Number', number_type='bool', number=0.51),
                                   probe(**outs('11', **NUMBER_OUTS)))),
    case('constant-number-as-text', g(text('10', '41'), node('11', 'Constant Number', number_type='integer', number=0.0,
                                                             number_as_text=['10', 0]),
                                      probe(**outs('11', **NUMBER_OUTS)))),
    case('constant-number-as-text-error', g(text('10', '4.5'), node('11', 'Constant Number', number_type='integer',
                                                                    number=0.0, number_as_text=['10', 0]),
                                            probe(number=['11', 0])), expect='error'),
] + [
    case(f'number-operation-{op.replace(" ", "-")}', g(numbers(7.5, 2), node('11', 'Number Operation', number_a=['20', 0],
                                                                             number_b=['21', 0], operation=op),
                                                     probe(**outs('11', **NUMBER_OUTS))))
    for op in OPERATIONS
] + [
    case('number-operation-division-by-zero', g(numbers(7.5, 0), node('11', 'Number Operation', number_a=['20', 0],
                                                                      number_b=['21', 0], operation='division'),
                                                probe(number=['11', 0])), expect='error'),
    case('number-conversions', g(node('20', 'Constant Number', number_type='float', number=3.5),
                                 node('11', 'Number to String', number=['20', 0]),
                                 node('12', 'Number to Float', number=['20', 0]),
                                 node('13', 'Number to Text', number=['20', 0]),
                                 probe(text=['11', 0], number_float=['12', 0], number=['13', 0]))),
    case('number-conversions-int', g(node('20', 'Constant Number', number_type='integer', number=12.0),
                                     node('11', 'Number to String', number=['20', 0]),
                                     node('12', 'Number to Float', number=['20', 0]),
                                     node('13', 'Number to Text', number=['20', 0]),
                                     probe(text=['11', 0], number_float=['12', 0], number=['13', 0]))),
] + [
    case(f'logic-boolean-{value}', g(node('11', 'Logic Boolean', boolean=value),
                                     probe(**outs('11', text=0, number=1, number_int=2, number_float=3))))
    for value in (0.0, 0.4, 0.5, 0.51, 1.0)
] + [
    case(f'latent-switch-{flag}', g(node('20', 'EmptyLatentImage', width=64, height=64, batch_size=1),
                                    node('21', 'EmptyLatentImage', width=32, height=48, batch_size=2),
                                    node('22', 'Logic Boolean', boolean=value),
                                    node('11', 'Latent Input Switch', latent_a=['20', 0], latent_b=['21', 0],
                                         boolean=['22', 0]),
                                    probe(latent=['11', 0])))
    for flag, value in (('true', 1.0), ('false', 0.0))
] + [
    case(f'text-switch-{flag}', g(text('10', 'A'), text('13', 'B'), node('22', 'Logic Boolean', boolean=value),
                                  node('11', 'Text Input Switch', text_a=['10', 0], text_b=['13', 0], boolean=['22', 0]),
                                  probe(text=['11', 0])))
    for flag, value in (('true', 1.0), ('false', 0.0))
] + [
    case(f'model-clip-vae-switches-{flag}', g(
        ckpt(), node('12', 'Load Lora', model=['1', 0], clip=['1', 1], lora_name='test-lora.safetensors',
                     strength_model=0.8, strength_clip=0.6),
        node('22', 'Logic Boolean', boolean=value),
        node('11', 'Lora Input Switch', model_a=['1', 0], clip_a=['1', 1], model_b=['12', 0], clip_b=['12', 1],
             boolean=['22', 0]),
        node('13', 'Model Input Switch', model_a=['12', 0], model_b=['1', 0], boolean=['22', 0]),
        node('14', 'VAE Input Switch', vae_a=['1', 2], vae_b=['1', 2], boolean=['22', 0]),
        probe(model=['11', 0], clip=['11', 1], files=['14', 0]), probe_at('98', model=['13', 0])))
    for flag, value in (('true', 1.0), ('false', 0.0))
] + [
    case(f'conditioning-switch-{flag}', g(ckpt(), text('10', 'red fox'), text('13', 'blue bird'),
                                          node('15', 'Text to Conditioning', clip=['1', 1], text=['10', 0]),
                                          node('16', 'Text to Conditioning', clip=['1', 1], text=['13', 0]),
                                          node('22', 'Logic Boolean', boolean=value),
                                          node('11', 'Conditioning Input Switch', conditioning_a=['15', 0],
                                               conditioning_b=['16', 0], boolean=['22', 0]),
                                          probe(conditioning=['11', 0])))
    for flag, value in (('true', 1.0), ('false', 0.0))
] + [
    case('text-list-to-text', g(text('10', 'alpha'), text('13', 'beta'), text('14', 'gamma'),
                                node('11', 'Text List', text_a=['10', 0], text_c=['13', 0], text_g=['14', 0]),
                                node('12', 'Text List to Text', delimiter=' | ', text_list=['11', 0]),
                                probe(text=['12', 0], number=['11', 0]))),
    case('text-list-concatenate-newline', g(text('10', 'a'), text('13', 'b'),
                                            node('11', 'Text List', text_a=['10', 0]),
                                            node('15', 'Text List', text_b=['13', 0], text_a=['10', 0]),
                                            node('12', 'Text List Concatenate', list_b=['11', 0], list_a=['15', 0]),
                                            node('16', 'Text List to Text', delimiter='\\n', text_list=['12', 0]),
                                            probe(number=['12', 0], text=['16', 0]))),
    case('text-string-tokens', g(node('11', 'Text String', text='a [time] b', text_b='[time(%H:%M)]', text_c='plain',
                                      text_d=''),
                                 probe(**outs('11', text=0, number=1, number_float=2, number_int=3)))),
    case('text-multiline-code-compatible', g(node('11', 'Text Multiline (Code Compatible)',
                                                  text='# kept\n[time]\n  indented # also kept'),
                                             probe(text=['11', 0]))),
    case('text-parse-tokens', g(text('10', 'on [time(%Y)] at [time]'), node('11', 'Text Parse Tokens', text=['10', 0]),
                                probe(text=['11', 0])), runs=2),
    case('text-parse-tokens-cuda-refused', g(text('10', 'gpu [cuda_name]'),
                                             node('11', 'Text Parse Tokens', text=['10', 0]), probe(text=['11', 0])),
         expect='refusal'),
    case('text-compare-difference', g(text('10', 'the quick brown fox'), text('13', 'the quick red fox'),
                                      node('11', 'Text Compare', text_a=['10', 0], text_b=['13', 0], mode='difference',
                                           tolerance=0.0),
                                      probe(**outs('11', text=0, number=1, number_int=2, number_float=3, files=4)))),
    case('text-compare-similarity-single-word', g(text('10', 'hello'), text('13', 'hello'),
                                                  node('11', 'Text Compare', text_a=['10', 0], text_b=['13', 0],
                                                       mode='similarity', tolerance=0.5),
                                                  probe(**outs('11', text=0, number=1, number_int=2, number_float=3,
                                                               files=4)))),
    case('text-compare-similarity-none', g(text('10', 'abc'), text('13', 'xyz'),
                                           node('11', 'Text Compare', text_a=['10', 0], text_b=['13', 0],
                                                mode='similarity', tolerance=0.0),
                                           probe(**outs('11', text=0, number=1, number_int=2, number_float=3,
                                                        files=4)))),
] + [
    case(f'text-truncate-{by}-{side}-{to}', g(text('10', 'one two three four five'), text('13', 'abcdefgh'),
                                              node('11', 'Text String Truncate', text=['10', 0], text_b=['13', 0],
                                                   truncate_by=by, truncate_from=side, truncate_to=to),
                                              probe(**outs('11', text=0, number=1, number_float=2, number_int=3))))
    for by, side, to in (('words', 'beginning', 2), ('words', 'end', 2), ('characters', 'beginning', 3),
                         ('characters', 'end', -3), ('words', 'end', 0))
] + [
    case('text-random-line', g(text('10', 'l1\nl2\nl3\nl4\nl5'),
                               node('11', 'Text Random Line', text=['10', 0], seed=987654321987654321),
                               probe(text=['11', 0]))),
    case('text-random-line-seed-0', g(text('10', 'x\ny'), node('11', 'Text Random Line', text=['10', 0], seed=0),
                                      probe(text=['11', 0]))),
]


def run_side(side):
    out = WORK / side
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-I', '-B', str(TESTS / 'was_parity_worker.py'), side, str(WORK / 'cases.json'),
           str(out), str(FIXTURES)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    (RESULTS / f'worker-{side}.log').write_text(proc.stdout[-20000:] + '\n--- stderr ---\n' + proc.stderr[-40000:])
    if proc.returncode != 0 or not (out / 'report.json').exists():
        raise RuntimeError(f'{side} worker failed rc={proc.returncode}: {proc.stderr[-2000:]}')
    (RESULTS / f'worker-{side}.json').write_bytes((out / 'report.json').read_bytes())
    return json.loads((out / 'report.json').read_text())


def _errors(run):
    return [(e['exception_type'].rsplit('.', 1)[-1], e['exception_message']) for e in run.get('errors', [])]


def _ui(run, output_dir=None):
    out = {}
    for node_id, node_ui in sorted(run.get('ui', {}).items()):
        if 'probe' in node_ui:
            report = json.loads(node_ui['probe'][0])
            files = report.get('files')
            if output_dir and isinstance(files, list):
                report['files'] = [_rel_file(item, output_dir) for item in files]
            out[node_id] = {'probe': report}
        else:
            value = copy.deepcopy(node_ui)
            if output_dir and isinstance(value.get('files'), list):
                value['files'] = [os.path.relpath(f, output_dir) if isinstance(f, str) and os.path.isabs(f) else f
                                  for f in value['files']]
            out[node_id] = value
    return out


def _rel_file(item, output_dir):
    # probe summaries are [type, value]; the original's "files" are absolute host paths
    if isinstance(item, list) and len(item) == 2 and isinstance(item[1], str) and os.path.isabs(item[1]):
        return [item[0], os.path.relpath(item[1], output_dir)]
    return item


def compare_files(a, b, allow):
    if a['sha256'] == b['sha256']:
        return 'EXACT', []
    same = all(a.get(k) == b.get(k) for k in ('pixels_sha256', 'size', 'mode', 'format', 'exif'))
    if a.get('format') == 'PNG' and 'DECODED-EXACT-PNG-PHYS' in allow and same and a.get('pil_text') == b.get('pil_text'):
        chunks_a = [row for row in a['png_chunks'] if row[0] != 'pHYs']
        if chunks_a == b['png_chunks'] and any(row[0] == 'pHYs' for row in a['png_chunks']):
            return 'DECODED-EXACT', [f'{a["path"]}: identical except the pHYs (DPI) chunk the original writes']
    if a.get('format') == 'WEBP' and 'DECODED-EXACT-WEBP-EMPTY-EXIF' in allow and same:
        image_a = [r for r in a['riff_chunks'] if r[0] in ('VP8 ', 'VP8L', 'ALPH')]
        image_b = [r for r in b['riff_chunks'] if r[0] in ('VP8 ', 'VP8L', 'ALPH')]
        if image_a == image_b:
            return 'DECODED-EXACT', [f'{a["path"]}: image chunks identical; RIFF {[(r[0], r[1]) for r in a["riff_chunks"]]} '
                                     f'vs {[(r[0], r[1]) for r in b["riff_chunks"]]} (the original writes an empty EXIF)']
    return 'MISMATCH', ['file content differs']


def compare_case(spec, orig, conv, output_dir):
    name, expect, allow = spec['name'], spec['expect'], set(spec['allow'])
    if 'harness_error' in orig or 'harness_error' in conv:
        return {'case': name, 'verdict': 'HARNESS-ERROR', 'original': orig.get('harness_error'),
                'v2': conv.get('harness_error')}
    runs_o, runs_c = orig['runs'], conv['runs']
    validation_o = [r for r in runs_o if 'validation_error' in r]
    validation_c = [r for r in runs_c if 'validation_error' in r]
    if expect == 'validation':
        ok = bool(validation_o) and bool(validation_c)
        return {'case': name, 'expect': expect, 'verdict': 'ERROR-PARITY' if ok else 'MISMATCH',
                'original': [r.get('node_errors') for r in runs_o], 'v2': [r.get('node_errors') for r in runs_c]}
    if expect == 'not-converted':
        text = json.dumps([r.get('node_errors') for r in validation_c])
        ok = not validation_o and all(r.get('success') for r in runs_o) and validation_c \
            and 'is not yet converted to Secure Nodes V2' in text
        return {'case': name, 'expect': expect, 'verdict': 'REFUSED-AS-DESIGNED' if ok else 'MISMATCH',
                'v2_validation': text[:400]}
    if validation_o or validation_c:
        return {'case': name, 'expect': expect, 'verdict': 'MISMATCH',
                'notes': [r.get('node_errors') for r in runs_o + runs_c]}
    errors_o = [_errors(r) for r in runs_o]
    errors_c = [_errors(r) for r in runs_c]
    if expect == 'not-converted-at-run':
        ok = all(r.get('success') for r in runs_o) and not any(errors_o) and all(
            e and e[-1][0] == 'SecureConversionRefusal' and 'is not yet converted to Secure Nodes V2' in e[-1][1]
            for e in errors_c)
        return {'case': name, 'expect': expect, 'verdict': 'REFUSED-AS-DESIGNED' if ok else 'MISMATCH',
                'errors': [errors_o, errors_c]}
    files_o = {f['path']: f for f in orig['files']}
    files_c = {f['path']: f for f in conv['files']}
    images_o = [p for p, f in files_o.items() if not f.get('not_an_image')]
    if expect in ('outputs', 'known:lora-metadata'):
        ui_o = [_ui(r, output_dir) for r in runs_o]
        ui_c = [_ui(r) for r in runs_c]
        notes = []
        if any(errors_o) or any(errors_c):
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'errors': [errors_o, errors_c]}
        if not all(any('probe' in v or 'images' in v for v in ui.values()) for ui in ui_o):
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'notes': ['nothing reached the probe']}
        if expect == 'known:lora-metadata':
            for ui in ui_c:
                for value in ui.values():
                    for key in ('model', 'clip'):
                        entry = value.get('probe', {}).get(key)
                        if isinstance(entry, dict):
                            notes.append({key: entry.get('attachments')})
                            entry['attachments'] = {}
        if ui_o != ui_c:
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'original': ui_o, 'v2': ui_c}
        if set(files_o) != set(files_c):
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH',
                    'files': [sorted(files_o), sorted(files_c)]}
        verdicts = {}
        for path in sorted(files_o):
            verdict, why = compare_files(files_o[path], files_c[path], allow)
            verdicts[path] = verdict
            notes.extend(why)
        if 'MISMATCH' in verdicts.values():
            return {'case': name, 'expect': expect, 'verdict': 'MISMATCH', 'files': verdicts, 'notes': notes}
        if expect == 'known:lora-metadata':
            ok = any(n for n in notes if isinstance(n, dict) and any(v and 'lora_metadata' in v for v in n.values()))
            return {'case': name, 'expect': expect, 'verdict': 'KNOWN-DIFFERENCE' if ok else 'MISMATCH',
                    'notes': notes, 'probe': ui_c[-1]}
        verdict = 'DECODED-EXACT' if 'DECODED-EXACT' in verdicts.values() else 'EXACT'
        return {'case': name, 'expect': expect, 'verdict': verdict, 'files': verdicts, 'notes': notes[:6],
                'probe': ui_c[-1]}
    if expect == 'error':
        ok = all(errors_o) and errors_o == errors_c
        return {'case': name, 'expect': expect, 'verdict': 'ERROR-PARITY' if ok else 'MISMATCH',
                'errors': [errors_o, errors_c]}
    if expect in ('refusal', 'refusal-outside'):
        refused = all(e and e[-1][0] == 'SecureConversionRefusal' for e in errors_c)
        if expect == 'refusal':
            wrote = not any(errors_o)
        else:
            wrote = not any(errors_o) and not images_o  # the original wrote outside the output folder
        ok = refused and wrote
        return {'case': name, 'expect': expect, 'verdict': 'REFUSED-AS-DESIGNED' if ok else 'MISMATCH',
                'errors': [errors_o, errors_c], 'original_files': sorted(files_o)}
    raise ValueError(expect)


MODEL_MENUS = {('Checkpoint Loader', 'config_name'): 'configs', ('Checkpoint Loader', 'ckpt_name'): 'checkpoints',
               ('Checkpoint Loader (Simple)', 'ckpt_name'): 'checkpoints',
               ('unCLIP Checkpoint Loader', 'ckpt_name'): 'checkpoints',
               ('Upscale Model Loader', 'model_name'): 'upscale_models',
               ('Load Lora', 'lora_name'): 'loras', ('Lora Loader', 'lora_name'): 'loras'}
RANDOM_DEFAULTS = {('Cache Node', 'latent_suffix'), ('Cache Node', 'image_suffix'), ('Cache Node', 'conditioning_suffix')}


def compare_schemas(orig, conv):
    """Every declared id: INPUT_TYPES as the executor and /object_info see them. Normalised projection details: a
    list type vs ("COMBO", {"options": [...]}); V3 adds hidden prompt/extra_pnginfo to output nodes
    (comfy_api/latest/_io.py:1826-1830); DESCRIPTION None vs '' (server.py:852); the two defaults that were absolute
    host paths; the model menus (the original listed a model folder; V2 declares the host's catalogue route for the
    same folder); Cache Node's suffix defaults (the original draws random digits on every INPUT_TYPES call)."""
    import re
    rows = {}
    ids_o, ids_c = set(orig['pack_ids']), set(conv['pack_ids'])
    for node in sorted(ids_o | ids_c):
        if node not in ids_o or node not in ids_c:
            rows[node] = 'MISSING on ' + ('original' if node not in ids_o else 'v2')
            continue
        so, sc = orig['schemas'][node], conv['schemas'][node]
        issues = []
        for group in ('required', 'optional', 'hidden'):
            go, gc = so['input_types'].get(group, {}) or {}, sc['input_types'].get(group, {}) or {}
            if group == 'hidden' and so['output_node']:
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
                opts_o = dict(vo[1]) if len(vo) > 1 else {}
                opts_c = dict(vc[1]) if len(vc) > 1 else {}
                if (node, key) in (('Cache Node', 'output_path'), ('Write to GIF', 'output_path')):
                    opts_o['default'] = ''
                if (node, key) in MODEL_MENUS:
                    route = f'/models/{MODEL_MENUS[(node, key)]}'
                    if not (type_c == 'COMBO' and opts_c.get('remote', {}).get('route') == route):
                        issues.append(f'{key} is not the {route} catalogue menu')
                    continue
                if (node, key) in RANDOM_DEFAULTS:
                    if all(re.fullmatch(r'\d+_cache', str(opts.get('default'))) for opts in (opts_o, opts_c)):
                        opts_o['default'] = opts_c['default']
                if isinstance(type_o, list):
                    if not (type_c == 'COMBO' and opts_c.pop('options', None) == type_o):
                        issues.append(f'{key}: combo options differ')
                    opts_c.pop('multiselect', None)
                elif type_o != type_c:
                    issues.append(f'{key}: type {type_o} vs {type_c}')
                if opts_o != opts_c:
                    issues.append(f'{key}: options {opts_o} vs {opts_c}')
        for field in ('return_types', 'return_names', 'output_node', 'category', 'input_is_list', 'output_is_list',
                      'description'):
            vo, vc = so[field], sc[field]
            if field == 'description':
                vo, vc = vo or '', vc or ''
            if field == 'output_is_list':
                vo, vc = [bool(x) for x in vo] or [False] * len(so['return_types']), \
                    [bool(x) for x in vc] or [False] * len(sc['return_types'])
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
    rows = [compare_case(spec, by_name_o[spec['name']], by_name_c[spec['name']], original['output_dir'])
            for spec in CASES]
    counts = {}
    for row in rows:
        counts[row['verdict']] = counts.get(row['verdict'], 0) + 1
    target = next((r for r in rows if r['verdict'] == 'EXACT' and r['case'] == 'text-concatenate'), None)
    if target is None:
        control = {'verdict': 'NOT-RUN'}
        target = {'case': None}
    else:
        spec = next(s for s in CASES if s['name'] == target['case'])
        tampered = copy.deepcopy(by_name_c[target['case']])
        for node_ui in tampered['runs'][-1]['ui'].values():
            if 'probe' in node_ui:
                report = json.loads(node_ui['probe'][0])
                report['text'] = ['str', report['text'][1] + 'X']
                node_ui['probe'] = [json.dumps(report, sort_keys=True)]
        control = compare_case(spec, by_name_o[target['case']], tampered, original['output_dir'])
    bare_out = WORK / 'bare-load.json'
    bare_proc = subprocess.run([sys.executable, '-I', '-B', str(TESTS / 'bare_load_check.py'), str(bare_out)],
                               capture_output=True, text=True, timeout=1200)
    (RESULTS / 'bare-load.log').write_text(bare_proc.stdout[-5000:] + '\n--- stderr ---\n' + bare_proc.stderr[-20000:])
    bare = json.loads(bare_out.read_text()) if bare_out.exists() else {'error': f'rc={bare_proc.returncode}'}
    bare_ok = (bare.get('rows') == len(converted['pack_ids']) and bare.get('ok') == bare.get('rows')
               and not bare.get('failures') and bare.get('root_init_executed') is False
               and bare.get('values_mode_issues') == {})
    schemas = compare_schemas(original, converted)
    schema_counts = {}
    for value in schemas.values():
        key = 'EXACT' if value == 'EXACT' else 'DIFFERS'
        schema_counts[key] = schema_counts.get(key, 0) + 1
    report = {'pack': 'was-ns', 'pin': '44de705818d4663fefefde57ffe0ea5a9ea39df4',
              'harness': 'ComfyUI core 6257422b PromptExecutor (classic cache), both sides; weightless MODEL/CLIP '
                         'stand-ins recording every LoRA patch; frozen clocks; torch seeded before every prompt',
              'counts': counts, 'cases': rows, 'schema_counts': schema_counts,
              'schemas': {k: v for k, v in schemas.items() if v != 'EXACT'}, 'schema_ids': sorted(schemas),
              'bare_load': {'ok': bare_ok, 'rows': bare.get('rows'), 'loaded': bare.get('ok'),
                            'failures': bare.get('failures'), 'root_init_executed': bare.get('root_init_executed'),
                            'converted': bare.get('converted'), 'values_mode_issues': bare.get('values_mode_issues'),
                            'modules': bare.get('modules'), 'error': bare.get('error')},
              'negative_control': {'case': target['case'], 'verdict_after_tamper': control['verdict'],
                                   'turned_red': control['verdict'] == 'MISMATCH'}}
    (RESULTS / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'schema_counts': schema_counts,
                      'schema_issues': dict(list(report['schemas'].items())[:12]),
                      'bare_load': {k: report['bare_load'][k] for k in ('ok', 'rows', 'loaded', 'root_init_executed')},
                      'negative_control': report['negative_control']}, indent=1))
    ok = control['verdict'] == 'MISMATCH' and set(counts) <= {
        'EXACT', 'DECODED-EXACT', 'ERROR-PARITY', 'REFUSED-AS-DESIGNED', 'KNOWN-DIFFERENCE'} \
        and schema_counts.get('DIFFERS', 0) == 0 and bare_ok
    sys.exit(0 if ok else 1)


main()
