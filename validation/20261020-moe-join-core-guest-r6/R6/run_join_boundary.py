"""Join-specific payload for the existing MIKE/AMY finite observed job path.

Prepared source only. This is not an independent process observer/framework.
The reviewed existing observer must wrap the trusted normal-site Host.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_bytes())
def require(value,message):
    if not value:raise RuntimeError(message)
def safe(name):
    p=PurePosixPath(name)
    require(name and not p.is_absolute() and p.as_posix()==name and '..' not in p.parts and ':' not in name and '\\' not in name,'Unsafe payload path')
    return p
def verify_packet(expected):
    table=HERE/'INPUT_SHA256SUMS'
    require(sha(table)==expected,'Packet table differs')
    pins={}
    for line in table.read_text().splitlines():
        digest,name=line.split('  ',1)
        safe(name)
        require(name not in pins and re.fullmatch('[0-9a-f]{64}',digest),'Duplicate/bad pin')
        p=HERE/name
        require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(HERE),'Unsafe packet source')
        require(sha(p)==digest,'Packet file changed: '+name)
        pins[name]=digest
    actual={p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file()}
    require(actual==set(pins)|{'INPUT_SHA256SUMS','HANDOFF.json'},'Unexpected packet files')
    return pins
def original(target,binding):
    rows={}
    for line in (HERE/'inputs/ORIGINAL_GIT_TREE.tsv').read_text().splitlines():
        metadata,name=line.split('\t',1)
        safe(name)
        mode,kind,blob=metadata.split()
        require(kind=='blob' and mode=='100644','Unsupported original mode/type')
        rows[name]=blob
    require(len(rows)==43 and set(rows)==set(binding['original_files']),'Original43 inventory differs')
    with zipfile.ZipFile(HERE/'inputs/ORIGINAL.zip') as z:
        infos=[i for i in z.infolist() if not i.is_dir()]
        require(len(infos)==len({i.filename for i in infos})==43 and {i.filename for i in infos}==set(rows),'Original ZIP set differs')
        for i in infos:
            require(i.file_size<16*1024**2 and not i.flag_bits&1,'Unsafe original member')
            data=z.read(i)
            require(hashlib.sha256(data).hexdigest()==binding['original_files'][i.filename],'Pristine original SHA differs')
            require(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==rows[i.filename],'Pristine original Git blob differs')
            out=target/safe(i.filename)
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(data)
            out.chmod(0o644)
def candidate(target,binding):
    require(len(binding['candidate_files'])==14,'Candidate14 count differs')
    for name,digest in binding['candidate_files'].items():
        p=HERE/'candidate'/safe(name)
        require(sha(p)==digest,'Candidate input changed')
        out=target/name
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(p.read_bytes())
        out.chmod(0o644)

def verify_constructor(binding):
    # Compile-to-code only: verify the loaded real constructor against the
    # pinned genuine source without executing a replacement module or class.
    import subprocess
    import types
    source=Path(subprocess.__file__).resolve()
    expected=binding['subprocess_source']
    require(str(source)==expected['path'] and sha(source)==expected['sha256'],'Actual stdlib source differs')
    actual=subprocess.Popen.__init__.__code__
    require(Path(actual.co_filename).resolve()==source and actual.co_firstlineno==binding['Popen_init_first_line'],'Actual constructor origin/line differs')
    module_code=compile(source.read_bytes(),actual.co_filename,'exec',dont_inherit=True,optimize=0)
    class_code=next(c for c in module_code.co_consts if isinstance(c,types.CodeType) and c.co_name=='Popen')
    expected_code=next(c for c in class_code.co_consts if isinstance(c,types.CodeType) and c.co_name=='__init__')
    require(actual==expected_code,'Actual loaded constructor code differs from exact pinned source')
    return dict(path=str(source),sha256=sha(source),first_line=actual.co_firstlineno,compiled_code_equal_to_actual=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--input-manifest-sha256',required=True)
    parser.add_argument('--authorization-message',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if not args.execute:
        print('SOURCE_ONLY_UNRUN; existing observer and separate Root runtime selection required')
        return 2
    require(re.fullmatch('m_[0-9a-f]+',args.authorization_message) and args.authorization_message not in {
        'm_a74054489e','m_a78e155343','m_704635ddc6','m_592e63221c'},'Source preparation/publication mail is not a runtime selection')
    pins=verify_packet(args.input_manifest_sha256)
    require(sys.platform=='darwin' and sys.flags.isolated and not sys.flags.no_site and sys.dont_write_bytecode,'Selected normal-site -I -B trusted Host required')
    spec=load(HERE/'JOB_PLAN.json')
    require(spec['execution_status']=='SOURCE_PREPARED_UNRUN_ROOT_SELECTION_REQUIRED','Wrong job plan')
    constructor=verify_constructor(load(HERE/'inputs/OBSERVER_BINDING.json'))
    output=args.output
    require(output.is_absolute() and not output.exists() and not output.is_symlink(),'Fresh owned absolute output required')
    parent=output.parent.resolve(strict=True)
    require(not parent.is_relative_to(HERE) and not HERE.is_relative_to(output),'Output overlaps packet')
    for raw in spec['protected_reference_roots']:
        protected=Path(raw).resolve()
        require(not output.is_relative_to(protected) and not protected.is_relative_to(output),'Output overlaps selected reference')
    output.mkdir(mode=0o700)
    binding=load(HERE/'inputs/CURRENT_SOURCE_BINDING.json')
    snapshot=output/'packs/comfy-join-prompt/x0832089'
    pack=snapshot/'comfy-join-prompt-HEAD'
    original(pack,binding)
    candidate(pack/'v2',binding)
    fixture_path=HERE/'join_public_guest_fixture.py'
    definition=importlib.util.spec_from_file_location('_moe_join_genuine_core_fixture',fixture_path)
    require(definition is not None and definition.loader is not None,'Fixture source unavailable')
    fixture=importlib.util.module_from_spec(definition)
    definition.loader.exec_module(fixture)
    journal_path=output/'HOST_JOURNAL.jsonl'
    def journal(row):
        with journal_path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row,sort_keys=True)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
    result={
        'status':'FAILED_JOIN_CORE_GUEST_PAYLOAD', 'authorization_message':args.authorization_message,
        'actual_stdlib_constructor_verification':constructor,
        'attempts':1,'automatic_retries':0,'whole_pack_or_managed_or_frontend_or_service_accepted':False,
        'observer_scope':'Existing MIKE finite process/RSS/deadline observer and AMY exact Guest argv/profile/PID observation; payload alone cannot claim outer supervision.'}
    code=1
    try:
        actual=asyncio.run(fixture.exercise(actual_profile=load(HERE/'inputs/ACTUAL_MAC_PROFILE.json'),
            backend_inventory=load(HERE/'inputs/SELECTED_BACKEND_INVENTORY.json'),
            source_binding=binding,fixtures_path=HERE/'inputs/BOUND_FIXTURES.json',
            snapshot=snapshot,owned_root=output,output_path=output/'BOUNDARY_RESULT.json',journal=journal,
            observer_binding=load(HERE/'inputs/OBSERVER_BINDING.json')))
        require(actual['status']=='PASS_CORE_FINALIZATION_AND_ORDINARY_CONFINED_GUEST_ONLY','Actual boundary checks failed')
        require(len(actual['comparisons'])==10 and len(actual['dispatches'])==10 and len(actual['wrong_controls'])==1,'Actual coverage incomplete')
        require(not actual['cleanup_errors'] and actual['normal_path_guest_group_absent'],'Normal-path cleanup failed')
        result.update(status='PASS_JOIN_CORE_AUTOGROW_AND_ORDINARY_GUEST_PAYLOAD_ONLY',
                      boundary_result_sha256=sha(output/'BOUNDARY_RESULT.json'),
                      native_bound_cases=9,core_original_order_diagnostics=1,actual_guest_dispatches=10,wrong_STRING_controls_detected=1)
        code=0
    except BaseException as error:
        result.update(error_type=type(error).__name__,error=str(error)[:4096])
    finally:
        changed=[n for n,d in pins.items() if sha(HERE/n)!=d]
        if changed:
            result.update(status='FAILED_PACKET_INPUT_PRESERVATION',changed_inputs=changed)
            code=1
        (output/'RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
    return code
if __name__=='__main__':
    raise SystemExit(main())
