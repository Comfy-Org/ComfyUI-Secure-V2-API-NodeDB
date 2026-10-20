"""Strict shared-owner Join diagnostic data intake; no returned code execution."""
import argparse
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[2]
SOURCE = WORK / 'coordination/joinprompt2-public-guest-payload-source-r6-20261019'
OWNER = WORK.parent / 'chat_f38536805264/coordination/review-shared-http-join-owner-20261019-r2/source'
AUTH = 'm_f78c41f7ce'
CONFIG_SHA = '8b475f52d55997ea6ef912e24f20e440e58c71100d5ae2f56c9c7e16a146a893'
CONFIG = WORK / 'coordination/joinprompt2-cleanup-r6-final-review-20261019/join_core_guest-R6-CONFIG.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())

def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--run-relative', required=True)
    parser.add_argument('--source-relative', required=True)
    args = parser.parse_args()
    capture = args.capture.resolve(strict=True)
    root = (capture / 'received').resolve(strict=True)
    run = (root / args.run_relative).resolve(strict=True)
    returned = (root / args.source_relative).resolve(strict=True)
    assert run.is_relative_to(root) and returned.is_relative_to(root)
    assert not (capture / 'VERIFIED_RESULT_RECEIPT.json').exists()
    captured = load(capture / 'CAPTURE_RECEIPT.json')
    assert sha(capture / 'MIKE_RESULT.zip') == captured['archive_sha256']
    manifest = load(root / 'MANIFEST.json')
    declared = {r['path']: r for r in manifest['files']}
    assert len(declared) == len(manifest['files']) and set(declared) == set(inventory(root)) - {'MANIFEST.json'}
    for name, row in declared.items():
        path = root / name
        assert row['bytes'] == path.stat().st_size and row['sha256'] == sha(path)
    assert sha(CONFIG) == CONFIG_SHA
    config = load(CONFIG)
    retained_files = [p for p in (root / 'retained-source').rglob('*') if p.is_file()]
    assert any(sha(p) == CONFIG_SHA for p in retained_files), 'Exact frozen R6 config missing'
    assert any(sha(p) == 'feb968e494962d4886b95ece9d33608cf26a0ec36b628952fdeeb4665057c79a' for p in retained_files), 'Reviewed shared source archive missing'
    assert inventory(returned) == inventory(SOURCE) and len(inventory(returned)) == 40
    assert sha(returned / 'HANDOFF.json') == '99236795e669696bbbab8db7d097a0ae66e61c8d74037783ed73beb49bd772c8'
    assert {name: r['sha256'] for name, r in config['input_files'].items()} == inventory(returned)
    captured_rows = {r['path']: r for r in captured['files']}
    for name, row in config['input_files'].items():
        relative = (returned / name).relative_to(root).as_posix()
        assert row['bytes'] == (returned / name).stat().st_size
        assert captured_rows[relative]['archive_mode'] == oct(row['mode']) == '0o644'
    for key, row in config['operator_sources'].items():
        source = root / 'operator-scripts' / Path(row['path']).name
        assert sha(source) == row['sha256']
    outer_path = run / 'OUTER_RECEIPT.json'
    outer = load(outer_path)
    assert outer['authorization_message'] == AUTH and outer['config_sha256'] == CONFIG_SHA
    assert outer['attempts'] == 1 and outer['automatic_retries'] == 0
    assert outer['limits'] == config['limits'] == dict(work_seconds=180, cleanup_seconds=15, outer_seconds=200)
    maps = []
    for stem in ('INPUT', 'RUNTIME', 'COMPONENT-PREFIX', 'FULL-SITE', 'BINDINGS', 'OPERATOR-SOURCES'):
        before, after = run / (stem + '-BEFORE.json'), run / (stem + '-AFTER.json')
        if stem == 'INPUT':
            # The reviewed owner compares hash/size/mode dictionaries, not JSON formatting.
            assert load(before) == load(after) == config['input_files']
        else:
            assert before.read_bytes() == after.read_bytes()
        maps.append(dict(name=stem, before_sha256=sha(before), after_sha256=sha(after),
                         before_after_bytes_equal=before.read_bytes() == after.read_bytes(),
                         before_after_JSON_equal=load(before) == load(after)))
    assert load(run / 'INPUT-BEFORE.json') == config['input_files']
    assert len(load(run / 'FULL-SITE-BEFORE.json')) == 84917
    assert len(load(run / 'COMPONENT-PREFIX-BEFORE.json')) == 96
    assert sha(run / 'FULL-SITE-BEFORE.json') == config['baseline_site_map']['sha256']
    assert sha(run / 'COMPONENT-PREFIX-BEFORE.json') == config['baseline_component_map']['sha256']
    assert not load(run / 'RUNTIME-BEFORE.json')['mismatches']
    assert outer['pyvenv_cfg_sha256_before'] == outer['pyvenv_cfg_sha256_after'] == config['interpreter_configuration']['sha256']
    assert outer['stdlib_sha256_before'] == outer['stdlib_sha256_after'] == config['subprocess_source']['sha256']
    assert outer['whole_owner_deadline_includes_preflight_and_postflight'] is True
    assert outer['hard_memory_or_CPU_quota'] is False
    assert outer['trusted_controller_outside_outer_Seatbelt'] and outer['required_Guest_Seatbelt']
    assert outer['environment']['COMFY_SECURE_SANDBOX_MODE'] == 'required'
    assert outer['environment']['COMFY_SECURE_SANDBOX_BACKEND'] == 'seatbelt'
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        assert outer['environment'][name] == '1'
    assert outer['argv'][1:3] == ['-I', '-B']
    assert outer['argv'][3] == config['operator_sources']['worker']['path']
    assert outer['argv'][4] == config['payload']['path']
    for key in ('inputs_unchanged', 'runtime_unchanged', 'site_unchanged', 'component_prefix_unchanged', 'config_unchanged',
                'observer_binding_unchanged', 'binding_files_unchanged', 'operator_sources_unchanged'):
        assert outer[key] is True
    assert outer['controller_group_absent'] and not outer['remaining_owned_processes'] and not outer['remaining_socket_paths']
    journal = outer['creation_journal']
    assert not journal['errors'] and not journal['rewrite_snapshots']
    assert not outer['cleanup_errors'] and not outer['monitor_errors']
    receipt = dict(archive_sha256=captured['archive_sha256'], manifest_pins_verified=len(declared),
                   outer_receipt_sha256=sha(outer_path), actual_outer_status=outer['status'],
                   authority=AUTH, config_sha256=CONFIG_SHA, maps=maps,
                   shared_owner_archive_sha256='feb968e494962d4886b95ece9d33608cf26a0ec36b628952fdeeb4665057c79a',
                   frozen_40_file_layout_verified=True, supplied_code_imported_or_executed=False,
                   Guest_or_native_reexecutions=0, accepted_delta=0,
                   pre_fsync_parent_kill_gap_closed=False,
                   scope='Selected Core/ordinary Seatbelt Guest diagnostic only; no managed/service/frontend/admission or whole-pack acceptance.')
    if outer['status'] != 'PASS_SHARED_OWNER_AND_SCOPED_PAYLOAD_ONLY':
        receipt.update(status='VERIFIED_FAILED_JOIN_DIAGNOSTIC_EVIDENCE_ONLY_NO_RETRY',
                       actual_exit_code=outer.get('exit_code'), actual_payload_status=outer.get('payload_status'),
                       actual_errors=outer.get('payload_error'), behavioral_acceptance=False)
        (capture / 'VERIFIED_RESULT_RECEIPT.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        print(json.dumps(receipt, indent=2))
        return
    assert outer['exit_code'] == 0 and outer['payload_coverage_confirmed'] is True
    assert outer['execution_wall_seconds'] < 200 and outer['payload_and_cleanup_wall_seconds'] < 195
    assert 0 < outer['aggregate_rss_peak_bytes'] <= 1024**3
    assert not outer['whole_owner_deadline_fired'] and not outer['watchdog_fired'] and not outer['pending_control_signals']
    out = run / 'actual-output'
    payload, boundary = load(out / 'RESULT.json'), load(out / 'BOUNDARY_RESULT.json')
    assert payload['status'] == outer['payload_status'] == 'PASS_JOIN_CORE_AUTOGROW_AND_ORDINARY_GUEST_PAYLOAD_ONLY'
    assert payload['authorization_message'] == AUTH and payload['attempts'] == 1 and payload['automatic_retries'] == 0
    assert payload['whole_pack_or_managed_or_frontend_or_service_accepted'] is False
    assert payload['boundary_result_sha256'] == sha(out / 'BOUNDARY_RESULT.json')
    assert payload['native_bound_cases'] == 9 and payload['core_original_order_diagnostics'] == 1
    assert payload['actual_guest_dispatches'] == 10 and payload['wrong_STRING_controls_detected'] == 1
    assert boundary['status'] == 'PASS_CORE_FINALIZATION_AND_ORDINARY_CONFINED_GUEST_ONLY'
    assert len(boundary['comparisons']) == len(boundary['dispatches']) == 10
    assert boundary['local_call_count'] == 0 and not boundary['cleanup_errors'] and boundary['normal_path_guest_group_absent'] is True
    assert boundary['wrong_controls'] == [dict(name='corrupted-actual-STRING', detected=True)]
    fixtures = load(SOURCE / 'inputs/BOUND_FIXTURES.json')['fixtures']
    assert len(fixtures) == 9
    for row, bound in zip(boundary['comparisons'][:9], fixtures, strict=True):
        assert row['name'] == bound['name'] and row['node'] == bound['node_id']
        expected = (dict(kind='error', **bound['expected_native_error']) if bound['expected_native_error']
                    else dict(kind='value', text=bound['expected_text']))
        assert row['original'] == row['guest'] == expected
    last = boundary['comparisons'][-1]
    assert last['name'] == 'actual-core-out-of-order-autogrow' and last['original'] == last['guest']
    assert last['guest'] == dict(kind='value', text='zero|first|second')
    assert all(row['capabilities'] == [] for row in boundary['dispatches'])
    startup = boundary['verified_actual_startup']
    guest = startup['pid']
    controller = outer['controller_pid_and_pgid']
    assert startup['status'] == 'ACTUAL_GUEST_STARTUP_AND_PROFILE_OBSERVED' and startup['sandbox_kind'] == 'seatbelt'
    assert startup['actual_profile_matches_genuine_supported_source_recipe'] is True
    assert startup['resolved_runtime']['spec']['pack_id'] == 'development/host'
    assert boundary['startup']['pid'] == boundary['startup']['pgid'] == guest and boundary['startup']['managed_runtime'] is False
    assert not ({'/', '/Users/ben', '/Users/ben/popbot/workspaces', '/private/tmp'} & set(startup['ordered_read_roots_source_bound']))
    assert len(journal['valid_births']) == 1
    raw = (out / 'GUEST_CREATION.jsonl').read_bytes()
    assert raw == (run / 'CREATION-JOURNAL-LAST-READ.raw').read_bytes() and raw.endswith(b'\n')
    assert hashlib.sha256(raw).hexdigest() == journal['raw_sha256'] and len(raw) == journal['raw_bytes']
    events = [json.loads(line) for line in raw.splitlines()]
    assert events == journal['events'] and len(events) == 3
    installed, launch, birth = events
    assert installed['parent_pid'] == controller
    assert birth['assigned_child_pid'] == birth['observed_pgid'] == birth['source_session_group_candidate'] == guest
    assert birth['start_new_session'] is True and birth['argv'] == launch['argv']
    assert birth['constructor_source'] == dict(config['subprocess_source'], qualified_callable='subprocess.Popen.__init__')
    assert launch['argv'][:2] == ['/usr/bin/sandbox-exec', '-f']
    assert launch['argv'][-2:] == ['-m', 'comfy_secure_nodes.guest']
    assert sha(out / 'GUEST_PROFILE_0.sb') == launch['profile_sha256']
    witness = journal['ownership_witnesses'][str(guest)]
    assert witness['pid'] == witness['pgid'] == witness['sid'] == guest and witness['ppid'] == controller
    assert journal['retirement'] and all(r['pid'] == guest and r['pid_absent'] and r['candidate_group_absent'] and not r.get('error') for r in journal['retirement'])
    profile = (out / 'GUEST_PROFILE_0.sb').read_text()
    assert '(deny default)' in profile and profile.count('(allow network-outbound ') == 1
    assert '(allow network-outbound (literal ' + json.dumps(launch['environment']['COMFY_GUEST_SOCKET']) + '))' in profile
    assert outer['pre_fsync_kill_gap_closed'] is False
    constructor = payload['actual_stdlib_constructor_verification']
    assert constructor['compiled_code_equal_to_actual'] is True and constructor['first_line'] == 817
    assert constructor['path'] == config['subprocess_source']['path']
    assert constructor['sha256'] == config['subprocess_source']['sha256']
    for read_root in startup['ordered_read_roots_source_bound']:
        assert '(subpath ' + json.dumps(read_root) + ')' in profile
    independent_path = run / 'INDEPENDENT-POSTFLIGHT-READBACK.json'
    independent = load(independent_path)
    assert independent['independent_groups_absent'] == {str(controller): True, str(guest): True}
    assert independent['independent_ps_owned_rows'] == []
    assert set(independent['full_maps']) == {r['name'] for r in maps}
    for stem, row in independent['full_maps'].items():
        assert row['equal'] is True
        assert row['before_sha256'] == sha(run / (stem + '-BEFORE.json'))
        assert row['after_sha256'] == sha(run / (stem + '-AFTER.json'))
        assert load(run / (stem + '-BEFORE.json')) == load(run / (stem + '-AFTER.json'))
    assert independent['interpreter_config_sha256'] == config['interpreter_configuration']['sha256']
    assert independent['frozen_config_sha256'] == CONFIG_SHA
    assert independent['runtime_attempts'] == 1 and independent['automatic_retries'] == 0
    assert independent['overall_qualification_status'] == outer['status']
    assert independent['hard_memory_or_CPU_quota'] is False
    assert independent['aggregate_rss_peak_bytes'] == outer['aggregate_rss_peak_bytes']
    receipt.update(status='VERIFIED_JOIN_CORE_BOUNDARY_AND_ORDINARY_SEATBELT_GUEST_ONLY',
                   correction_revision='R6_METADATA_R5_SYNC_SHUTDOWN',
                   independent_postflight_sha256=sha(independent_path),
                   selected_corrective_attempts=1, historical_R4_remains_failed=True,
                   behavioral_acceptance_scope='These ten Core/Guest diagnostic cases only',
                   actual_Guest_dispatches=10, local_fallback_count=0,
                   actual_Guest_profile_sha256=sha(out / 'GUEST_PROFILE_0.sb'),
                   raw_journal_sha256=journal['raw_sha256'],
                   whole_owner_seconds=outer['execution_wall_seconds'],
                   payload_cleanup_seconds=outer['payload_and_cleanup_wall_seconds'],
                   no_hard_quota_claim=True,
                   independent_controller_and_Guest_groups_absent=True,
                   payload_result_sha256=sha(out / 'RESULT.json'), boundary_result_sha256=sha(out / 'BOUNDARY_RESULT.json'),
                   actual_comparisons=10, actual_Guest_creations=1, Guest_pid=guest, controller_pid=controller,
                   wrong_STRING_controls=1, exact_nine_native_bound_outcomes_verified=True,
                   aggregate_RSS_peak_bytes=outer['aggregate_rss_peak_bytes'],
                   all_reported_groups_and_socket_paths_absent=True, whole_pack_or_service_accepted=False)
    (capture / 'VERIFIED_RESULT_RECEIPT.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
