import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
import zipfile


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'temp/summaries/sdk-main-rebase-20261019'
TASKS = {
    'resolution-ratio-r1': {
        'container': 'resolution-ratio-r1-input',
        'packet': 'resolution-ratio-generation-macos-r1-20261019',
        'invocation_sha256': 'ab658aa66713b1e4464318aac0ca48e506750ddab8ed25ff08d6c1ae9740c096',
        'handoff_sha256': 'c940ac0ad27e196d3c28efb4b5095bb9dfed2d350be9f43634c028b684ded83c',
        'input_table_sha256': '322adf8a2b25460c271fefd9928d0c3dadcfce4dddcae7bd7b331f103fda0c6e',
        'authorization_message': 'm_f106f35b81',
        'expected_status': 'PASS_REAL_RESOLUTION_BACKEND_SDK_NORMAL_ENCODER_AND_CANONICAL_REPLAYS_ONLY',
        'expected_commands': ['sdk_parity', 'normal_generate', 'pair_generate', 'pair_bundle', 'replay_pair', 'replay_zip'],
    },
    'joinprompt2-r2': {
        'container': 'joinprompt2-r2-input',
        'packet': 'joinprompt2-generation-macos-r2-20261019',
        'invocation_sha256': '95b732ddb1547388331790adb7fb41aaffc1a846c964f06bf0b67904f937f8a0',
        'handoff_sha256': 'ed42b44230bc46f2ed2ba98e2031f79378758907d52aaca56fe5733d18f98895',
        'input_table_sha256': '71fe278ea47d81ed75d54b01c295abc2f98382b593090f6d4f2b623df76bece7',
        'authorization_message': 'm_42a4e59d1c',
        'expected_status': 'PASS_GENUINE_JOIN_FULL_ORIGINAL_SDK_NORMALGEN_AND_REPLAYS_ONLY',
        'expected_commands': ['sdk_parity', 'normal_generate', 'pair_generate', 'pair_bundle', 'replay_pair', 'replay_zip'],
    },
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    rows = {}
    for path in sorted(directory.rglob('*')):
        assert not path.is_symlink(), path
        if path.is_file():
            rows[path.relative_to(directory).as_posix()] = {
                'bytes': path.stat().st_size, 'sha256': digest(path),
                'mode': path.stat().st_mode & 0o777,
            }
    return rows


def runtime_readback(profile, backend, science):
    result = {'sdk_files': {}, 'core_files': {}, 'dependency_files': {},
              'backend_files': {}, 'science_files': {}, 'mismatches': []}
    site = Path(profile['common_site_packages'])
    for key, directory in [('sdk_files', site), ('core_files', Path(profile['core_source']))]:
        for name, expected in profile[key].items():
            actual = digest(directory / name)
            result[key][name] = actual
            if actual != expected:
                result['mismatches'].append(str(directory / name))
    for name, data in profile['dependency_readbacks'].items():
        actual = {relative: digest(site / relative) for relative in data['verified_files']}
        result['dependency_files'][name] = actual
        if actual != data['verified_files']:
            result['mismatches'].append(name)
    for relative, row in backend['files'].items():
        actual = digest(Path(backend['backend_source_root']) / relative.removeprefix('backend/'))
        result['backend_files'][relative] = actual
        if actual != row['sha256']:
            result['mismatches'].append(relative)
    for relative, expected in science['site_file_pins'].items():
        actual = digest(site / relative)
        result['science_files'][relative] = actual
        if actual != expected:
            result['mismatches'].append(relative)
    result['python_sha256'] = digest(Path(profile['python']).resolve(strict=True))
    if result['python_sha256'] != profile['python_sha256']:
        result['mismatches'].append('python')
    return result


def absent(group):
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return True
    return False


def process_rows(markers):
    output = subprocess.check_output(
        ['/bin/ps', '-axww', '-o', 'pid=,ppid=,pgid=,rss=,command='],
        text=True, timeout=1,
    )
    result = []
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5 and any(marker in parts[4] for marker in markers):
            result.append({'pid': int(parts[0]), 'ppid': int(parts[1]),
                           'pgid': int(parts[2]), 'rss_bytes': int(parts[3]) * 1024,
                           'command': parts[4]})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('task', choices=TASKS)
    args = parser.parse_args()
    selected = TASKS[args.task]
    container = BASE / selected['container']
    packet = container / selected['packet']
    invocation_path = container / (selected['packet'] + '.INVOCATION.json')
    assert digest(invocation_path) == selected['invocation_sha256']
    assert digest(packet / 'HANDOFF.json') == selected['handoff_sha256']
    assert digest(packet / 'INPUT_SHA256SUMS') == selected['input_table_sha256']
    before = inventory(container)
    pins = {}
    for line in (packet / 'INPUT_SHA256SUMS').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        assert relative not in pins and not Path(relative).is_absolute() and '..' not in Path(relative).parts
        assert digest(packet / relative) == expected
        pins[relative] = expected
    assert set(inventory(packet)) == set(pins) | {'INPUT_SHA256SUMS', 'HANDOFF.json'}
    assert json.loads((packet / 'HANDOFF.json').read_bytes())['files'] == pins
    source = json.loads((packet / 'inputs/SOURCE_BINDING.json').read_bytes())
    assert {name: row['sha256'] for name, row in inventory(packet / 'candidate').items()} == source['candidate_files']
    original_rows = {}
    for line in (packet / 'inputs/ORIGINAL_GIT_TREE.tsv').read_text().splitlines():
        metadata, name = line.split('\t', 1)
        mode, kind, blob = metadata.split()
        assert kind == 'blob' and mode in {'100644', '100755'}
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        original_rows[name] = {'mode': mode, 'git_blob': blob}
    with zipfile.ZipFile(packet / 'inputs/ORIGINAL.zip') as archive:
        assert set(archive.namelist()) == set(original_rows) == set(source['original_files'])
        for name, row in original_rows.items():
            data = archive.read(name)
            assert hashlib.sha256(data).hexdigest() == source['original_files'][name]
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['git_blob']
    profile = json.loads((packet / 'inputs/ACTUAL_MAC_PROFILE.json').read_bytes())
    backend = json.loads((packet / 'inputs/mac-readback/OVERLAY-SOURCE-INVENTORY.json').read_bytes())
    science = json.loads((packet / 'inputs/SCIENCE_BINDING.json').read_bytes())
    runtime_before = runtime_readback(profile, backend, science)
    assert not runtime_before['mismatches']
    invocation = json.loads(invocation_path.read_bytes())
    original_argv = invocation['argv_if_released']
    argv = [str(packet / 'run_generation.py') if value == str(BASE / selected['packet'] / 'run_generation.py')
            else selected['authorization_message'] if value == 'ROOT_SEQUENCE_MAIL_PENDING'
            else value for value in original_argv]
    scratch = Path(argv[argv.index('--scratch') + 1])
    outer = BASE / (args.task + '-attempt1-outer')
    assert scratch.is_absolute() and scratch.parent == BASE and not scratch.exists() and not outer.exists()
    assert argv[0] == profile['python'] and argv[4] == str(packet / 'run_generation.py')
    markers = [str(packet), str(scratch)]
    assert not process_rows(markers)
    outer.mkdir()

    def save(name, value):
        (outer / name).write_text(json.dumps(value, indent=2) + '\n')

    save('INPUT-BEFORE.json', before)
    save('RUNTIME-BEFORE.json', runtime_before)
    save('SOURCE-INTAKE-READBACK.json', {
        'sealed_payload_files': len(pins), 'total_container_files': len(before),
        'pristine_git_files': original_rows, 'candidate_files': source['candidate_files'],
        'handoff_sha256': selected['handoff_sha256'], 'input_table_sha256': selected['input_table_sha256'],
    })
    save('EXPANDED-INVOCATION.json', {
        'original_argv': original_argv, 'argv': argv,
        'only_substitutions': {'transport_packet_root': str(packet),
                               'authorization_message': selected['authorization_message']},
        'invocation_sha256': selected['invocation_sha256'],
    })
    receipt = {
        'task': args.task, 'attempts': 1, 'automatic_retries': 0,
        'authorization_message': selected['authorization_message'],
        'started_utc': datetime.now(timezone.utc).isoformat(), 'exact_argv': argv,
        'cwd': str(packet), 'scratch': str(scratch), 'work_seconds': 55,
        'cleanup_deadline_seconds': 58, 'outer_watchdog_seconds': 60,
        'rss_watchdog_bytes': 1024**3, 'hard_memory_quota_enforced': False,
        'hard_cpu_core_quota_enforced': False, 'observed_processes': [],
        'monitor_error': None, 'outer_watchdog_fired': False, 'rss_watchdog_fired': False,
    }
    save('STARTED.json', receipt)
    state_path = ROOT / 'temp/in_progress/sdk-main-rebase-20261019/FOLLOWUP-QUEUE.json'
    state = json.loads(state_path.read_bytes())
    assert state['active_jobs'] == 0
    state.update(active_jobs=1, active_job=args.task + '-attempt1', runtime_queue_status='one_bounded_local_job_running')
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    process = None
    groups = set()
    started = time.monotonic()
    with (outer / 'stdout.txt').open('xb') as stdout, (outer / 'stderr.txt').open('xb') as stderr:
        try:
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
            try:
                process = subprocess.Popen(
                    ['/usr/bin/time', '-l', '-o', str(outer / 'time-resources.txt')] + argv,
                    cwd=packet, stdout=stdout, stderr=stderr, start_new_session=True,
                )
                groups.add(process.pid)
                receipt['outer_pid_and_pgid'] = process.pid
                save('STARTED.json', receipt)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            while process.poll() is None:
                rows = process_rows(markers)
                for row in rows:
                    if row not in receipt['observed_processes']:
                        receipt['observed_processes'].append(row)
                    groups.add(row['pgid'])
                receipt['outer_watchdog_fired'] = time.monotonic() - started >= 60
                receipt['rss_watchdog_fired'] = any(row['rss_bytes'] > 1024**3 for row in rows)
                if receipt['outer_watchdog_fired'] or receipt['rss_watchdog_fired']:
                    break
                assert stdout.tell() < 1024**2 and stderr.tell() < 1024**2
                time.sleep(.1)
        except BaseException as error:
            receipt['monitor_error'] = repr(error)
        finally:
            if process is not None:
                for row in process_rows(markers):
                    groups.add(row['pgid'])
                if process.poll() is None:
                    for group in groups:
                        if not absent(group):
                            os.killpg(group, signal.SIGKILL)
                receipt['exit_code'] = process.wait(timeout=3)
    result_path = scratch / 'RESULT.json'
    supervisor = json.loads(result_path.read_bytes()) if result_path.is_file() else {}
    receipt['supervisor_status'] = supervisor.get('status')
    receipt['supervisor_error'] = supervisor.get('error')
    receipt['worker_cleanup_rows'] = [row.get('cleanup', {}) for row in supervisor.get('commands', [])]
    recorded = {row['name']: row['pid'] for row in supervisor.get('commands', []) if 'pid' in row}
    groups.update(recorded.values())
    receipt['worker_groups_recorded_at_creation'] = recorded
    receipt['all_observed_and_recorded_groups_absent'] = {str(group): absent(group) for group in sorted(groups)}
    receipt['exact_owned_processes_remaining'] = process_rows(markers)
    after = inventory(container)
    runtime_after = runtime_readback(profile, backend, science)
    save('INPUT-AFTER.json', after)
    save('RUNTIME-AFTER.json', runtime_after)
    receipt.update(
        finished_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic() - started,
        observed_children_maxrss_bytes_darwin=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        inputs_unchanged=before == after,
        sdk_core_dependency_backend_python_unchanged=runtime_before == runtime_after and not runtime_after['mismatches'],
    )
    receipt['pass_with_evidence'] = (
        receipt.get('exit_code') == 0 and not receipt['monitor_error']
        and not receipt['outer_watchdog_fired'] and not receipt['rss_watchdog_fired']
        and supervisor.get('status') == selected['expected_status']
        and list(recorded) == selected['expected_commands']
        and all(row.get('confirmed') for row in receipt['worker_cleanup_rows'])
        and all(receipt['all_observed_and_recorded_groups_absent'].values())
        and not receipt['exact_owned_processes_remaining']
        and receipt['inputs_unchanged'] and receipt['sdk_core_dependency_backend_python_unchanged']
    )
    save('OUTER_RECEIPT.json', receipt)
    state.update(active_jobs=0, runtime_queue_status='selected_local_attempt_terminal')
    state.pop('active_job', None)
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in [
        'task', 'pass_with_evidence', 'supervisor_status', 'supervisor_error', 'wall_seconds',
        'inputs_unchanged', 'sdk_core_dependency_backend_python_unchanged',
        'worker_groups_recorded_at_creation', 'all_observed_and_recorded_groups_absent',
    ]}, indent=2))
    return 0 if receipt['pass_with_evidence'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
