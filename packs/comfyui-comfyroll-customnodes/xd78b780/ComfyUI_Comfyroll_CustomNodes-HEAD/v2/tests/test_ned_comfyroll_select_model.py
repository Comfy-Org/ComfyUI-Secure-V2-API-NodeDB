"""Approved no-selection repair and typed checkpoint outputs; no trained load/inference."""
import ast,asyncio,copy,json,types
import pytest
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire,loaders,ModelPatcher,CLIP,VaeDouble
ID='CR Select Model'
LEDGER=json.loads((V2/'select-model-draft-ledger.json').read_text())[ID]
def args_for(**changes):
    a=dict(ckpt_name1='one',ckpt_name2='two',ckpt_name3='three',ckpt_name4='one',ckpt_name5='two',select_model=1);a.update(changes);return a
def source(loaders,args):
    cls=next(n for n in ast.parse((PACK/'nodes/nodes_core.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CR_SelectModel')
    ns={'icons':{},'folder_paths':types.SimpleNamespace(get_full_path=lambda k,n:n,get_folder_paths=lambda k:[]),'comfy':types.SimpleNamespace(sd=types.SimpleNamespace(load_checkpoint_guess_config=loaders['load']))}
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),'pinned-select-model','exec'),ns)
    return ns['CR_SelectModel']().select_model(**args)
async def migrated(args):
    refs=_sdk.InProcessRefResolver()
    with _sdk.bind_runtime(refs,types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):
        r=await NEW.NODE_CLASS_MAPPINGS[ID].execute(**args)
        out=[]
        for value in r.result:out.append(await refs.resolve(value) if isinstance(value,_sdk.Ref) else value)
        return tuple(out)
@pytest.mark.parametrize('choice',[1,2,3,4,5,1.,True])
def test_exact_selected_checkpoint_loader_output_order_and_source_help(loaders,choice):
    args=args_for(select_model=choice);expected=source(loaders,args);loaders['calls'].clear();actual=asyncio.run(migrated(args))
    assert len(actual)==len(expected)==5 and actual[3:]==expected[3:]
    assert loaders['calls']==[expected[3]]
    assert actual[0].model_options==expected[0].model_options and actual[1].tokenizer_options==expected[1].tokenizer_options
    assert isinstance(actual[2],VaeDouble)
@pytest.mark.parametrize('choice',[0,6,-1,'1',None])
def test_native_invalid_unbound_and_explicit_preload_error(loaders,choice):
    args=args_for(select_model=choice)
    with pytest.raises(UnboundLocalError):source(loaders,args)
    with pytest.raises(ValueError,match='Invalid checkpoint selection'):asyncio.run(migrated(args))
    assert not loaders['calls']
@pytest.mark.parametrize('choice',[1,2,3,4,5])
def test_native_empty_outputs_and_explicit_missing_selection(loaders,choice):
    args=args_for(select_model=choice,**{f'ckpt_name{choice}':'None'})
    assert source(loaders,args)==()
    with pytest.raises(ValueError,match='No checkpoint selected'):asyncio.run(migrated(args))
    assert not loaders['calls']
@pytest.mark.parametrize('name',['../host','/host','a/../b','a\\b','x'*2049])
def test_only_chosen_name_validated_before_broker(loaders,name):
    with pytest.raises(ValueError,match='logical'):asyncio.run(migrated(args_for(ckpt_name1=name)))
    assert not loaders['calls']
    actual=asyncio.run(migrated(args_for(ckpt_name1=name,select_model=2)));assert actual[3]=='two'
def test_exact_schema_registered_catalogue_no_hidden_or_new_authority():
    c=NEW.NODE_CLASS_MAPPINGS[ID];s=c.GET_SCHEMA()
    assert s.node_id==ID and s.display_name==LEDGER['display_name'] and s.category==LEDGER['category']
    assert c.SDK_REFS is True and c.SDK_PERMISSIONS==('models',)
    assert [i.id for i in s.inputs]==list(LEDGER['source_inputs']['required'])
    assert [o.io_type for o in s.outputs]==LEDGER['return_types'] and [o.display_name for o in s.outputs]==LEDGER['return_names']
    for i in s.inputs[:5]:assert i.options==['None'] and i.remote.route=='/secure-nodes/models/checkpoints'
    for key,value in LEDGER['source_inputs']['required']['select_model'][1].items():assert s.inputs[-1].as_dict()[key]==value
def test_two_fresh_guests_outer_ref_identity_denials_and_production(loaders,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-select-model-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('models',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(args):
                    cls=NEW.NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
                    r=await execution._async_map_node_over_list(prompt_id='select-model',unique_id='selector',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None);return r[0].result
                try:
                    for choice in (1,2,3,4,5):
                        actual=await execute(args_for(select_model=choice));loaded=loaders['loaded'][-1]
                        assert len(actual)==5 and all(actual[i] is loaded[i] for i in range(3))
                        assert type(actual[3]) is str and type(actual[4]) is str
                    before=len(loaders['calls'])
                    for changes,error in [({'ckpt_name1':'None'},'No checkpoint'),({'select_model':0},'Invalid checkpoint'),({'ckpt_name1':'../host'},'logical')]:
                        with pytest.raises(wire.WireError,match=error):await execute(args_for(**changes))
                    assert len(loaders['calls'])==before
                    backend.caps=()
                    with pytest.raises(wire.WireError,match='models'):await execute(args_for())
                    assert len(loaders['calls'])==before;pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-select-model-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                cls=NEW.NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA();args=args_for()
                r=await execution._async_map_node_over_list(prompt_id='select-production',unique_id='selector',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                r=await execution.resolve_map_node_over_list_results(r);assert all(r[0].result[i] is loaders['loaded'][-1][i] for i in range(3)) and r[0].result[3]=='one'
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
