"""Native string/seed/options, declared interface and actual confined execution."""
import asyncio,ast,hashlib,importlib.util,json,math,os,random,shutil,sys
from pathlib import Path
import pytest
CORE=Path(os.environ['COMFY_CORE_ROOT']).resolve();OVERLAY=Path(os.environ['MANY_FLUX_OVERLAY_ROOT']).resolve()
sys.dont_write_bytecode=True;sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
from comfy_api.latest import io,_sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.execution import CloudExecutionBackend
import execution
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
def load(name,root):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('many_flux_native',PACK).NODE_CLASS_MAPPINGS['FluxPromptGenerator']
NEW=load('many_flux_new',V2).NODE_CLASS_MAPPINGS['FluxPromptGenerator']
NATIVE=sys.modules['many_flux_native.flux_prompt_generator'];GUARD=sys.modules['many_flux_new._secure_node']
SCHEMA=OLD.INPUT_TYPES()['required']
def defaults(seed=193):return {n:seed if n=='seed' else spec[1]['default'] for n,spec in SCHEMA.items()}
def inputs(delta=None,seed=193):return {**defaults(seed),**(delta or {})}
CASES=[{}]
for name,spec in SCHEMA.items():
    if isinstance(spec[0],list):CASES.extend({name:choice} for choice in spec[0])
CASES.extend([{'custom':'a, b,, Unicode 雪 🙂 BREAK_CLIPL lens BREAK_CLIPL','subject':'a woman'},
              {'custom':' '*3500},{'custom':'BREAK_CLIPG sky BREAK_CLIPG subject'},
              {'lighting':'one,two, three','default_tags':'random'},
              {name:'random' for name,spec in SCHEMA.items() if isinstance(spec[0],list)}])

@pytest.mark.parametrize('delta',CASES)
def test_all_source_literal_options_random_disabled_and_prompt_parts(delta):
    values=inputs(delta);before=random.getstate();expected=OLD().execute(**values)
    actual=NEW.execute(**values).result
    assert actual==expected and len(actual)==5 and type(actual[1]) is int
    assert random.getstate()==before
    # Legacy has no OUTPUT_IS_LIST mask and retains five internal columns.
    # V3 derives a one-column mask from the single declared output socket.
    # Preserve every raw native value and compare the sole connectable socket.
    legacy=execution.get_output_from_returns([expected],OLD())[0]
    converted=execution.get_output_from_returns([io.NodeOutput(*actual)],NEW)[0]
    assert legacy==[[value] for value in expected]
    assert converted==[legacy[0]]==[[expected[0]]]

@pytest.mark.parametrize('seed',[0,1,30000,-1,2**63-1,-2**63])
def test_source_seed_determinism_and_fingerprint_nan(seed):
    v=inputs({n:'random' for n,s in SCHEMA.items() if isinstance(s[0],list)},seed)
    assert NEW.execute(**v).result==OLD().execute(**v)
    assert NEW.execute(**v).result==NEW.execute(**v).result
    assert math.isnan(NEW.fingerprint_inputs(**v)) and math.isnan(OLD.IS_CHANGED(**v))

def test_source_schema_census_resources_and_inactive_installer_removal_only():
    assert NEW.SDK_PERMISSIONS==() and NEW.SDK_REFS is False
    s=NEW.GET_SCHEMA();s.validate()
    assert s.node_id=='FluxPromptGenerator' and len(s.outputs)==1 and s.outputs[0].io_type=='STRING'
    assert [x.id for x in s.inputs]==list(SCHEMA)
    assert 0<=next(x for x in s.inputs if x.id=='seed').default<=30000
    a=ast.parse((PACK/'flux_prompt_generator.py').read_bytes());b=ast.parse((V2/'flux_prompt_generator.py').read_bytes())
    filtered=[n for n in a.body if not (isinstance(n,ast.FunctionDef) and n.name=='install_and_import') and not (isinstance(n,ast.Import) and any(x.name in ('sys','subprocess') for x in n.names))]
    assert ast.dump(ast.Module(body=filtered,type_ignores=[]),include_attributes=False)==ast.dump(b,include_attributes=False)
    for relative,row in GUARD.PROFILE['files'].items():assert hashlib.sha256((V2/relative).read_bytes()).hexdigest()==row['sha256']

def test_before_operation_refusal_plain_string_seed_budget_and_recovery(monkeypatch):
    def forbidden(self,**values):raise AssertionError('native operation entered before admission')
    original=GUARD.Native.execute;monkeypatch.setattr(GUARD.Native,'execute',forbidden)
    for delta in ({'custom':'x'*4097},{'custom':object()},{'custom':['x']},{'seed':2**100}):
        with pytest.raises((ValueError,TypeError)):NEW.execute(**inputs(delta))
    monkeypatch.setattr(GUARD.Native,'execute',original)
    assert NEW.execute(**defaults()).result==OLD().execute(**defaults())

async def outer(cls,values,prompt='flux-acceptance'):
    cls.GET_SCHEMA() if hasattr(cls,'GET_SCHEMA') else None
    rows=await execution._async_map_node_over_list(prompt,'1',cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    rows=await execution.resolve_map_node_over_list_results(rows)
    return rows[0]

def test_actual_two_fresh_required_zero_cap_guests_full_native_result_declared_interface_errors_recovery(tmp_path):
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for index in range(2):
                root=tmp_path/str(index);shutil.copytree(V2,root)
                cls=load('many_flux_guest_'+str(index),root).NODE_CLASS_MAPPINGS['FluxPromptGenerator']
                session=await GuestSession('many-flux-'+str(index),guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=(),tenant='flux-test-account')
                _sdk.providers.register_execution_backend(Backend())
                try:
                    selected=[{},CASES[-1],{'custom':'a  ,,, b 雪 BREAK_CLIPL x BREAK_CLIPL'},
                              {'artform':'photography','photo_type':'random','lighting':'random'},
                              {'custom':' '*3500}]
                    for seed in (0,193,-1):
                        for delta in selected:
                            v=inputs(delta,seed);expected=OLD().execute(**v);actual=await outer(cls,v)
                            assert actual.result==expected
                            assert execution.get_output_from_returns([actual],cls)[0]==[[expected[0]]]
                    for delta in ({'custom':'x'*4097},{'seed':2**100},{'custom':{'hidden':'object'}}):
                        with pytest.raises(Exception):await outer(cls,inputs(delta))
                    assert (await outer(cls,defaults())).result==OLD().execute(**defaults())
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
        print('FLUX_REQUIRED_GUEST_PIDS='+json.dumps(sorted(pids)))
    asyncio.run(run())

def test_actual_production_outer_consumed_declared_string_and_native_five_values(tmp_path):
    async def run():
        root=tmp_path/'outer';shutil.copytree(V2,root)
        cls=load('many_flux_outer',root).NODE_CLASS_MAPPINGS['FluxPromptGenerator']
        backend=CloudExecutionBackend();prior=_sdk.providers.execution_backend
        _sdk.providers.register_execution_backend(backend)
        try:
            for delta in ({},CASES[-1],{'custom':'Unicode 🙂 雪','subject':'a woman'}):
                v=inputs(delta);actual=await outer(cls,v,'many-flux-production');expected=OLD().execute(**v)
                assert actual.result==expected and execution.get_output_from_returns([actual],cls)[0]==[[expected[0]]]
        finally:await backend.guests.shutdown();_sdk.providers.register_execution_backend(prior)
    asyncio.run(run())
