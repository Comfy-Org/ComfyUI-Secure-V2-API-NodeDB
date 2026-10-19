"""Read returned evidence only. No supplied imports, SDK or replay execution."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / 'resolution-ratio-generation-macos-r1-20261019'
SNAPSHOT = Path('comfyui_resolution-and-ratio/x58769e5/ComfyUI_Resolution-and-Ratio-HEAD')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return json.loads(path.read_bytes())

def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--attempt-relative', required=True)
    parser.add_argument('--outer-relative', required=True)
    parser.add_argument('--source-relative', required=True)
    parser.add_argument('--authorization-message', required=True)
    args = parser.parse_args()
    received = (args.capture / 'received').resolve(strict=True)
    attempt = (received / args.attempt_relative).resolve(strict=True)
    outer_path = (received / args.outer_relative).resolve(strict=True)
    assert attempt.is_relative_to(received) and outer_path.is_relative_to(received)
    assert not (args.capture / 'VERIFIED_RESULT_RECEIPT.json').exists()
    capture = load(args.capture / 'CAPTURE_RECEIPT.json')
    rows = {row['path']: row for row in capture['files']}
    assert len(rows) == capture['regular_members']
    assert sha(args.capture / 'MIKE_RESULT.zip') == capture['archive_sha256']
    assert set(inventory(received)) == set(rows)
    for name, row in rows.items():
        path = received / name
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    manifest = load(received / 'MANIFEST.json')
    declared = {row['path']: row for row in manifest['files']}
    assert len(declared) == len(manifest['files']) and set(declared) == set(rows) - {'MANIFEST.json'}
    for name, row in declared.items():
        assert row['sha256'] == rows[name]['sha256'] and row['bytes'] == rows[name]['bytes']
    returned_source = (received / args.source_relative).resolve(strict=True)
    assert returned_source.is_relative_to(received)
    assert inventory(SOURCE) == inventory(returned_source), 'Sealed source differs'
    assert sha(SOURCE / 'HANDOFF.json') == 'c940ac0ad27e196d3c28efb4b5095bb9dfed2d350be9f43634c028b684ded83c'
    result = load(attempt / 'RESULT.json')
    assert result['status'] == 'PASS_REAL_RESOLUTION_BACKEND_SDK_NORMAL_ENCODER_AND_CANONICAL_REPLAYS_ONLY'
    assert result['actual_sdk_attempts'] == result['normal_generation_attempts'] == 1
    assert result['root_execution_mail'] == args.authorization_message
    assert not result['managed_runtime_claim'] and not result['frontend_or_service_or_registry_acceptance']
    assert result['hard_memory_cap_bytes'] is None and result['cpu_quota'] is None
    assert result['elapsed_seconds'] < 58
    outer = load(outer_path)
    expected_argv = list(load(SOURCE.with_suffix('.INVOCATION.json'))['argv_if_released'])
    actual_argv = outer['exact_argv']
    for flag in ('--scratch', '--authorization-message'):
        index = expected_argv.index(flag) + 1
        expected_argv[index] = actual_argv[index]
    # Transport location may change, but the invoked runner must be the sealed packet.
    assert Path(actual_argv[actual_argv.index('--execute') - 1]).name == 'run_generation.py'
    runner_index = expected_argv.index('--execute') - 1
    expected_argv[runner_index] = actual_argv[runner_index]
    assert actual_argv == expected_argv
    assert actual_argv[actual_argv.index('--authorization-message') + 1] == args.authorization_message
    assert outer['attempts'] == 1 and outer['automatic_retries'] == 0 and outer['exit_code'] == 0
    assert not outer['outer_watchdog_fired'] and outer['wall_seconds'] < 60
    assert outer['authorization_message'] == args.authorization_message
    assert (outer['work_seconds'], outer['cleanup_deadline_seconds'], outer['outer_watchdog_seconds']) == (55, 58, 60)
    assert not outer['rss_watchdog_fired'] and outer['monitor_error'] is None
    assert outer['hard_memory_quota_enforced'] is False and outer['hard_cpu_core_quota_enforced'] is False
    assert outer['supervisor_status'] == result['status'] and outer['supervisor_error'] is None
    assert outer['inputs_unchanged'] and outer['sdk_core_dependency_backend_python_unchanged'] and outer['pass_with_evidence']
    assert outer['exact_owned_processes_remaining'] == []
    commands = result['commands']
    assert [row['name'] for row in commands] == ['sdk_parity', 'normal_generate', 'pair_generate', 'pair_bundle', 'replay_pair', 'replay_zip']
    groups = outer['all_observed_and_recorded_groups_absent']
    assert set(groups) == {str(row['pid']) for row in commands} | {str(outer['outer_pid_and_pgid'])}
    assert all(value is True for value in groups.values())
    assert outer['worker_groups_recorded_at_creation'] == {row['name']: row['pid'] for row in commands}
    assert outer['worker_cleanup_rows'] == [row['cleanup'] for row in commands]
    for row in commands:
        assert row['exit_code'] == 0 and row['argv'][0] == '/usr/bin/sandbox-exec'
        assert row['cleanup']['confirmed'] and row['cleanup']['leader_reaped'] and row['cleanup']['group_absence_confirmed']
        assert not row['cleanup']['errors'] and groups[str(row['pid'])]
    profile = load(SOURCE / 'inputs/ACTUAL_MAC_PROFILE.json')
    post_path = attempt / 'POST_GENERATION_READBACK.json'
    post = load(post_path)
    assert sha(post_path) == result['post_generation_readback_sha256']
    assert post['sdk'] == profile['sdk_files'] and len(post['sdk']) == 141
    assert post['core'] == profile['core_files'] and len(post['core']) == 1384
    assert post['science'] == load(SOURCE / 'inputs/SCIENCE_BINDING.json')['site_file_pins'] and len(post['science']) == 4
    backend = load(SOURCE / 'inputs/mac-readback/OVERLAY-SOURCE-INVENTORY.json')
    assert post['backend'] == {n.removeprefix('backend/'): row['sha256'] for n, row in backend['files'].items()} and len(post['backend']) == 83
    candidate = inventory(SOURCE / 'candidate')
    assert post['candidate'] == candidate and len(candidate) == 12
    sdk_path = attempt / 'ACTUAL_SDK_RESULT.json'
    sdk = load(sdk_path)
    assert sha(sdk_path) == result['actual_sdk_result_sha256']
    assert sdk['status'] == 'PASS_REAL_ORIGINAL_AND_SELECTED_SDK_BACKEND_ONLY' and sdk['node_id'] == 'ResolutionAndRatio'
    assert sdk['schema_count'] == 1 and sdk['execution_comparisons'] == sdk['validator_comparisons'] == 1033
    assert sdk['random_comparisons'] == 1000 and sdk['random_seed'] == 20261019
    assert len(sdk['guard_denials']) == len({row['case'] for row in sdk['guard_denials']}) == 33
    assert {row['control'] for row in sdk['negative_controls']} == {'swapped_dimensions', 'javascript_tie_rounding', 'unwanted_scale_recompute'}
    assert len(sdk['negative_controls']) == 3 and all(row['detected'] is True for row in sdk['negative_controls'])
    fixed = sdk['fixed_cases']
    assert len(fixed) == 33 and sum(row['kind'] == 'fixed' for row in fixed) == 32
    assert sum(row['kind'] == 'backend_frontend_separation' for row in fixed) == 1
    assert all(row['expected'] == row['actual'] and len(row['actual']) == 2 and all(type(v) is int and 8 <= v <= 4096 for v in row['actual']) for row in fixed)
    assert not sdk['frontend_tested'] and not sdk['service_tested'] and not sdk['general_runtime_adoption']
    assert Path(sdk['sdk_io_origin']).is_relative_to(Path(profile['common_site_packages']))
    spec = load(SOURCE / 'JOB_SPEC.json')
    assert Path(sdk['encoder_origin']).is_relative_to(Path(spec['actual_mac_binding']['backend_source_root']))
    with zipfile.ZipFile(SOURCE / 'inputs/ORIGINAL.zip') as archive:
        pristine = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    binding = load(SOURCE / 'inputs/SOURCE_BINDING.json')
    if set(pristine) != set(binding['original_files']):
        prefix = next(iter(pristine)).split('/')[0] + '/'
        pristine = {n.removeprefix(prefix): data for n, data in pristine.items()}
    assert len(pristine) == 7 and {n: hashlib.sha256(data).hexdigest() for n, data in pristine.items()} == binding['original_files']
    trees = [attempt / kind / SNAPSHOT for kind in ('packs', 'replay-pair', 'replay-zip')]
    expected = dict(candidate, **{'secure-nodes.json': sha(trees[0] / 'v2/secure-nodes.json')})
    for tree in trees:
        originals = {p.relative_to(tree).as_posix(): p.read_bytes() for p in tree.rglob('*') if p.is_file() and not p.is_relative_to(tree / 'v2')}
        assert originals == pristine
        assert inventory(tree / 'v2') == expected
        assert all(rows[p.relative_to(received).as_posix()]['archive_mode'] == '0o644' for p in tree.rglob('*') if p.is_file())
    assert result['v2_files'] == {n: {'sha256': digest, 'git_mode': '100644'} for n, digest in expected.items()}
    normal = load(trees[0] / 'v2/secure-nodes.json')
    assert set(normal['nodes']) == {'ResolutionAndRatio'} and normal['web_directory'] == 'web'
    assert normal['runtime'] == {'python': {'requires': '>=3.13,<3.14', 'resolved': '3.13'}}
    node = normal['nodes']['ResolutionAndRatio']
    assert node['class'] == 'ResolutionAndRatio' and node['module'] == 'resolution_and_ratio'
    assert node['sdk_refs'] is False and node['permissions'] == [] and node['methods']['validate_inputs'] is True
    assert node['validation_inputs'] == sdk['validator_signature_encoded_by_actual_encoder']
    assert [row['attrs']['id'] for row in node['schema']['inputs']] == ['width', 'height', 'W_ratio', 'H_ratio', 'scale_percent', 'reset', 'swap', 'preset', 'custom_presets']
    assert [row['io_type'] for row in node['schema']['outputs']] == ['INT', 'INT']
    assert result['normal_manifest_sha256'] == expected['secure-nodes.json']
    patches = attempt / 'patches/comfyui_resolution-and-ratio/x58769e5'
    pair = patches / 'comfyui_resolution-and-ratio-x58769e5.json'
    diff, bundle = pair.with_suffix('.diff'), pair.with_suffix('.zip')
    patch = load(pair)
    assert patch['format'] == 'comfy-pack-patch/1' and patch['pack'] == 'comfyui_resolution-and-ratio' and patch['key'] == 'x58769e5'
    patch_rows = {row['path']: row for row in patch['files']}
    assert len(patch_rows) == len(patch['files']) and set(patch_rows) == set(expected) | set(pristine)
    for name, row in patch_rows.items():
        base_digest = hashlib.sha256(pristine[name]).hexdigest() if name in pristine else None
        if name not in expected:
            assert row == {'path': name, 'op': 'delete', 'base_sha256': base_digest}
        elif name not in pristine:
            assert row == {'path': name, 'op': 'add', 'v2_sha256': expected[name], 'mode': 0o644}
        elif base_digest == expected[name]:
            assert row == {'path': name, 'op': 'copy', 'base_sha256': base_digest, 'mode': 0o644}
        else:
            assert row == {'path': name, 'op': 'convert', 'base_sha256': base_digest, 'v2_sha256': expected[name], 'mode': 0o644}
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None and set(archive.namelist()) == {pair.name, diff.name}
        assert archive.read(pair.name) == pair.read_bytes() and archive.read(diff.name) == diff.read_bytes()
    receipt = {'status': 'VERIFIED_RETURNED_RESOLUTION_ORIGINAL_SDK_NORMALGEN_AND_REPLAYS_ONLY',
               'archive_sha256': capture['archive_sha256'], 'result_sha256': sha(attempt / 'RESULT.json'),
               'actual_sdk_result_sha256': sha(sdk_path), 'normal_manifest_sha256': expected['secure-nodes.json'],
               'pair_sha256': sha(pair), 'diff_sha256': sha(diff), 'bundle_sha256': sha(bundle),
               'patch_operations_verified': len(patch_rows), 'original_only_delete_operations': sum(row['op'] == 'delete' for row in patch_rows.values()),
               'outer_receipt_sha256': sha(outer_path), 'post_generation_sha256': sha(post_path),
               'original_files_per_tree': 7, 'v2_files_per_tree': 12, 'equal_trees': 3,
               'reported_execution_comparisons': 1033, 'reported_validator_comparisons': 1033,
               'reported_guard_denials': 33, 'reported_wrong_controls_detected': 3,
               'postmaps': {k: len(v) for k, v in post.items()},
               'wall_seconds': outer['wall_seconds'], 'observed_children_maxrss_bytes_darwin': outer['observed_children_maxrss_bytes_darwin'],
               'outer_actual_authorization': outer['authorization_message'], 'source_transport_relative': args.source_relative,
               'source_relocation_recorded_no_bytes_changed': True, 'outer_rss_watchdog_bytes': outer['rss_watchdog_bytes'],
               'hard_memory_or_cpu_quota_claimed': False, 'six_child_and_outer_group_ids': sorted(groups),
               'supplied_code_executed_during_intake': False,
               'local_sdk_generator_or_replay_runs': 0, 'service_or_frontend_acceptance': False,
               'scope': 'Byte/metadata verification of returned actual records only; no independent reexecution and no blanket environment/dependency certification.'}
    (args.capture / 'VERIFIED_RESULT_RECEIPT.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
