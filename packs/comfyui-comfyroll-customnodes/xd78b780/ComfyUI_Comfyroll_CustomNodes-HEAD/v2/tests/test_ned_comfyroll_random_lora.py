"""Pinned selection math; deliberate scoped lifecycle; actual local broker/guest proofs."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-random','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes import storage
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_random_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
M=NEW.secure_random_lora;W=M.CR_RandomWeightLoRA;S=M.CR_RandomLoRAStack
LEDGER=json.loads((V2/'random-lora-draft-ledger.json').read_text())

class Draws:
    def __init__(self,values):self.values=iter(values);self.calls=0
    def __call__(self,*args):self.calls+=1;return next(self.values)

def native(draws):
    tree=ast.parse((PACK/'nodes/nodes_lora.py').read_text())
    icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
    ns={'icons':icons,'hashlib':hashlib,'uniform':draws,'random':draws}
    selected=[copy.deepcopy(n) for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('CR_RandomWeightLoRA','CR_RandomLoRAStack')]
    exec(compile(ast.Module(body=selected,type_ignores=[]),'pinned-random-lora','exec'),ns)
    return ns['CR_RandomWeightLoRA'],ns['CR_RandomLoRAStack']

def weight_args(**changes):
    args=dict(stride=3,force_randomize_after_stride='Off',lora_name='a.safetensors',switch='On',weight_min=0.,weight_max=1.,clip_weight=1.)
    args.update(changes);return args

def stack_args(**changes):
    args=dict(exclusive_mode='Off',stride=3,force_randomize_after_stride='Off')
    for i,name in enumerate(('a','b','c'),1):args.update({f'lora_name_{i}':name,f'model_weight_{i}':float(i),f'clip_weight_{i}':-float(i),f'switch_{i}':'On',f'chance_{i}':.5})
    args.update(changes);return args

class LocalService:
    """Real local backing in process, optionally injecting optimistic conflicts."""
    def __init__(self,path,tenant='a',pack='p'):
        self.store=storage.PackStorage(path);self.tenant=tenant;self.pack=pack;self.reads=0;self.writes=0;self.conflicts=0
    async def read(self,key):
        self.reads+=1;await asyncio.sleep(0)
        return self.store.read(self.tenant,self.pack,key)
    async def compare_and_set(self,key,revision,value):
        self.writes+=1;await asyncio.sleep(0)
        if self.conflicts:
            self.conflicts-=1;return dict(self.store.read(self.tenant,self.pack,key),updated=False)
        return self.store.compare_and_set(self.tenant,self.pack,key,revision,value)

async def call(service,cls,method,args):
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),SimpleNamespace(storage=service),_sdk.InProcessOps()):
        return await getattr(cls,method)(**copy.deepcopy(args))

def weight_key(args):return 'random-weight.v1.'+M.weight_id(args['lora_name'],args['force_randomize_after_stride'],args['stride'],args['weight_min'],args['weight_max'],args['clip_weight'])
def stack_key(args):return 'random-stack.v1.'+M._digest(M.deduplicateLoraNames(*(args[f'lora_name_{i}'] for i in range(1,4))))

@pytest.mark.parametrize('stride',[1,2,3,1000])
@pytest.mark.parametrize('force',['Off','On'])
def test_weight_nonpathological_pinned_sequence_execute_readonly_and_cache(stride,force,tmp_path,monkeypatch):
    draws=[.1,.1,.2,.3,.4,.5,.6,.7,.8,.9]*3
    oracle_draws=Draws(draws);new_draws=Draws(draws);old,_=native(oracle_draws)
    monkeypatch.setattr(M,'uniform',new_draws);service=LocalService(tmp_path)
    args=weight_args(stride=stride,force_randomize_after_stride=force,lora_stack=[('None',4.,5.),('prior',2.,3.)])
    async def run():
        assert (await call(service,W,'execute',args)).result==old().random_weight_lora(**args)
        for i in range(7):
            expected=old.IS_CHANGED(**args)
            assert await call(service,W,'fingerprint_inputs',args)==expected
            record=service.store.read('a','p',weight_key(args));writes=service.writes
            for _ in range(3):assert (await call(service,W,'execute',args)).result==old().random_weight_lora(**args)
            assert service.store.read('a','p',weight_key(args))==record and service.writes==writes
        assert new_draws.calls==oracle_draws.calls
    asyncio.run(run())

@pytest.mark.parametrize('changes',[{'switch':'Off'},{'lora_name':'None'}])
def test_disabled_weight_fingerprint_never_accesses_storage(tmp_path,changes):
    service=LocalService(tmp_path);args=weight_args(**changes);old,_=native(Draws([]))
    assert asyncio.run(call(service,W,'fingerprint_inputs',args))==old.IS_CHANGED(**args)
    assert service.reads==service.writes==0 and not list(tmp_path.iterdir())

@pytest.mark.parametrize('changes',[
    {},{'exclusive_mode':'On'},{'lora_name_2':'a','lora_name_3':'a'},
    {'lora_name_1':'None','lora_name_2':'None','lora_name_3':'None'},
    {'switch_1':'Off','switch_2':'Off','switch_3':'Off'},
    {'chance_1':0.,'chance_2':1.,'chance_3':.9},
    {'force_randomize_after_stride':'On','stride':1},
])
def test_stack_pinned_draw_sequence_duplicates_sentinel_exclusive_stride(tmp_path,monkeypatch,changes):
    sequence=[.1,.9,.9, .9,.1,.9, .9,.9,.1, .1,.1,.1, .8,.1,.2, .1,.8,.2]*10
    source_draws=Draws(sequence);new_draws=Draws(sequence);_,old=native(source_draws)
    monkeypatch.setattr(M,'random',new_draws);service=LocalService(tmp_path);args=stack_args(**changes)
    async def run():
        assert (await call(service,S,'execute',args)).result==old().random_lora_stacker(**args)
        for _ in range(7):
            old.IS_CHANGED(**args);fp=await call(service,S,'fingerprint_inputs',args)
            assert isinstance(fp,str) and len(fp)==64  # documented replacement of salted integer hash
            expected=old().random_lora_stacker(**args)
            assert (await call(service,S,'execute',args)).result==expected
        assert source_draws.calls==new_draws.calls
    asyncio.run(run())

def test_weight_two_decimal_collisions_and_stack_ignored_settings_order(tmp_path,monkeypatch):
    a=weight_args(weight_min=.001,weight_max=.999,clip_weight=1.001)
    b=weight_args(weight_min=.002,weight_max=1.,clip_weight=1.002)
    assert weight_key(a)==weight_key(b)
    monkeypatch.setattr(M,'random',Draws([.1,.9,.9]));service=LocalService(tmp_path)
    args=stack_args();changed=stack_args(chance_1=0.,model_weight_1=8.)
    assert stack_key(args)==stack_key(changed)==stack_key(stack_args(lora_name_1='c',lora_name_2='a',lora_name_3='b'))
    async def run():
        fp=await call(service,S,'fingerprint_inputs',args)
        assert await call(service,S,'fingerprint_inputs',changed)==fp
        assert (await call(service,S,'execute',changed)).result==([('a',8.,-1.)],)
    asyncio.run(run())

def test_native_three_decimal_fingerprint_collision_retained_not_cache_certification(tmp_path,monkeypatch):
    args=weight_args(stride=1);draws=Draws([.0001,.0002]);old,_=native(Draws([.0001,.0002]));service=LocalService(tmp_path)
    monkeypatch.setattr(M,'uniform',draws)
    async def run():
        fingerprints=[];weights=[]
        for _ in range(2):
            expected=old.IS_CHANGED(**args);fingerprints.append(await call(service,W,'fingerprint_inputs',args))
            assert fingerprints[-1]==expected
            output=await call(service,W,'execute',args);assert output.result==old().random_weight_lora(**args)
            weights.append(output.result[0][0][1])
        assert fingerprints[0]==fingerprints[1] and weights==[.0001,.0002]
    asyncio.run(run())

@pytest.mark.parametrize('cls,args,key',[(W,weight_args(stride=1,weight_min=.5,weight_max=.5),weight_key),(S,stack_args(stride=1,force_randomize_after_stride='On',chance_1=1.,chance_2=1.,chance_3=1.),stack_key)])
def test_native_indefinite_repeat_is_bounded_before_commit(cls,args,key,tmp_path,monkeypatch):
    service=LocalService(tmp_path);draws=Draws([.5]*2000)
    monkeypatch.setattr(M,'uniform',draws);monkeypatch.setattr(M,'random',draws)
    async def run():
        await call(service,cls,'fingerprint_inputs',args)
        before=service.store.read('a','p',key(args));writes=service.writes;count=draws.calls
        with pytest.raises(RuntimeError,match='256 draw cycles'):await call(service,cls,'fingerprint_inputs',args)
        assert draws.calls-count==256*(1 if cls is W else 3)
        assert service.store.read('a','p',key(args))==before and service.writes==writes
    asyncio.run(run())
    oldW,oldS=native(Draws([.5]*4));old=oldW if cls is W else oldS
    old.IS_CHANGED(**args)
    with pytest.raises(StopIteration):old.IS_CHANGED(**args)

@pytest.mark.parametrize('conflicts',[1,3,31,32])
def test_conflict_retry_bound_and_fail_closed_without_reset(tmp_path,monkeypatch,conflicts):
    service=LocalService(tmp_path);service.conflicts=conflicts
    monkeypatch.setattr(M,'uniform',Draws([.2]*40))
    async def run():
        if conflicts==32:
            with pytest.raises(RuntimeError,match='32 storage conflicts'):await call(service,W,'fingerprint_inputs',weight_args())
            assert service.store.read('a','p',weight_key(weight_args()))['value'] is None
        else:await call(service,W,'fingerprint_inputs',weight_args())
        assert service.writes==min(conflicts+1,32)
    asyncio.run(run())

def test_concurrent_same_config_fingerprints_do_not_lose_stride_updates(tmp_path,monkeypatch):
    service=LocalService(tmp_path);monkeypatch.setattr(M,'uniform',lambda *args:.25)
    async def run():
        results=await asyncio.gather(*(call(service,W,'fingerprint_inputs',weight_args(stride=1000)) for _ in range(8)))
        assert len(set(results))==1
        state=json.loads(service.store.get('a','p',weight_key(weight_args(stride=1000))))
        assert state['counter']==7 and service.writes>8
    asyncio.run(run())

@pytest.mark.parametrize('payload',['not json','{}','{"v":1,"v":1}',json.dumps({'v':1,'counter':0,'last_weight':.2,'last_fingerprint':'forged'}),'x'*8193])
@pytest.mark.parametrize('method',['execute','fingerprint_inputs'])
def test_corrupt_state_never_overwritten(tmp_path,payload,method):
    service=LocalService(tmp_path);args=weight_args();service.store.set('a','p',weight_key(args),payload)
    before=service.store.read('a','p',weight_key(args))
    with pytest.raises(ValueError,match='Corrupt'):asyncio.run(call(service,W,method,args))
    assert service.store.read('a','p',weight_key(args))==before and service.writes==0

def test_quota_failure_preserves_previous_choice(tmp_path,monkeypatch):
    service=LocalService(tmp_path);monkeypatch.setattr(M,'uniform',Draws([.2,.8]));args=weight_args(stride=1)
    asyncio.run(call(service,W,'fingerprint_inputs',args));before=service.store.read('a','p',weight_key(args))
    monkeypatch.setattr(storage,'MAX_TOTAL_BYTES',1)
    with pytest.raises(ValueError,match='quota'):asyncio.run(call(service,W,'fingerprint_inputs',args))
    assert service.store.read('a','p',weight_key(args))==before

@pytest.mark.parametrize('changes',[{'v':True},{'counter':True},{'counter':1000},{'used_names':['outside']},{'used_names':['a','a']},{'last_fingerprint':'wrong'}])
@pytest.mark.parametrize('method',['execute','fingerprint_inputs'])
def test_stack_corrupt_records_never_reset(tmp_path,changes,method):
    args=stack_args();service=LocalService(tmp_path)
    record={'v':1,'counter':0,'used_names':['a'],'last_fingerprint':M._digest(['a'])};record.update(changes)
    service.store.set('a','p',stack_key(args),json.dumps(record))
    before=service.store.read('a','p',stack_key(args))
    with pytest.raises(ValueError,match='Corrupt'):asyncio.run(call(service,S,method,args))
    assert service.store.read('a','p',stack_key(args))==before and service.writes==0

def test_two_actual_guest_fingerprints_share_atomic_config_not_process_cache(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(tmp_path/'backing'))
    args=weight_args(stride=1000,weight_min=.5,weight_max=.5)
    async def run():
        sessions=await asyncio.gather(*(GuestSession('ned-random-concurrent',tenant='same-user',guest_runtime_root=V2).start() for _ in range(2)))
        async def fingerprint(session,index):
            runtime=_sdk.Runtime(refs=_sdk.InProcessRefResolver(),ctx=SimpleNamespace(),ops=_sdk.InProcessOps())
            plan=_sdk.ExecutionPlan(prompt_id='different-graph-'+str(index),node_id=str(index),node_type=W.__name__,tier='sandbox',node_module=NEW.__name__+'.secure_random_lora',method='fingerprint_inputs',inputs=args)
            return await session.execute(plan,runtime,capabilities=('storage',),tenant='same-user')
        try:
            results=await asyncio.gather(*(fingerprint(s,i) for i,s in enumerate(sessions)))
            assert results[0]==results[1] and sessions[0].last_guest_pid!=sessions[1].last_guest_pid
            state=json.loads(storage.host_storage().get('same-user','development/ned-random-concurrent',weight_key(args)))
            assert state['counter']==1 and state['last_weight']==.5
        finally:await asyncio.gather(*(s.kill() for s in sessions))
    asyncio.run(run())

@pytest.mark.parametrize('cls,args',[(W,weight_args(stride=True)),(W,weight_args(weight_min=float('nan'))),(W,weight_args(lora_name='../secret')),(S,stack_args(chance_1=float('inf'))),(S,stack_args(lora_stack=[('a',1,2)]*257))])
def test_input_bounds_precede_broker(cls,args,tmp_path):
    service=LocalService(tmp_path)
    with pytest.raises(ValueError):asyncio.run(call(service,cls,'fingerprint_inputs',args))
    assert service.reads==service.writes==0

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_declared_storage_not_models_or_raw(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types']
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==('storage',)
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,src=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(src[0],list):
            assert inp.options==src[0]
            if inp.id.startswith('lora_name'):assert inp.remote.route=='/secure-nodes/models/loras'
        else:assert inp.io_type==src[0]
        for key,value in (src[1] if len(src)>1 else {}).items():assert inp.as_dict()[key]==value

def test_real_guests_recreated_backing_graph_sharing_user_pack_isolation_denial_and_outer(tmp_path,monkeypatch):
    import execution
    backing=tmp_path/'local-backing';monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
    async def dispatch(cls,args,method='execute',tenant='user-a',pack='ned-random-lora',graph='g1',caps=('storage',),outer=False):
        session=await GuestSession(pack,tenant=tenant,guest_runtime_root=V2).start()
        try:
            if outer:
                previous=_sdk.providers.execution_backend
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=caps,tenant=tenant)
                _sdk.providers.register_execution_backend(Backend())
                try:
                    cls.GET_SCHEMA()
                    result=await execution._async_map_node_over_list(prompt_id=graph,unique_id='node-'+graph,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result,session.last_guest_pid
                finally:_sdk.providers.register_execution_backend(previous)
            runtime=_sdk.Runtime(refs=_sdk.InProcessRefResolver(),ctx=SimpleNamespace(),ops=_sdk.InProcessOps())
            plan=_sdk.ExecutionPlan(prompt_id=graph,node_id='node-'+graph,node_type=cls.__name__,tier='sandbox',node_module=NEW.__name__+'.secure_random_lora',method=method,inputs=args)
            result=await session.execute(plan,runtime,capabilities=caps,tenant=tenant)
            return result,session.last_guest_pid
        finally:await session.kill()
    async def run():
        args=weight_args(weight_min=.25,weight_max=.25,stride=3)
        before,p0=await dispatch(W,args,outer=True);assert before==([('a.safetensors',0.,1.)],)
        fp,p1=await dispatch(W,args,method='fingerprint_inputs');assert fp.endswith('_0.250')
        monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
        chosen,p2=await dispatch(W,args,graph='different-graph',outer=True);assert chosen==([('a.safetensors',.25,1.)],)
        assert len({p0,p1,p2})==3
        for overrides in ({'tenant':'user-b'},{'pack':'other-pack'}):
            out,_=await dispatch(W,args,outer=True,**overrides);assert out==before
        for cls,a in ((W,args),(S,stack_args(chance_1=1.,chance_2=1.,chance_3=1.))):
            with pytest.raises(Exception,match='storage'):await dispatch(cls,a,method='fingerprint_inputs',caps=())
        all_args=stack_args(chance_1=1.,chance_2=1.,chance_3=1.,stride=3)
        empty,_=await dispatch(S,all_args,outer=True);assert empty==([],)
        sfp,spid=await dispatch(S,all_args,method='fingerprint_inputs')
        monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
        full,epid=await dispatch(S,all_args,graph='other-node',outer=True)
        assert full==([('a',1.,-1.),('b',2.,-2.),('c',3.,-3.)],) and spid!=epid
        again,_=await dispatch(S,all_args,method='fingerprint_inputs');assert sfp==again
        assert storage.host_storage().list('user-a','development/ned-random-lora')==sorted([weight_key(args),stack_key(all_args)])
    asyncio.run(run())
