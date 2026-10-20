"""Report-only Tiny publication handoff; canonical file work, no node imports."""
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

WORK=Path(__file__).resolve().parents[1]
COORD=WORK/'coordination'
HERE=COORD/'tiny-scoped-native-source-publication-r1-20261020'
STAGE=HERE/'stage/corpus'
GIT='/mnt/c/Program Files/Git/cmd/git.exe'
REPO='C:/Users/benjc/.popbot-host/workspaces/scratch/chat_f38536805264/corpus'
BASE='2634f74ee8969080066bef180a54b652c50a0f24'
PACK_ID='comfyui-tinyterranodes/x97096a3'
PACK='packs/'+PACK_ID+'/ComfyUI_tinyterraNodes-HEAD/'
PATCH='patches/'+PACK_ID+'/comfyui-tinyterranodes-x97096a3'
PROOF='validation/20261020-moe-tiny-scoped-native-r4/'
TOOL_PATH='validation/20261019-moe-resolution-join-native/publication-r2/packpatch.py'
TOOL_SHA='268df53fa640b4eb42ee342850e686790016ad15a207cf6a5a7e57ee5d5953a2'
PASS=COORD/'tinyterra-r4-result-intake-r1-20261020'
FAIL=COORD/'tinyterra-r3-failed-result-intake-r1-20261020'
sha=lambda data:hashlib.sha256(data).hexdigest()
digest=lambda p:sha(p.read_bytes())
load=lambda p:json.loads(p.read_bytes())
encoded=lambda value:(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def git(*args,data=None):
    return subprocess.check_output([GIT,'--no-optional-locks','-C',REPO,*args],input=data,stderr=subprocess.PIPE,timeout=30,
        env=dict(os.environ,GIT_NO_LAZY_FETCH='1',GIT_OPTIONAL_LOCKS='0'))
def write(name,data):
    p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists()
    p.write_bytes(data if isinstance(data,bytes) else encoded(data));return p
def retain(name,p,expected=None):
    if expected:assert digest(p)==expected
    return write(PROOF+name,p.read_bytes())
def inventory(directory):
    rows={}
    for p in sorted(directory.rglob('*')):
        assert not p.is_symlink()
        if p.is_file():rows[p.relative_to(directory).as_posix()]=dict(sha256=digest(p),mode=stat.S_IMODE(p.stat().st_mode))
    return rows
def materialize(records,directory):
    for name,row in records.items():
        p=directory/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(row['data']);p.chmod(0o644)

def main():
    assert sys.platform=='linux'
    if HERE.exists():assert not any(HERE.iterdir()),'Never rewrite a staged/sealed successor'
    else:HERE.mkdir()
    assert git('rev-parse',BASE).decode().strip()==BASE
    tree=git('ls-tree','-r','-z',BASE,'--',PACK)
    rows={}
    for raw in tree.split(b'\0'):
        if not raw:continue
        meta,path=raw.split(b'\t',1);mode,kind,oid=meta.decode().split()
        assert kind=='blob' and mode=='100644'
        data=git('cat-file','blob',oid)
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==oid
        rows[path.decode().removeprefix(PACK)]=dict(mode=mode,oid=oid,data=data,sha256=sha(data))
    original={k:v for k,v in rows.items() if not k.startswith('v2/')}
    candidate={k.removeprefix('v2/'):dict(v) for k,v in rows.items() if k.startswith('v2/')}
    assert len(original)==30 and len(candidate)==29
    tested=load(COORD/'tinyterra-onephase-binding-r4-20261020/packet/CANDIDATE_FILES.json')
    assert {name:row['sha256'] for name,row in candidate.items()}=={name:row['sha256'] for name,row in tested.items()}
    assert digest(PASS/'VERIFIED_RESULT_RECEIPT.json')=='bbeda25b61158b91f9099608928ccdac9f6d92d4060df437280d70eaae74d6fe'
    assert digest(FAIL/'VERIFIED_RESULT_RECEIPT.json')=='0f0f7db40be16d9682e511157f51353f05b0615ba2adfe86adae2eefe8779b16'
    actual=PASS/'received';failed=FAIL/'received'
    result=load(actual/'actual-owner/actual-output/RESULT.json')
    cases=load(COORD/'tinyterra-onephase-binding-r4-20261020/packet/BATCH_CASES.json')['cases']
    purposes={}
    for case in cases:
        entry=purposes.setdefault(case['original_id'],dict(case_ids=[],purposes=[],ordinary=0,direct_diagnostics=0))
        entry['case_ids'].append(case['case_id'])
        if case['purpose'] not in entry['purposes']:entry['purposes'].append(case['purpose'])
        entry['direct_diagnostics' if case['comparison_kind']!='ordinary_direct_native' else 'ordinary']+=1
    assert len(purposes)==24 and sum(v['ordinary'] for v in purposes.values())==50 and sum(v['direct_diagnostics'] for v in purposes.values())==2
    table='\n'.join('| `'+name+'` | '+str(row['ordinary'])+' | '+str(row['direct_diagnostics'])+' | '+'; '.join(row['purposes'])+' |' for name,row in purposes.items())
    section='''## Current finite direct-native/default-SDK evidence (2026-10-20)

One separately selected corrective R4 attempt passed **50 ordinary direct comparisons and two direct native diagnostics**, plus **three separate comparator controls**, across selected purposes of24 original identities. This is not full behavior acceptance for24 nodes or the43-original-node pack. The52 cases and their typed original/candidate values are retained under `validation/20261020-moe-tiny-scoped-native-r4`.

The driver normally imported the candidate package and complete genuine original main/legacy modules with their real helper imports. It called actual original FUNCTION methods and candidate generated execute methods under the unmodified default SDK runtime, declared permissions and real public refs. It excluded the original root entrypoint, whose config/JS mutation is outside this component comparison. Core input/default/list scheduling, hidden-input hydration, actual model handles, cross-render lifetime and Guest transport were not exercised by this direct-call batch. Pipe cases contain null resource fields and compare metadata/tuple/wire routing only. Debug console output was disabled and text output exercised Preview only.

| Original identity (selected purposes only) | Ordinary comparisons | Direct diagnostics | Selected scope |
|---|---:|---:|---|
'''+table+'''

The two diagnostic cases are the original textCycle negative-index value observation and too-negative IndexError behavior. They remain distinct from the50 ordinary cases. Three controls independently corrupted actual STRING content, numeric type and pipe seed and detected the changes; they are comparator checks, not security-boundary tests. The historical19 constructor/plot checks and47-registration/43-validator generation evidence were not rerun or added to52.

Actual runtime authority was `m_ce29735a42`, one attempt without automatic retries, on the selected Python3.13.14 normal-site isolated interpreter, SDK0.42/API141, Core44564d0279c275eef52b11750a9d76349f4e7a88, backend59bd3e1acba6520bb32717ad03833f6ab2967ecc and actual profile40fbb95d729e2f10ba9c7809fa08135f5d9f433372d41d2d9d044cd58a68cdaf. The actual f1 engine and public facade origins were read back and matched their selected leaf hashes. No providers were replaced or private raw constructors called.

R3 remains **FAILED**, with zero comparisons/controls/qualification: its hash helper expected Path but received a module __file__ string. R4 changes only that helper to Path(p).read_bytes; the previously reviewed zero-output NodeOutput normalization remains. No production computation, normal manifest, schema, permission or case was changed. R2 was never run. Failed and corrective evidence stays separate.

R4 actual outer and payload exited0. Whole owner48.922350875 seconds and payload/cleanup8.691823792 seconds fit the90work/15cleanup/120whole envelope including full pre/postflight and receipt. Cleanup0.265858 seconds had no errors; the corrected terminal-leader/no-other-owned no-signal branch was observed. Actual recorded PIDs22073/22074/23285 and two groups were independently absent twice, checked against raw process snapshots. The deadline marker remained empty. The socket observation covers filesystem sockets under the owned output tree, not a whole-system socket table.

All99 input leaves retained their exact bytes/sizes/modes. Full INPUT99, site84,917, component96, runtime and operator/config6 maps were byte-equal before/after; the runtime map independently matched SDK141/Core1,384/backend83/dependency/science/Python pins. Sampled payload-plus-descendant peak RSS543,670,272 bytes excludes the owner; the separate external maxRSS1,049,673,728 bytes is reported independently. The1GiB sampled watchdog and one-thread environment are not hard memory or CPU quotas.

Strict independent receipt is bbeda25b61158b91f9099608928ccdac9f6d92d4060df437280d70eaae74d6fe; complete raw archive54b4c07e79bf63c40c77c1c3cfaceb9f37cfa1a8b353f84f0dc453fd39ea01ae; actual resultf71e7dde1502bf1bf63b4294f7195d87b4a58339069f02f01f79643a4ae84665. Large raw maps/archives remain external; compact retained evidence binds them. Report-only publication changes no executable source or normal manifest. Canonical pair/bundle reconstruction is file-only and supplies no new native or47/43 generation credit.

All four embedded sampler XY and three legacy Hold purposes remain named partials. The closed, unwired inline XY prototype and current-model/continuation/Hold-owner source designs are separate unrun work, not exercised by52. No model/sampling, public graph, real U2Net, Guest, browser/frontend, service/admission or whole-pack acceptance follows from this evidence.

'''
    before=candidate['SECURE_CONVERSION.md']['data'].decode()
    report=before.replace('> INPROGRESS: source and canonical generation only. See SDK_REQUIREMENTS.json.','> INPROGRESS: selected finite direct-native/default-SDK evidence; whole-pack acceptance remains open. See SDK_REQUIREMENTS.json.',1)
    report=report.replace('The selected source contains the graph, prompt, model, asset and output repairs described below. Their final combined trusted SDK and consumer tuple has not been built or runtime-qualified by this packet. Earlier tests on other tuples remain scoped to those exact inputs and cases.',
        'The selected source contains the graph, prompt, model, asset and output repairs described below. The current finite direct-native/default-SDK tuple has the scoped evidence recorded below; the installed Guest/service tuple and remaining purposes are not qualified by that batch. Earlier tests on other tuples remain scoped to those exact inputs and cases.',1)
    report=report.replace('## Two purposes refused in the current secure profile','## Seven named sampler purposes still partial in the current profile',1)
    report=report.replace('Root accepted the following purpose-level limitations. They do not refuse entire sampler nodes and do not claim the features are permanently impossible.',
        'The following purpose-level limitations remain open and currently guarded. They do not refuse entire sampler nodes or declare the features permanently impossible, and missing resource metadata alone is not a formal purpose refusal.',1)
    report=report.replace('The seven sampler-purpose refusals and all admission/dependency/permission constraints above remain in force.','The seven named sampler-purpose partials and all admission/dependency/permission constraints above remain open.',1)
    marker='## Qualified public constructor successor\n';assert report.count(marker)==1
    report=report.replace(marker,section+marker,1)
    candidate['SECURE_CONVERSION.md'].update(data=report.encode(),sha256=sha(report.encode()))
    write(PACK+'v2/SECURE_CONVERSION.md',report.encode())
    normal_sha=candidate['secure-nodes.json']['sha256'];assert normal_sha=='f7a6f6b980b77f23bc0a482ac95262d879de41b5bf7a0fe46bcb84dba18da808'
    old_records=[dict(mode=420,path=name,sha256=row['sha256']) for name,row in rows.items()];old_records.sort(key=lambda row:tuple(row['path'].split('/')))
    new_records=[dict(row) for row in old_records]
    for row in new_records:
        if row['path']=='v2/SECURE_CONVERSION.md':row['sha256']=sha(report.encode())
    catalogue=json.loads(git('show',BASE+':packs/packs.json'));upstream=catalogue['comfyui-tinyterranodes']['commit'];assert upstream=='97096a39847b74e15886a16049ae89ad918e1aea'
    dependency=json.loads(candidate['secure-nodes.json']['data']).get('runtime',{}).get('dependencies',{}).get('profile_sha256',sha(b''))
    def source_tuple(records):
        fields=[PACK_ID,upstream,sha(json.dumps(records,separators=(',',':'),sort_keys=True,ensure_ascii=False).encode()),normal_sha,dependency]
        return dict(zip(['pack_id','upstream_commit','source_sha256','manifest_sha256','dependency_profile_sha256','revision_id'],fields+[sha('\0'.join(fields).encode())],strict=True))
    old_tuple,new_tuple=source_tuple(old_records),source_tuple(new_records)
    assert old_tuple['source_sha256']=='425f0c30464cc66cd8cd48f5724554d9a87a7b8c1a1f7ba7dbd889ff5dad1cb3'
    write(PROOF+'SOURCE_TUPLE.json',dict(base_main=BASE,current_tuple=old_tuple,proposed_tuple=new_tuple,only_changed_pack_leaf='v2/SECURE_CONVERSION.md',proposed_records=new_records))
    copies={
      'R4/STRICT_RESULT_RECEIPT.json':PASS/'VERIFIED_RESULT_RECEIPT.json',
      'R4/ACTUAL_RESULT.json':actual/'actual-owner/actual-output/RESULT.json',
      'R4/OWNER_RECEIPT.json':actual/'actual-owner/OWNER_RECEIPT.json',
      'R4/EXTERNAL_EXECUTION_RECEIPT.json':actual/'external-evidence/EXTERNAL-EXECUTION-RECEIPT.json',
      'R4/INDEPENDENT_TERMINAL_RETIREMENT.json':actual/'external-evidence/INDEPENDENT-TERMINAL-RETIREMENT.json',
      'R4/INDEPENDENT_LIVE_OWNER_WITNESS.json':actual/'external-evidence/INDEPENDENT-LIVE-OWNER-WITNESS.json',
      'R4/INDEPENDENT_TERMINAL_PS_0.txt':actual/'external-evidence/INDEPENDENT-TERMINAL-PS-0.txt',
      'R4/INDEPENDENT_TERMINAL_PS_1.txt':actual/'external-evidence/INDEPENDENT-TERMINAL-PS-1.txt',
      'R4/SELECTION_AND_CAPACITY.json':actual/'external-evidence/SELECTION-AND-CAPACITY.json',
      'R4/EXTERNAL_TOOL_TERMINAL.json':actual/'external-evidence/EXTERNAL-TOOL-TERMINAL.json',
      'R4/OWNER_TIME_RESOURCES.txt':actual/'external-evidence/OWNER-TIME-RESOURCES.txt',
      'R4/OWNER_STDOUT.txt':actual/'external-evidence/OWNER-STDOUT.txt',
      'R4/OWNER_STDERR.txt':actual/'external-evidence/OWNER-STDERR.txt',
      'R4/PAYLOAD_STDERR.txt':actual/'actual-owner/stderr.txt',
      'R4/CONFIG.json':actual/'selected-data/CONFIG.json',
      'R4/INVOCATION.json':actual/'selected-data/INVOCATION.json',
      'R4/EXTERNAL_CAPTURE_PLAN.json':actual/'selected-data/EXTERNAL-CAPTURE-PLAN.json',
      'R4/BATCH_CASES.json':actual/'actual-input/BATCH_CASES.json',
      'R4/ACTUAL_MAC_PROFILE.json':actual/'actual-input/inputs/ACTUAL_MAC_PROFILE.json',
      'R4/worker.py':actual/'actual-input/worker.py',
      'R4/check_result.py':actual/'actual-input/check_result.py',
      'R4/sdk_tiny_pure52_owner_r2.py':actual/'operators/sdk_tiny_pure52_owner_r2.py',
      'R3/STRICT_FAILED_RECEIPT.json':FAIL/'VERIFIED_RESULT_RECEIPT.json',
      'R3/EXTERNAL_EXECUTION_RECEIPT.json':failed/'external-evidence/EXTERNAL-EXECUTION-RECEIPT.json',
      'R3/PAYLOAD_STDERR.txt':failed/'actual-owner/stderr.txt',
      'R3/INDEPENDENT_TERMINAL_RETIREMENT.json':failed/'external-evidence/INDEPENDENT-TERMINAL-RETIREMENT.json',
      'lineage/R2_R3_worker.diff':COORD/'tinyterra-onephase-binding-r3-20261020/R2-R3-worker.diff',
      'lineage/R3_R4_worker.diff':COORD/'tinyterra-onephase-binding-r4-20261020/R3-R4-worker.diff',
      'lineage/HASH_CALLER_STATIC_REVIEW.json':COORD/'tinyterra-onephase-binding-r4-20261020/HASH_CALLER_STATIC_REVIEW.json',
      'intake/verify_tiny_r4_result.py':COORD/'verify_tiny_r4_result_20261020.py',
      'intake/tiny52_data_predicate_intake_20261020.py':COORD/'tiny52_data_predicate_intake_20261020.py'}
    evidence={}
    for name,p in copies.items():
        target=retain(name,p);evidence[name]=dict(sha256=digest(target),bytes=target.stat().st_size,git_mode='100644')
    write(PROOF+'PURPOSE_ROWS.json',dict(status='SCOPED_PURPOSES_ONLY_NOT_COMPLETE_NODES',original_identities=24,comparisons=52,ordinary=50,direct_diagnostics=2,separate_controls=3,purposes=purposes,
        model_or_sampling_or_Guest_or_public_graph=False,whole_pack_accepted=False,seven_sampler_purposes_remain_partial=True))
    map_rows=[]
    for name in ('INPUT','FULL-SITE','COMPONENT-PREFIX','RUNTIME','OPERATOR-CONFIG'):
        before_map,after_map=actual/'actual-owner'/(name+'-BEFORE.json'),actual/'actual-owner'/(name+'-AFTER.json')
        assert before_map.read_bytes()==after_map.read_bytes()
        map_rows.append(dict(name=name,rows=len(load(before_map)),before_sha256=digest(before_map),after_sha256=digest(after_map),byte_equal=True))
    write(PROOF+'PRESERVATION_BINDING.json',dict(actual_archive_sha256=digest(PASS/'MIKE_RESULT.zip'),actual_archive_bytes=(PASS/'MIKE_RESULT.zip').stat().st_size,actual_members=137,pins=136,
        failed_R3_archive_sha256=digest(FAIL/'MIKE_RESULT.zip'),failed_R3_receipt_sha256=digest(FAIL/'VERIFIED_RESULT_RECEIPT.json'),
        full_maps=map_rows,full_raw_maps_and_ZIPs_committed=False,evidence_files=evidence,actual_source_99_unchanged=True,
        publication_source_change='One report only; all28 other V2 and30 original files unchanged',no_additional_runtime_or_normal_generator=True))
    tool_data=git('show',BASE+':'+TOOL_PATH);assert sha(tool_data)==TOOL_SHA
    commands=[];replays=[];scratch=Path(tempfile.mkdtemp(prefix='moe-tiny-publication-r1-'));assert scratch.parent==Path('/tmp') and not scratch.is_symlink()
    started=time.monotonic()
    try:
        tool=scratch/'packpatch.py';tool.write_bytes(tool_data)
        snapshot=scratch/'generated'/PACK_ID;materialize(original,snapshot/'ComfyUI_tinyterraNodes-HEAD');materialize(candidate,snapshot/'ComfyUI_tinyterraNodes-HEAD/v2')
        original_map={name:dict(sha256=row['sha256'],mode=420) for name,row in original.items()};candidate_map={name:dict(sha256=row['sha256'],mode=420) for name,row in candidate.items()}
        assert inventory(snapshot/'ComfyUI_tinyterraNodes-HEAD/v2')==candidate_map
        generated=scratch/'patches'/PACK_ID;pair=generated/'comfyui-tinyterranodes-x97096a3'
        def run(action,*args):
            argv=[sys.executable,'-I','-S','-B',str(tool),action,*map(str,args)]
            child=subprocess.run(argv,cwd=scratch,capture_output=True,timeout=20,env={'PATH':'/usr/bin:/bin','HOME':str(scratch),'TMPDIR':str(scratch),'LC_ALL':'C.UTF-8'})
            write(PROOF+'file-only/'+action+'.log',child.stdout+child.stderr);commands.append(dict(action=action,argv=argv,exit_code=child.returncode));assert child.returncode==0,child.stderr.decode(errors='replace')
        run('generate',snapshot,generated);run('bundle',pair,pair.with_suffix('.zip'))
        for kind,action,artifact in [('pair','apply',pair),('zip','apply-zip',pair.with_suffix('.zip'))]:
            target=scratch/('replay-'+kind)/PACK_ID;materialize(original,target/'ComfyUI_tinyterraNodes-HEAD')
            run(action,target,artifact)
            assert inventory(target/'ComfyUI_tinyterraNodes-HEAD/v2')==candidate_map
            assert {name:row for name,row in inventory(target/'ComfyUI_tinyterraNodes-HEAD').items() if not name.startswith('v2/')}==original_map
            replays.append(dict(kind=kind,status='PASS_PRISTINE_BYTE_MODE_RECONSTRUCTION',original_files=30,candidate_files=29))
        for suffix in ('.json','.diff'):write(PATCH+suffix,pair.with_suffix(suffix).read_bytes())
        derived=HERE/'derived/comfyui-tinyterranodes-x97096a3.zip';derived.parent.mkdir();shutil.copyfile(pair.with_suffix('.zip'),derived)
    finally:
        assert scratch.parent==Path('/tmp') and scratch.name.startswith('moe-tiny-publication-r1-') and not scratch.is_symlink();shutil.rmtree(scratch)
    assert not scratch.exists()
    write(PROOF+'FILE_ONLY_REPLAY_RECEIPT.json',dict(status='PASS_FILE_ONLY_CANONICAL_PAIR_AND_TWO_PRISTINE_REPLAYS',base_main=BASE,tool_sha256=TOOL_SHA,tool_base_path=TOOL_PATH,
        commands=commands,independent_pristine_replays=replays,original_inventory=original_map,candidate_inventory=candidate_map,
        derived_bundle_sha256=digest(derived),derived_bundle_committed=False,scratch_removed=True,synchronous_children_reaped=True,
        elapsed_seconds=round(time.monotonic()-started,6),native_SDK_science_normal47_validator43_Guest_model_or_service_reruns=0))
    write(PROOF+'SUMMARY.json',dict(status='TINY52_SCOPED_DIRECT_NATIVE_DEFAULT_SDK_PASS_REPORT_ONLY',Root_assignment='m_d1a1a38b99',runtime_authority='m_ce29735a42',
        strict_receipt_sha256=digest(PASS/'VERIFIED_RESULT_RECEIPT.json'),comparisons=52,ordinary_values=50,direct_diagnostics=2,separate_controls=3,selected_original_identities=24,
        complete_original_nodes_claimed=0,R3_remains_failed_zero_credit=True,R2_unrun=True,normal_manifest_sha256=normal_sha,
        untouched_originals=30,untouched_other_V2_files=28,proposed_source_tuple=new_tuple,whole_pack_accepted=False,
        named_partial_purposes=['ttN KSampler_v2 embedded XY','ttN pipeKSampler_v2 embedded XY','ttN pipeKSamplerAdvanced_v2 embedded XY','ttN pipeKSamplerSDXL_v2 embedded XY','ttN pipeKSampler Hold','ttN pipeKSamplerAdvanced Hold','ttN pipeKSamplerSDXL Hold'],
        publication_runtime_jobs=0,publication_file_only_tool_calls=4))
    retain('prepare_source_handoff.py',Path(__file__))
    assert git('ls-tree','-r','-z',BASE,'--',PACK)==tree
    staged={p.relative_to(STAGE).as_posix():dict(sha256=digest(p),bytes=p.stat().st_size,git_mode='100644') for p in sorted(STAGE.rglob('*')) if p.is_file()}
    assert all(name.startswith((PACK+'v2/SECURE_CONVERSION.md',PATCH,PROOF)) for name in staged) and not any(name.endswith('.zip') for name in staged)
    (HERE/'STAGED_FILES.json').write_bytes(encoded(staged));(HERE/'STAGE_SHA256SUMS').write_text(''.join(row['sha256']+'  '+name+'\n' for name,row in staged.items()))
    (HERE/'BASE_PACK_FILES.json').write_bytes(encoded({name:dict(sha256=row['sha256'],bytes=len(row['data']),git_mode=row['mode'],git_oid=row['oid']) for name,row in rows.items()}))
    archive_path=HERE.with_name(HERE.name+'.CORPUS.zip')
    with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in staged:
            item=zipfile.ZipInfo('corpus/'+name,(2026,10,20,0,0,0));item.create_system=3;item.external_attr=0o100644<<16;item.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(item,(STAGE/name).read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None and len(archive.infolist())==len(staged)
        assert {item.filename.removeprefix('corpus/'):sha(archive.read(item)) for item in archive.infolist()}=={name:row['sha256'] for name,row in staged.items()}
    handoff=dict(status='READY_ROOT_TINY_REPORT_ONLY_SCOPED_NATIVE_REVIEW',Root_assignment='m_d1a1a38b99',base_main=BASE,stage_root=str(STAGE),
        staged_files=staged,staged_file_count=len(staged),staged_bytes=sum(v['bytes'] for v in staged.values()),all_modes='100644',
        staged_table_sha256=digest(HERE/'STAGED_FILES.json'),corpus_zip_sha256=digest(archive_path),corpus_zip_bytes=archive_path.stat().st_size,
        current_source_tuple=old_tuple,proposed_source_tuple=new_tuple,report_sha256=sha(report.encode()),
        canonical_pair_sha256=digest(STAGE/(PATCH+'.json')),canonical_diff_sha256=digest(STAGE/(PATCH+'.diff')),
        file_only_receipt_sha256=digest(STAGE/(PROOF+'FILE_ONLY_REPLAY_RECEIPT.json')),file_only_commands=4,independent_pristine_replays=2,
        unchanged_original_files=30,unchanged_other_V2_files=28,normal_manifest_sha256=normal_sha,new_pack_identities=0,
        R3_failure_preserved=True,normal47_validator43_native_model_Guest_or_service_reruns=0,root_or_unrelated_corpus_writes=0,
        registry_admission_or_deployment_actions=0,whole_pack_accepted=False)
    (HERE/'HANDOFF.json').write_bytes(encoded(handoff))
    print(json.dumps({key:handoff[key] for key in ('status','staged_file_count','staged_bytes','corpus_zip_sha256','corpus_zip_bytes','report_sha256','canonical_pair_sha256','canonical_diff_sha256','proposed_source_tuple')},indent=2))

if __name__=='__main__':main()
