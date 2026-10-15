"""Approved one-socket repair; source case mismatch retained, tuple algorithm unchanged."""
import asyncio
import copy
import os

from test_ned_comfyroll_animation_models import NEW, V2, oracle, list_args, _sdk, GuestSession


def test_production_graph_validator_native_red_and_corrected_chain_admission(monkeypatch):
    import execution
    import nodes
    source=oracle('CR LoRA List')
    cls=NEW.NODE_CLASS_MAPPINGS['CR LoRA List'];cls.GET_SCHEMA()
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS,'ned-native-lora-list',source)
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS,'ned-v2-lora-list',cls)
    async def run():
        args=list_args('CR LoRA List')
        def graph(key):
            return {'a':{'class_type':key,'inputs':dict(args)},'b':{'class_type':key,'inputs':dict(args,lora_list=['a',0])}}
        native=await execution.validate_inputs('ned-lora-source',graph('ned-native-lora-list'),'b',{})
        assert native[0] is False and len(native[1])==1
        error=native[1][0]
        assert error['type']=='return_type_mismatch'
        assert error['extra_info']['received_type']=='LORA_LIST'
        assert error['extra_info']['input_config'][0]=='lora_LIST'
        corrected=await execution.validate_inputs('ned-lora-corrected',graph('ned-v2-lora-list'),'b',{})
        assert corrected==(True,[],'b')
        wrong=graph('ned-v2-lora-list');wrong['b']['inputs']['lora_list']=['a',1]
        invalid=await execution.validate_inputs('ned-lora-wrong-slot',wrong,'b',{})
        assert invalid[0] is False and invalid[1][0]['type']=='return_type_mismatch'
        assert invalid[1][0]['extra_info']['received_type']=='STRING'
    asyncio.run(run())


def test_only_optional_type_changes_every_other_schema_field_preserved():
    from test_ned_comfyroll_animation_models import LEDGER
    from comfy_execution.validation import validate_node_input
    row=copy.deepcopy(LEDGER['CR LoRA List'])
    cls=NEW.NODE_CLASS_MAPPINGS['CR LoRA List'];schema=cls.GET_SCHEMA()
    expected={k:(g,v) for g,values in row['source_inputs'].items() for k,v in values.items()}
    for inp in schema.inputs:
        group,spec=expected[inp.id]
        assert inp.optional==(group=='optional')
        if inp.id=='lora_list':assert spec[0]=='lora_LIST' and inp.io_type=='LORA_LIST'
        elif isinstance(spec[0],list):assert inp.options==spec[0]
        else:assert inp.io_type==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert inp.as_dict()[key]==value
    assert cls.SDK_PERMISSIONS==() and cls.SDK_REFS is True
    assert [o.io_type for o in schema.outputs]==row['return_types']
    assert validate_node_input(schema.outputs[0].io_type,'LORA_LIST')
    assert not validate_node_input('LORA_LIST','lora_LIST')


def test_two_fresh_zero_capability_guest_outer_producer_self_chain_and_reconstruction():
    import execution
    async def run():
        prior=_sdk.providers.execution_backend;pids=[];outputs=[]
        source=oracle('CR LoRA List')
        cls=NEW.NODE_CLASS_MAPPINGS['CR LoRA List'];cls.GET_SCHEMA()
        try:
            for render in range(2):
                session=await GuestSession('ned-lora-socket-closure-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                async def execute(args,unique):
                    result=await execution._async_map_node_over_list(prompt_id='lora-socket-closure',unique_id=unique,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result
                try:
                    first_args=list_args('CR LoRA List',lora_name1='first.safetensors',alias1='same',model_strength_1=.25,clip_strength_1=-.5)
                    first=await execute(first_args,'first')
                    assert first==source().lora_list(**first_args)
                    next_args=list_args('CR LoRA List',lora_name2='next.safetensors',alias2='same',lora_list=first[0])
                    second=await execute(next_args,'second')
                    assert second==source().lora_list(**next_args)
                    empty_args=list_args('CR LoRA List',lora_list=second[0])
                    third=await execute(empty_args,'third')
                    assert third==source().lora_list(**empty_args)
                    assert third[0]==second[0] and all(type(row) is tuple for row in third[0])
                    assert first_args.get('lora_list') is None
                    assert second[0]==[('same','first.safetensors',.25,-.5),('same','next.safetensors',1.,1.)]
                    outputs.append((first,second,third));pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert outputs[0]==outputs[1]
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())
