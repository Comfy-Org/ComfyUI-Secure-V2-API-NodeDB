from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path('/Users/ben/popbot/workspaces/comfyui-frontend/comfyui-frontend-1')
CAPTURE = Path('/Users/ben/pip-giriss-r3-binding-20261026-r1/capture1')


def main():
    selection = json.loads((CAPTURE / 'SELECTION-AND-CAPACITY.json').read_bytes())
    assert selection['status'] == 'PASS_GIRISS_R3_PREFLIGHT_READY_FOR_ONE_EXACT_ATTEMPT'
    owner = next(value for value in selection['actual_outer_argv'] if value.endswith('.py'))
    output = Path(selection['actual_output_root'])
    report = {'observer_pid': os.getpid(), 'observer_pgid': os.getpgid(0),
        'started_utc': datetime.now(timezone.utc).isoformat(), 'owner_live_rows': {},
        'observer_live_identity': {'pid': os.getpid(), 'pgid': os.getpgid(0), 'uid': os.getuid(), 'sid': os.getsid(0)},
        'controller_pid': None, 'controller_and_descendant_live_rows': {}, 'errors': [], 'live_identities': {},
        'scope': 'Passive ps readback only, no signals, payload import or supervisor; not an exhaustive transient-child census.'}
    path = CAPTURE / 'INDEPENDENT-LIVE-WITNESSES.json'
    deadline = time.monotonic() + 140
    while time.monotonic() < deadline:
        changed = False
        try:
            raw = subprocess.check_output(['/bin/ps', '-axww', '-o', 'pid=,ppid=,pgid=,rss=,command='], text=True, timeout=2)
            rows = []
            for line in raw.splitlines():
                fields = line.split(None, 4)
                if len(fields) == 5:
                    rows.append({'pid': int(fields[0]), 'ppid': int(fields[1]), 'pgid': int(fields[2]),
                        'rss_bytes': int(fields[3]) * 1024, 'command': fields[4]})
            for row in rows:
                if owner in row['command'] and row['pid'] != os.getpid() and str(row['pid']) not in report['owner_live_rows']:
                    report['owner_live_rows'][str(row['pid'])] = {**row, 'observed_utc': datetime.now(timezone.utc).isoformat()}
                    changed = True
            started = output / 'STARTED.json'
            if started.is_file() and not started.is_symlink() and started.stat().st_size <= 1024**2:
                try:
                    pid = json.loads(started.read_bytes()).get('controller_pid_and_pgid')
                    if pid is not None and report['controller_pid'] is None:
                        report['controller_pid'] = pid
                        changed = True
                except json.JSONDecodeError:
                    pass
            controller = report['controller_pid']
            accepted = {controller} if controller is not None else set()
            while accepted:
                found = {row['pid'] for row in rows if row['ppid'] in accepted or row['pgid'] == controller}
                if found <= accepted:
                    break
                accepted.update(found)
            for row in rows:
                if row['pid'] in accepted and str(row['pid']) not in report['controller_and_descendant_live_rows']:
                    report['controller_and_descendant_live_rows'][str(row['pid'])] = {**row, 'observed_utc': datetime.now(timezone.utc).isoformat()}
                    changed = True
            targets = {int(pid) for pid in report['owner_live_rows']} | accepted
            for pid in targets:
                if str(pid) in report['live_identities']:
                    continue
                identity = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'pid=,ppid=,pgid=,uid=,lstart=,command='], capture_output=True, text=True, timeout=1)
                if identity.returncode == 1 and not identity.stdout.strip():
                    continue
                fields = identity.stdout.strip().split(None, 9)
                if identity.returncode or len(fields) != 10 or int(fields[0]) != pid:
                    raise RuntimeError('Incomplete passive identity readback for PID ' + str(pid))
                try:
                    sid = os.getsid(pid)
                except ProcessLookupError:
                    continue
                report['live_identities'][str(pid)] = {'pid': pid, 'ppid': int(fields[1]), 'pgid': int(fields[2]), 'uid': int(fields[3]), 'started': ' '.join(fields[4:9]), 'command': fields[9], 'sid': sid, 'observed_utc': datetime.now(timezone.utc).isoformat()}
                changed = True
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            report['errors'].append({'operation': 'passive_ps_readback', 'errno': getattr(error, 'errno', None), 'error': repr(error)})
            changed = True
        if changed or not path.exists():
            path.write_text(json.dumps(report, indent=2) + '\n')
        if (output / 'OUTER_RECEIPT.json').is_file() or (CAPTURE / 'TERMINAL.json').is_file():
            report['stop_reason'] = 'Owner or external terminal receipt exists'
            break
        time.sleep(.025)
    else:
        report['stop_reason'] = 'Passive observer140second bound'
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'owner_live_rows': len(report['owner_live_rows']), 'controller_pid': report['controller_pid'],
        'payload_live_identities': len(report['controller_and_descendant_live_rows']), 'errors': report['errors'], 'stop_reason': report['stop_reason']}))


if __name__ == '__main__':
    main()
