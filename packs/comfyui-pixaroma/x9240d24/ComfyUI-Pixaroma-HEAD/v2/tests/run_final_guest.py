"""Finite combined real Guest qualification with lock guard throughout calls."""
import asyncio
import builtins
import contextvars
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import traceback
import types

sys.path.insert(0,'/tests')
import run_round1 as base
import run_images as images
import run_io as asset_tests
import qualify_static
from comfy_api.latest import _sdk as sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire

signal.alarm(360)
PLAN=contextvars.ContextVar('pixaroma-final-plan')
RECEIPT={'status':'RUNNING','evidence':'gate, B13 sources 38f28c98','timeout_seconds':360,
 'scheduled_cases':{'round1':607,'images':410,'io':112,'disable_metadata':12},'nodes':{},'failures':[],
 'qualification':'real development GuestSession subprocess; backend only; no browser/OS-isolation/live-B13 claim'}
real_base_runtime=base.in_runtime
real_io_runtime=asset_tests.in_runtime

class LockedSession(GuestSession):
    def _guest_command(self,python):return [python,'/tests/_pixaroma_guest_entry.py']
    def _adjust_guest_env(self,env):
        super()._adjust_guest_env(env)
        env['PIXAROMA_GUARD_ROOT']=str(self.guest_runtime_root)
        env['PIXAROMA_GUARD_LOG']='/results/guest-import-denials.jsonl'
        env['PIXAROMA_GUARD_REPORT']='/results/guest-import-guard.json'

async def base_runtime(plan,op):
    token=PLAN.set(plan)
    try:return await real_base_runtime(plan,op)
    finally:PLAN.reset(token)

async def io_runtime(plan,scope,op):
    token=PLAN.set(plan)
    try:return await real_io_runtime(plan,scope,op)
    finally:PLAN.reset(token)

async def main():
    for label,root in [('source',base.PACK),('v2',base.V2)]:
        count=0
        for file in root.rglob('*.py'):
            if label=='source' and file.is_relative_to(base.V2):continue
            compile(file.read_bytes(),str(file),'exec');count+=1
        RECEIPT['compile_'+label]=count
    RECEIPT['static']=qualify_static.main()
    base.namespace('pixaroma_recovery_original',base.PACK);base.namespace('pixaroma_recovery_original.nodes',base.PACK/'nodes')
    metadata_new=base.load_v2();RECEIPT['schemas']=base.encode_and_check(metadata_new)
    with tempfile.TemporaryDirectory(prefix='pixaroma-sealed-guest-') as temp,tempfile.TemporaryDirectory(prefix='pixaroma-final-fixtures-') as fixtures:
        root=Path(temp)/'v2';shutil.copytree(base.V2,root)
        (root/'__init__.py').write_text("raise AssertionError('package __init__ executed by namespace guest')\n")
        (root/'_guest_denial_probe.py').write_text('from comfy_api.latest import io\nclass ImportProbe(io.ComfyNode):\n @classmethod\n async def execute(cls, **kwargs):\n  import scipy\n  return io.NodeOutput()\n')
        classes={}
        for node,row in base.ROWS.items():
            module=packdb.load('custom_nodes.pixaroma_final_guest',root,row['module']);cls=getattr(module,node);cls.GET_SCHEMA();classes[node]=cls
        new=types.SimpleNamespace(NODE_CLASS_MAPPINGS=classes)
        session=await asyncio.wait_for(LockedSession('pixaroma-finite-final',guest_runtime_root=root).start(),45)
        try:
            RECEIPT.update(sandbox_kind=session.sandbox_kind,host_pid=os.getpid(),namespace_init_guard=True)
            async def guest_call(cls,method,fields):
                runtime=sdk.current_runtime();wrapped={}
                def contains_ref(value):
                    if isinstance(value,sdk.Ref):return True
                    if isinstance(value,dict):return any(contains_ref(v) for v in value.values())
                    if isinstance(value,(list,tuple)):return any(contains_ref(v) for v in value)
                    return False
                async def wrap(value):
                    if isinstance(value,sdk.Ref):return value
                    if contains_ref(value):
                        if isinstance(value,dict):return {k:await wrap(v) for k,v in value.items()}
                        values=[await wrap(v) for v in value]
                        return tuple(values) if isinstance(value,tuple) else values
                    return (await sdk.wrap_inputs(runtime.refs,{'value':value}))['value']
                for key,value in fields.items():
                    wrapped[key]=await wrap(value)
                plan=replace(PLAN.get(),node_module=cls.__module__,node_type=cls.__name__,inputs=wrapped,method=method,permissions=tuple(cls.SDK_PERMISSIONS))
                try:out=await session.execute(plan,runtime,capabilities=tuple(cls.SDK_PERMISSIONS),tenant='pixaroma-finite-final')
                except wire.WireError as error:
                    name=getattr(error,'remote_type','');message=getattr(error,'remote_message','')
                    if name=='DependencyRefusal':raise RuntimeError(message) from error
                    if name in ('ValueError','TypeError','RuntimeError','AttributeError','OverflowError','KeyError','IndexError','RecursionError','ImportError','ModuleNotFoundError'):
                        raise getattr(builtins,name)(message) from error
                    raise
                RECEIPT['guest_pid']=session.last_guest_pid;assert session.last_guest_pid!=os.getpid();return out
            probe=packdb.load('custom_nodes.pixaroma_final_guest',root,'_guest_denial_probe').ImportProbe;probe.SDK_PERMISSIONS=[]
            async def deny():
                try:await guest_call(probe,'execute',{})
                except ModuleNotFoundError as error:assert "guest profile excludes 'scipy'" in str(error);return
                raise AssertionError('undeclared scipy import escaped child lock guard')
            base.in_runtime=base_runtime;asset_tests.in_runtime=io_runtime
            await base_runtime(base.plan_for('ImportProbe',{}),deny)
            RECEIPT['child_import_negative_control']='scipy denied during actual Guest execution'
            for cls in classes.values():
                async def execute(cls,**fields):return await guest_call(cls,'execute',fields)
                cls.execute=classmethod(execute)
                for name in ('validate_inputs','fingerprint_inputs','check_lazy_status'):
                    if name=='validate_inputs' and cls.__name__!='PixaromaXYPlot':continue
                    if name in cls.__dict__:
                        def make(method):
                            async def call(cls,**fields):return await guest_call(cls,method,fields)
                            return classmethod(call)
                        setattr(cls,name,make(name))
            asset_tests.assets(fixtures)
            phases=[('round1',base.CASES,lambda case,index:base.compare_case(case,new,None)),
                ('images',images.CASES,lambda case,index:images.compare(case,new)),
                ('io',asset_tests.CASES,lambda case,index:asset_tests.compare(case,new,fixtures,index))]
            for phase,cases,operation in phases:
                for index,case in enumerate(cases):
                    row=RECEIPT['nodes'].setdefault(phase+'/'+case['node'],{})
                    try:
                        verdict=await operation(case,index);row[verdict]=row.get(verdict,0)+1
                    except Exception as error:
                        row['MISMATCH']=row.get('MISMATCH',0)+1
                        RECEIPT['failures'].append({'phase':phase,'index':index,'node':case['node'],'label':case['label'],'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc(),'guest_stderr':session.last_stderr,'guest_stdout':session.last_stdout})
                        if len(RECEIPT['failures'])>=12:raise AssertionError('finite failure stop')
            RECEIPT['round1_lifecycle_cases']=await base.lifecycle(new)
            RECEIPT['io_lifecycle_checks']=asset_tests.LIFECYCLE_CHECKS
            disabled=[case for case in asset_tests.CASES if case['node']=='PixaromaPreview' and not case.get('refused_match') or case['node']=='PixaromaSaveImage' and case['label'] in ('metadata','preview-clean','counter','folder') or case['node']=='PixaromaXYPlot' and case['label']=='dark-0']
            assert len(disabled)==12
            base.args.disable_metadata=True
            try:
                for index,case in enumerate(disabled):await asset_tests.compare(case,new,fixtures,1000+index)
            finally:base.args.disable_metadata=False
            RECEIPT['disable_metadata_cases']=len(disabled)
            RECEIPT['disable_metadata_lifecycle_checks']=asset_tests.LIFECYCLE_CHECKS-RECEIPT['io_lifecycle_checks']
            assert sum(len(cases) for _,cases,_ in phases)==1129
            assert len(asset_tests.XY_REFUSAL_EVIDENCE)==16
            RECEIPT['retained_input_cases']=1129
            RECEIPT['xy_refusal_evidence']=asset_tests.XY_REFUSAL_EVIDENCE
            RECEIPT['xy_refusal_cases']=15
            RECEIPT['xy_disabled_metadata_refusal_cases']=1
            RECEIPT['xy_lifecycle_named_refusals']=16
            denial_rows=[json.loads(line) for line in Path('/results/guest-import-denials.jsonl').read_text().splitlines()]
            assert len(denial_rows)==1 and denial_rows[0]['module']=='scipy',denial_rows
            RECEIPT['import_denials']=denial_rows
            RECEIPT['status']='PASS' if not RECEIPT['failures'] else 'FAIL'
        finally:
            await session.kill();RECEIPT['guest_killed']=True
            base.in_runtime=real_base_runtime;asset_tests.in_runtime=real_io_runtime
    RECEIPT['temporary_namespace_removed']=not root.exists()

try:asyncio.run(main())
except BaseException as error:
    RECEIPT['status']='FAIL';RECEIPT['failures'].append({'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()})
finally:
    signal.alarm(0);Path('/results/final-guest-receipt.json').write_text(json.dumps(RECEIPT,indent=2,sort_keys=True)+'\n');print(json.dumps(RECEIPT,indent=2),flush=True)
if RECEIPT['status']!='PASS':raise SystemExit(1)
