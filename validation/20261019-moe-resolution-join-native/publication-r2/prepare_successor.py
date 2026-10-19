"""Documentation successor; stdlib-only canonical file operations, no pack imports."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parent.parent
R1 = HERE.with_name('resolution-join-native-publication-r1-20261019')
STAGE = HERE / 'stage'
PROOF = Path('corpus/validation/20261019-moe-resolution-join-native')
TOOL_SHA = '268df53fa640b4eb42ee342850e686790016ad15a207cf6a5a7e57ee5d5953a2'
TOOL_BLOB = '170cd00c3cb0b2e8bd23d06dcfef711191503df9'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')

def hashes(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}

def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        assert not p.is_symlink()
        if p.is_file():
            result[p.relative_to(root).as_posix()] = {'sha256': sha(p), 'mode': stat.S_IMODE(p.stat().st_mode)}
    return result

def materialize(source, target, pins):
    for name, digest in pins.items():
        p = source / name
        assert sha(p) == digest
        out = target / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(p.read_bytes())
        out.chmod(0o644)

configs = [
    dict(key='resolution', snapshot='comfyui_resolution-and-ratio/x58769e5/ComfyUI_Resolution-and-Ratio-HEAD',
         capture='resolution-ratio-result-intake-r1-20261019', attempt='resolution-ratio-generation-macos-r1-attempt1',
         job='resolution-ratio-generation-macos-r1-20261019', count=12,
         normal='047b4a54cb22b673ab2f2a910045c9b935969d5d9a53d7f046124dbe808e0f5e'),
    dict(key='joinprompt2', snapshot='comfy-join-prompt/x0832089/comfy-join-prompt-HEAD',
         capture='joinprompt2-result-intake-r1-20261019', attempt='joinprompt2-generation-macos-r2-attempt1',
         job='joinprompt2-generation-macos-r2-20261019', count=14,
         normal='fdaced83feb6523a1e4d0903313c3a8f716022bbbf786478172a5d16f0f6ce94')]

def correct_report(text, c):
    old = '> Nodes: all '
    assert old in text
    start = text.index(old)
    end = text.index('\n\n', start)
    text = text[:start] + (
        '> Native backend differential and genuine normal-manifest evidence was verified on 2026-10-19.\n'
        '> The older conversion suites below are historical and unrefreshed; they are not claimed to pass\n'
        '> unchanged on the current SDK. Frontend, Guest/public executor and service acceptance remain open.\n'
        '> Not accepted: no whole-pack certificate.'
    ) + text[end:]
    assert '## Verification results\n' in text
    caveat = (
        '## Current native evidence (2026-10-19)\n\n'
        'The actual selected Mac attempt used Python 3.13.14, installed SDK 0.42.0/API141, '
        'Core `44564d0279c275eef52b11750a9d76349f4e7a88` and backend '
        '`59bd3e1acba6520bb32717ad03833f6ab2967ecc`. '
    )
    if c['key'] == 'resolution':
        caveat += (
            'The unchanged original and candidate completed 1033 output and 1033 validator comparisons, '
            '33 bound/type guard denials and 3 detected comparator controls. '
        )
    else:
        caveat += (
            'The genuine full original package and candidate completed 704 value/error comparisons '
            'plus 704 unchanged-component crosschecks, 7 resource guard denials and 6 detected comparator controls. '
        )
    caveat += (
        'Genuine normal encoding, canonical pair/bundle generation and both pristine-tree replays passed. '
        'Exact returned evidence and missing-purpose qualification are published separately under '
        f'`validation/20261019-moe-resolution-join-native/{c["key"]}`. '
        'This proves the recorded native backend and artifact subset; it does not exercise the current '
        'frontend, isolated Guest/Core public executor or shared service.\n\n'
        'This publication successor changes only this report and regenerates its canonical patch artifacts '
        'with byte/mode checks. Runtime code, the genuine normal manifest and prior native evidence remain '
        'byte-identical; the native scientific tests were not rerun for these prose changes.\n\n'
        '## Historical verification results (unrefreshed)\n\n'
        'All test counts, paths and environment hashes in this section describe older observations. '
        'The retained Python test builds its expected manifest by hand and includes '
        '`frontend_permissions: []`; the current genuine encoder omits that empty field. '
    )
    if c['key'] == 'resolution':
        caveat += 'Its handwritten builder also omits the current node `validation_inputs` signature. '
    caveat += (
        'Consequently these historical tests are not represented as currently passing unchanged. '
        'The genuine SDK differential and normal-generation evidence above stands separately; '
        'it does not refresh this whole historical suite.\n'
    )
    text = text.replace('## Verification results\n', caveat, 1)
    text = text.replace('## Release integrity\n', '## Current manifest and historical release integrity\n\n'
                        f'- Current genuine normal manifest SHA-256: `{c["normal"]}`.\n'
                        '- Other stub/runtime hashes below are retained historical environment identifiers, not current pins.\n', 1)
    if c['key'] == 'joinprompt2':
        assert text.count('29fce6f7fdaf711ef8f6174fc48cea55a8bd5360b89fda3c92c6837396ea8a69') == 1
        text = text.replace('- Manifest SHA-256: `29fce6f7fdaf711ef8f6174fc48cea55a8bd5360b89fda3c92c6837396ea8a69`.',
                            '- Historical handwritten manifest SHA-256 (superseded): `29fce6f7fdaf711ef8f6174fc48cea55a8bd5360b89fda3c92c6837396ea8a69`.')
        text = text.replace('Frozen/current canonical', 'Historical canonical')
        text = text.replace('Final report/artifact refresh is repeated before handoff; coordinator reviews actual logs, not this declaration alone.',
                            'Those historical logs are retained as provenance; this successor does not claim that suite was refreshed.')
    else:
        text = text.replace('Backend and frontend behavior gates pass under the generalized renderer fix described below.',
                            'Historical backend and frontend observations under the older generalized renderer fix are described below; current frontend acceptance is open.')
        text = text.replace('The production bridge exercises these paths,', 'The historical production bridge fixture exercised these paths,')
        text = text.replace('After the coordinator\'s generalized renderer fix, the expanded production bridge passes.',
                            'After the coordinator\'s older generalized renderer fix, the historical expanded production bridge fixture passed.')
        text = text.replace('Final command uses the same explicit core/bytecode settings above, omitting `-k`, and runs all 53 tests against the frozen dependency below.',
                            'The historical final command used the same explicit core/bytecode settings above, omitting `-k`, for the 53-test suite and older dependency below; it has not been refreshed here.')
        text = text.replace('then run the final-byte gate twice.',
                            'then verify byte/mode reconstruction. The older behavior gate is unrefreshed in this documentation successor.')
        text = text.replace('## Resolved generalized runtime dependency', '## Historical generalized runtime dependency')
    return text

def main():
    assert sys.platform == 'linux', 'Genuine POSIX scratch required'
    assert not STAGE.exists(), 'Never modify an existing successor stage'
    r1_expected = load(R1 / 'HANDOFF.json')['files']
    assert hashes(R1 / 'stage') == r1_expected
    r1_table_sha = sha(R1 / 'STAGE_SHA256SUMS')
    tool_source = Path('/mnt/c/Users/benjc/popbot/sent_files/packpatch.py')
    data = tool_source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == TOOL_SHA
    assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == TOOL_BLOB
    shutil.copytree(R1 / 'stage', STAGE)
    correction = STAGE / PROOF / 'publication-r2'
    correction.mkdir()
    (correction / 'packpatch.py').write_bytes(data)
    write(correction / 'PACKPATCH_SOURCE.json', dict(sha256=TOOL_SHA, bytes=len(data), git_blob=TOOL_BLOB,
          git_mode='100644', selected_native_commit='59bd3e1acba6520bb32717ad03833f6ab2967ecc',
          source_mail='m_e55e32b592', scope='Only stdlib imports and file generation/apply CLI; no SDK, pack imports, network or service operations.'))
    shutil.copyfile(R1 / 'HANDOFF.json', correction / 'PRIOR_R1_HANDOFF.json')
    commands = []
    results = []
    scratch = Path(tempfile.mkdtemp(prefix='moe-publication-r2-'))
    assert scratch.parent == Path('/tmp') and not scratch.is_symlink()
    started = time.monotonic()
    try:
        tool = scratch / 'packpatch.py'
        tool.write_bytes(data)
        tool.chmod(0o644)
        def run(key, action, args):
            argv = [sys.executable, '-I', '-S', '-B', str(tool), action] + [str(a) for a in args]
            before = time.monotonic()
            p = subprocess.run(argv, capture_output=True, timeout=15, cwd=scratch,
                               env={'PATH':'/usr/bin:/bin', 'HOME':str(scratch), 'LC_ALL':'C.UTF-8', 'TMPDIR':str(scratch)})
            log = f'{key}-{action}.log'
            (correction / log).write_bytes(p.stdout + p.stderr)
            commands.append(dict(pack=key, action=action, argv=argv, exit_code=p.returncode,
                                 elapsed_seconds=round(time.monotonic()-before, 6), log=log))
            assert p.returncode == 0, p.stderr.decode(errors='replace')
        for c in configs:
            rel = Path(c['snapshot'])
            slug, release, folder = rel.parts
            binding = load(WORK / 'coordination' / c['job'] / 'inputs/SOURCE_BINDING.json')
            source = WORK / 'coordination' / c['capture'] / 'received' / c['attempt'] / 'packs' / rel
            candidate = STAGE / 'corpus/packs' / rel / 'v2'
            assert sha(candidate / 'secure-nodes.json') == c['normal']
            report = candidate / 'SECURE_CONVERSION.md'
            report.write_text(correct_report(report.read_text(), c))
            original = binding['original_files']
            expected_hashes = hashes(candidate)
            assert len(expected_hashes) == c['count']
            generated = scratch / 'generated' / slug / release
            pack = generated / folder
            materialize(source, pack, original)
            materialize(candidate, pack / 'v2', expected_hashes)
            original_map = {n:dict(sha256=d, mode=0o644) for n,d in original.items()}
            expected_map = {n:dict(sha256=d, mode=0o644) for n,d in expected_hashes.items()}
            assert inventory(pack / 'v2') == expected_map
            out = scratch / 'patches' / slug / release
            pair = out / (slug + '-' + release)
            run(c['key'], 'generate', [generated, out])
            run(c['key'], 'bundle', [pair, pair.with_suffix('.zip')])
            for kind, action, artifact in [('pair','apply',pair), ('zip','apply-zip',pair.with_suffix('.zip'))]:
                snapshot = scratch / ('replay-' + kind) / slug / release
                materialize(source, snapshot / folder, original)
                run(c['key'], action, [snapshot, artifact])
                assert inventory(snapshot / folder / 'v2') == expected_map
                assert {n:r for n,r in inventory(snapshot / folder).items() if not n.startswith('v2/')} == original_map
            assert {n:r for n,r in inventory(pack).items() if not n.startswith('v2/')} == original_map
            patchdir = STAGE / 'corpus/patches' / slug / release
            prior = correction / c['key'] / 'actual-native-artifacts'
            prior.mkdir(parents=True)
            artifact_hashes = {}
            for suffix in ('.json', '.diff', '.zip'):
                target = patchdir / (pair.name + suffix)
                shutil.copyfile(target, prior / target.name)
                shutil.copyfile(pair.with_suffix(suffix), target)
                artifact_hashes[suffix] = sha(target)
            proof = STAGE / PROOF / c['key'] / 'QUALIFICATION.json'
            q = load(proof)
            q['actual_native_pair_sha256'] = q['pair_sha256']
            q['actual_native_diff_sha256'] = q['diff_sha256']
            q['actual_native_bundle_sha256'] = q['bundle_sha256']
            q.update(pair_sha256=artifact_hashes['.json'], diff_sha256=artifact_hashes['.diff'], bundle_sha256=artifact_hashes['.zip'])
            q['historical_note'] = 'Historical manual-manifest tests remain unchanged and unrefreshed. They include frontend_permissions:[] omitted by the genuine encoder; Resolution additionally omits validation_inputs. Do not claim they pass unchanged. Actual native SDK/normalgen results stand separately.'
            q['staged_production_changes'] = 'Versus sealed R1: only SECURE_CONVERSION.md prose changed, plus matching canonical pair/diff/bundle regenerated locally. Runtime, genuine normal manifest and all prior scientific evidence remain exact. Actual native artifacts retained under publication-r2.'
            q['publication_file_only_replay'] = 'Current pair and ZIP each reconstruct the complete candidate byte/mode-exactly on independent pristine trees, with original sources unchanged. Local WSL Python3.12 stdlib canonical tool operations; no native SDK/scientific rerun or frontend/Guest/service acceptance.'
            write(proof, q)
            results.append(dict(pack_id=slug+'/'+release, normal_manifest_sha256=c['normal'],
                                report_sha256=sha(report), artifacts=artifact_hashes,
                                original_files=len(original), candidate_files=len(expected_hashes),
                                expected_v2=expected_map, independent_replays=2, original_sources_unchanged=True))
    finally:
        # Exactly the fresh owned POSIX directory; never operate recursively on a computed workspace path.
        assert scratch.parent == Path('/tmp') and scratch.name.startswith('moe-publication-r2-') and not scratch.is_symlink()
        shutil.rmtree(scratch)
    assert not scratch.exists()
    assert hashes(R1 / 'stage') == r1_expected and sha(R1 / 'STAGE_SHA256SUMS') == r1_table_sha
    summary_path = STAGE / PROOF / 'SUMMARY.json'
    summary = load(summary_path)
    summary.update(status='TWO_EXISTING_PACK_NATIVE_QUALIFICATION_WITH_DOCUMENTATION_SUCCESSOR',
                   publication_correction_requests=['m_79448d4b50','m_345d9030ba'],
                   production_source_or_notes_edited=True,
                   canonical_artifacts_are_exact_actual_returns=False,
                   current_artifacts='Regenerated with unchanged selected canonical tool for two prose corrections only. Prior exact native artifacts retained under publication-r2.',
                   current_changes_from_r1=dict(production_notes=2, runtime_files=0, normal_manifests=0, canonical_artifacts=6),
                   local_sdk_generator_or_replay_calls=0,
                   local_file_only_canonical_tool_calls=8,
                   scientific_or_broad_runtime_reruns=0)
    write(summary_path, summary)
    stage_now = hashes(STAGE)
    changed = sorted(n for n,d in r1_expected.items() if stage_now[n] != d)
    assert len(changed) == 11, changed
    for n in changed:
        assert n.endswith('/SECURE_CONVERSION.md') or n.startswith('corpus/patches/') or n.endswith('/QUALIFICATION.json') or n.endswith('/SUMMARY.json')
    evidence = dict(status='PASS_DOCUMENTATION_ONLY_CANONICAL_REBUILD_AND_TWO_REPLAYS_PER_PACK',
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    python_version=sys.version, executable=sys.executable, platform=sys.platform,
                    scope='Local WSL Python3.12 stdlib file operations, no pack/SDK imports, no scientific test rerun, no service or admission actions.',
                    canonical_tool_sha256=TOOL_SHA, commands=commands, packs=results,
                    scratch_path=str(scratch), scratch_removed_and_confirmed_absent=True,
                    synchronous_children_reaped=True, subprocess_timeout_seconds=15,
                    hard_memory_or_cpu_quota_enforced=False,
                    elapsed_seconds=round(time.monotonic()-started,6), r1_files_preserved=True,
                    changed_prior_stage_files=changed, prior_runtime_normal_manifest_and_native_evidence_preserved=True)
    write(correction / 'FILE_ONLY_REBUILD_RECEIPT.json', evidence)
    shutil.copyfile(HERE / 'prepare_successor.py', correction / 'prepare_successor.py')
    files = hashes(STAGE)
    (HERE / 'STAGE_SHA256SUMS').write_text(''.join(f'{d}  {n}\n' for n,d in files.items()))
    archive_path = HERE.with_suffix('.CORPUS.zip')
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            info = zipfile.ZipInfo(name, (2026,10,19,0,0,0))
            info.create_system, info.external_attr, info.compress_type = 3, 0o100644 << 16, zipfile.ZIP_DEFLATED
            archive.writestr(info, (STAGE / name).read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert {i.filename:hashlib.sha256(archive.read(i)).hexdigest() for i in archive.infolist()} == files
        assert all((i.external_attr >> 16) == 0o100644 for i in archive.infolist())
    handoff = dict(status='PUBLICATION_R2_PROSE_CORRECTED_ARTIFACT_REPLAYS_VERIFIED_FOR_ROOT_REVIEW',
                   supersedes_publication_r1=True, prior_r1_handoff_sha256=sha(R1 / 'HANDOFF.json'),
                   requests=['m_79448d4b50','m_345d9030ba'],
                   corpus_zip_sha256=sha(archive_path), corpus_zip_bytes=archive_path.stat().st_size,
                   regular_files=len(files), all_archive_modes='100644',
                   files=files, stage_table_sha256=sha(HERE / 'STAGE_SHA256SUMS'),
                   production_changes_from_r1='Two SECURE_CONVERSION.md reports only; six matching canonical artifacts regenerated. Runtime and genuine normal manifest bytes unchanged.',
                   prior_native_evidence_unchanged=True, prior_native_artifacts_retained=True,
                   scientific_reruns=0, local_file_only_commands=8,
                   file_only_receipt_sha256=sha(correction / 'FILE_ONLY_REBUILD_RECEIPT.json'),
                   new_pack_identities=0, whole_pack_accepted=False,
                   frontend_guest_public_executor_service_acceptance=False,
                   canonical_corpus_github_service_registry_or_admission_writes=0,
                   packs=results)
    write(HERE / 'HANDOFF.json', handoff)
    ledger_path = WORK / 'coordination/MOE_NEXT_ACTION.json'
    ledger = load(ledger_path)
    ledger.update(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  status='PUBLICATION_R2_READY_NATIVE_PROOF_PRESERVED_FRONTEND_GUEST_SERVICE_OPEN',
                  next_action='Root reviews R2 prose and matching artifacts, preserving existing identities. Continue source-only Guest/public executor design under shared-service read-only hold.')
    ledger['resolution_join_native_publication_r2'] = dict(handoff=str((HERE/'HANDOFF.json').relative_to(WORK)),
           sha256=sha(HERE/'HANDOFF.json'), corpus_zip_sha256=sha(archive_path), files=len(files), whole_pack_accepted=False)
    write(ledger_path, ledger)
    print(json.dumps({k:handoff[k] for k in ('status','corpus_zip_sha256','corpus_zip_bytes','regular_files','file_only_receipt_sha256')},indent=2))
    print('HANDOFF_SHA256='+sha(HERE/'HANDOFF.json'))

if __name__ == '__main__':
    main()
