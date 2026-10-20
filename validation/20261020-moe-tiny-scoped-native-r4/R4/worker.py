"""Prepared one-phase genuine Tiny modules/default SDK differential. UNRUN.

Only an externally reviewed bounded native owner may select this worker.
No Guest, model load, output write domain, graph expansion or generator is used.
"""
import argparse
import asyncio
import contextlib
import copy
import hashlib
import importlib
import importlib.machinery
import importlib.util
import inspect
import io as textio
import json
from pathlib import Path
import sys
import traceback
import types

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def namespace(name, path):
    require(name not in sys.modules, 'Reference namespace already exists')
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    module.__package__ = name
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    sys.modules[name] = module
    return module

def real_module(name, path, package=False):
    require(name not in sys.modules, 'Selected module already imported')
    spec = importlib.util.spec_from_file_location(name, path,
            submodule_search_locations=[str(path.parent)] if package else None)
    require(spec is not None and spec.loader is not None, 'Genuine source loader unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def tagged(value):
    if value is None:
        return ['none']
    if type(value) is bool:
        return ['bool', value]
    if type(value) is int:
        return ['int', str(value)]
    if type(value) is float:
        return ['float', value.hex()]
    if type(value) is str:
        return ['str', value]
    if type(value) in (list, tuple):
        return ['tuple' if type(value) is tuple else 'list', [tagged(v) for v in value]]
    if type(value) is dict:
        require(all(type(k) is str for k in value), 'Expected string-keyed pure result')
        return ['dict', [[k, tagged(value[k])] for k in sorted(value)]]
    raise TypeError('Unselected value type in pure batch: ' + type(value).__qualname__)

async def public_values(value, sdk):
    if isinstance(value, sdk.Ref):
        # Public materialization only. Null-resource cases do not create models.
        return await public_values(await value.value(), sdk)
    if type(value) is dict:
        return {('samples' if k == '__ttn_latent__' else k): await public_values(v, sdk) for k, v in value.items()}
    if type(value) in (list, tuple):
        values = [await public_values(v, sdk) for v in value]
        return tuple(values) if type(value) is tuple else values
    return value

def result_parts(value, io):
    if isinstance(value, io.NodeOutput):
        return (() if value.result is None else value.result), value.ui
    if type(value) is dict and ('ui' in value or 'result' in value):
        return value.get('result', ()), value.get('ui')
    values = value if type(value) in (list, tuple) else (value,)
    return values, None

async def outcome(call, io, sdk, converted=False):
    try:
        result = call()
        if inspect.isawaitable(result):
            result = await result
        if converted:
            require(isinstance(result, io.NodeOutput), 'Converted generated node did not return genuine NodeOutput')
        values, ui = result_parts(result, io)
        normalized = dict(kind='value', values=tagged(await public_values(tuple(values), sdk)),
                          ui=tagged(await public_values(ui, sdk)))
        require(len(json.dumps(normalized).encode()) <= 65536, 'Pure result byte bound exceeded')
        return normalized
    except Exception as error:
        return dict(kind='error', type=type(error).__name__, message=str(error))

def mutate_tag(value, kind, replacement, expected=None):
    if type(value) is list and value and value[0] == kind and (expected is None or value[1] == expected):
        value[:] = replacement
        return True
    children = value.values() if type(value) is dict else value if type(value) is list else []
    for child in children:
        if mutate_tag(child, kind, replacement, expected):
            return True
    return False

async def run(options):
    require(options.execute and options.authorization_message.startswith('m_'), 'Separate reviewed owner authorization required')
    require(sys.flags.isolated and sys.dont_write_bytecode, 'Selected interpreter must run -I -B')
    profile_path = HERE / 'inputs/ACTUAL_MAC_PROFILE.json'
    require(sha(profile_path) == '40fbb95d729e2f10ba9c7809fa08135f5d9f433372d41d2d9d044cd58a68cdaf', 'Qualified profile changed')
    profile = load(profile_path)
    site, core = Path(profile['common_site_packages']), Path(profile['core_source'])
    require(Path(sys.executable).resolve() == Path(profile['python']).resolve(), 'Wrong selected Python')
    sdk_pins = {k: v for k, v in profile['sdk_files'].items() if k.endswith(('.py', '.pyi')) and k.startswith('comfy_api/')}
    require(len(sdk_pins) == 69, 'Wrong SDK text inventory')
    for name, digest in sdk_pins.items():
        require(sha(site / name) == digest, 'Qualified SDK source changed: ' + name)
    source = HERE / 'source'
    source_pins = load(HERE / 'SOURCE_FILES.json')
    require(len(source_pins) == 59, 'Wrong frozen Tiny source inventory')
    for name, row in source_pins.items():
        require(sha(source / name) == row['sha256'], 'Frozen Tiny source changed: ' + name)
    require(not options.output.exists(), 'Fresh external owned output required')
    require(not options.output.resolve().is_relative_to(HERE.resolve()), 'Output must be outside frozen inputs')
    options.output.mkdir(parents=True)
    # The real Core's CPU argument must be selected before importing Torch/Core.
    sys.path[:0] = [str(site), str(core)]
    sys.argv = ['moe-tiny-pure-differential', '--cpu']
    import comfy.options
    comfy.options.enable_args_parsing()
    import comfy.cli_args
    from comfy_api.latest import io, sdk, _sdk as engine
    require(comfy.cli_args.args.cpu is True, 'CPU profile is required')
    for module in (io, sdk, engine):
        require(Path(module.__file__).resolve().is_relative_to(site.resolve()), 'Wrong genuine SDK origin')
    require(sha(engine.__file__) == 'f1a73e4f160e70862f51abdddbb9268e2ce94dd96e18455a79e42307a443f91c', 'Wrong actual engine')
    require(sha(sdk.__file__) == '0fa030498183001898097cddf0983f1167bccc86c753137ec132027b91c6a8db', 'Wrong actual public facade')
    require(sdk.Ref is engine.Ref and not sdk.providers.engaged, 'Unmodified default SDK providers required')
    namespace('moe_tiny_native', source)
    namespace('moe_tiny_native.ttNpy', source / 'ttNpy')
    native = {key: real_module('moe_tiny_native.ttNpy.' + leaf, source / 'ttNpy' / (leaf + '.py'))
              for key, leaf in [('main', 'tinyterraNodes'), ('legacy', 'ttNlegacyNodes')]}
    # Complete original module bodies and their genuine imports are used. The
    # original root entrypoint performs config/JS mutation and is intentionally
    # outside this module-FUNCTION differential, not replaced by a fake facade.
    candidate = HERE / 'candidate'
    candidate_pins = load(HERE / 'CANDIDATE_FILES.json')
    require(len(candidate_pins) == 29, 'Wrong isolated candidate inventory')
    for name, row in candidate_pins.items():
        require(sha(candidate / name) == row['sha256'], 'Isolated candidate changed: ' + name)
    converted = real_module('moe_tiny_converted', candidate / '__init__.py', package=True)
    converted_nodes = importlib.import_module('moe_tiny_converted._nodes')
    schemas = load(source / 'v2/_schemas.json')
    batch = load(HERE / 'BATCH_CASES.json')
    require(batch['comparison_count'] == 52 and len(batch['cases']) == 52, 'Finite52 matrix changed')
    rows, failures, controls = [], [], []
    all_console = textio.StringIO()
    try:
        for case in batch['cases']:
            row = schemas[case['original_id']]
            original_class = getattr(native[row['module']], row['class'])
            require(original_class.__module__.startswith('moe_tiny_native.'), 'Wrong genuine original class origin')
            node = converted_nodes.NODE_CLASS_MAPPINGS[row['id']]
            original_kwargs, candidate_kwargs = copy.deepcopy(case['inputs']), copy.deepcopy(case['inputs'])
            original_method = getattr(original_class(), row['function'])
            native_signature = inspect.signature(original_method)
            native_accepts_extra = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in native_signature.parameters.values())
            # Match the converted runtime's existing public hidden defaults.
            # No Core execution/hidden hydration is claimed by this direct batch.
            hidden = getattr(node, 'hidden', None)
            for name, source_name in row['inputs'].get('hidden', {}).items():
                attribute = {'PROMPT': 'prompt', 'EXTRA_PNGINFO': 'extra_pnginfo', 'UNIQUE_ID': 'unique_id'}.get(source_name) if isinstance(source_name, str) else None
                if attribute and (name in native_signature.parameters or native_accepts_extra):
                    value = getattr(hidden, attribute, None)
                    original_kwargs[name] = '0' if name == 'my_unique_id' and value is None else value
            for section in ('required', 'optional'):
                for key, spec in row['inputs'].get(section, {}).items():
                    if spec[0] in ('PIPE_LINE', 'PIPE_LINE_SDXL') and type(candidate_kwargs.get(key)) is dict:
                        candidate_kwargs[key] = {('__ttn_latent__' if k == 'samples' else k): v for k, v in candidate_kwargs[key].items()}
            resolver = engine.InProcessRefResolver()
            plan = engine.ExecutionPlan(prompt_id='tiny-pure-native', node_id=case['case_id'], node_type=row['id'],
                                        node_module=node.__module__, permissions=tuple(node.SDK_PERMISSIONS))
            context = engine.InProcessCtxProvider().build(plan)
            operations = engine.InProcessOps()
            try:
                with contextlib.redirect_stdout(all_console), engine.bind_runtime(resolver, context, operations):
                    left = await outcome(lambda: original_method(**original_kwargs), io, sdk)
                    right = await outcome(lambda: node.execute(**candidate_kwargs), io, sdk, converted=True)
                matched = left == right
                if case['case_id'] == 'cycle-too-negative':
                    matched = matched and left['kind'] == 'error' and left['type'] == 'IndexError'
                else:
                    matched = matched and left['kind'] == 'value'
                rows.append(dict(case_id=case['case_id'], original_id=case['original_id'], registered_id=row['id'],
                                 comparison_kind=case['comparison_kind'], original=left, candidate=right, matched=matched,
                                 native_module_path=native[row['module']].__file__, declared_permissions=list(node.SDK_PERMISSIONS)))
                if not matched:
                    failures.append(case['case_id'])
            finally:
                resolver.clear()
            require(len(all_console.getvalue().encode()) <= 16384, 'Console byte bound exceeded')
        for control, case_id, kind, replacement, expected in [
            ('corrupt_actual_STRING', 'text-1', 'str', ['str', 'wrong STRING'], None),
            ('numeric_type_change', 'int-0', 'int', ['str', '0'], '0'),
            ('pipe_seed_change', 'pipe-out-null-carriers', 'int', ['int', '8'], '7')]:
            actual = next(r for r in rows if r['case_id'] == case_id)['candidate']
            wrong = copy.deepcopy(actual)
            changed = mutate_tag(wrong, kind, replacement, expected)
            detected = changed and wrong != actual
            controls.append(dict(control=control, source_case=case_id, detected=detected))
            if not detected:
                failures.append('control:' + control)
        for name, pin in source_pins.items():
            require(sha(source / name) == pin['sha256'], 'Frozen source changed after batch')
        for name, pin in candidate_pins.items():
            require(sha(candidate / name) == pin['sha256'], 'Isolated candidate changed after batch')
        for name, pin in sdk_pins.items():
            require(sha(site / name) == pin, 'SDK source changed after batch')
        report = dict(status='PASS_FINITE_TINY_PURE_DIRECT_NATIVE_BATCH_ONLY' if not failures else 'FAILED_FINITE_TINY_PURE_DIRECT_NATIVE_BATCH_NO_RETRY',
                      authorization_message=options.authorization_message, attempts=1, automatic_retries=0,
                      comparisons=rows, comparison_count=52, selected_original_nodes=24, native_direct_diagnostics=2,
                      comparator_controls=controls, comparator_control_count=3, failures=failures,
                      actual_SDK_origins={m.__name__: dict(path=m.__file__, sha256=sha(m.__file__)) for m in (io,sdk,engine)},
                      original_full_modules_loaded=True, original_root_entrypoint_exercised=False,
                      provider_replacements=0, private_raw_constructor_calls=0, historical19_or_normal47_validator43_reruns=0,
                      models_loaded=0, Guest_launches=0, graph_expansions=0, output_domain_writes=0,
                      pipe_scope='Null-resource metadata/tuple/wire routing only; no real model/latent/conditioning lifetime claim',
                      seven_restricted_purposes_exercised=0, whole_pack_or_service_or_frontend_or_admission_accepted=False)
        (options.output / 'RESULT.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        (options.output / 'console.txt').write_text(all_console.getvalue())
        return 0 if not failures else 1
    finally:
        for name in list(sys.modules):
            if name in ('moe_tiny_native','moe_tiny_converted') or name.startswith(('moe_tiny_native.','moe_tiny_converted.')):
                del sys.modules[name]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-message', required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    try:
        code = asyncio.run(run(options))
    except BaseException:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)
