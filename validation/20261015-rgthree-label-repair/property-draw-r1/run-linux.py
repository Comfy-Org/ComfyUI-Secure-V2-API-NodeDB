"""Finite isolated actual property/drawing diagnostic; no install or live-service access."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence' / 'run2'
IMAGE = 'sha256:e48accf76d58011cc86b1d88a6ff96d1c48597d13a2148bf931a6a9ce9e578e6'
OWNER = {'cloud2.owner': 'MERVYN', 'cloud2.role': 'rgthree-label-draw-test-r1'}
NODE = Path('<NODE_ROOT>')
DEPS = Path('<CACHED_DEPENDENCIES>')
LIB = Path('<NODE_LIBATOMIC>')

def main():
    OUT.mkdir(exist_ok=False)
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    if available < 4 << 30:
        raise RuntimeError('Actual MemAvailable below4GiB test/admission reserve')
    bindings = {}
    for directory in ('baseline',):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file(): bindings[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    bindings['property-draw-linux.mjs'] = hashlib.sha256((ROOT / 'property-draw-linux.mjs').read_bytes()).hexdigest()
    command = ['docker', 'create', '--pull=never', '--name', 'mervyn-rgthree-label-draw-test-r1']
    for key, value in OWNER.items(): command += ['--label', key + '=' + value]
    command += ['--memory', '805306368', '--memory-swap', '805306368', '--cpus', '1', '--pids-limit', '64', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '1000:1000', '--log-driver', 'none', '--tmpfs', '/tmp:rw,nosuid,nodev,size=16777216', '--env', 'LD_LIBRARY_PATH=/node-libraries']
    workspace = ROOT.parents[4]
    corpus_constants = workspace / 'corpus/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/web/comfyui/constants.js'
    mounts = [(ROOT, str(ROOT), True), (OUT, str(OUT), False), (NODE, '/node', True), (LIB, '/node-libraries/libatomic.so.1', True)]
    for source in [ROOT.parent / 'test-dependencies', ROOT.parent / 'integration-r1/frontend', ROOT.parent / 'integration-r1/handoff-r2/label-acceptance-workflow.json', corpus_constants]:
        if not source.exists(): raise FileNotFoundError(source)
        mounts.append((source, str(source), True))
    for source, target, readonly in mounts:
        command += ['--mount', f'type=bind,src={source},dst={target}' + (',readonly' if readonly else '')]
    command += [IMAGE, '/node/bin/node', '--max-old-space-size=512', '--experimental-vm-modules', str(ROOT / 'property-draw-linux.mjs')]
    (OUT / 'PLAN.json').write_text(json.dumps({'create_argv': command, 'source_sha256': bindings, 'MemAvailable': available, 'limits': {'wall_seconds': 90, 'container_mib': 768, 'node_heap_mib': 512, 'cpus': 1, 'network': 'none', 'install': False}}, indent=2) + '\n')
    cid = subprocess.check_output(command, text=True).strip()
    info = json.loads(subprocess.check_output(['docker', 'inspect', cid]))[0]
    if info['Id'] != cid or any(info['Config']['Labels'].get(k) != v for k, v in OWNER.items()):
        raise RuntimeError('Exact owned container binding mismatch; start refused')
    started = time.monotonic()
    receipt = {'container_id': cid, 'status': 'NOT_STARTED'}
    try:
        with (OUT / 'stdout.txt').open('wb') as stdout, (OUT / 'stderr.txt').open('wb') as stderr:
            result = subprocess.run(['docker', 'start', '--attach', cid], stdout=stdout, stderr=stderr, timeout=90)
        state = json.loads(subprocess.check_output(['docker', 'inspect', cid]))[0]['State']
        receipt.update(status='PASS' if result.returncode == 0 and state['ExitCode'] == 0 and not state['OOMKilled'] else 'FAIL', exit_code=state['ExitCode'], oom=state['OOMKilled'])
    except subprocess.TimeoutExpired:
        receipt.update(status='TIMEOUT', exit_code=124)
    finally:
        current = json.loads(subprocess.check_output(['docker', 'inspect', cid]))[0]
        if current['Id'] != cid or any(current['Config']['Labels'].get(k) != v for k, v in OWNER.items()):
            raise RuntimeError('Ownership changed; cleanup refused')
        if current['State']['Running']:
            subprocess.run(['docker', 'kill', cid], check=True, stdout=subprocess.DEVNULL)
        receipt['wall_seconds'] = time.monotonic() - started
        (OUT / 'TERMINAL.json').write_text(json.dumps(receipt, indent=2) + '\n')
        subprocess.run(['docker', 'rm', cid], check=True, stdout=subprocess.DEVNULL)
    print(json.dumps(receipt))
    print((OUT / 'stdout.txt').read_text())
    if receipt['status'] != 'PASS':
        print((OUT / 'stderr.txt').read_text())
        raise SystemExit(1)

if __name__ == '__main__': main()
