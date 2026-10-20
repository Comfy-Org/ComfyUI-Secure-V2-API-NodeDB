import time

OWNER_STARTED = time.monotonic()
OWNER_DEADLINE = OWNER_STARTED + 120

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys


sys.dont_write_bytecode = True
PROCESS = None
PROCESS_HELD = False
HARD_FAILURE_FD = None
CANCELLED = None
WITNESSED = set()


def hard_stop(number, frame):
    if PROCESS_HELD:
        try:
            os.killpg(PROCESS.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        if HARD_FAILURE_FD is not None:
            os.write(HARD_FAILURE_FD, b'{"status":"FAILED_WHOLE_OWNER_DEADLINE_CLEANUP_UNCONFIRMED","pass_with_evidence":false}\n')
    finally:
        os._exit(124)


def cancel(number, frame):
    global CANCELLED
    CANCELLED = number


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def child_limits():
    signal.pthread_sigmask(signal.SIG_SETMASK, set())
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))


def exited():
    return os.waitid(os.P_PID, PROCESS.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None


def owned_rows(helper):
    rows = helper.process_rows([''])
    owned = WITNESSED | {PROCESS.pid}
    while True:
        expanded = owned | {row['pid'] for row in rows if row['ppid'] in owned or row['pgid'] == PROCESS.pid}
        if expanded == owned:
            WITNESSED.update(owned)
            return [row for row in rows if row['pid'] in owned]
        owned = expanded


def retire(helper, receipt):
    global PROCESS_HELD
    started = time.monotonic()
    cleanup_started = receipt.setdefault('cleanup_started_owner_seconds', started - OWNER_STARTED)
    end = min(OWNER_DEADLINE, OWNER_STARTED + cleanup_started + 15)
    errors, error_details = [], []
    operation = 'waitid_initial_WNOWAIT'
    try:
        leader_terminal = exited()
        operation = 'ps_owned_snapshot'
        other_owned = [row for row in owned_rows(helper) if row['pid'] != PROCESS.pid]
        receipt['cleanup_signal_decision'] = {'leader_terminal': leader_terminal,
                                               'other_owned': other_owned,
                                               'signals_required': not leader_terminal or bool(other_owned)}
        if not leader_terminal or other_owned:
            operation = 'waitid_before_TERM'
            if not exited():
                operation = 'killpg_SIGTERM'
                os.killpg(PROCESS.pid, signal.SIGTERM)
                grace = min(end, time.monotonic() + 2)
                operation = 'waitid_grace_WNOWAIT'
                while time.monotonic() < grace and not exited():
                    time.sleep(.02)
            operation = 'killpg_SIGKILL'
            os.killpg(PROCESS.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except (OSError, subprocess.SubprocessError) as error:
        errors.append(repr(error))
        error_details.append({'operation': operation, 'errno': getattr(error, 'errno', None), 'error': repr(error)})
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    try:
        try:
            operation = 'Popen_wait_reap'
            receipt['exit_code'] = PROCESS.wait(timeout=max(.001, end - time.monotonic()))
            PROCESS_HELD = False
        except (OSError, subprocess.TimeoutExpired) as error:
            errors.append(repr(error))
            error_details.append({'operation': operation, 'errno': getattr(error, 'errno', None), 'error': repr(error)})
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
    observations = []
    while time.monotonic() < end:
        try:
            operation = 'kill_pid_0_absence'
            try:
                os.kill(PROCESS.pid, 0)
                pid_absent = False
            except ProcessLookupError:
                pid_absent = True
            operation = 'ps_owned_absence'
            remaining = owned_rows(helper)
            operation = 'killpg_0_absence'
            observation = {'pid_absent': pid_absent, 'group_absent': helper.absent(PROCESS.pid), 'remaining': remaining}
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(repr(error))
            error_details.append({'operation': operation, 'errno': getattr(error, 'errno', None), 'error': repr(error)})
            break
        observations.append(observation)
        if len(observations) >= 2 and all(row['pid_absent'] and row['group_absent'] and not row['remaining'] for row in observations[-2:]):
            break
        time.sleep(.05)
    receipt['cleanup'] = {'seconds': time.monotonic() - OWNER_STARTED - cleanup_started,
                          'errors': errors, 'error_details': error_details, 'last_operation': operation,
                          'independent_observations': observations,
                          'confirmed': not PROCESS_HELD and not errors and len(observations) >= 2
                          and all(row['pid_absent'] and row['group_absent'] and not row['remaining'] for row in observations[-2:])}

def snapshots(helper, config, config_path):
    packet = Path(config['packet_root'])
    profile = json.loads((packet / 'inputs/ACTUAL_MAC_PROFILE.json').read_bytes())
    backend = json.loads((packet / 'inputs/SELECTED_BACKEND_INVENTORY.json').read_bytes())
    science = json.loads((packet / 'inputs/SCIENCE_BINDING.json').read_bytes())
    files = [Path(__file__).resolve(), config_path, Path(config['pyvenv_config'])]
    files.extend(Path(row['path']) for row in config['baseline_maps'].values())
    files.extend(Path(name) for name in config['operator_pins'])
    return {
        'INPUT': helper.inventory(packet),
        'FULL-SITE': helper.inventory(Path(profile['common_site_packages'])),
        'COMPONENT-PREFIX': helper.inventory(Path(config['component_prefix'])),
        'RUNTIME': helper.runtime_readback(profile, backend, science),
        'OPERATOR-CONFIG': {str(path): {'bytes': path.stat().st_size, 'sha256': digest(path),
                                     'mode': path.stat().st_mode & 0o777} for path in sorted(set(files))},
    }


def result_check(result_path, packet, authorization):
    spec = importlib.util.spec_from_file_location('tiny52_result_predicate', packet / 'check_result.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.check(result_path, packet, authorization)


def main():
    global PROCESS, PROCESS_HELD, HARD_FAILURE_FD
    signal.signal(signal.SIGALRM, hard_stop)
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    signal.setitimer(signal.ITIMER_REAL, max(.001, OWNER_DEADLINE - time.monotonic()))
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-message', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args()
    require(args.execute and re.fullmatch('m_[0-9a-f]+', args.authorization_message)
            and args.authorization_message not in {'m_ee64cb7e78', 'm_6abe9c56a7', 'm_8e30eda430', 'm_fa6a78b71c'}, 'Separate exact runtime release required')
    require(sys.platform == 'darwin' and sys.version_info[:3] == (3, 13, 14)
            and sys.flags.isolated and not sys.flags.no_site, 'Selected normal-site isolated Darwin interpreter required')
    require(all(hasattr(os, name) for name in ('waitid', 'WNOWAIT', 'WEXITED', 'P_PID')), 'Non-reaping child observation unavailable')
    require(digest(args.config) == args.config_sha256, 'Reviewed config bytes differ')
    config = json.loads(args.config.read_bytes())
    packet = Path(config['packet_root'])
    output = Path(config['output_root'])
    require(output.is_absolute() and not output.exists() and output.parent.resolve() == Path(config['output_parent']).resolve(), 'Fresh owned output required')
    require(not output.resolve().is_relative_to(packet.resolve()), 'Output must be outside frozen input')
    require(digest(Path(__file__).resolve()) == config['owner_sha256'], 'Reviewed owner differs')
    require(digest(packet / 'references/native-owner-346e.py') == config['reference_owner_sha256'], 'Accepted helper source differs')
    output.mkdir()
    HARD_FAILURE_FD = os.open(output / 'HARD-DEADLINE-UNCONFIRMED.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    spec = importlib.util.spec_from_file_location('accepted_native_owner_346e', packet / 'references/native-owner-346e.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    receipt = {'status': 'FAILED_SINGLE_TINY52_NATIVE_ATTEMPT_NO_RETRY', 'pass_with_evidence': False,
               'attempts': 1, 'automatic_retries': 0, 'authorization_message': args.authorization_message,
               'whole_owner_seconds_limit': 120, 'payload_seconds_limit': 90, 'cleanup_seconds_limit': 15,
               'hard_memory_or_cpu_quota_claim': False, 'rss_watchdog_bytes': 1024**3,
               'rss_watchdog_scope': 'sampled_payload_and_descendants_only_owner_excluded',
               'aggregate_rss_peak_bytes': 0, 'observed_processes': [], 'errors': [],
               'exact_owner_argv': sys.argv, 'normal_generation_runs': 0, 'Guest_launches': 0,
               'service_admission': False, 'whole_pack_acceptance': False}
    before = None
    save(output / 'STARTED.json', receipt)
    try:
        before = snapshots(helper, config, args.config)
        for name, rows in before.items():
            save(output / (name + '-BEFORE.json'), rows)
        require(before['INPUT'] == config['packet_files'] and not before['RUNTIME']['mismatches'], 'Input/runtime preflight differs')
        for key, row in config['baseline_maps'].items():
            path = Path(row['path'])
            require(digest(path) == row['sha256'] and before[key] == json.loads(path.read_bytes()), 'Full baseline differs: ' + key)
        for name, expected in config['operator_pins'].items():
            require(digest(Path(name)) == expected, 'Operator/config source differs: ' + name)
        profile = json.loads((packet / 'inputs/ACTUAL_MAC_PROFILE.json').read_bytes())
        require(Path(sys.executable).resolve() == Path(profile['python']).resolve()
                and digest(Path(config['pyvenv_config'])) == config['pyvenv_config_sha256'], 'Interpreter/config differs')
        require(not helper.process_rows([str(packet), str(output)]), 'Existing marked payload process')
        temporary = output / 'temporary'
        temporary.mkdir()
        environment = dict(PATH='/usr/bin:/bin', HOME=str(temporary), TMPDIR=str(temporary),
                           XDG_CACHE_HOME=str(temporary / 'cache'), PYTHONDONTWRITEBYTECODE='1',
                           PYTHONNOUSERSITE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                           CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                           MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', BLIS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
        argv = ['/usr/bin/sandbox-exec', '-f', str(packet / 'inputs/deny-network.sb'), profile['python'],
                '-I', '-B', str(packet / 'worker.py'), '--execute', '--authorization-message', args.authorization_message,
                '--output', str(output / 'actual-output')]
        receipt['exact_payload_argv'] = argv
        require(not CANCELLED and time.monotonic() < OWNER_DEADLINE - 15, 'Cancelled/cleanup reserve exhausted before payload creation')
        payload_start = time.monotonic()
        payload_end = min(payload_start + 90, OWNER_DEADLINE - 15)
        with (output / 'stdout.txt').open('xb') as stdout, (output / 'stderr.txt').open('xb') as stderr:
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGINT, signal.SIGTERM})
            try:
                PROCESS = subprocess.Popen(argv, cwd=packet, env=environment, stdout=stdout, stderr=stderr,
                                           start_new_session=True, preexec_fn=child_limits)
                PROCESS_HELD = True
                receipt['recorded_at_creation'] = {'pid': PROCESS.pid, 'pgid': PROCESS.pid,
                                                   'session_created_by_Popen': True, 'name': 'tiny52_pure_direct_differential'}
                save(output / 'STARTED.json', receipt)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            try:
                while True:
                    rows = owned_rows(helper)
                    peak = sum(row['rss_bytes'] for row in rows)
                    receipt['aggregate_rss_peak_bytes'] = max(receipt['aggregate_rss_peak_bytes'], peak)
                    receipt['observed_processes'].append({'owner_seconds': time.monotonic() - OWNER_STARTED, 'rows': rows})
                    require(all(row['pgid'] == PROCESS.pid for row in rows), 'Unexpected descendant session; cleanup cannot be assumed')
                    require(peak <= 1024**3, 'Aggregate observed RSS watchdog exceeded')
                    require(stdout.tell() <= 1024**2 and stderr.tell() <= 1024**2, 'Captured output bound exceeded')
                    require(not CANCELLED and time.monotonic() < payload_end, 'Payload cancellation/work deadline')
                    if exited():
                        break
                    time.sleep(.05)
            finally:
                retire(helper, receipt)
                receipt['payload_and_cleanup_seconds'] = time.monotonic() - payload_start
        require(receipt['exit_code'] == 0 and receipt['cleanup']['confirmed'], 'Payload exit/retirement differs')
        result_path = output / 'actual-output/RESULT.json'
        require(result_path.is_file() and not result_path.is_symlink() and result_path.stat().st_size <= 1024**2, 'Actual result missing/unsafe')
        receipt['payload_result_sha256'] = digest(result_path)
        receipt['payload_result'] = result_check(result_path, packet, args.authorization_message)
    except Exception as error:
        receipt['errors'].append(repr(error))
    finally:
        if PROCESS_HELD:
            try:
                retire(helper, receipt)
            except Exception as error:
                receipt['errors'].append('cleanup: ' + repr(error))
        try:
            after = snapshots(helper, config, args.config)
            for name, rows in after.items():
                save(output / (name + '-AFTER.json'), rows)
            receipt['full_maps_equal'] = before == after
            require(before is not None and before == after and not after['RUNTIME']['mismatches'], 'Complete before/after maps differ')
            receipt['remaining_marked_processes'] = helper.process_rows([str(packet), str(output)])
            require(not receipt['remaining_marked_processes'], 'Marked payload process remains')
        except Exception as error:
            receipt['errors'].append('postflight: ' + repr(error))
        receipt['cancelled_by_signal'] = CANCELLED
        receipt['whole_owner_seconds'] = time.monotonic() - OWNER_STARTED
        receipt['observed_children_maxrss_bytes_darwin'] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        receipt['pass_with_evidence'] = (not receipt['errors'] and not CANCELLED and not PROCESS_HELD
                                         and receipt.get('cleanup', {}).get('confirmed') is True
                                         and receipt.get('full_maps_equal') is True and time.monotonic() < OWNER_DEADLINE
                                         and receipt.get('payload_result', {}).get('comparisons') == 52
                                         and receipt.get('payload_result', {}).get('original_nodes') == 24
                                         and receipt.get('payload_result', {}).get('separate_comparator_controls') == 3)
        if receipt['pass_with_evidence']:
            receipt['status'] = 'PASS_ONE_PHASE_TINY52_NATIVE_OWNER_AND_SCOPED_PAYLOAD_ONLY'
        save(output / 'OWNER_RECEIPT.json', receipt)
    print(json.dumps({'status': receipt['status'], 'pass_with_evidence': receipt['pass_with_evidence'],
                      'whole_owner_seconds': receipt['whole_owner_seconds'], 'errors': receipt['errors']}))
    return 0 if receipt['pass_with_evidence'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
