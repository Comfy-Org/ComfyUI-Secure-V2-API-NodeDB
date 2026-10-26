import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess


def process_identity(pid):
    result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'pid=,ppid=,pgid=,uid=,lstart=,command='],
                            capture_output=True, text=True, timeout=1)
    if result.returncode == 1 and not result.stdout.strip():
        return None
    if result.returncode:
        raise RuntimeError('Process identity readback failed')
    parts = result.stdout.strip().split(None, 9)
    if len(parts) != 10 or int(parts[0]) != pid:
        raise RuntimeError('Incomplete process identity readback')
    return {'pid': pid, 'ppid': int(parts[1]), 'pgid': int(parts[2]), 'uid': int(parts[3]),
            'started': ' '.join(parts[4:9]), 'command': parts[9], 'sid': os.getsid(pid)}


def pid_absent(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def group_absent(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


class GuestJournal:
    def __init__(self, output, evidence, temporary, controller_pid, python, source):
        self.output = Path(output).resolve()
        self.evidence = Path(evidence).resolve()
        self.temporary = Path(temporary).resolve()
        self.controller = controller_pid
        self.python = python
        self.source = source
        self.protected = {os.getpid(), os.getpgrp(), controller_pid}
        self.events = []
        self.births = {}
        self.witnesses = {}
        self.errors = []
        self.retirement = []
        self.signaled = set()
        self.file_identity = None
        self.last_raw = b''
        self.raw_snapshots = []

    def error(self, message):
        if message not in self.errors:
            self.errors.append(message)

    def read(self, final=False):
        path = self.output / 'GUEST_CREATION.jsonl'
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            if final:
                self.error('No durable creation journal was retained; no exhaustive creation/absence claim')
            return
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise RuntimeError('Creation journal is not an owned regular file')
            identity = (metadata.st_dev, metadata.st_ino)
            if self.file_identity not in (None, identity):
                self.error('Creation journal identity changed')
            self.file_identity = identity
            raw = bytearray()
            while len(raw) <= 1024**2:
                block = os.read(descriptor, min(65536, 1024**2 + 1 - len(raw)))
                if not block:
                    break
                raw.extend(block)
            raw = bytes(raw)
        finally:
            os.close(descriptor)
        if not raw.startswith(self.last_raw):
            self.error('Creation journal was truncated or rewritten')
            for body in [self.last_raw, raw]:
                signature = hashlib.sha256(body).hexdigest()
                if signature in self.raw_snapshots:
                    continue
                if len(self.raw_snapshots) >= 4:
                    self.error('Raw rewrite snapshot limit reached')
                    break
                snapshot = self.evidence / ('CREATION-JOURNAL-' + signature + '.raw')
                with snapshot.open('xb') as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                self.raw_snapshots.append(signature)
        capture = self.evidence / 'CREATION-JOURNAL-LAST-READ.raw'
        with capture.open('wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.last_raw = raw
        if len(raw) > 1024**2:
            self.error('Creation journal exceeds the one-MiB bound; raw bounded prefix retained')
        lines = raw.splitlines(keepends=True)
        if len(lines) > 64:
            self.error('Creation journal exceeds 64 records')
        events = []
        for index, line in enumerate(lines[:64], 1):
            if not line.endswith(b'\n'):
                if final:
                    self.error('Partial trailing creation record at line ' + str(index))
                continue
            try:
                if len(line) > 65536:
                    raise RuntimeError('Creation record exceeds 64 KiB')
                row = json.loads(line)
                if (type(row) is not dict or type(row.get('event')) is not str
                        or type(row.get('observer_parent_pid')) is not int
                        or row['observer_parent_pid'] != self.controller):
                    raise RuntimeError('Record does not belong to the directly owned controller')
                if row.get('event') not in {'observer-installed', 'Guest-launch-intent-not-yet-creation',
                                            'Pinned-Popen-constructor-return-or-unwind'}:
                    raise RuntimeError('Unknown creation journal event')
                events.append(row)
            except (KeyError, TypeError, ValueError, RuntimeError) as error:
                self.error('Line ' + str(index) + ': ' + str(error))
        self.events = events
        intents = [row for row in events if row['event'] == 'Guest-launch-intent-not-yet-creation']
        for row in events:
            if row['event'] != 'Pinned-Popen-constructor-return-or-unwind':
                continue
            self.accept_birth(row, intents)

    def accept_birth(self, row, intents):
        pid = row.get('assigned_child_pid')
        if pid is None:
            return
        try:
            if type(pid) is not int or pid <= 1 or pid in self.protected:
                raise RuntimeError('Protected/invalid PID cannot be a Guest target')
            if row.get('constructor_source') != self.source or row.get('start_new_session') is not True:
                raise RuntimeError('Birth source or session ownership differs')
            if row.get('source_session_group_candidate') != pid or row.get('observed_pgid') not in (None, pid):
                raise RuntimeError('Observed group and source candidate must remain distinct and valid')
            argv = row['argv']
            if len(argv) != 6 or argv[:2] != ['/usr/bin/sandbox-exec', '-f'] or argv[3:] != [self.python, '-m', 'comfy_secure_nodes.guest']:
                raise RuntimeError('Guest argv differs from the pinned canonical launch')
            if pid in self.births and self.births[pid] != row:
                raise RuntimeError('Conflicting birth records for one PID')
            self.births[pid] = row
            if len(self.births) > 1:
                self.error('More than one Guest birth is outside this finite plan')
            matches = [launch for launch in intents if launch.get('argv') == argv]
            if len(matches) != 1:
                raise RuntimeError('Birth has no unique matching intent')
            launch = matches[0]
            environment = launch['environment']
            policy = Path(argv[2]).resolve()
            if not policy.is_relative_to(self.temporary) and not policy.is_relative_to(self.output / 'work'):
                raise RuntimeError('Guest profile is outside exact owned writable roots')
            saved = Path(launch['saved_profile'])
            if saved.parent.resolve() != self.output or saved.is_symlink() or not saved.is_file():
                raise RuntimeError('Saved Guest profile is not in the owned output')
            if hashlib.sha256(saved.read_bytes()).hexdigest() != launch['profile_sha256']:
                raise RuntimeError('Saved Guest profile hash differs')
            if not Path(environment['COMFY_GUEST_SOCKET']).resolve().is_relative_to(self.temporary):
                raise RuntimeError('Guest socket is outside the exact short temporary root')
            if Path(environment['TMPDIR']).resolve() != policy.parent:
                raise RuntimeError('Guest temporary/profile directories differ')
            if Path(environment['VIRTUAL_ENV']).resolve() != Path(self.python).parent.parent.resolve():
                raise RuntimeError('Guest venv differs from the selected interpreter')
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            self.error('Birth ' + str(pid) + ': ' + str(error))

    def capture_witnesses(self):
        for pid, birth in self.births.items():
            if pid in self.witnesses:
                continue
            try:
                identity = process_identity(pid)
                if identity is None:
                    continue
                if identity['ppid'] != self.controller or identity['uid'] != os.getuid():
                    raise RuntimeError('No live direct-parent ownership witness; orphan is unconfirmed')
                if identity['pgid'] != pid or identity['sid'] != pid:
                    raise RuntimeError('Guest is not the independently observed session/group leader')
                if 'comfy_secure_nodes.guest' not in identity['command']:
                    raise RuntimeError('Guest command does not match the recorded intent')
                self.witnesses[pid] = identity
            except ProcessLookupError:
                continue
            except (OSError, RuntimeError) as error:
                self.error('PID witness ' + str(pid) + ': ' + str(error))

    def retire(self, final=False):
        for pid, birth in self.births.items():
            row = {'pid': pid, 'observed_pgid': birth.get('observed_pgid'),
                   'source_session_group_candidate': birth['source_session_group_candidate'], 'signaled': False}
            try:
                if not pid_absent(pid) and pid not in self.signaled:
                    previous = self.witnesses.get(pid)
                    current = process_identity(pid)
                    keys = ['pid', 'uid', 'pgid', 'sid', 'started']
                    if previous is None or current is None or any(previous[key] != current[key] for key in keys):
                        raise RuntimeError('Unwitnessed or changed identity is not signaled')
                    if current['ppid'] not in {self.controller, 1} or 'comfy_secure_nodes.guest' not in current['command']:
                        raise RuntimeError('Guest lineage/command changed; target is not signaled')
                    if pid in self.protected or current['pgid'] in self.protected:
                        raise RuntimeError('Protected owner/controller target is not signaled')
                    os.killpg(current['pgid'], signal.SIGKILL)
                    self.signaled.add(pid)
                    row['signaled'] = True
                row['pid_absent'] = pid_absent(pid)
                row['candidate_group_absent'] = group_absent(birth['source_session_group_candidate'])
            except ProcessLookupError:
                row.update(pid_absent=pid_absent(pid), candidate_group_absent=group_absent(pid))
            except (OSError, RuntimeError) as error:
                row['error'] = str(error)
                self.error('Guest retirement ' + str(pid) + ': ' + str(error))
            if final and (not row.get('pid_absent') or not row.get('candidate_group_absent')):
                self.error('Recorded Guest still present or absence is unconfirmed: ' + str(pid))
            self.retirement.append(row)

    def snapshot(self):
        return {'events': self.events, 'valid_births': list(self.births.values()),
                'ownership_witnesses': self.witnesses, 'errors': self.errors, 'retirement': self.retirement,
                'raw_bytes': len(self.last_raw), 'raw_sha256': hashlib.sha256(self.last_raw).hexdigest(),
                'rewrite_snapshots': self.raw_snapshots,
                'limits': 'Uncatchable kill before durable observation and unwitnessed or reused identities remain unconfirmed. POSIX identity checks are not an atomic kernel process handle.'}
