"""Verify retained actual Join R2 records without executing returned code."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

WORK = Path(__file__).resolve().parents[2]
SOURCE = WORK / 'coordination/joinprompt2-generation-macos-r2-20261019'
SNAPSHOT = Path('comfy-join-prompt/x0832089/comfy-join-prompt-HEAD')
IDS = ['jupo.JoinPrompt.JoinStrings', 'jupo.JoinPrompt.JoinPrompt']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
load = lambda path: json.loads(path.read_bytes())

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
    capture = args.capture.resolve(strict=True)
    received = (capture / 'received').resolve(strict=True)
    attempt, outer_path = (received / args.attempt_relative).resolve(strict=True), (received / args.outer_relative).resolve(strict=True)
    assert attempt.is_relative_to(received) and outer_path.is_relative_to(received)
    assert not (capture / 'VERIFIED_RESULT_RECEIPT.json').exists()
    capture_record = load(capture / 'CAPTURE_RECEIPT.json')
    assert sha(capture / 'MIKE_RESULT.zip') == capture_record['archive_sha256']
    rows = {row['path']: row for row in capture_record['files']}
    assert len(rows) == capture_record['regular_members']
    assert set(rows) == set(inventory(received))
    manifest = load(received / 'MANIFEST.json')
    declared = {row['path']: row for row in manifest['files']}
    assert len(declared) == len(manifest['files']) and set(declared) == set(rows) - {'MANIFEST.json'}
    for name, row in rows.items():
        assert row['sha256'] == sha(received / name) and row['bytes'] == (received / name).stat().st_size
        if name in declared:
            assert row['sha256'] == declared[name]['sha256'] and row['bytes'] == declared[name]['bytes']
    assert sha(SOURCE / 'HANDOFF.json') == 'ed42b44230bc46f2ed2ba98e2031f79378758907d52aaca56fe5733d18f98895'
    returned_source = (received / args.source_relative).resolve(strict=True)
    assert returned_source.is_relative_to(received)
    assert inventory(SOURCE) == inventory(returned_source), 'Returned sealed source differs'
    report = load(attempt / 'RESULT.json')
    assert report['status'] == 'PASS_GENUINE_JOIN_FULL_ORIGINAL_SDK_NORMALGEN_AND_REPLAYS_ONLY'
    assert report['actual_sdk_attempts'] == report['normal_generation_attempts'] == 1
    assert report['root_execution_mail'] == args.authorization_message
    assert report['hard_memory_cap_bytes'] is None and report['cpu_quota'] is None
    assert not report['managed_runtime_claim'] and not report['guest_or_frontend_or_service_or_registry_acceptance']
    assert report['elapsed_seconds'] < 58
    outer = load(outer_path)
    actual_argv = outer['exact_argv']
    expected_argv = list(load(SOURCE.with_suffix('.INVOCATION.json'))['argv_if_released'])
    for flag in ('--scratch', '--authorization-message'):
        index = expected_argv.index(flag) + 1
        expected_argv[index] = actual_argv[index]
    runner_index = expected_argv.index('--execute') - 1
    assert Path(actual_argv[runner_index]).name == 'run_generation.py'
    expected_argv[runner_index] = actual_argv[runner_index]
    assert actual_argv == expected_argv and actual_argv[actual_argv.index('--authorization-message') + 1] == args.authorization_message
    assert outer['attempts'] == 1 and outer['automatic_retries'] == 0 and outer['exit_code'] == 0
    assert not outer['outer_watchdog_fired'] and outer['wall_seconds'] < 60
    assert outer['authorization_message'] == args.authorization_message
    assert (outer['work_seconds'], outer['cleanup_deadline_seconds'], outer['outer_watchdog_seconds']) == (55, 58, 60)
    assert not outer['rss_watchdog_fired'] and outer['monitor_error'] is None
    assert outer['hard_memory_quota_enforced'] is False and outer['hard_cpu_core_quota_enforced'] is False
    assert outer['supervisor_status'] == report['status'] and outer['supervisor_error'] is None
    assert outer['inputs_unchanged'] and outer['sdk_core_dependency_backend_python_unchanged'] and outer['pass_with_evidence']
    assert outer['exact_owned_processes_remaining'] == []
    commands = report['commands']
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
    profile, spec = load(SOURCE / 'inputs/ACTUAL_MAC_PROFILE.json'), load(SOURCE / 'JOB_SPEC.json')
    post_path = attempt / 'POST_GENERATION_READBACK.json'
    post = load(post_path)
    assert sha(post_path) == report['post_generation_readback_sha256']
    assert post['sdk'] == profile['sdk_files'] and len(post['sdk']) == 141
    assert post['core'] == profile['core_files'] and len(post['core']) == 1384
    assert post['science'] == load(SOURCE / 'inputs/SCIENCE_BINDING.json')['site_file_pins'] and len(post['science']) == 4
    backend = load(SOURCE / 'inputs/mac-readback/OVERLAY-SOURCE-INVENTORY.json')
    assert post['backend'] == {n.removeprefix('backend/'): row['sha256'] for n, row in backend['files'].items()} and len(post['backend']) == 83
    candidate = inventory(SOURCE / 'candidate')
    assert post['candidate'] == candidate and len(candidate) == 14
    sdk_path = attempt / 'ACTUAL_SDK_RESULT.json'
    sdk = load(sdk_path)
    assert sha(sdk_path) == report['actual_sdk_result_sha256']
    assert sdk['status'] == 'PASS_GENUINE_FULL_ORIGINAL_AND_REAL_SELECTED_SDK_COMPONENTS_ONLY'
    assert sdk['node_ids'] == IDS and set(sdk['schemas']) == set(IDS)
    assert sdk['execution_comparisons'] == sdk['component_crosschecks'] == 704
    assert sdk['full_original_entrypoint_imported'] and sdk['real_server_constructor']
    assert sdk['synthetic_server_or_sdk'] is False and sdk['server_setup_or_listeners_started'] is False
    assert sdk['original_added_routes'] == 0 and sdk['route_registration_count_before_and_after'] > 0
    assert set(sdk['cleanup']) == {'client_session_closed', 'app_cleaned', 'asset_manager_shutdown', 'owned_paths_checked'}
    assert all(value is True for value in sdk['cleanup'].values())
    assert not sdk['frontend_or_guest_or_service_or_general_adoption']
    scope = sdk['component_oracle_scope']
    assert scope['full_original_package_imported'] is False and scope['server_module_injected'] is False and scope['sdk_substituted'] is False
    vectors = load(SOURCE / 'inputs/BACKEND_VECTORS.json')
    expected_ids = {row['id'] for row in vectors['direct_cases']} | {row['id'] for row in vectors['boundary_recipes']}
    outcomes = sdk['outcome_summaries']
    assert len(outcomes) == len({row['case_id'] for row in outcomes}) == len(expected_ids) == 704
    assert {row['case_id'] for row in outcomes} == expected_ids
    for row in outcomes:
        assert row['node_id'] in IDS and row['kind'] in ('value', 'error')
        if row['kind'] == 'value':
            assert type(row['characters']) is int and 0 <= row['characters'] <= 1048576
            assert re.fullmatch('[0-9a-f]{64}', row['sha256_utf8_surrogatepass'])
        else:
            assert isinstance(row['type'], str) and isinstance(row['message'], str) and len(row['message']) <= 2048
    guards = sdk['guard_denials']
    assert len(guards) == len({row['id'] for row in guards}) == 7
    assert {row['id'] for row in guards} == {row['id'] for row in vectors['guard_denial_recipes']}
    assert all(row['type'] == 'ValueError' for row in guards)
    controls = sdk['negative_controls']
    assert len(controls) == len({row['control'] for row in controls}) == 6
    assert {row['control'] for row in controls} == set(vectors['wrong_controls']) and all(row['detected'] is True for row in controls)
    assert Path(sdk['sdk_io_origin']).is_relative_to(Path(profile['common_site_packages']))
    assert Path(sdk['server_origin']) == Path(profile['core_source']) / 'server.py'
    assert Path(sdk['encoder_origin']).is_relative_to(Path(spec['actual_mac_binding']['backend_source_root']))
    binding = load(SOURCE / 'inputs/SOURCE_BINDING.json')
    with zipfile.ZipFile(SOURCE / 'inputs/ORIGINAL.zip') as archive:
        pristine = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    assert len(pristine) == 43 and {n: hashlib.sha256(data).hexdigest() for n, data in pristine.items()} == binding['original_files']
    for name, digest in scope['original_files_sha256'].items():
        assert digest == binding['original_files'][name]
    trees = [attempt / kind / SNAPSHOT for kind in ('packs', 'replay-pair', 'replay-zip')]
    expected = dict(candidate)
    expected['secure-nodes.json'] = sha(trees[0] / 'v2/secure-nodes.json')
    for tree in trees:
        originals = {p.relative_to(tree).as_posix(): p.read_bytes() for p in tree.rglob('*') if p.is_file() and not p.is_relative_to(tree / 'v2')}
        assert originals == pristine and inventory(tree / 'v2') == expected
        assert all(rows[p.relative_to(received).as_posix()]['archive_mode'] == '0o644' for p in tree.rglob('*') if p.is_file())
    assert report['v2_files'] == {n: {'sha256': digest, 'git_mode': '100644'} for n, digest in expected.items()}
    normal = load(trees[0] / 'v2/secure-nodes.json')
    assert set(normal) == {'format', 'nodes', 'runtime', 'web_directory'}
    assert normal['format'] == 'comfy-secure-nodes-v1' and normal['web_directory'] == 'web'
    assert normal['runtime'] == {'python': {'requires': '>=3.13,<3.14', 'resolved': '3.13'}}
    assert set(normal['nodes']) == set(IDS)
    for node_id, node in normal['nodes'].items():
        assert node['class'] == node_id.rsplit('.', 1)[1] and node['module'] == 'nodes'
        assert node['sdk_refs'] is False and node['permissions'] == [] and not any(node['methods'].values())
        assert node['schema'] == sdk['schemas'][node_id] and [row['io_type'] for row in node['schema']['outputs']] == ['STRING']
    assert report['normal_manifest_sha256'] == expected['secure-nodes.json']
    patches = attempt / 'patches/comfy-join-prompt/x0832089'
    pair = patches / 'comfy-join-prompt-x0832089.json'
    diff, bundle = pair.with_suffix('.diff'), pair.with_suffix('.zip')
    patch = load(pair)
    assert patch['format'] == 'comfy-pack-patch/1' and patch['pack'] == 'comfy-join-prompt' and patch['key'] == 'x0832089'
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
    receipt = {'status': 'VERIFIED_RETURNED_JOIN_FULL_ORIGINAL_SDK_NORMALGEN_REPLAYS_ONLY',
               'archive_sha256': capture_record['archive_sha256'], 'result_sha256': sha(attempt / 'RESULT.json'),
               'sdk_result_sha256': sha(sdk_path), 'normal_manifest_sha256': expected['secure-nodes.json'],
               'pair_sha256': sha(pair), 'diff_sha256': sha(diff), 'bundle_sha256': sha(bundle),
               'patch_operations_verified': len(patch_rows), 'original_only_delete_operations': sum(row['op'] == 'delete' for row in patch_rows.values()),
               'outer_receipt_sha256': sha(outer_path), 'post_generation_sha256': sha(post_path),
               'reported_primary_differentials': 704, 'reported_component_crosschecks': 704,
               'reported_guard_denials': 7, 'reported_negative_controls': 6,
               'verified_equal_trees': 3, 'original_files_per_tree': 43, 'candidate_files_per_tree': 14,
               'postmap_counts': {name: len(pins) for name, pins in post.items()},
               'genuine_original_vs_component_scope_checked': True, 'all_command_and_outer_groups_absent_in_records': True,
               'wall_seconds': outer['wall_seconds'], 'observed_children_maxrss_bytes_darwin': outer['observed_children_maxrss_bytes_darwin'],
               'outer_actual_authorization': outer['authorization_message'], 'source_transport_relative': args.source_relative,
               'source_relocation_recorded_no_bytes_changed': True, 'outer_rss_watchdog_bytes': outer['rss_watchdog_bytes'],
               'hard_memory_or_cpu_quota_claimed': False, 'six_child_and_outer_group_ids': sorted(groups),
               'supplied_code_executed_during_intake': False,
               'local_generator_or_sdk_or_replay_runs': 0, 'guest_frontend_service_registry_or_general_adoption': False,
               'scope': 'Strict returned byte/metadata verification only; no independent runtime reexecution, target-engine acceptance or blanket dependency certification.'}
    (capture / 'VERIFIED_RESULT_RECEIPT.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
