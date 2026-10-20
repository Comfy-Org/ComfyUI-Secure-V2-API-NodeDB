"""Independent stdlib-only data verification. No supplied code is imported/run."""
import ast
import collections
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'prompt-combinator3-actual-result-intake-r1-20261020'
ARCHIVE=Path('/mnt/c/Users/benjc/popbot/sent_files/PROMPT-COMBINATOR3-R1-ATTEMPT1-RESULT-20261020.zip')
MANAGER=ROOT.parent.parent/'chat_f38536805264'
CHECKS=[]
def check(ok,label):
    if not ok:raise AssertionError(label)
    CHECKS.append(label)
def digest(data):return hashlib.sha256(data).hexdigest()
def write(name,value):(OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def kind(value,label):
    check(type(value) is dict and 'kind' in value,label+' typed record')
    k=value['kind']
    if k in ('tuple','list'):
        check(set(value)=={'kind','items'} and type(value['items']) is list,label+' container')
        for i,v in enumerate(value['items']):kind(v,label+'/'+str(i))
    elif k=='dict':
        check(set(value)=={'kind','items'} and type(value['items']) is list,label+' dictionary')
        for pair in value['items']:
            check(type(pair) is list and len(pair)==2,label+' key/value pair')
            for v in pair:kind(v,label+'/entry')
    else:
        types={'str':str,'bool':bool,'int':int,'float':float,'NoneType':type(None)}
        check(k in types and set(value)=={'kind','value'} and type(value['value']) is types[k],label+' exact scalar type')

with zipfile.ZipFile(ARCHIVE) as Z:
    names=Z.namelist();infos={v.filename:v for v in Z.infolist()}
    def data(name):return Z.read(name)
    def load(name):return json.loads(data(name))
    raw_manifest=load('MANIFEST.json');pins={r['path']:r for r in raw_manifest['files']}
    check(len(names)==len(set(names))==3143 and len(pins)==3142,'Archive member/pin counts')
    check(set(pins)==set(names)-{'MANIFEST.json'},'Exact complete manifest member set')
    for name,row in pins.items():
        raw=data(name)
        check(len(raw)==row['bytes'] and digest(raw)==row['sha256'], 'Archive pin '+name)
        check((infos[name].external_attr>>16)&0o777==row['mode'],'Archive mode '+name)
    check(raw_manifest['receipt']==load('capture/EXTERNAL-EXECUTION-RECEIPT.json'),'External receipt bound by archive')
    def inventory(prefix):
        return {n.removeprefix(prefix):dict(sha256=r['sha256'],mode=r['mode']) for n,r in pins.items() if n.startswith(prefix)}
    def full_inventory(prefix):
        return {n.removeprefix(prefix):dict(sha256=r['sha256'],bytes=r['bytes'],mode=r['mode']) for n,r in pins.items() if n.startswith(prefix)}
    packet=inventory('packet/')
    inner=load('packet/INPUTS.json')['files']
    check(len(inner)==640 and len(packet)==641,'Inner packet exact member count')
    for row in inner:
        check(pins['packet/'+row['path']]['sha256']==row['sha256'] and pins['packet/'+row['path']]['bytes']==row['bytes'],'Inner pin '+row['path'])
    check(set(r['path'] for r in inner)|{'INPUTS.json'}==set(packet),'Inner complete packet pins')
    config=load('prepared/CONFIG.json');source_config=load('source-bindings/CONFIG.SOURCE.json')
    check(data('prepared/CONFIG.json')==data('source-bindings/CONFIG.json'),'Actual config copies byte exact')
    changed={k for k in set(config)|set(source_config) if config.get(k)!=source_config.get(k)}
    def rebind(value):
        if type(value) is dict:return {k:rebind(v) for k,v in value.items()}
        if type(value) is list:return [rebind(v) for v in value]
        if type(value) is str and (value==source_config['packet'] or value.startswith(source_config['packet']+'/')):
            return config['packet']+value.removeprefix(source_config['packet'])
        return value
    expected_config=rebind(source_config)
    expected_config.update(execution_selected=True,runtime_authority='m_7972430879')
    check(config==expected_config,'Actual config only exact packet-root rebinding and selection/authority delta')
    check(config['execution_selected'] is True and config['runtime_authority']=='m_7972430879','Single actual runtime selection')
    config_hash=digest(data('prepared/CONFIG.json'))
    check(config_hash=='f3c90ac030a48089a0918da04a2b457ab7053b441595ba67f3a6be8f73a816a6','Selected actual config SHA')
    check(len(config['input_files'])==641,'Actual config complete packet inventory')
    for name,row in config['input_files'].items():
        check(row['sha256']==pins['packet/'+name]['sha256'] and row['bytes']==pins['packet/'+name]['bytes'],'Config packet pin '+name)
    root_config=MANAGER/'coordination/prompt-combinator-runtime-metadata-20261020-r1/PROMPT_COMBINATOR_CONFIG.R1.DRAFT.json'
    check(root_config.read_bytes()==data('source-bindings/CONFIG.SOURCE.json'),'Independent Root reviewed source config correspondence')
    review=json.loads((MANAGER/'coordination/review-prompt-combinator3-source-20261020-r1/REVIEW.json').read_bytes())
    for role,name in [('worker','packet/worker.py'),('owner','packet/operator-scripts/sdk_prompt_combinator_outer_r1.py'),('handoff','packet/HANDOFF.json'),('inputs','packet/INPUTS.json')]:
        check(review['source'][role]['sha256']==pins[name]['sha256'],'Reviewed source lineage '+role)
    check(pins['packet/generate_popular_pack_manifest.py']['sha256']=='f929ea628fec11c5cf695a3bee0928866b128050654acc2abf25415c3af9ad2f','Canonical actual generator source')
    for key,rel in [('handoff','HANDOFF.json'),('profile','inputs/ACTUAL_MAC_PROFILE.json'),('backend','inputs/SELECTED_BACKEND_INVENTORY.json'),('science','inputs/SCIENCE_BINDING.json'),('baseline_site_map','inputs/RETAINED_FULL_SITE_MAP.json'),('baseline_component_map','inputs/RETAINED_COMPONENT_MAP.json')]:
        check(config[key]['sha256']==pins['packet/'+rel]['sha256'],'Selected binding '+key)
    binding=load('output/BINDINGS-BEFORE.json')
    check(binding==load('output/BINDINGS-AFTER.json'),'All selected binding identities preserved')
    for key,value in binding.items():check(config[key]['sha256']==value,'Binding hash joins '+key)
    maps={}
    for label,expected,external in [('INPUT',641,'INPUT'),('FULL-SITE',84917,'FULL-SITE'),('COMPONENT-PREFIX',96,'COMPONENT-PREFIX'),('RUNTIME',7,'RUNTIME')]:
        before=data('output/'+label+'-BEFORE.json');after=data('output/'+label+'-AFTER.json')
        check(before==after and load('capture/EXTERNAL-'+external+'-BEFORE.json')==json.loads(before),'Before/after independent map '+label)
        value=json.loads(before);check(len(value)==expected,'Full map entry count '+label)
        maps[label]=dict(entries=len(value),sha256=digest(before),before_after_and_external_equal=True)
    check(data('capture/EXTERNAL-OPERATOR-CONFIG-BEFORE.json')==data('capture/EXTERNAL-OPERATOR-CONFIG-AFTER.json'),'Operator/config complete map equality')
    opmap=load('capture/EXTERNAL-OPERATOR-CONFIG-BEFORE.json');check(len(opmap)==18,'Operator/config18 entries')
    check(data('output/OPERATOR-SOURCES-BEFORE.json')==data('output/OPERATOR-SOURCES-AFTER.json'),'Owner/helper source preservation')
    inputmap=load('output/INPUT-BEFORE.json')
    check(inputmap==full_inventory('packet/'),'All641 actual pre/post input bytes/modes join archive source')
    for role,row in config['operator_sources'].items():
        rel=row['path'].removeprefix(config['packet']+'/')
        check(rel!=row['path'] and row['sha256']==pins['packet/'+rel]['sha256'],'Actual operator executable pin '+role)
    for path,row in opmap.items():
        if path.startswith(config['packet']+'/'):
            ref='packet/'+path.removeprefix(config['packet']+'/')
        elif '/prompt-combinator-owner-r3-prepared/' in path:
            ref='source-bindings/'+path.rsplit('/',1)[1]
        elif path.endswith('/sdk_prepare_prompt_combinator_r3_attempt1.py'):
            ref='operator-source/sdk_prepare_prompt_combinator_r3_attempt1.py'
        else:
            check(path in (config['interpreter_configuration']['path'],config['subprocess_source']['path']),'Known externally mapped nonarchived source')
            expected=config['interpreter_configuration'] if path==config['interpreter_configuration']['path'] else config['subprocess_source']
            check(row['sha256']==expected['sha256'],'External stdlib/config source pin join')
            continue
        check(pins[ref]['sha256']==row['sha256'] and pins[ref]['bytes']==row['bytes'] and pins[ref]['mode']==row['mode'],'External complete operator/config source bytes '+path)
    profile=load('packet/inputs/ACTUAL_MAC_PROFILE.json');backend=load('packet/inputs/SELECTED_BACKEND_INVENTORY.json');science=load('packet/inputs/SCIENCE_BINDING.json')
    rt=load('output/RUNTIME-BEFORE.json');site=load('output/FULL-SITE-BEFORE.json');component=load('output/COMPONENT-PREFIX-BEFORE.json')
    check(not rt['mismatches'] and rt['python_sha256']==profile['python_sha256']=='e81eb555fbfb8c6bd4ea528c60d4b3a8f9a94e53c31b0470f4f1524b4b9548c0','Actual Python binary profile')
    for key in ('sdk_files','core_files'):
        check(rt[key]==profile[key],'Actual runtime/profile full table '+key)
    check(rt['dependency_files']=={k:v['verified_files'] for k,v in profile['dependency_readbacks'].items()},'Actual content-record Kitchen/Aimdo files; duplicate metadata not version authority')
    check(rt['backend_files']=={k:v['sha256'] for k,v in backend['files'].items()},'Actual complete backend source table')
    check(rt['science_files']==science['site_file_pins'],'Actual science metadata/table')
    check(rt['backend_files']['backend/comfy_secure_nodes/packpatch.py']=='268df53fa640b4eb42ee342850e686790016ad15a207cf6a5a7e57ee5d5953a2','Canonical actual268 patch implementation')
    for name,d in rt['sdk_files'].items():check(site[name]['sha256']==d,'Full site to SDK join '+name)
    for name,d in science['site_file_pins'].items():check(site[name]['sha256']==d,'Full site to science join '+name)
    origins=load('output/ACTUAL-IMPORT-ORIGINS.json')['actual_loaded_modules']
    for name,row in origins.items():
        if not row['imported']:continue
        path=row['path'];matches=[]
        for root,table in [(profile['common_site_packages'],site),(profile['core_source'],rt['core_files']),(backend['backend_source_root'],{k.removeprefix('backend/'):v for k,v in rt['backend_files'].items()}),(config['component_prefix'],component)]:
            if path.startswith(root+'/'):
                found=table.get(path.removeprefix(root+'/'))
                if found is not None:matches.append(found['sha256'] if type(found) is dict else found)
        check(row['sha256'] in matches,'Actual imported module source origin '+name)
    check(origins['torch']['version'].split('+')[0]=='2.13.0' and origins['numpy']['version']=='2.4.6','Actual observed Torch/numpy versions')
    owner=load('output/OUTER_RECEIPT.json');selection=load('capture/SELECTION-AND-CAPACITY.json');invocation=load('prepared/INVOCATION.json');external=load('capture/EXTERNAL-EXECUTION-RECEIPT.json')
    check(data('prepared/INVOCATION.json')==data('source-bindings/INVOCATION.ACTUAL.json'),'Actual invocation copies exact')
    check(invocation['argv']==selection['actual_outer_argv'] and invocation['runtime_authority']==config['runtime_authority'],'Invocation selection joins')
    check(invocation['config_sha256']==owner['config_sha256']==selection['actual_config_sha256']==config_hash,'Actual config invocation/owner joins')
    check(selection['invocation_sha256']==digest(data('prepared/INVOCATION.json')),'Invocation selected exact SHA')
    check(owner['attempts']==1 and owner['automatic_retries']==0 and owner['authorization_message']==config['runtime_authority'],'One actual owner attempt, no retries')
    check(owner['status']=='PASS_SHARED_OWNER_AND_SCOPED_PAYLOAD_ONLY' and owner['exit_code']==0,'Actual owner terminal status')
    for field in ('monitor_errors','cleanup_errors','remaining_owned_processes','remaining_socket_paths','pending_control_signals'):check(not owner[field],'Owner clean '+field)
    for field in ('inputs_unchanged','runtime_unchanged','site_unchanged','component_prefix_unchanged','config_unchanged','observer_binding_unchanged','binding_files_unchanged','operator_sources_unchanged','controller_group_absent'):check(owner[field] is True,'Owner positive preservation '+field)
    check(not owner['watchdog_fired'] and not owner['whole_owner_deadline_fired'] and owner['whole_owner_deadline_includes_preflight_and_postflight'],'Actual deadline coverage')
    check(owner['limits']==dict(cleanup_seconds=15,outer_seconds=200,work_seconds=180),'Actual accepted finite limits')
    check(owner['aggregate_rss_peak_bytes']==702775296<2147483648 and owner['hard_memory_or_CPU_quota'] is False,'Sampled RSS within inherited2GiB; no hard-quota claim')
    native_time=data('capture/time.txt').decode()
    check('35.79 real' in native_time and '989872128  maximum resident set size' in native_time,'Distinct native time/RSS raw metrics retained')
    check(owner['execution_wall_seconds']<200 and owner['payload_and_cleanup_wall_seconds']<195,'Whole and payload/cleanup measured bounds')
    check(owner['pyvenv_cfg_sha256_before']==owner['pyvenv_cfg_sha256_after']==config['interpreter_configuration']['sha256'],'Normal site interpreter configuration unchanged')
    check(owner['stdlib_sha256_before']==owner['stdlib_sha256_after']==config['subprocess_source']['sha256'],'Actual constructor source unchanged')
    result=load('output/actual-output/RESULT.json');cases=load('packet/CASES.json');rows=result['rows']
    check(data('output/actual-output/RESULT.json')==data('output/actual-output/WORKER_RESULT.json'),'Worker result copies byte exact')
    check(load('output/actual-output/PARTIAL_ROWS.json')==rows,'Progress raw rows join final rows')
    check(result['status']==config['success_status']==owner['payload_status'] and result['stage']=='complete','Worker completed selected exact result stage')
    check(result['authorization_message']==config['runtime_authority'],'Worker selected authority')
    check(len(cases)==len(rows)==100 and len({c['case_id'] for c in cases})==100,'100 unique actual case identities')
    counts=collections.Counter();pairs={};random_cases=[]
    for case,row in zip(cases,rows):
        check(row['case_id']==case['case_id'] and row['node']==case['node'],'Raw case identity '+case['case_id'])
        check(row['native']['outcome']==row['Guest']['outcome']=='return','Ordinary returned outcomes '+case['case_id'])
        for route in ('native','Guest'):
            observation=row[route]
            check(set(observation)=={'outcome','result','ui'},'Complete outcome fields '+case['case_id']+'/'+route)
            kind(observation['result'],case['case_id']+'/'+route+'/result');kind(observation['ui'],case['case_id']+'/'+route+'/ui')
            check(observation['result']['kind']=='tuple' and len(observation['result']['items'])==3,'Exact three-output tuple '+case['case_id']+'/'+route)
        check(row['native']==row['Guest'] and row['equal'] is True and row['inputs_unchanged'] is True,'Independent complete typed result/UI equality '+case['case_id'])
        check(row['ignored_seed_pair']==case.get('ignored_seed_pair') and row['fixture_seed']==case.get('fixture_seed'),'Raw case fixture metadata '+case['case_id'])
        counts[row['node']]+=1
        if row['ignored_seed_pair']:pairs.setdefault(row['ignored_seed_pair'],[]).append((case,row))
        if row['node']=='PromptCombinatorRandomPrompt':random_cases.append((case,row))
    check(dict(counts)==dict(PromptCombinator=36,PromptCombinatorMerger=32,PromptCombinatorRandomPrompt=32),'Counts derived from raw matched rows36/32/32')
    check(len(pairs)==16 and all(len(p)==2 for p in pairs.values()),'Sixteen actual ignored-seed pairs')
    for pair,entries in pairs.items():
        (ca,ra),(cb,rb)=entries
        check(ca['fixture_seed']==cb['fixture_seed'] and ca['inputs']['seed']!=cb['inputs']['seed'],'Ignored seed changed only authored production seed '+pair)
        check({k:v for k,v in ca['inputs'].items() if k!='seed'}=={k:v for k,v in cb['inputs'].items() if k!='seed'},'Other ignored-seed inputs exact '+pair)
        check(ra['native']==rb['native'] and ra['Guest']==rb['Guest'],'Both routes ignore production seed '+pair)
    births=result['creation_observation']['assigned_PID_events'];check(len(births)==1,'One recorded Guest creation')
    pid=births[0]['assigned_child_pid'];check(pid==55643 and births[0]['observed_pgid']==pid and births[0]['start_new_session'] is True,'Guest assigned PID/session group')
    check(not result['creation_observation']['errors'] and result['actual_startup']['pid']==pid and result['actual_startup']['sandbox_kind']=='seatbelt','Actual required Guest startup')
    intent=result['creation_observation']['intent_events'][0]
    check(intent['profile_sha256']==digest(data('output/actual-output/GUEST_PROFILE_0.sb')),'Actual saved Seatbelt profile bytes')
    journal=[json.loads(line) for line in data('output/actual-output/GUEST_CREATION.jsonl').decode().splitlines()]
    check(len(journal)==3 and journal[0]['event']=='observer-installed','Durable constructor observer installation')
    check(all(journal[1].get(k)==v for k,v in intent.items()) and all(journal[2].get(k)==v for k,v in births[0].items()),'Durable constructor journal raw event joins')
    check(owner['creation_journal']['raw_sha256']==pins['output/actual-output/GUEST_CREATION.jsonl']['sha256'] and not owner['creation_journal']['errors'],'Owner independent raw journal pin')
    check(result['actual_startup']['actual_profile_matches_genuine_supported_source_recipe'] is True,'Genuine actual profile recipe reported by accepted observer')
    rng=result['rng_fixture_rows'];check(len(rng)==len(random_cases)==32,'32 separate actual RNG fixture acknowledgements')
    for fixture,(case,_) in zip(rng,random_cases):
        check(fixture['seed']==case['fixture_seed'] and fixture['Guest_PID']==pid and fixture['returned'] is True,'RNG fixture case/PID join '+case['case_id'])
        check(fixture['actual_acknowledgement']==dict(kind='tuple',items=[dict(kind='int',value=case['fixture_seed'])]),'Actual exact RNG acknowledgement '+case['case_id'])
    check(result['native_cases']==result['Guest_dispatches']==100 and result['all_actual_Guest_dispatches']==132 and result['Guest_instances']==1,'Separate production100 and fixture32 accounting')
    check(not result['ordinary_mismatches'] and not result['cleanup_errors'] and result['normal_path_guest_group_absent'],'Actual payload clean exit')
    expected_controls={'wrong-output-arity','wrong-custom-ui','changed-scalar-type','ordinary-versus-error','paired-matching-errors'}
    check(len(result['controls'])==5 and {r['name'] for r in result['controls']}==expected_controls and all(r['refused'] is True for r in result['controls']),'Five separately recorded comparator controls')
    retirement=load('capture/INDEPENDENT-TERMINAL-RETIREMENT.json');live=load('capture/INDEPENDENT-LIVE-WITNESSES.json')
    check(not live['errors'] and retirement['all_absent'] is True,'Independent live/terminal capture completed')
    check(set(retirement['pids'])=={55250,55265,55266,55578,55641,55643} and set(retirement['groups'])=={55250,55265,55578,55643},'Six actual PIDs and four actual groups')
    check(len(retirement['observations'])==2,'Two independent retirement probes')
    for obs in retirement['observations']:
        check(set(map(int,obs['pids']))==set(retirement['pids']) and all(v is True for v in obs['pids'].values()),'All actual PIDs absent in terminal probe')
        check(set(map(int,obs['groups']))==set(retirement['groups']) and all(v is True for v in obs['groups'].values()) and not obs['remaining_marked_processes'],'All actual groups absent in terminal probe')
    identities=retirement['recorded_pid_to_actual_pgid']
    check(identities[str(pid)]['ppid']==retirement['controller_pid']==55578 and identities['55578']['ppid']==retirement['owner_pid']==55266 and identities['55266']['ppid']==retirement['time_pid']==55265,'Actual Guest/controller/owner/time lineage')
    for identity in identities.values():check(identity['pgid'] in retirement['groups'] and identity['observed_pgids']==[identity['pgid']],'Recorded actual PGID join '+str(identity['pid']))
    check(retirement['Guest_live_identity_independently_witnessed'] is True and external['actual_Guest_live_identity']['pid']==pid,'Guest independently live-witnessed')
    check(all(not r['socket'] for r in retirement['residual_readback']),'No remaining socket in retained temporary root readback')
    check(retirement['not_an_exhaustive_transient_child_census'] is True and not owner['pre_fsync_kill_gap_closed'],'Preserve explicit transient census / pre-fsync limitation')
    check({r['pid'] for r in owner['observed_processes']}<=set(retirement['pids']),'Every owner sampled PID joins terminal retirement')
    for k,identity in live['live_identities'].items():
        actual=identities[k]
        check(all(identity.get(field)==actual.get(field) for field in ('pid','ppid','pgid','uid','started','sid')),'Independent raw live identity joins terminal identity '+k)
    root='output/actual-output/node-root/packs/comfyui-prompt-combinator/x3576ace/ComfyUI-Prompt-Combinator-HEAD/'
    tested=inventory(root);original=inventory('packet/original/');candidate=inventory('packet/candidate/')
    check({k:v for k,v in tested.items() if not k.startswith('v2/')}==original,'All tested original bytes/modes equal packet302')
    tested_v2={k.removeprefix('v2/'):v for k,v in tested.items() if k.startswith('v2/')}
    check(set(tested_v2)==set(candidate)|{'secure-nodes.json'} and all(tested_v2[k]==v for k,v in candidate.items()),'All tested production bytes/modes exact; only normal manifest added')
    verification=load('packet/reference/SOURCE_VERIFICATION.json')
    check(verification['commit']=='3576ace3f2776918c1046b6674fbe345a46dba2f' and len(verification['files'])==len(original)==302,'Immutable original full Git census source join')
    for row in verification['files']:
        raw=data('packet/original/'+row['path'])
        check(digest(raw)==row['sha256'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['git_blob'],'Original actual Git blob '+row['path'])
        check(original[row['path']]['mode']==int(row['git_mode'],8)&0o777,'Original actual Git mode '+row['path'])
    orig_text=data('packet/original/prompt_combinator.py').decode();alg_text=data('packet/candidate/_algorithms.py').decode()
    original_ast=ast.parse(orig_text);algorithm_ast=ast.parse(alg_text)
    for node in counts:
        a=next(n for n in original_ast.body if isinstance(n,ast.ClassDef) and n.name==node)
        b=next(n for n in algorithm_ast.body if isinstance(n,ast.ClassDef) and n.name==node)
        check(ast.get_source_segment(orig_text,a)==ast.get_source_segment(alg_text,b),'Exact original computation class source '+node)
    check(data('packet/original/LICENSE')==data('packet/candidate/LICENSE'),'License byte preservation')
    manifest=load(root+'v2/secure-nodes.json');check(set(manifest['nodes'])==set(counts),'Actual normal manifest three production IDs only')
    check(result['manifest']==dict(normal_generator_runs=1,sha256=pins[root+'v2/secure-nodes.json']['sha256']),'Actual normal generation manifest origin hash')
    for node,row in manifest['nodes'].items():check(row['module']=='nodes' and row['class']==node and row['sdk_refs'] is True and row['permissions']==[],'Actual generated public registration '+node)
    for source in load('packet/SOURCE_PORT.json')['rows']:
        schema=manifest['nodes'][source['node_id']]['schema'];attrs=schema['attrs']
        check(attrs['node_id']==source['node_id'] and attrs['display_name']==source['display_name'] and attrs['category']==source['category'],'Actual encoded original schema identity '+source['node_id'])
        check([r['attrs']['id'] for r in schema['inputs']]==source['required_order']+source['optional_order'],'Actual encoded source input order '+source['node_id'])
        check([r['attrs']['optional'] for r in schema['inputs']]==[False]*len(source['required_order'])+[True]*len(source['optional_order']),'Actual encoded input optionality '+source['node_id'])
        check(attrs['is_input_list']==source['INPUT_IS_LIST'] and attrs['is_output_node']==source['OUTPUT_NODE'],'Actual encoded source node flags '+source['node_id'])
        check([r['attrs']['is_output_list'] for r in schema['outputs']]==source['OUTPUT_IS_LIST'],'Actual encoded output list flags '+source['node_id'])
    patchroot='output/actual-output/patches/comfyui-prompt-combinator/x3576ace/comfyui-prompt-combinator-x3576ace'
    patch=load(patchroot+'.json');check(patch['format']=='comfy-pack-patch/1' and patch['pack']=='comfyui-prompt-combinator' and patch['key']=='x3576ace','Actual canonical distribution identity')
    patch_names=set()
    for row in patch['files']:
        name=row['path'];check(name not in patch_names,'Unique canonical pair path '+name);patch_names.add(name)
        if row['op']=='delete':check(name in original and name not in tested_v2,'Canonical deletion '+name)
        else:
            check(name in tested_v2 and row['mode']==tested_v2[name]['mode'],'Canonical target mode '+name)
            check((row.get('v2_sha256') or row.get('base_sha256'))==tested_v2[name]['sha256'],'Canonical target source hash '+name)
        if row['op'] in ('copy','convert','delete'):check(row['base_sha256']==original[name]['sha256'],'Canonical original base hash '+name)
    check(patch_names==set(original)|set(tested_v2),'Exact full canonical pair file set')
    with zipfile.ZipFile(io.BytesIO(data(patchroot+'.zip'))) as bundle:
        bundle_names=bundle.namelist()
        check(len(bundle_names)==len(set(bundle_names))==2,'Canonical bundle exact two pair members')
        check(sorted(bundle.read(n) for n in bundle_names)==sorted([data(patchroot+'.json'),data(patchroot+'.diff')]),'Bundle carries exact generated pair bytes')
    check(len(result['schemas'])==3 and {r['node'] for r in result['schemas']}==set(counts) and all(r['ordered_schema_exact'] is True and r['outputs']==3 for r in result['schemas']),'Actual three original-schema comparisons')
    for mode in ('pair','bundle'):
        prefix='output/actual-output/replay-'+mode+'/comfyui-prompt-combinator/x3576ace/ComfyUI-Prompt-Combinator-HEAD/'
        check(inventory(prefix)==tested,'Raw complete pristine replay '+mode)
        before=load('output/actual-output/CHANGED-BASE-'+mode+'-BEFORE.json');after=load('output/actual-output/CHANGED-BASE-'+mode+'-AFTER.json')
        check(before==after,'Raw unchanged wrong-base refusal inventories '+mode)
        broken=inventory('output/actual-output/changed-base-'+mode+'/comfyui-prompt-combinator/x3576ace/')
        check(broken==after,'Actual changed-base file bytes match persisted inventory '+mode)
        independent_broken=load('capture/CHANGED-BASE-'+mode.upper()+'-ACTUAL-AFTER-INVENTORY.json')
        check(independent_broken==full_inventory('output/actual-output/changed-base-'+mode+'/comfyui-prompt-combinator/x3576ace/ComfyUI-Prompt-Combinator-HEAD/'),'External actual wrong-base state independently matches '+mode)
        command=next(v for v in result['commands'] if v['pristine_replay']==mode)
        check(command['changed_base_refused']['exception']=='PackPatchError' and 'base file does not match the manifest: __init__.py' in command['changed_base_refused']['message'],'Specific actual wrong-base hash refusal '+mode)
    gallery=load('packet/candidate/GALLERY_API_GAP.json')
    check(gallery['status']=='FORMAL_CURRENT_RELEASE_PURPOSE_REFUSAL','Fourth original gallery purpose formally refused')
    check(result['whole_pack_service_or_managed_acceptance'] is False and result['browser_frontend_or_public_graph_runs']==0 and result['model_forwards']==0,'No broadened whole-pack/service/frontend/model credit')
    catalogue=json.loads((MANAGER/'coordination/current-catalogue-5b4b778-20261020-r1/packs.json').read_bytes())
    check(len(catalogue)==260 and 'comfyui-prompt-combinator' not in catalogue,'New pack absent exact immutable260 catalogue; no duplicate source identity')
    write('VERIFIED_RESULT_RECEIPT.json',dict(status='PASS_INDEPENDENT_DATA_INTAKE_THREE_COMPONENT_PURPOSES_ONLY',
        archive_sha256='eb76d27e3d5b5637fb243e8c312e82c2729cf529f5ba742ae0090b8ee5e6a2a3',checks=len(CHECKS),
        matched_native_Guest_cases=len(rows),per_node_matched_cases=dict(counts),separate_rng_fixture_calls=len(rng),actual_Guest_dispatches=132,
        ignored_seed_pairs=16,schemas=3,comparator_controls=5,normal_generations=1,pristine_replays=2,specific_wrong_base_refusals=2,
        exact_original_files=len(original),exact_candidate_files=len(candidate),tested_manifest_sha256=pins[root+'v2/secure-nodes.json']['sha256'],
        complete_maps=maps,operator_config_map_entries=18,recorded_retired_PIDs=retirement['pids'],recorded_actual_retired_groups=retirement['groups'],
        independent_retirement_probes=2,normal_site=True,required_real_Seatbelt_Guests=1,
        config_sha256=config_hash,selected_authority=config['runtime_authority'],actual_SDK_sha256=origins['comfy_api.latest._sdk']['sha256'],
        whole_owner_seconds=owner['execution_wall_seconds'],payload_cleanup_seconds=owner['payload_and_cleanup_wall_seconds'],sampled_RSS_peak_bytes=owner['aggregate_rss_peak_bytes'],
        native_time_real_seconds=35.79,native_time_maximum_resident_set_size_bytes=989872128,hard_memory_quota=False,
        remaining_temporary_directory=retirement['residual_readback'],pre_fsync_kill_gap_closed=False,exhaustive_transient_child_census=False,
        ExportGallery='FORMALLY_REFUSED_CURRENT_RELEASE',whole_four_original_node_pack_accepted=False,
        supplied_imports_tests_replays_generation_or_runtime_execution=0,conditional_GO=False,
        scope='Direct original computations and production real-Guest component paths only. No separate default-Core graph, browser, serialization, service, managed release or current platform-wide acceptance inferred.'))
    write('CHECK_INDEX.json',dict(checks=CHECKS))
    print(json.dumps(dict(status='PASS_DATA_ONLY_INTAKE',checks=len(CHECKS),matched_cases=len(rows),source_files=len(tested))))
