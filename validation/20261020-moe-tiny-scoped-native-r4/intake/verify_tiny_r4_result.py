"""Independent data-only scoped PASS intake; never executes returned source."""
import hashlib
import json
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parent
out=root/'tinyterra-r4-result-intake-r1-20261020'
src=out/'received'
frozen=root/'tinyterra-onephase-binding-r4-20261020'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
def need(value,message):
    if not value:raise AssertionError(message)
manifest=load(src/'MANIFEST.json')['files']
need(len(manifest)==136,'Manifest count')
need({p.relative_to(src).as_posix() for p in src.rglob('*') if p.is_file()}==set(manifest)|{'MANIFEST.json'},'Extra/missing leaves')
for name,row in manifest.items():
    need(sha(src/name)==row['sha256'] and (src/name).stat().st_size==row['bytes'],'Manifest mismatch: '+name)
need(sha(out/'MIKE_RESULT.zip')=='54b4c07e79bf63c40c77c1c3cfaceb9f37cfa1a8b353f84f0dc453fd39ea01ae','Archive')
for name in ('CONFIG.json','INVOCATION.json','HANDOFF.json','EXTERNAL-CAPTURE-PLAN.json'):
    need((src/'selected-data'/name).read_bytes()==(frozen/name).read_bytes(),'Selected source mismatch: '+name)
need((src/'operators/sdk_tiny_pure52_owner_r2.py').read_bytes()==(frozen/'owner/sdk_tiny_pure52_owner_r2.py').read_bytes(),'Owner source')
need(sha(src/'source-archives/tinyterra-onephase-binding-r4-20261020.SOURCE.zip')=='bc3c78a314b03858d98e484b3d18b49a27808cbbb6e5250bcb383474dbfa190e','Nested selected source seal')
config=load(frozen/'CONFIG.json');capture=load(frozen/'EXTERNAL-CAPTURE-PLAN.json')
need(len(config['packet_files'])==99,'Input count')
for name,row in config['packet_files'].items():
    path=src/'actual-input'/name
    need(sha(path)==row['sha256'] and path.stat().st_size==row['bytes'],'Actual input mismatch: '+name)
    need(path.read_bytes()==(frozen/'packet'/name).read_bytes(),'Frozen input changed: '+name)
owner=load(src/'actual-owner/OWNER_RECEIPT.json')
external=load(src/'external-evidence/EXTERNAL-EXECUTION-RECEIPT.json')
capacity=load(src/'external-evidence/SELECTION-AND-CAPACITY.json')
terminal=load(src/'external-evidence/EXTERNAL-TOOL-TERMINAL.json')
retirement=load(src/'external-evidence/INDEPENDENT-TERMINAL-RETIREMENT.json')
live=load(src/'external-evidence/INDEPENDENT-LIVE-OWNER-WITNESS.json')
authority='m_ce29735a42'
need(owner['authorization_message']==external['authority']==capacity['authority']==authority,'Authority')
need(owner['attempts']==external['attempts']==capacity['attempts']==1 and owner['automatic_retries']==external['automatic_retries']==capacity['automatic_retries']==0,'Attempt count')
need(owner['status']=='PASS_ONE_PHASE_TINY52_NATIVE_OWNER_AND_SCOPED_PAYLOAD_ONLY' and owner['pass_with_evidence'] is True,'Owner did not pass')
need(external['qualification_PASS'] is True and external['comparisons']==52 and external['ordinary_direct_cases']==50 and external['native_direct_diagnostics']==2 and external['separate_comparator_controls']==3 and external['original_nodes']==24,'Wrong scoped counts')
need(owner['exit_code']==external['actual_tool_terminal']['exit_code']==0,'Exit codes')
need(terminal==external['actual_tool_terminal'],'Independent tool terminal mismatch')
actual_argv=[authority if part=='FUTURE_EXACT_ROOT_RELEASE' else part for part in capture['actual_outer_argv_template']]
need(external['actual_outer_argv']==capacity['actual_outer_argv']==actual_argv,'Invocation differs')
need(external['actual_capture_paths']==capacity['capture_paths']==capture['capture_paths'],'Capture paths differ')
need(owner['exact_owner_argv']==actual_argv[7:],'Owner argv differs')
need(capacity['no_added_wrapper_or_prefix'] is True and capacity['only_substitution']=={'FUTURE_EXACT_ROOT_RELEASE':authority},'Extra wrapper/substitution')
need(capacity['source_sha256']==sha(frozen.with_suffix('.SOURCE.zip')) and capacity['config_sha256']==sha(frozen/'CONFIG.json'),'Capacity source binding')
need(capacity['capacity']['reported_free_percent']>0 and capacity['capacity']['free_disk_bytes']>0,'Capacity evidence')
maps={}
for name,count in [('INPUT',99),('FULL-SITE',84917),('COMPONENT-PREFIX',96),('RUNTIME',7),('OPERATOR-CONFIG',6)]:
    before,after=src/'actual-owner'/(name+'-BEFORE.json'),src/'actual-owner'/(name+'-AFTER.json')
    need(before.read_bytes()==after.read_bytes(),'Map bytes differ: '+name)
    data=load(before);need(len(data)==count,'Map count differs: '+name)
    need(external['full_maps'][name]['before_sha256']==sha(before)==external['full_maps'][name]['after_sha256'],'Map receipt hash: '+name)
    maps[name]=dict(rows=count,sha256=sha(before),byte_equal=True)
    if name=='INPUT':need(data==config['packet_files'],'Input map is not the selected table')
    if name in config['baseline_maps']:need(sha(before)==config['baseline_maps'][name]['sha256'],'Baseline changed: '+name)
runtime=load(src/'actual-owner/RUNTIME-BEFORE.json')
profile=load(src/'actual-input/inputs/ACTUAL_MAC_PROFILE.json')
backend=load(src/'actual-input/inputs/SELECTED_BACKEND_INVENTORY.json')
science=load(src/'actual-input/inputs/SCIENCE_BINDING.json')
need(not runtime['mismatches'] and runtime['sdk_files']==profile['sdk_files'] and runtime['core_files']==profile['core_files'],'SDK/Core runtime map')
need(runtime['dependency_files']=={k:v['verified_files'] for k,v in profile['dependency_readbacks'].items()},'Dependency runtime map')
need(runtime['backend_files']=={k:v['sha256'] for k,v in backend['files'].items()} and runtime['science_files']==science['site_file_pins'] and runtime['python_sha256']==profile['python_sha256'],'Backend/science/Python runtime map')
operator=load(src/'actual-owner/OPERATOR-CONFIG-BEFORE.json')
expected={**config['operator_pins'],config['pyvenv_config']:config['pyvenv_config_sha256'],actual_argv[7]:config['owner_sha256'],actual_argv[actual_argv.index('--config')+1]:sha(frozen/'CONFIG.json')}
expected.update({v['path']:v['sha256'] for v in config['baseline_maps'].values()})
need({name:row['sha256'] for name,row in operator.items()}==expected,'Complete operator/config map')
cleanup=owner['cleanup']
need(cleanup['confirmed'] is True and not cleanup['errors'] and not cleanup['error_details'] and cleanup['seconds']<=15,'Cleanup failed')
need(len(cleanup['independent_observations'])>=2 and all(row=={'pid_absent':True,'group_absent':True,'remaining':[]} for row in cleanup['independent_observations'][-2:]),'Payload absence')
need(owner['cleanup_signal_decision']=={'leader_terminal':True,'other_owned':[],'signals_required':False},'Wrong retirement branch')
child=owner['recorded_at_creation']['pid'];need(child==owner['recorded_at_creation']['pgid']==23285,'Created child identity')
need(len(live['rows'])==2 and live['rows'][1]['ppid']==live['rows'][0]['pid'],'Live owner ancestry')
pids={row['pid'] for row in live['rows']}|{child};groups={row['pgid'] for row in live['rows']}|{child}
need(set(retirement['pids'])==pids and set(retirement['groups'])==groups and retirement['all_absent'] and retirement['no_signals_sent'],'Retirement identity list')
need(len(retirement['observations'])==2 and retirement==external['independent_retirement'],'Independent observer count/receipt')
for index,row in enumerate(retirement['observations']):
    need(set(map(int,row['pids_absent']))==pids and all(v is True for v in row['pids_absent'].values()),'PID absence')
    need(set(map(int,row['groups_absent']))==groups and all(v is True for v in row['groups_absent'].values()),'PGID absence')
    need(not row['remaining'] and not row['errors'],'Observer error/residue')
    ps=src/'external-evidence'/('INDEPENDENT-TERMINAL-PS-'+str(index)+'.txt')
    need(sha(ps)==row['raw_ps_sha256'],'Raw ps hash')
    for line in ps.read_text().splitlines():
        fields=line.split(None,4)
        if len(fields)>=3 and all(f.isdigit() for f in fields[:3]):
            need(int(fields[0]) not in pids and int(fields[2]) not in groups,'Raw ps contains recorded owner identity')
need((src/'actual-owner/HARD-DEADLINE-UNCONFIRMED.json').stat().st_size==0 and not owner['remaining_marked_processes'] and owner['full_maps_equal'] is True,'Deadline/residue/maps')
need(owner['whole_owner_seconds']<120 and owner['cancelled_by_signal'] is None and not owner['hard_memory_or_cpu_quota_claim'],'Clock/cancellation/quota')
need(owner['rss_watchdog_scope']=='sampled_payload_and_descendants_only_owner_excluded' and owner['aggregate_rss_peak_bytes']<=1073741824,'RSS scope/limit')
trace=(src/'actual-owner/stderr.txt').read_text()
need('Traceback (most recent call last)' not in trace and not owner['errors'],'Unexpected payload/owner error')
result_path=src/'actual-owner/actual-output/RESULT.json'
need(result_path.is_file() and not result_path.is_symlink() and result_path.stat().st_size<=1024**2,'Unsafe/missing result')
need(sha(result_path)==owner['payload_result_sha256']==external['worker_result_sha256'],'Raw result hash mismatch')
import importlib.util
own_checker=root/'tiny52_data_predicate_intake_20261020.py'
need(sha(own_checker)=='14506bc5d72792be276bedb35da3ca3bacd695d743f8fdbfbb086263073448bc','Own predicate validator changed')
spec=importlib.util.spec_from_file_location('own_tiny52_data_predicate',own_checker)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
payload_predicate=module.check(result_path,frozen/'packet',authority,reported_packet_root=config['packet_root'])
need(owner['payload_result']==payload_predicate,'Independent typed result predicate differs from owner')
need(owner['whole_owner_seconds_limit']==120 and owner['payload_seconds_limit']==90 and owner['cleanup_seconds_limit']==15,'Limits changed')
need(owner['payload_and_cleanup_seconds']<=105,'Payload+cleanup envelope')
need(external['normal_generation_runs']==0 and external['Guest_or_model_or_public_graph_or_service_or_whole_pack_qualification'] is False,'Scope overclaim')
owner_stdout=load(src/'external-evidence/OWNER-STDOUT.txt')
need(owner_stdout['status']==owner['status'] and owner_stdout['pass_with_evidence'] is True and not owner_stdout['errors'],'Actual owner stdout')
need(external['owner_receipt_sha256']==sha(src/'actual-owner/OWNER_RECEIPT.json'),'Owner receipt digest')

record=dict(status='VERIFIED_PASS_SCOPED_TINY52_DIRECT_NATIVE_DEFAULT_SDK_ONLY',reviewer='MOE',
    archive_sha256=sha(out/'MIKE_RESULT.zip'),archive_bytes=(out/'MIKE_RESULT.zip').stat().st_size,members=137,pins_verified=136,
    authority=authority,attempts=1,automatic_retries=0,owner_sha256=config['owner_sha256'],worker_sha256=sha(src/'actual-input/worker.py'),
    config_sha256=sha(src/'selected-data/CONFIG.json'),owner_receipt_sha256=sha(src/'actual-owner/OWNER_RECEIPT.json'),external_receipt_sha256=sha(src/'external-evidence/EXTERNAL-EXECUTION-RECEIPT.json'),
    comparisons=52,ordinary_direct_cases=50,native_direct_diagnostics=2,separate_comparator_controls=3,selected_original_nodes=24,actual_outer_exit_code=0,payload_exit_code=0,
    payload_predicate=payload_predicate,payload_result_sha256=sha(result_path),
    full_maps=maps,selected_runtime_maps_independently_matched=True,owner_cleanup=cleanup,independent_pids=sorted(pids),independent_groups=sorted(groups),twice_absence_verified_against_raw_ps=True,
    whole_owner_seconds=owner['whole_owner_seconds'],payload_descendant_sampled_RSS_peak_bytes=owner['aggregate_rss_peak_bytes'],owner_excluded_from_RSS_sample=True,
    socket_evidence_scope='Producer scanned only owned output tree for filesystem sockets; no whole-system socket-table claim',
    remaining_filesystem_sockets=external['remaining_sockets'],R3_failure_preserved=True,new_runtime_selected=False,
    no_models_sampling_Guest_graph_normal_generation_service_frontend_or_whole_pack_credit=True,
    external_maxrss_bytes_darwin_separately_reported=external['external_maxrss_bytes_darwin'],
    acceptance_scope='52 finite purpose comparisons across24 originals, not full24-node or43-node completion',
    local_intake='Own stdlib ZIP/JSON/hash/text checks only; no returned code, worker, SDK or science imported/executed')
need(record['remaining_filesystem_sockets']==[],'Owned output filesystem socket residue')
receipt=out/'VERIFIED_RESULT_RECEIPT.json';receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(status=record['status'],receipt_sha256=sha(receipt),comparisons=52,ordinary=50,diagnostics=2,controls=3),indent=2))
