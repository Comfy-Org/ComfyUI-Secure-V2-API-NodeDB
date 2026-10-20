"""Prepare a Join report/evidence successor using Git objects and file-only replay."""
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

WORK = Path(__file__).resolve().parents[1]
COORD = WORK / 'coordination'
HERE = COORD / 'join-core-guest-source-publication-r1-20261020'
STAGE = HERE / 'stage/corpus'
GIT = '/mnt/c/Program Files/Git/cmd/git.exe'
REPO = 'C:/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/corpus'
BASE = 'c717653e421b2f42c55f0a5d908aefa7ede1a856'
PACK_ID = 'comfy-join-prompt/x0832089'
PACK = 'packs/' + PACK_ID + '/comfy-join-prompt-HEAD/'
PATCH = 'patches/' + PACK_ID + '/comfy-join-prompt-x0832089'
PROOF = 'validation/20261020-moe-join-core-guest-r6/'
TOOL_SHA = '268df53fa640b4eb42ee342850e686790016ad15a207cf6a5a7e57ee5d5953a2'
TOOL_PATH = 'validation/20261019-moe-resolution-join-native/publication-r2/packpatch.py'
R6 = COORD / 'joinprompt2-boundary-result-intake-r6-20261019'
ACTUAL = R6 / 'received/join_core_guest-r6-owner-r2-attempt1'
R4 = COORD / 'joinprompt2-boundary-result-intake-r1-20261019'
FAILED = R4 / 'received/join_core_guest-owner-r2-attempt1'
sha = lambda data: hashlib.sha256(data).hexdigest()
digest = lambda path: sha(path.read_bytes())
load = lambda path: json.loads(path.read_bytes())
encoded = lambda value: (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()

def git(*args, data=None):
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0')
    return subprocess.check_output([GIT, '--no-optional-locks', '-C', REPO, *args], input=data, stderr=subprocess.PIPE, timeout=30, env=env)

def write(relative, data):
    target = STAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists(), str(target)
    target.write_bytes(data if isinstance(data, bytes) else encoded(data))
    return target

def file_copy(relative, source, expected=None):
    data = source.read_bytes()
    if expected is not None:
        assert sha(data) == expected, str(source)
    return write(PROOF + relative, data)

def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        assert not p.is_symlink()
        if p.is_file():
            result[p.relative_to(root).as_posix()] = {'sha256': digest(p), 'mode': stat.S_IMODE(p.stat().st_mode)}
    return result

def materialize(records, root):
    for name, row in records.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(row['data'])
        target.chmod(int(row['mode'], 8) & 0o777)

def report_update(text):
    old = '> **STATUS: IN PROGRESS — UNVERIFIED.**'
    assert text.count(old) == 1
    text = text.replace(old, '> **STATUS: IN PROGRESS — PARTIAL VERIFICATION.**', 1)
    old = '> unchanged on the current SDK. Frontend, Guest/public executor and service acceptance remain open.'
    new = ('> unchanged on the current SDK. Ten selected Core/ordinary required-Seatbelt Guest cases now pass.\n'
           '> Current frontend, managed-runtime admission and service acceptance remain open.')
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
    old = 'This proves the recorded native backend and artifact subset; it does not exercise the current frontend, isolated Guest/Core public executor or shared service.'
    new = ('That native run proves the recorded backend and artifact subset. The separate Core/Guest evidence below '
           'does not refresh the native suite or exercise the current frontend or shared service.')
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
    section = '''## Current Core boundary and ordinary Guest evidence (2026-10-19)

The separately selected corrective revision 6 attempt passed ten comparisons between the genuine full original package and the unchanged candidate through real Core input finalization and ordinary Guest execution. Nine cases bind the retained native fixtures; a tenth supplies out-of-order `texts.text_2`, `texts.text_0`, `texts.text_1` inputs and observes Core's `zero|first|second` result. All ten actual Core-created plans dispatched through the genuine Guest session with zero local fallbacks. A corrupted actual STRING result was rejected by the comparator. These are ten selected cases, not another run of the 704-case native suite.

The trusted controller used the selected Python 3.13.14/SDK 0.42.0/API141 environment, Core `44564d0279c275eef52b11750a9d76349f4e7a88` and backend `59bd3e1acba6520bb32717ad03833f6ab2967ecc`. One actual Guest started under required macOS Seatbelt with the genuine supported Host policy recipe, a candidate-only pack root, zero node capabilities and the recorded exact constructor, profile, argv, import and startup bindings. The controller itself ran outside outer Seatbelt. This development-host diagnostic does not establish managed module admission or production runtime readiness.

The first revision 4 attempt remains **FAILED**: its ten comparisons completed, but fixture cleanup incorrectly awaited the `None` returned by the selected Core's synchronous `NoAssets.shutdown`. That failure receives no overall PASS or acceptance credit. Revision 5 calls the same synchronous shutdown exactly once and preserves fatal exception handling; revision 6 only corrects and reseals metadata. No node implementation changed. The single separately selected revision 6 attempt completed with no cleanup errors and no automatic retry. Both failed and corrective evidence are retained under `validation/20261020-moe-join-core-guest-r6`.

The unchanged owner observed 41.059917875 seconds including preflight and postflight, with 8.2256455 seconds for payload and cleanup, within the selected 180-second work, 15-second cleanup and 200-second whole-owner bounds. Peak sampled aggregate RSS was 800,571,392 bytes under the observed 1 GiB watchdog; this is not a hard memory or CPU quota. Controller 77980 and Guest 78394 were independently absent after completion; no owned process or socket path remained. The actual journal contains one durable Guest birth with no journal, monitor or cleanup errors. This observation does not close the pre-fsync uncatchable-parent-kill gap.

All 40 input files retained their exact bytes, sizes and modes. The before/after INPUT map JSON serializations differ (SHA-256 `047b27a75f44c2b4a20fc815cb2edf92e137366a7a85b4ceb87d3ef66c4e8146` and `8430b6ba84dfb6f4f009f07a3bfcb5fb553c50659e2fd8df55396affb79b650e`), while both parsed dictionaries equal the complete frozen configuration. The other five maps are byte-exact before/after: selected runtime, full site (84,917 entries), component prefix (96 entries), bindings and operator sources. Interpreter configuration and operator/payload bytes also remained unchanged. Compact records retain both INPUT maps and bind the larger raw maps in the retained archive.

The strict result receipt is `73b3c3471b2ec2175313f9040888ab6065599ec6bbe4695b5b2d547cdf95120b`; the actual terminal archive is `821cad6fa3ff323e88478956efecc1bc6c92eabddb3ba4226e4d78248958a804`. Source-only publication updates this report and its matching canonical JSON/diff. Both current patch forms reconstruct all candidate files byte/mode-exactly on independent pristine trees, preserving all 43 original files. The normal manifest, node code, frontend, stubs and historical tests remain unchanged. No normal-generator, native, SDK, Guest or service job was rerun for publication. These observations do not constitute whole-pack, frontend, shared-service, managed-runtime or admission acceptance.

'''
    marker = '## Historical verification results (unrefreshed)\n'
    assert text.count(marker) == 1
    text = text.replace(marker, section + marker, 1)
    old = 'No full multi-pack workflow/browser deployment is certified by a recording harness or schema pass. Final supported recommendation requires the focused guest/executor/behavior/security/artifact gate twice and coordinator review.'
    new = ('No full multi-pack workflow/browser deployment is certified. The recorded Core/Guest subset and '
           'file-only reconstruction do not refresh the historical full suite or close frontend, shared-service, '
           'managed-runtime and production-admission requirements. Coordinator review and separately selected '
           'remaining-purpose evidence are still required for a whole-pack recommendation.')
    assert text.count(old) == 1
    return text.replace(old, new, 1)

def main():
    assert sys.platform == 'linux'
    assert not HERE.exists(), 'Never rewrite a sealed publication successor'
    HERE.mkdir()
    assert git('rev-parse', BASE).decode().strip() == BASE
    all_tree = git('ls-tree', '-r', '-z', BASE)
    rows = {}
    for raw in git('ls-tree', '-r', '-z', BASE, '--', PACK).split(b'\0'):
        if not raw:
            continue
        meta, path = raw.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        assert kind == 'blob' and mode == '100644'
        name = path.decode().removeprefix(PACK)
        data = git('cat-file', 'blob', oid)
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid
        rows[name] = dict(mode=mode, oid=oid, data=data, sha256=sha(data))
    original = {n: r for n, r in rows.items() if not n.startswith('v2/')}
    candidate = {n.removeprefix('v2/'): dict(r) for n, r in rows.items() if n.startswith('v2/')}
    assert len(original) == 43 and len(candidate) == 14
    binding = load(COORD / 'joinprompt2-public-guest-payload-source-r6-20261019/inputs/CURRENT_SOURCE_BINDING.json')
    assert {n: r['sha256'] for n, r in original.items()} == binding['original_files']
    assert {n: r['sha256'] for n, r in candidate.items()} == binding['candidate_files']
    strict = R6 / 'VERIFIED_RESULT_RECEIPT.json'
    assert digest(strict) == '73b3c3471b2ec2175313f9040888ab6065599ec6bbe4695b5b2d547cdf95120b'
    assert load(strict)['status'] == 'VERIFIED_JOIN_CORE_BOUNDARY_AND_ORDINARY_SEATBELT_GUEST_ONLY'
    assert digest(R4 / 'DIAGNOSTIC_DETAIL_RECEIPT.json') == '19c34b33cd45478c5f03c7b2f608f3f043362782da4558045ebb9f9e495a3642'
    assert load(R4 / 'DIAGNOSTIC_DETAIL_RECEIPT.json')['overall_PASS'] is False
    new_report = report_update(candidate['SECURE_CONVERSION.md']['data'].decode()).encode()
    candidate['SECURE_CONVERSION.md'].update(data=new_report, sha256=sha(new_report))
    write(PACK + 'v2/SECURE_CONVERSION.md', new_report)
    normal_sha = candidate['secure-nodes.json']['sha256']
    assert normal_sha == 'fdaced83feb6523a1e4d0903313c3a8f716022bbbf786478172a5d16f0f6ce94'
    old_records = [{'mode': 420, 'path': n, 'sha256': r['sha256']} for n, r in rows.items()]
    old_records.sort(key=lambda r: tuple(r['path'].split('/')))
    new_records = [dict(r) for r in old_records]
    for row in new_records:
        if row['path'] == 'v2/SECURE_CONVERSION.md':
            row['sha256'] = sha(new_report)
    catalogue = json.loads(git('show', BASE + ':packs/packs.json'))
    upstream = catalogue['comfy-join-prompt']['commit']
    assert upstream == binding['upstream_commit']
    manifest = json.loads(candidate['secure-nodes.json']['data'])
    dependency = manifest.get('runtime', {}).get('dependencies', {}).get('profile_sha256', sha(b''))
    def source_tuple(records):
        source = sha(json.dumps(records, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode())
        fields = [PACK_ID, upstream, source, normal_sha, dependency]
        return dict(zip(['pack_id', 'upstream_commit', 'source_sha256', 'manifest_sha256', 'dependency_profile_sha256', 'revision_id'], fields + [sha('\0'.join(fields).encode())], strict=True))
    old_tuple, new_tuple = source_tuple(old_records), source_tuple(new_records)
    assert old_tuple['source_sha256'] == '818451ebd83a21b8b3741ec044724c9a0cd3c2bbdc7a418b13be879a1260a4d3'
    assert old_tuple['revision_id'] == '4618648707f86f1873f5492c5a628ce56f5f95552ebcde0d8504617574b62bcd'
    write(PROOF + 'SOURCE_TUPLE.json', dict(base_main=BASE, upstream=binding['upstream'], base_tuple=old_tuple,
          proposed_tuple=new_tuple, original_files=43, candidate_files=14, proposed_source_records=new_records,
          only_changed_pack_leaf='v2/SECURE_CONVERSION.md', runtime_and_manifest_unchanged=True))
    # Exact actual evidence only; large raw maps and ZIPs stay outside Git.
    copies = {
        'R6/STRICT_RESULT_RECEIPT.json': strict,
        'R6/INVOCATION_AND_LINEAGE_RECEIPT.json': R6 / 'INVOCATION_AND_LINEAGE_RECEIPT.json',
        'R6/BOUNDARY_RESULT.json': ACTUAL / 'actual-output/BOUNDARY_RESULT.json',
        'R6/RESULT.json': ACTUAL / 'actual-output/RESULT.json',
        'R6/OUTER_RECEIPT.json': ACTUAL / 'OUTER_RECEIPT.json',
        'R6/INDEPENDENT_POSTFLIGHT_READBACK.json': ACTUAL / 'INDEPENDENT-POSTFLIGHT-READBACK.json',
        'R6/GUEST_CREATION.jsonl': ACTUAL / 'actual-output/GUEST_CREATION.jsonl',
        'R6/GUEST_PROFILE_0.sb': ACTUAL / 'actual-output/GUEST_PROFILE_0.sb',
        'R6/INPUT_BEFORE.json': ACTUAL / 'INPUT-BEFORE.json',
        'R6/INPUT_AFTER.json': ACTUAL / 'INPUT-AFTER.json',
        'R6/FROZEN_CONFIG.json': R6 / 'received/retained-source/join_core_guest-R6-CONFIG.json',
        'R6/ACTUAL_RUNTIME_INSTANTIATION.json': R6 / 'received/retained-source/JOIN-R6-RUNTIME-INSTANTIATION.json',
        'R6/EXECUTION_SELECTION.json': R6 / 'received/execution/JOIN-CORE-GUEST-R6-SELECTION.json',
        'R6/BOUND_FIXTURES.json': COORD / 'joinprompt2-public-guest-payload-source-r6-20261019/inputs/BOUND_FIXTURES.json',
        'R6/PAYLOAD_HANDOFF.json': COORD / 'joinprompt2-public-guest-payload-source-r6-20261019/HANDOFF.json',
        'R6/join_public_guest_fixture.py': COORD / 'joinprompt2-public-guest-payload-source-r6-20261019/join_public_guest_fixture.py',
        'R6/run_join_boundary.py': COORD / 'joinprompt2-public-guest-payload-source-r6-20261019/run_join_boundary.py',
        'R6/guest_startup_observer.py': COORD / 'joinprompt2-public-guest-payload-source-r6-20261019/guest_startup_observer.py',
        'R4/STRICT_FAILED_RECEIPT.json': R4 / 'VERIFIED_RESULT_RECEIPT.json',
        'R4/DIAGNOSTIC_DETAIL_RECEIPT.json': R4 / 'DIAGNOSTIC_DETAIL_RECEIPT.json',
        'R4/BOUNDARY_RESULT.json': FAILED / 'actual-output/BOUNDARY_RESULT.json',
        'R4/OUTER_RECEIPT.json': FAILED / 'OUTER_RECEIPT.json',
        'R4/FAILURE_DIAGNOSIS.json': FAILED / 'FAILURE-DIAGNOSIS.json',
        'R4/INDEPENDENT_POSTFLIGHT_READBACK.json': FAILED / 'INDEPENDENT-POSTFLIGHT-READBACK.json',
        'lineage/FIXTURE_R4_R5.diff': COORD / 'joinprompt2-cleanup-r6-final-review-20261019/FIXTURE_R4_R5.diff',
        'lineage/HANDOFF_R5_R6.diff': COORD / 'joinprompt2-cleanup-r6-final-review-20261019/HANDOFF_R5_R6.diff',
        'lineage/ROOT_R6_REVIEW.json': WORK.parent / 'chat_f38536805264/coordination/review-join-cleanup-r6-20261019/REVIEW.json',
        'intake/verify_result.py': COORD / 'joinprompt2-boundary-result-intake-source-r6-v2-20261019/verify_result.py',
        'intake/VERIFIER_FORMAT_DELTA.diff': COORD / 'joinprompt2-boundary-result-intake-source-r6-v2-20261019/VERIFIER_FORMAT_DELTA.diff',
    }
    evidence_pins = {}
    for name, source in copies.items():
        target = file_copy(name, source)
        evidence_pins[name] = {'sha256': digest(target), 'bytes': target.stat().st_size, 'git_mode': '100644'}
    assert evidence_pins['R6/BOUNDARY_RESULT.json']['sha256'] == 'd286699eb0c08aa2d6675c13bd230b1f40cd0693adec9fe8416cb144b00384fd'
    assert evidence_pins['R4/BOUNDARY_RESULT.json']['sha256'] == '4f4e107686aaabee2f959235b4c7bdde381fc460f6e9acb20ea329932acbd70b'
    map_rows = []
    for stem in ('INPUT', 'RUNTIME', 'FULL-SITE', 'COMPONENT-PREFIX', 'BINDINGS', 'OPERATOR-SOURCES'):
        before, after = ACTUAL / (stem + '-BEFORE.json'), ACTUAL / (stem + '-AFTER.json')
        assert load(before) == load(after)
        if stem != 'INPUT':
            assert before.read_bytes() == after.read_bytes()
        map_rows.append(dict(name=stem, before_sha256=digest(before), after_sha256=digest(after),
                             entries=len(load(before)), bytes_equal=before.read_bytes() == after.read_bytes(), dictionaries_equal=True))
    assert load(ACTUAL / 'INPUT-BEFORE.json') == load(ACTUAL / 'INPUT-AFTER.json') == load(copies['R6/FROZEN_CONFIG.json'])['input_files']
    write(PROOF + 'PRESERVATION_BINDING.json', dict(actual_archive_sha256='821cad6fa3ff323e88478956efecc1bc6c92eabddb3ba4226e4d78248958a804',
          actual_archive_bytes=9609111, actual_archive_members=142, manifest_pins=141,
          actual_manifest_sha256=digest(R6 / 'received/MANIFEST.json'),
          failed_R4_archive_sha256='094c4f2cc94266b58b5feb41668ba6dd0f5f25a283bdda812f6d2d99d5d24072',
          before_after_maps=map_rows, retained_evidence_files=evidence_pins,
          full_raw_maps_and_derived_ZIPs_committed=False, input_file_bytes_sizes_modes_unchanged=True,
          whole_pack_or_service_accepted=False))
    tool_data = git('show', BASE + ':' + TOOL_PATH)
    assert sha(tool_data) == TOOL_SHA
    tool_blob = hashlib.sha1(b'blob ' + str(len(tool_data)).encode() + b'\0' + tool_data).hexdigest()
    assert tool_blob == '170cd00c3cb0b2e8bd23d06dcfef711191503df9'
    commands, replays = [], []
    scratch = Path(tempfile.mkdtemp(prefix='moe-join-publication-r1-'))
    assert scratch.parent == Path('/tmp') and not scratch.is_symlink()
    started = time.monotonic()
    try:
        tool = scratch / 'packpatch.py'
        tool.write_bytes(tool_data)
        tool.chmod(0o644)
        snapshot = scratch / 'generated/comfy-join-prompt/x0832089'
        materialize(original, snapshot / 'comfy-join-prompt-HEAD')
        materialize(candidate, snapshot / 'comfy-join-prompt-HEAD/v2')
        candidate_map = {n: {'sha256': r['sha256'], 'mode': 420} for n, r in candidate.items()}
        original_map = {n: {'sha256': r['sha256'], 'mode': 420} for n, r in original.items()}
        assert inventory(snapshot / 'comfy-join-prompt-HEAD/v2') == candidate_map
        generated = scratch / 'patches/comfy-join-prompt/x0832089'
        pair = generated / 'comfy-join-prompt-x0832089'
        def run(action, *args):
            argv = [sys.executable, '-I', '-S', '-B', str(tool), action, *map(str, args)]
            child = subprocess.run(argv, cwd=scratch, capture_output=True, timeout=15,
                    env={'PATH': '/usr/bin:/bin', 'HOME': str(scratch), 'TMPDIR': str(scratch), 'LC_ALL': 'C.UTF-8'})
            write(PROOF + 'file-only/' + action + '.log', child.stdout + child.stderr)
            commands.append(dict(action=action, argv=argv, exit_code=child.returncode))
            assert child.returncode == 0, child.stderr.decode(errors='replace')
        run('generate', snapshot, generated)
        run('bundle', pair, pair.with_suffix('.zip'))
        for key, action, artifact in [('pair', 'apply', pair), ('zip', 'apply-zip', pair.with_suffix('.zip'))]:
            target = scratch / ('replay-' + key) / 'comfy-join-prompt/x0832089'
            materialize(original, target / 'comfy-join-prompt-HEAD')
            assert inventory(target / 'comfy-join-prompt-HEAD') == original_map
            run(action, target, artifact)
            actual = inventory(target / 'comfy-join-prompt-HEAD')
            assert inventory(target / 'comfy-join-prompt-HEAD/v2') == candidate_map
            assert {n: r for n, r in actual.items() if not n.startswith('v2/')} == original_map
            replays.append(dict(kind=key, status='PASS_COMPLETE_BYTE_MODE_RECONSTRUCTION', candidate=candidate_map,
                                original_files=43, original_bytes_and_modes_preserved=True))
        assert {n: r for n, r in inventory(snapshot / 'comfy-join-prompt-HEAD').items() if not n.startswith('v2/')} == original_map
        for suffix in ('.json', '.diff'):
            write(PATCH + suffix, pair.with_suffix(suffix).read_bytes())
        retained_bundle = HERE / 'derived/comfy-join-prompt-x0832089.zip'
        retained_bundle.parent.mkdir()
        shutil.copyfile(pair.with_suffix('.zip'), retained_bundle)
    finally:
        assert scratch.parent == Path('/tmp') and scratch.name.startswith('moe-join-publication-r1-') and not scratch.is_symlink()
        shutil.rmtree(scratch)
    assert not scratch.exists()
    write(PROOF + 'FILE_ONLY_REPLAY_RECEIPT.json', dict(status='PASS_REPORT_ONLY_CANONICAL_PAIR_AND_TWO_PRISTINE_REPLAYS',
          base_main=BASE, tool_sha256=TOOL_SHA, tool_base_path=TOOL_PATH, tool_git_blob=tool_blob,
          python_version=sys.version, local_file_only_commands=4, commands=commands, replays=replays,
          original_inventory=original_map, candidate_inventory=candidate_map,
          derived_bundle_sha256=digest(retained_bundle), derived_bundle_bytes=retained_bundle.stat().st_size,
          derived_bundle_committed=False, scratch_removed_and_confirmed_absent=True, synchronous_children_reaped=True,
          elapsed_seconds=round(time.monotonic() - started, 6), subprocess_timeout_seconds=15,
          SDK_normal_generator_native_science_Guest_service_reruns=0, whole_pack_accepted=False))
    write(PROOF + 'PURPOSE_ROWS.json', dict(Core_finalization_and_ordinary_Guest=dict(status='PASS_TEN_SELECTED_CASES_ONLY', comparisons=10,
          actual_Guest_dispatches=10, corrupted_STRING_controls_detected=1, local_fallbacks=0, cleanup_errors=0),
          failed_R4=dict(status='FAILED_CLEANUP_PRESERVED_NO_ACCEPTANCE', correction='Exactly-once sync NoAssets.shutdown, exceptions fatal'),
          native704=dict(status='RETAINED_EXISTING_EVIDENCE_NOT_RERUN', path='validation/20261019-moe-resolution-join-native/joinprompt2'),
          current_publication_replay=dict(status='PASS_FILE_ONLY', independent_pristine_replays=2),
          frontend_browser='OPEN_UNREFRESHED', managed_runtime_admission='NOT_EXERCISED', shared_service='NOT_EXERCISED',
          pre_fsync_uncatchable_parent_kill_gap='NOT_CLOSED', whole_pack='NOT_ACCEPTED'))
    write(PROOF + 'SUMMARY.json', dict(status='JOIN_R6_SCOPED_CORE_GUEST_PASS_SOURCE_EVIDENCE_ONLY', root_assignment='m_bf8cf451e5',
          execution_authority='m_f78c41f7ce', strict_receipt_sha256=digest(strict), proposed_source_tuple=new_tuple,
          source_delta='Only V2 SECURE_CONVERSION.md changes; canonical JSON/diff rebuilt. New compact validation evidence only.',
          current_normal_manifest_sha256=normal_sha, unchanged_candidate_files=13, unchanged_original_files=43,
          original_native_evidence_unchanged=True, historical_R4_remains_failed=True,
          input_map_dictionary_equal_serialization_different=True, other_five_maps_byte_exact=True,
          actual_R6_runtime_attempts=1, publication_runtime_attempts=0, publication_file_only_tool_calls=4,
          managed_service_frontend_or_whole_pack_acceptance=False))
    file_copy('prepare_source_handoff.py', Path(__file__))
    assert git('ls-tree', '-r', '-z', BASE) == all_tree
    rows_now = {str(p.relative_to(STAGE)): dict(sha256=digest(p), bytes=p.stat().st_size, git_mode='100644')
                for p in sorted(STAGE.rglob('*')) if p.is_file()}
    assert all(n.startswith((PACK + 'v2/SECURE_CONVERSION.md', PATCH, PROOF)) for n in rows_now)
    assert not any(n.endswith('.zip') for n in rows_now)
    table = HERE / 'STAGED_FILES.json'
    table.write_bytes(encoded(rows_now))
    (HERE / 'STAGE_SHA256SUMS').write_text(''.join(r['sha256'] + '  ' + n + '\n' for n, r in rows_now.items()))
    base_rows = {n: {'sha256': r['sha256'], 'bytes': len(r['data']), 'git_mode': r['mode'], 'git_oid': r['oid']} for n, r in rows.items()}
    (HERE / 'BASE_PACK_FILES.json').write_bytes(encoded(base_rows))
    archive = HERE.with_name(HERE.name + '.CORPUS.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in rows_now:
            info = zipfile.ZipInfo('corpus/' + name, (2026, 10, 20, 0, 0, 0))
            info.create_system, info.external_attr, info.compress_type = 3, 0o100644 << 16, zipfile.ZIP_DEFLATED
            bundle.writestr(info, (STAGE / name).read_bytes())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.infolist()) == len(rows_now)
        assert all(i.external_attr >> 16 == 0o100644 for i in bundle.infolist())
        assert {i.filename.removeprefix('corpus/'): sha(bundle.read(i)) for i in bundle.infolist()} == {n: r['sha256'] for n, r in rows_now.items()}
    handoff = dict(status='READY_ROOT_COMPACT_JOIN_CORE_GUEST_SOURCE_REVIEW', root_assignment='m_bf8cf451e5', base_main=BASE,
          stage_root=str(STAGE), staged_file_count=len(rows_now), staged_bytes=sum(r['bytes'] for r in rows_now.values()),
          staged_files=rows_now, staged_table_sha256=digest(table), base_pack_files_sha256=digest(HERE / 'BASE_PACK_FILES.json'),
          corpus_zip_sha256=digest(archive), corpus_zip_bytes=archive.stat().st_size, all_modes='100644',
          current_source_tuple=old_tuple, proposed_source_tuple=new_tuple,
          canonical_pair_sha256=digest(STAGE / (PATCH + '.json')), canonical_diff_sha256=digest(STAGE / (PATCH + '.diff')),
          derived_bundle_sha256=digest(retained_bundle), derived_ZIPs_staged_for_Git=0,
          report_sha256=sha(new_report), file_only_receipt_sha256=digest(STAGE / (PROOF + 'FILE_ONLY_REPLAY_RECEIPT.json')),
          local_file_only_commands=4, independent_pristine_replays=2, unchanged_original_files=43, unchanged_other_V2_files=13,
          root_and_unrelated_corpus_writes=0, new_pack_identities=0, registry_service_or_admission_actions=0,
          SDK_normal_generator_native704_Guest_reruns=0, historical_R4_remains_failed=True, whole_pack_accepted=False)
    (HERE / 'HANDOFF.json').write_bytes(encoded(handoff))
    state_path = COORD / 'MOE_NEXT_ACTION.json'
    state = load(state_path)
    state['status'] = 'JOIN_COMPACT_CORE_GUEST_SOURCE_HANDOFF_READY_ROOT_REVIEW'
    state['join_core_guest_source_publication'] = dict(handoff=str((HERE / 'HANDOFF.json').relative_to(WORK)), sha256=digest(HERE / 'HANDOFF.json'),
          base_main=BASE, corpus_zip_sha256=digest(archive), staged_files=len(rows_now), file_only_commands=4, native_or_SDK_or_Guest_reruns=0)
    state['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state_path.write_bytes(encoded(state))
    print(json.dumps({k: handoff[k] for k in ('status', 'staged_file_count', 'staged_bytes', 'corpus_zip_sha256', 'corpus_zip_bytes', 'canonical_pair_sha256', 'canonical_diff_sha256', 'file_only_receipt_sha256', 'proposed_source_tuple')}, indent=2))
    print('HANDOFF_SHA256=' + digest(HERE / 'HANDOFF.json'))

if __name__ == '__main__':
    main()
