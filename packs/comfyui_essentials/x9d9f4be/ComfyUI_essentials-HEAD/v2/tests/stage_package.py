"""Gate-only POSIX staging; requires separately selected real positive/negative receipts."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import types

assert Path('/pack/v2/image.py').is_file() and Path('/tests/guest_common.lock').is_file()
sys.dont_write_bytecode = True
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('packaging exceeded 430 seconds')))
signal.alarm(430)
RESULTS = Path('/results')
EVIDENCE = Path('/tests/stage-evidence')
selection = json.loads((EVIDENCE / 'SELECTION.json').read_text())
expected_sources = json.loads(Path('/tests/expected-source-placeholders.json').read_text())
for row in selection['files']:
    source = EVIDENCE / row['path']
    assert source.stat().st_size == row['bytes']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256']
for kind in ('positive', 'negative'):
    receipt = EVIDENCE / kind / 'qualification.json'
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == selection[kind + '_qualification_sha256']
positive = json.loads((EVIDENCE / 'positive/qualification.json').read_text())
negative = json.loads((EVIDENCE / 'negative/qualification.json').read_text())
assert positive['status'] == 'PASS' and positive['scheduled_cases'] == 118
assert positive['nodes'] == {'guest/GetImageSize+': {'EXACT': 32}, 'guest/ImageBatchMultiple+': {'EXACT': 66, 'REFUSED-AS-DESIGNED': 20}}
assert positive['guest_unqualified_execution_refusals'] == 83
assert positive['schemas']['source_schema_exact'] == 85 and positive['schemas']['unqualified_validation_refusals'] == 83
assert positive['guest_import_control_before'] == positive['guest_import_control_after'] == 'DENIED'
assert positive['guest_killed'] and positive['temporary_namespace_removed']
assert negative['status'] == 'FAIL' and negative['negative_control_observed'] is True
assert negative['scheduled_cases'] == 1 and negative['negative_control_overlay']['case_index'] == 245
assert negative['negative_control_overlay']['classification'] == 'actual Guest wrong-output witness; no host output mutation'
assert negative['guest_killed'] and negative['temporary_namespace_removed']
assert negative['guest_pid'] != negative['host_pid']

sys.path[:0] = ['/core', '/overlay', '/tests']
import packpair
from comfy_secure_nodes import packpatch, packdb
assert hashlib.sha256(Path(packpatch.__file__).read_bytes()).hexdigest() == '234c4abb2fbbccb7dcb2b59decea4a4236525a0b0b6d9455968981cdc7eb6668'
assert hashlib.sha256(Path(packdb.__file__).read_bytes()).hexdigest() == '7cc6d97729a1591c25022ec4ff7e83100cfd7de90ecf718cc0509e921dea85d1'

def regular_tree(root):
    out = {}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink(), path
        if path.is_file():
            out[path.relative_to(root).as_posix()] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(path.stat().st_mode))
        else:
            assert path.is_dir() and stat.S_IMODE(path.stat().st_mode) == 0o755
    return out

def identical(a, b):
    result = packpair.cmptree(a, b)
    assert not any(result[key] for key in ('missing_in_a', 'missing_in_b', 'bytes_differ', 'modes_differ')), result
    return result

with tempfile.TemporaryDirectory(prefix='essentials-r8-package-') as temporary:
    root = Path(temporary)
    stage = root / 'stage'
    snapshot = stage / 'packs/comfyui_essentials/x9d9f4be'
    pack = snapshot / 'ComfyUI_essentials-HEAD'
    shutil.copytree('/pack', pack)
    shutil.copytree('/tests', pack / 'v2/tests', dirs_exist_ok=True, ignore=shutil.ignore_patterns('negative-overlay'))
    # This second positive qualification reads this actual final POSIX source tree.
    with (RESULTS / 'qualification-driver.log').open('w') as output:
        finished = subprocess.run([sys.executable, '/tests/run_qualification.py', '--phase', 'guest-batch-size', '--pack-root', str(pack)],
            stdout=output, stderr=subprocess.STDOUT, timeout=375)
    assert finished.returncode == 0, 'Final POSIX source qualification failed; raw outcome retained'
    actual = json.loads((RESULTS / 'qualification.json').read_text())
    assert actual['status'] == 'PASS' and actual['pack_root'] == str(pack)
    assert actual['nodes'] == positive['nodes'] and actual['guest_unqualified_execution_refusals'] == 83
    assert actual['temporary_namespace_removed'] and actual['guest_killed']
    manifest = json.loads((RESULTS / 'secure-nodes.json').read_text())
    assert hashlib.sha256((RESULTS / 'secure-nodes.json').read_bytes()).hexdigest() == selection['manifest_sha256']
    assert len(manifest['nodes']) == 85 and manifest['web_directory'] is None
    assert manifest['nodes']['ImageResize+']['module'] == '_refusals'
    shutil.copyfile(RESULTS / 'secure-nodes.json', pack / 'v2/secure-nodes.json')
    before_modules = set(sys.modules)
    loaded = packdb.load_pack(snapshot)
    prefix = 'custom_nodes.pack_comfyui_essentials_x9d9f4be'
    def describe(value):
        if value is None or type(value) in (str, bool, int, float):
            return value
        return {'type': type(value).__module__ + '.' + type(value).__qualname__}
    pack_module_closure = []
    observed_modules = {}
    for module_name, module in tuple(sys.modules.items()):
        source = getattr(module, '__file__', None)
        if (module_name == prefix or module_name.startswith(prefix + '.')
                or isinstance(source, str) and Path(source).resolve().is_relative_to(pack.resolve())):
            observed_modules[module_name] = module
            observed_sha256 = None
            observed_source_error = None
            if isinstance(source, str):
                try:
                    observed_sha256 = hashlib.sha256(Path(source).read_bytes()).hexdigest()
                except OSError as error:
                    observed_source_error = {'type': type(error).__name__, 'message': str(error)}
            pack_module_closure.append({'module': module_name,
                'type': type(module).__module__ + '.' + type(module).__qualname__,
                'exact_module_type': type(module) is types.ModuleType,
                'keys': sorted(vars(module)),
                'metadata': {key: describe(value) for key, value in sorted(vars(module).items())},
                'has_builtins': '__builtins__' in vars(module),
                'source_sha256': observed_sha256, 'source_read_error': observed_source_error})
    proxy_metadata = []
    for node_id, cls in loaded.node_mappings.items():
        function = getattr(cls.execute, '__func__', None)
        proxy_metadata.append({'node_id': node_id, 'class': cls.__name__, 'module': cls.__module__,
            'secure_node_proxy': getattr(cls, 'SECURE_NODE_PROXY', None),
            'sdk_refs': getattr(cls, 'SDK_REFS', None), 'permissions': list(cls.SDK_PERMISSIONS),
            'class_keys': sorted(vars(cls)), 'execute_type': type(cls.execute).__name__,
            'execute_function_module': getattr(function, '__module__', None),
            'execute_function_name': getattr(function, '__qualname__', None),
            'execute_function_source': getattr(getattr(function, '__code__', None), 'co_filename', None),
            'execute_is_trusted_packdb_refusal': function is packdb._refuse_local})
    normal_load = {'status': 'OBSERVED_BEFORE_ASSERTIONS', 'loader': 'packdb.load_pack(snapshot)',
        'observed_registered_ids': sorted(loaded.node_mappings),
        'manifest_modules': sorted({row['module'] for row in manifest['nodes'].values()}),
        'host_pack_module_closure': pack_module_closure, 'proxy_metadata': proxy_metadata,
        'sealed_expected_source_sha256': expected_sources,
        'new_host_modules': sorted(set(sys.modules) - before_modules),
        'observed_web_directory': describe(loaded.web_directory),
        'observed_routes': describe(loaded.routes), 'observed_frontend_permissions': sorted(loaded.frontend_permissions),
        'restored_original_modules_activated': None}
    normal_path = RESULTS / 'normal-pack-load.json'
    normal_path.write_text(json.dumps(normal_load, indent=2, sort_keys=True) + '\n')
    # Only the two exact inert source placeholders constructed by selected packdb
    # are permitted. Their source paths do not mean that source was executed.
    assert normal_load['manifest_modules'] == ['_refusals', 'image']
    assert set(expected_sources) == {'image', '_refusals'}
    expected_modules = {prefix + '.' + name: (pack / 'v2' / (name + '.py')).resolve() for name in ('image', '_refusals')}
    assert set(observed_modules) == set(expected_modules)
    standard_keys = {'__name__', '__doc__', '__package__', '__loader__', '__spec__', '__file__'}
    for name, module in observed_modules.items():
        assert type(module) is types.ModuleType and set(vars(module)) == standard_keys
        assert module.__name__ == name and module.__package__ == prefix
        assert module.__doc__ is None and module.__loader__ is None and module.__spec__ is None
        assert Path(module.__file__).resolve() == expected_modules[name]
        assert '__builtins__' not in vars(module)
        short_name = name.removeprefix(prefix + '.')
        assert expected_sources[short_name]['relative_path'] == 'v2/' + short_name + '.py'
        observation = next(row for row in pack_module_closure if row['module'] == name)
        assert observation['source_read_error'] is None
        assert observation['source_sha256'] == expected_sources[short_name]['sha256']
    assert len(proxy_metadata) == 85
    assert all(row['secure_node_proxy'] is True and row['execute_is_trusted_packdb_refusal'] for row in proxy_metadata)
    assert set(loaded.node_mappings) == set(manifest['nodes']) == set(json.loads((pack / 'v2/_schemas.json').read_text()))
    assert len(loaded.node_mappings) == 85
    checked_ids = []
    for node_id, cls in loaded.node_mappings.items():
        schema = cls.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        checked_ids.append(node_id)
    assert loaded.web_directory is None and not loaded.routes and not loaded.frontend_permissions
    assert not loaded.static_directories and not loaded.asset_directories and not loaded.scheduler_providers
    assert manifest['web_directory'] is None and manifest.get('frontend_permissions', []) == []
    assert manifest.get('routes', []) == [] and manifest.get('static_directories', {}) == {}
    assert manifest.get('asset_directories', {}) == {} and manifest.get('scheduler_providers', []) == []
    normal_load.update({'status': 'PASS', 'registered_ids': sorted(checked_ids), 'validated_schema_ids': len(checked_ids),
        'web_directory': None, 'routes': [], 'frontend_permissions': [],
        'static_directories': {}, 'asset_directories': {}, 'scheduler_providers': [],
        'restored_original_modules_activated': False, 'exact_source_placeholders_verified': 2,
        'trusted_host_refusal_proxy_classes_verified': 85})
    normal_path.write_text(json.dumps(normal_load, indent=2, sort_keys=True) + '\n')
    evidence = pack / 'v2/tests/evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    for name in ('qualification.json', 'guest-import-guard.json', 'guest-import-denials.jsonl', 'source-schemas.json', 'source-schema-differences.json', 'normal-pack-load.json'):
        shutil.copyfile(RESULTS / name, evidence / name)
    with (pack / 'v2/SECURE_CONVERSION.md').open('a') as output:
        output.write('\nFinal POSIX assembly verification: 118 actual Guest cases (98 exact, 20 named branch refusals), 85 source-exact/Guest-validated schemas and 83 actual whole-node execution refusals. Strict tensor checks, import guard before/after, distinct PID, kill and temporary-root removal passed. Detailed actual receipt: tests/evidence/qualification.json. The selected separate actual-Guest wrong-output witness failed the logical-byte assertion as required; its raw receipt is in tests/stage-evidence/negative/.\n')
    shutil.copyfile('/tests/pack-entry.json', stage / 'packs-json-entry.json')
    for path in [stage] + list(stage.rglob('*')):
        assert not path.is_symlink()
        path.chmod(0o755 if path.is_dir() else 0o644)
    pair_manifest, pair_diff = packpair.generate(snapshot)
    real_manifest, real_diff = packpatch.generate(snapshot)
    assert pair_manifest == real_manifest and pair_diff == real_diff
    pairdir = stage / 'patches/comfyui_essentials/x9d9f4be'
    pairdir.mkdir(parents=True)
    stem = pairdir / 'comfyui_essentials-x9d9f4be'
    Path(str(stem) + '.json').write_text(json.dumps(pair_manifest, indent=1) + '\n')
    Path(str(stem) + '.diff').write_text(pair_diff)
    comparisons = {}
    for kind in ('independent', 'selected-real'):
        replay = root / kind / 'comfyui_essentials/x9d9f4be'
        replay_pack = replay / pack.name
        shutil.copytree(pack, replay_pack, ignore=shutil.ignore_patterns('v2'))
        if kind == 'independent':
            packpair.apply(replay, pair_manifest, pair_diff)
        else:
            packpatch.apply(replay, pair_manifest, pair_diff)
        comparisons[kind] = identical(pack / 'v2', replay_pack / 'v2')
    for path in [stage] + list(stage.rglob('*')):
        path.chmod(0o755 if path.is_dir() else 0o644)
    files = regular_tree(stage)
    (stage / 'SHA256SUMS').write_text(''.join(value[0] + '  ' + name + '\n' for name, value in files.items()))
    (stage / 'SHA256SUMS').chmod(0o644)
    archive = RESULTS / 'stage-r8.tar'
    with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as handle:
        handle.add(stage, arcname='stage')
    extracted = root / 'archive-check'
    with tarfile.open(archive) as handle:
        assert all(member.isfile() or member.isdir() for member in handle.getmembers())
        handle.extractall(extracted, filter='data')
    assert regular_tree(stage) == regular_tree(extracted / 'stage')
    proof = {'status': 'PASS', 'authoritative_stage': 'stage-r8.tar', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'stage_files': len(regular_tree(stage)), 'pair_counts': pair_manifest['counts'], 'replay': comparisons,
        'archive_roundtrip_bytes_modes_exact': True, 'runtime_qualification_source': 'POSIX temporary stage',
        'ntfs_stage_mount_qualified': False, 'source_pack': str(pack),
        'normal_pack_load': normal_load,
        'final_guest_receipt_sha256': hashlib.sha256((RESULTS / 'qualification.json').read_bytes()).hexdigest()}
    (RESULTS / 'packaging.json').write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps(proof), flush=True)
signal.alarm(0)
