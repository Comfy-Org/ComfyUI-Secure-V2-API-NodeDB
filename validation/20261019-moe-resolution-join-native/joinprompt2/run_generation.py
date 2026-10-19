"""Prepared one serial genuine Core/original/SDK and normal-generation job."""
import argparse
import json
from pathlib import Path
import resource
import signal
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--input-manifest-sha256', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--authorization-message', required=True)
    args = parser.parse_args()
    if not args.execute:
        print('SOURCE_ONLY_UNRUN; explicit Root Join sequencing required')
        return 2
    s.require(args.authorization_message not in {'ROOT_SEQUENCE_MAIL_PENDING', 'm_39c60259eb', 'm_f92ff47ea7', 'm_014c3874f7', 'm_2c6904a2d3', 'm_53c64c8643', 'm_68445dee27'}, 'Source preparation/other-pack/service hold is not a Join run release')
    report = {'status': 'PRECHECK_FAILED', 'commands': [], 'actual_sdk_attempts': 0,
              'normal_generation_attempts': 0, 'root_execution_mail': args.authorization_message,
              'hard_memory_cap_bytes': None, 'cpu_quota': None, 'managed_runtime_claim': False,
              'guest_or_frontend_or_service_or_registry_acceptance': False}
    scratch, code = None, 1
    signal.signal(signal.SIGTERM, s.stop)
    signal.signal(signal.SIGALRM, s.stop)
    signal.setitimer(signal.ITIMER_REAL, max(.001, s.DEADLINE - time.monotonic()))
    try:
        s.packet(args.input_manifest_sha256)
        spec = json.loads((s.ROOT / 'JOB_SPEC.json').read_bytes())
        actual = json.loads((s.ROOT / 'inputs/ACTUAL_MAC_PROFILE.json').read_bytes())
        science = json.loads((s.ROOT / 'inputs/SCIENCE_BINDING.json').read_bytes())
        python, site, core = s.verify_runtime(actual, science)
        backend, tools = s.verify_backend(argparse.Namespace(backend_root=Path(spec['actual_mac_binding']['backend_source_root']), backend_commit=spec['actual_mac_binding']['overlay_commit']), spec)
        binding = json.loads((s.ROOT / 'inputs/SOURCE_BINDING.json').read_bytes())
        candidate = s.inventory(s.ROOT / 'candidate')
        s.require({name: row['sha256'] for name, row in candidate.items()} == binding['candidate_files'] and len(candidate) == 14, 'Frozen candidate14 differs')
        s.require(args.scratch.is_absolute() and not args.scratch.exists() and not args.scratch.is_symlink(), 'Fresh absolute scratch required')
        scratch = args.scratch.parent.resolve(strict=True) / args.scratch.name
        s.require(not scratch.is_relative_to(s.ROOT) and not s.ROOT.is_relative_to(scratch), 'Scratch overlaps sealed packet')
        scratch.mkdir(mode=0o700)
        (scratch / 'temporary').mkdir(mode=0o700)
        (scratch / 'headless').mkdir(mode=0o700)
        relative = Path(spec['slug']) / ('x' + spec['commit'][:7])
        snapshot = scratch / 'packs' / relative
        pack = snapshot / spec['folder']
        s.original(pack)
        pristine = s.inventory(pack)
        s.require({name: row['sha256'] for name, row in pristine.items()} == binding['original_files'], 'Original43 Git source differs')
        v2 = pack / 'v2'
        v2.mkdir(mode=0o700)
        for name in candidate:
            target = v2 / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(s.file_at(s.ROOT / 'candidate', name).read_bytes())
            target.chmod(0o644)
        cmd = ['/usr/bin/sandbox-exec', '-f', s.ROOT / 'inputs/deny-network.sb', python, '-I', '-S', '-B']
        result_path = scratch / 'ACTUAL_SDK_RESULT.json'
        report['actual_sdk_attempts'] = 1
        s.run(cmd + [s.ROOT / 'actual_sdk_driver.py', '--backend', backend, '--site', site, '--core', core,
                     '--original', pack, '--candidate', v2, '--vectors', s.ROOT / 'inputs/BACKEND_VECTORS.json',
                     '--scratch', scratch / 'headless', '--output', result_path], scratch, 'sdk_parity', report)
        s.require(result_path.is_file() and result_path.stat().st_size <= 512 * 1024, 'SDK result absent/oversized')
        sdk = json.loads(result_path.read_bytes())
        s.require(sdk['status'] == 'PASS_GENUINE_FULL_ORIGINAL_AND_REAL_SELECTED_SDK_COMPONENTS_ONLY'
                  and sdk['execution_comparisons'] == sdk['component_crosschecks'] == 704
                  and sdk['full_original_entrypoint_imported'] and sdk['real_server_constructor']
                  and not sdk['synthetic_server_or_sdk'] and not sdk['server_setup_or_listeners_started'], 'Genuine original/SDK coverage incomplete')
        s.require(len(sdk['guard_denials']) == 7 and len(sdk['negative_controls']) == 6
                  and all(row['detected'] for row in sdk['negative_controls']) and all(sdk['cleanup'].values()), 'Guard/control/cleanup coverage incomplete')
        s.require(s.inventory(v2) == candidate, 'Actual SDK stage changed frozen candidate')
        report['normal_generation_attempts'] = 1
        s.run(cmd + [s.ROOT / 'invoke_manifest.py', '--backend', backend, '--site', site, '--core', core,
                     '--v2', v2, '--generator', s.ROOT / 'generate_popular_pack_manifest.py'], scratch, 'normal_generate', report)
        (v2 / 'secure-nodes.json').chmod(0o644)
        normal = json.loads((v2 / 'secure-nodes.json').read_bytes())
        s.require(set(normal['nodes']) == set(sdk['schemas']) and normal['web_directory'] == 'web', 'Actual node/frontend declaration differs')
        for node_id, schema in sdk['schemas'].items():
            node = normal['nodes'][node_id]
            s.require(node['schema'] == schema and node['sdk_refs'] is False and node['permissions'] == []
                      and not any(node['methods'].values()), 'Actual schema/authority mismatch')
        s.require(normal['runtime'] == {'python': {'requires': '>=3.13,<3.14', 'resolved': '3.13'}}, 'Runtime declaration mismatch')
        expected = s.inventory(v2)
        s.require(set(expected) == set(candidate), 'Generated candidate file set differs')
        for name, row in candidate.items():
            if name != 'secure-nodes.json':
                s.require(expected[name] == {'sha256': row['sha256'], 'git_mode': '100644'}, 'Normal encoder changed code/source: ' + name)
        s.require({n: r for n, r in s.inventory(pack).items() if not n.startswith('v2/')} == pristine, 'Original changed')
        patches = scratch / 'patches' / relative
        pair = patches / (spec['slug'] + '-x' + spec['commit'][:7])
        tool = backend / 'comfy_secure_nodes/packpatch.py'
        s.run(cmd + [tool, 'generate', snapshot, patches], scratch, 'pair_generate', report)
        s.run(cmd + [tool, 'bundle', pair, pair.with_suffix('.zip')], scratch, 'pair_bundle', report)
        for kind, action, artifact in (('pair', 'apply', pair), ('zip', 'apply-zip', pair.with_suffix('.zip'))):
            replay = scratch / ('replay-' + kind) / relative
            replay_pack = replay / spec['folder']
            s.original(replay_pack)
            s.run(cmd + [tool, action, replay, artifact], scratch, 'replay_' + kind, report)
            s.require(s.inventory(replay_pack / 'v2') == expected, 'Replay bytes/Git modes differ: ' + kind)
            s.require({n: r for n, r in s.inventory(replay_pack).items() if not n.startswith('v2/')} == pristine, 'Replay original changed')
        post = {}
        for key, root, pins in (('sdk', site, actual['sdk_files']), ('core', core, actual['core_files']),
                                ('science', site, science['site_file_pins']), ('candidate', s.ROOT / 'candidate', binding['candidate_files']),
                                ('backend', backend, {n: row['sha256'] for n, row in tools.items()})):
            observed = {name: s.sha(s.file_at(root, name)) for name in pins}
            s.require(observed == pins, 'Post-attempt selected inputs differ: ' + key)
            post[key] = observed
        post_path = scratch / 'POST_GENERATION_READBACK.json'
        post_path.write_text(json.dumps(post, indent=2) + '\n')
        report.update(status='PASS_GENUINE_JOIN_FULL_ORIGINAL_SDK_NORMALGEN_AND_REPLAYS_ONLY',
                      actual_sdk_result_sha256=s.sha(result_path), normal_manifest_sha256=s.sha(v2 / 'secure-nodes.json'),
                      v2_files=expected, artifact_files=s.inventory(patches), post_generation_readback_sha256=s.sha(post_path))
        code = 0
    except BaseException as error:
        report.update(status='FAILED_ACTUAL_ATTEMPT' if report['actual_sdk_attempts'] else 'PRECHECK_FAILED',
                      error_type=type(error).__name__, error=str(error)[:1024])
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if any(not row.get('cleanup', {}).get('confirmed', False) for row in report['commands']):
            report['status'], code = 'FAILED_OWNED_GROUP_CLEANUP', 1
        report['elapsed_seconds'] = round(time.monotonic() - s.STARTED, 6)
        if sys.platform == 'darwin':
            report['observed_children_maxrss_bytes_darwin'] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if scratch is not None:
            (scratch / 'RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'scratch': str(scratch) if scratch else None, 'error': report.get('error')}))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
