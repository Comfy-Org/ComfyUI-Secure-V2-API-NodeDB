"""Tiny52 functional result predicate; stdlib only, no reported code imports."""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath

def read_json(path, limit=1024*1024):
    raw=Path(path).read_bytes()
    if len(raw)>limit:
        raise ValueError('Result-check JSON byte bound exceeded')
    return json.loads(raw)

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def mutate_tag(value,kind,replacement,expected=None):
    if type(value) is list and value and value[0]==kind and (expected is None or value[1]==expected):
        value[:]=replacement
        return True
    children=value.values() if type(value) is dict else value if type(value) is list else []
    return any(mutate_tag(child,kind,replacement,expected) for child in children)

def check(result_path, packet, authorization_message):
    packet=Path(packet)
    require(type(authorization_message) is str and authorization_message.startswith('m_'),'Concrete selected authorization required')
    case_file=packet/'BATCH_CASES.json'
    require(hashlib.sha256(case_file.read_bytes()).hexdigest()=='542adf447ec5458e7c9c6157e0e165892b89d5662c822b390c84f6ee986dae3d','Frozen case matrix changed')
    cases=read_json(case_file)['cases']
    expected={row['case_id']:row for row in cases}
    schemas=read_json(packet/'source/v2/_schemas.json')
    nodes=read_json(packet/'source/v2/secure-nodes.json')['nodes']
    profile=read_json(packet/'inputs/ACTUAL_MAC_PROFILE.json')
    report=read_json(result_path)
    require(report['status']=='PASS_FINITE_TINY_PURE_DIRECT_NATIVE_BATCH_ONLY','Payload is not PASS')
    require(report['authorization_message']==authorization_message,'Wrong selected authorization')
    require(report['attempts']==1 and report['automatic_retries']==0,'Wrong attempt count')
    rows=report['comparisons']
    actual={row['case_id']:row for row in rows}
    require(len(rows)==len(actual)==len(expected)==52 and set(actual)==set(expected),'Missing/duplicate/extra comparison')
    require(report['comparison_count']==52 and report['selected_original_nodes']==24,'Wrong counts')
    require(report['native_direct_diagnostics']==2 and not report['failures'],'Diagnostic count or failure mismatch')
    require(len({row['original_id'] for row in rows})==24,'Wrong distinct node count')
    for name,case in expected.items():
        row=actual[name]
        schema=schemas[case['original_id']]
        require(row['original_id']==case['original_id'] and row['registered_id']==case['registered_id']==schema['id'],'Node identity changed')
        require(row['comparison_kind']==case['comparison_kind'],'Comparison scope changed')
        require(row['declared_permissions']==nodes[schema['id']]['permissions'],'Declared rights changed')
        require(row['matched'] is True and row['original']==row['candidate'],'Unmatched comparison')
        value=row['original']
        if name=='cycle-too-negative':
            require(value=={'kind':'error','type':'IndexError','message':'list index out of range'},'Wrong native diagnostic error')
        else:
            require(value['kind']=='value' and set(value)=={'kind','values','ui'},'Ordinary case unexpectedly failed')
        leaf={'main':'tinyterraNodes.py','legacy':'ttNlegacyNodes.py'}[schema['module']]
        expected_path=PurePosixPath(packet.as_posix())/'source/ttNpy'/leaf
        require(PurePosixPath(row['native_module_path'])==expected_path,'Wrong genuine reference source path')
    require(report['comparator_control_count']==3,'Wrong separate control count')
    controls=report['comparator_controls']
    control_expected=[('corrupt_actual_STRING','text-1','str',['str','wrong STRING'],None),
                      ('numeric_type_change','int-0','int',['str','0'],'0'),
                      ('pipe_seed_change','pipe-out-null-carriers','int',['int','8'],'7')]
    require(len(controls)==3,'Missing or extra separate controls')
    for row,(name,case_id,kind,replacement,prior) in zip(controls,control_expected,strict=True):
        require(row=={'control':name,'source_case':case_id,'detected':True},'Control record mismatch')
        value=actual[case_id]['candidate']
        wrong=copy.deepcopy(value)
        require(mutate_tag(wrong,kind,replacement,prior) and wrong!=value,'Independent negative comparator check failed')
    origins=report['actual_SDK_origins']
    require(set(origins)=={'comfy_api.latest._io_public','comfy_api.latest._sdk_public','comfy_api.latest._sdk'},'Wrong actual SDK origin set')
    for module,row in origins.items():
        relative=module.replace('.','/')+'.py'
        require(PurePosixPath(row['path'])==PurePosixPath(profile['common_site_packages'])/relative,'SDK came from an unselected import root')
        require(row['sha256']==profile['sdk_files'][relative],'Actual SDK leaf hash mismatch')
    require(report['original_full_modules_loaded'] is True and report['original_root_entrypoint_exercised'] is False,'Wrong genuine-original loading scope')
    for key in ('provider_replacements','private_raw_constructor_calls','historical19_or_normal47_validator43_reruns','models_loaded','Guest_launches','graph_expansions','output_domain_writes','seven_restricted_purposes_exercised'):
        require(type(report[key]) is int and report[key]==0,'Unexpected operation: '+key)
    require(report['whole_pack_or_service_or_frontend_or_admission_accepted'] is False,'Scope overclaim')
    return dict(status='PASS_EXACT_TINY52_FUNCTIONAL_RESULT_ONLY',comparisons=52,original_nodes=24,
         ordinary_direct_cases=50,native_direct_diagnostics=2,separate_comparator_controls=3,
         result_sha256=hashlib.sha256(Path(result_path).read_bytes()).hexdigest(),
         source_integrity_and_owner_cleanup_must_be_verified_separately=True,
         whole_pack_or_service_or_Guest_acceptance=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--authorization-message',required=True)
    args=parser.parse_args()
    print(json.dumps(check(args.result,args.packet,args.authorization_message),indent=2,sort_keys=True))
