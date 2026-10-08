"""Full12 source math/PNG differentials, required guests/outer, and artifact gate."""
import ast
import asyncio
from dataclasses import replace
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;CORPUS=PACK.parents[3]
CORE='/Users/ben/comfy/ComfyUI-secure-nodes';BACKEND='/Users/ben/comfy/ComfyUI_secure_nodes/backend'
sys.path[:0]=[CORE,BACKEND]
os.environ.setdefault('COMFY_CORE_ROOT',CORE)
import numpy as np
import pytest
import torch
from comfy_api.latest import io, _sdk
from comfy_secure_nodes import packdb,packpatch,packruntime
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire

def load(root):
    name='_jack_analysis_'+hashlib.sha256(str(root).encode()).hexdigest()[:12]
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

class Pixels:
    def __init__(self,value):self.value=value
    async def describe(self,**kwargs):return dict(shape=list(self.value.shape))
    async def raw(self):return self.value

def image(kind='gradient',batch=2,h=32,w=40,c=3):
    pixels=torch.arange(h*w*c,dtype=torch.float32).reshape(h,w,c)
    pixels=(pixels%257)/256
    if kind=='black':pixels=torch.zeros_like(pixels)
    elif kind=='white':pixels=torch.ones_like(pixels)
    return torch.stack([pixels if i==0 else 1-pixels for i in range(batch)])

def defaults(cls,pixels=None):
    fields={}
    for inp in cls.GET_SCHEMA().inputs:
        if inp.id=='image':fields[inp.id]=image() if pixels is None else pixels
        elif hasattr(inp,'default'):fields[inp.id]=inp.default
        elif hasattr(inp,'options'):fields[inp.id]=inp.options[0]
        else:raise AssertionError(inp)
    return fields

def cases():
    rows=[]
    for node_id,cls in load(PACK).NODE_CLASS_MAPPINGS.items():
        base=defaults(cls)
        combos=[(x.id,list(x.options)) for x in cls.GET_SCHEMA().inputs if x.io_type=='COMBO']
        flags=[x.id for x in cls.GET_SCHEMA().inputs if x.io_type=='BOOLEAN']
        for choice in itertools.product(*(opts for _,opts in combos)):
            for enabled in ([False,True] if flags else [None]):
                args=dict(base)
                args.update(zip((key for key,_ in combos),choice))
                for key in flags:args[key]=enabled
                rows.append((node_id,args))
    return rows

def same(a,b):
    assert len(a)==len(b)
    for x,y in zip(a,b):
        if isinstance(x,torch.Tensor):
            assert isinstance(y,torch.Tensor) and x.shape==y.shape and x.dtype==y.dtype
            assert torch.equal(x,y) or torch.allclose(x,y,rtol=0,atol=0,equal_nan=True), (x.shape,y.shape,torch.max(torch.abs(x-y)))
        elif type(x) is float and math.isnan(x):assert math.isnan(y)
        else:assert type(x) is type(y) and x==y,(type(x),type(y),x,y)

def native(node_id,args,seed=41):
    # Test-oracle normalization only, restored after every source call.
    before=np.random.get_state()
    try:
        np.random.seed(seed)
        with np.errstate(all='ignore'):return load(PACK).NODE_CLASS_MAPPINGS[node_id].execute(**args)
    finally:np.random.set_state(before)

async def in_process(cls,fields):
    # Actual public publication/resolution, metadata recorder only on input.
    refs=_sdk.InProcessRefResolver()
    plan=_sdk.ExecutionPlan('local','1',cls.__name__,inputs={},permissions=('inspect','raw'))
    with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
        output=await cls.execute(**fields)
        result=[]
        for value in output.result:
            result.append(await value.raw() if isinstance(value,_sdk.ImageRef) else value)
        return tuple(result)

def test_pristine_census_schemas_ids_and_ast_preserved():
    old=load(PACK);new=load(V2)
    assert len(old.NODE_CLASS_MAPPINGS)==12 and list(old.NODE_CLASS_MAPPINGS)==list(new.NODE_CLASS_MAPPINGS)
    assert old.NODE_DISPLAY_NAME_MAPPINGS==new.NODE_DISPLAY_NAME_MAPPINGS
    pairs=[]
    for node_id,cls in old.NODE_CLASS_MAPPINGS.items():
        before=encode_schema(cls.GET_SCHEMA());after=encode_schema(new.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA())
        pairs.append((node_id,before['attrs']['node_id']))
        assert before['attrs']['node_id']!=node_id
        before['attrs']['node_id']=node_id
        before['attrs']['display_name']=old.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert before==after
        assert new.NODE_CLASS_MAPPINGS[node_id].SDK_PERMISSIONS==('inspect','raw')
    print(json.dumps({'exact_registration_to_native_schema_ids':pairs,'backend_ids':12,'frontend_entrypoints':1,'js_only_nodes':0}))
    # Numerical bodies are extracted, never source ComfyNode bridge classes.
    for path in (V2/'algorithms').glob('*.py'):
        tree=ast.parse(path.read_text())
        assert not any(isinstance(n,ast.ClassDef) for n in ast.walk(tree))
        assert not any(isinstance(n,ast.ImportFrom) and n.module=='comfy_api.latest' for n in ast.walk(tree))
        assert not any(isinstance(n,ast.ImportFrom) and n.module=='matplotlib' and any(a.name=='pyplot' for a in n.names) for n in ast.walk(tree))
    # Source helper remains identical except the local renderer import.
    oldhelper=(PACK/'nodes/_utils.py').read_text().replace('from matplotlib import pyplot as plt','from .. import _render as plt')
    oldhelper=oldhelper.replace('buf = _io.BytesIO()', 'buf = plt.PNGBuffer()').replace('fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")','plt.save_png(fig, buf)').replace('pil = Image.open(buf).convert("RGB")','source = Image.open(buf)\n    plt.admit_png(source.size)\n    pil = source.convert("RGB")')
    assert ast.dump(ast.parse((V2/'algorithms/_utils.py').read_text()))==ast.dump(ast.parse(oldhelper))
    # Compare every source numerical body after only class-to-function calls
    # and the declared local RNG injection. No metric/FFT/KMeans substitution.
    class Extract(ast.NodeTransformer):
        def visit_Attribute(self,n):
            if isinstance(n.value,ast.Name) and n.value.id in ('cls','instance'):
                return ast.copy_location(ast.Name(id=n.attr,ctx=n.ctx),n)
            return self.generic_visit(n)
        def visit_Assign(self,n):
            if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='cls':return None
            return self.generic_visit(n)
    for path in (PACK/'nodes').glob('*.py'):
        if path.name=='_utils.py':continue
        expected=[]
        for cls in [n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef)]:
            for f in cls.body:
                if not isinstance(f,ast.FunctionDef) or f.name=='define_schema':continue
                f.decorator_list=[]
                if f.args.args and f.args.args[0].arg in ('cls','self'):f.args.args.pop(0)
                if f.name=='execute':f.name='compute'
                f=Extract().visit(f)
                if path.stem=='color_harmony_analyzer' and f.name=='compute':
                    f.args.kwonlyargs.append(ast.arg(arg='rng'));f.args.kw_defaults.append(None)
                    for n in ast.walk(f):
                        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='KMeans':
                            n.keywords.append(ast.keyword(arg='random_state',value=ast.Name(id='rng',ctx=ast.Load())))
                expected.append(f)
        actual=[n for n in ast.parse((V2/'algorithms'/path.name).read_text()).body if isinstance(n,ast.FunctionDef)]
        assert [ast.dump(n) for n in expected]==[ast.dump(n) for n in actual],path.name

def test_all_options_png_outputs_and_rng_differential(monkeypatch):
    converted=load(V2)
    module=__import__(converted.__name__+'._execute',fromlist=['execute'])
    monkeypatch.setattr(module,'execution_rng',lambda np:np.random.RandomState(41))
    import matplotlib
    from matplotlib import pyplot as plt
    from matplotlib._pylab_helpers import Gcf
    rc=dict(matplotlib.rcParams);backend=matplotlib.get_backend();managers=list(Gcf.get_all_fig_managers())
    globalrng=np.random.get_state()
    async def run():
        rows=cases()
        for node_id,args in rows:
            expected=native(node_id,args)
            with np.errstate(all='ignore'):
                output=await in_process(converted.NODE_CLASS_MAPPINGS[node_id],dict(args,image=Pixels(args['image'])))
            same(expected,output)
            assert not Gcf.get_all_fig_managers()
        print(json.dumps({'all_option_visualization_cases':len(rows),'positively_exercised_ids':12,'png_pixel_exact':True,'rng_local_seed':41}))
    asyncio.run(run())
    assert dict(matplotlib.rcParams)==rc and matplotlib.get_backend()==backend
    assert Gcf.get_all_fig_managers()==managers
    after=np.random.get_state()
    assert globalrng[0]==after[0] and np.array_equal(globalrng[1],after[1]) and globalrng[2:]==after[2:]

def test_native_malformed_small_domains_and_first_batch(monkeypatch):
    converted=load(V2)
    module=__import__(converted.__name__+'._execute',fromlist=['execute'])
    monkeypatch.setattr(module,'execution_rng',lambda np:np.random.RandomState(41))
    rows=[]
    for node_id,cls in load(PACK).NODE_CLASS_MAPPINGS.items():
        for kind in ('black','white'):
            rows.append((node_id,defaults(cls,image(kind,h=8,w=8))))
        for c in (1,2,4):rows.append((node_id,defaults(cls,image(h=16,w=16,c=c))))
        fields=defaults(cls)
        if 'block_size' in fields:
            for block in (0,-1,8,128):rows.append((node_id,dict(fields,block_size=block)))
        if 'num_clusters' in fields:
            for clusters in (0,-1,8):rows.append((node_id,dict(fields,num_clusters=clusters)))
    async def run():
        errors=0
        for node_id,args in rows:
            try:expected=native(node_id,args)
            except Exception as e:
                with pytest.raises(type(e)) as caught:
                    await converted.NODE_CLASS_MAPPINGS[node_id].execute(**dict(args,image=Pixels(args['image'])))
                assert str(caught.value)==str(e);errors+=1
            else:
                with np.errstate(all='ignore'):
                    out=await in_process(converted.NODE_CLASS_MAPPINGS[node_id],dict(args,image=Pixels(args['image'])))
                same(expected,out)
        print(json.dumps({'native_domain_cases':len(rows),'native_uncaught_errors':errors,'caught_source_fallbacks_preserved':True}))
    asyncio.run(run())

@pytest.mark.parametrize('shape,algorithm,extras',[
    ([5,32,40,3],'rgb_histogram_renderer',{}),
    ([1,1025,2,3],'rgb_histogram_renderer',{}),
    ([4,1024,1024,3],'defocus_analysis',{}),
    ([1,512,512,3],'color_harmony_analyzer',{'num_clusters':8}),
    ([1,32,40,3],'noise_estimation_basic',{'block_size':129}),
    ([1,32,40,3],'noise_estimation_basic',{'block_size':2**100}),
    ([1,32,40,3],'noise_estimation_basic',{'block_size':object()}),
])
def test_refuse_before_input_import_raw_or_compute(shape,algorithm,extras,monkeypatch):
    new=load(V2);module=__import__(new.__name__+'._execute',fromlist=['execute'])
    def forbidden(*a,**kw):raise AssertionError('algorithm import before admission')
    monkeypatch.setattr(module,'import_module',forbidden)
    class Metadata:
        async def describe(self,**kw):return dict(shape=shape)
        async def raw(self):raise AssertionError('raw before admission')
    with pytest.raises((TypeError,ValueError)):
        asyncio.run(module.execute(algorithm,dict(image=Metadata(),**extras)))

def test_publication_and_render_cleanup_on_error():
    new=load(V2);admission=__import__(new.__name__+'._admission',fromlist=['admit_outputs'])
    with pytest.raises(ValueError,match='publication'):
        admission.admit_outputs((torch.empty(1,4096,4096,3,device='meta'),))
    render=__import__(new.__name__+'._render',fromlist=['scope'])
    with pytest.raises(RuntimeError,match='forced'):
        with render.scope():
            fig,ax=render.subplots(figsize=(6,6))
            ax.plot([0,1],[0,1]);raise RuntimeError('forced')
    assert not fig.axes and render._figures.get() is None
    with render.scope():
        with pytest.raises(ValueError,match='canvas'):render.subplots(figsize=(600,600))
    with pytest.raises(ValueError,match='decoded PNG'):render.admit_png((4096,4096))
    buffer=render.PNGBuffer();buffer.seek(16*1024*1024)
    with pytest.raises(ValueError,match='encoded PNG'):buffer.write(b'x')

async def guest_session(label,root,monkeypatch):
    real=packruntime.resolve_for_tenant
    def selected(spec,tenant):
        assert spec is None
        resolved=real(spec,tenant)
        assert resolved.python_executable==Path(sys.executable)
        return replace(resolved,spec=replace(resolved.spec,pack_root=root.resolve()))
    with monkeypatch.context() as context:
        context.setattr(packruntime,'resolve_for_tenant',selected)
        guest=await GuestSession(label,module_source_root=root,guest_runtime_root='/Users/ben/comfy/ComfyUI/.venv').start()
    assert guest.sandbox_kind=='seatbelt'
    return guest

def test_all12_required_guests_production_outer_and_cap_denials(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for i in range(2):
                root=V2 if i==0 else tmp_path/'fresh'/'ComfyUI-Image-Analysis-Tools-HEAD'/'v2'
                if i:shutil.copytree(V2,root)
                mapping=packdb.load_pack(root.parent.parent,mount_name='custom_nodes.jack_analysis_'+str(i)).node_mappings
                guest=await guest_session('jack-analysis-'+str(i),root,monkeypatch)
                class Backend:
                    caps=('inspect','raw')
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await guest.execute(plan,runtime,capabilities=self.caps,tenant='jack-analysis-user-'+str(i))
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def outer(node_id,args):
                    cls=mapping[node_id]
                    values,missing,meta=execution.get_input_data(args,cls,node_id,None)
                    assert not missing
                    outputs=await execution._async_map_node_over_list('jack-analysis',node_id,cls,values,'execute',v3_data=meta)
                    return (await execution.resolve_map_node_over_list_results(outputs))[0].result
                try:
                    positive=[]
                    for node_id,cls in load(PACK).NODE_CLASS_MAPPINGS.items():
                        fields=defaults(cls)
                        if node_id=='Color Harmony Analyzer':
                            # Constant hues avoid invented seed authority; math
                            # draw equivalence is separately proved in-process.
                            fields['image']=image('white')
                        same(native(node_id,fields),await outer(node_id,fields));positive.append(node_id)
                    # Actual native caught fallback and uncaught cv2 failure,
                    # not only in-process metadata/algorithm tests.
                    source=load(PACK).NODE_CLASS_MAPPINGS
                    fields=dict(defaults(source['Noise Estimation']),block_size=0)
                    same(native('Noise Estimation',fields),await outer('Noise Estimation',fields))
                    fields=defaults(source['Defocus Analysis'],image(c=2))
                    with pytest.raises(Exception) as original:native('Defocus Analysis',fields)
                    with pytest.raises(wire.WireError,match='Bad number of channels'):
                        await outer('Defocus Analysis',fields)
                    with pytest.raises(wire.WireError,match='dimensions'):
                        await outer('RGB Histogram Renderer',dict(image=image(batch=1,h=1025,w=1)))
                    same(native('RGB Histogram Renderer',dict(image=image())),await outer('RGB Histogram Renderer',dict(image=image())))
                    for caps,denied in [(('inspect',),'raw'),(('raw',),'inspect')]:
                        backend.caps=caps
                        with pytest.raises(wire.WireError,match=denied):
                            await outer('RGB Histogram Renderer',dict(image=image()))
                        backend.caps=('inspect','raw')
                        same(native('RGB Histogram Renderer',dict(image=image())),await outer('RGB Histogram Renderer',dict(image=image())))
                    print(json.dumps({'required_seatbelt_pid':guest.pid,'fresh_root':str(root),'positive_outer_ids':positive,'native_fallbacks':1,'native_uncaught_errors':1,'projected_dimension_refusals':1,'raw_denials':1,'inspect_denials':1,'recovery_calls':3,'scope':'unsealed Macdevelopment; no LinuxCloud'}))
                    pids.append(guest.pid)
                finally:await guest.kill()
            assert len(set(pids))==2
        finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())

def test_frontend_harness():
    result=subprocess.run(['node',str(V2/'tests/frontend_harness.mjs')],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    print(result.stdout)

def test_required_guest_outside_read_import_refusal_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    probe=load(V2)
    spec=importlib.util.spec_from_file_location(probe.__name__+'.tests.boundary_probe',V2/'tests/boundary_probe.py')
    boundary=importlib.util.module_from_spec(spec);sys.modules[spec.name]=boundary;spec.loader.exec_module(boundary)
    outside=tmp_path/'outside_marker.py';shutil.copyfile(PACK/'__init__.py',outside)
    async def run():
        guest=await guest_session('jack-analysis-boundary',V2,monkeypatch)
        try:
            refs=_sdk.InProcessRefResolver()
            plan=_sdk.ExecutionPlan('boundary','1','OutsideBoundaryProbe',node_module=boundary.OutsideBoundaryProbe.__module__,
                inputs=await _sdk.wrap_inputs(refs,{'outside':str(outside)}),input_mode='refs',permissions=(),tier='sandbox')
            runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
            assert (await guest.execute(plan,runtime,capabilities=(),tenant='jack-analysis-boundary')).result==('read,import',)
            plan=_sdk.ExecutionPlan('boundary','libraries','RuntimeProbe',node_module=boundary.RuntimeProbe.__module__,
                inputs={},input_mode='refs',permissions=(),tier='sandbox')
            observed=json.loads((await guest.execute(plan,runtime,capabilities=(),tenant='jack-analysis-boundary')).result[0])
            expected=json.loads((V2/'DEVELOPMENT_RUNTIME.json').read_text())['selected_dependencies']
            for name,record in observed['distributions'].items():assert record['version']==expected[name]['version']
            assert observed['pyplot_loaded'] is False
            print(json.dumps({'actual_guest_libraries':observed}))
            cls=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.jack_analysis_boundary').node_mappings['RGB Histogram Renderer']
            fields={'image':image()}
            plan=_sdk.ExecutionPlan('boundary','2',cls.__name__,node_module=cls.__module__,
                inputs=await _sdk.wrap_inputs(refs,fields,{'image':'IMAGE'}),input_mode='refs',permissions=('inspect','raw'),tier='sandbox')
            runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
            output=await guest.execute(plan,runtime,capabilities=('inspect','raw'),tenant='jack-analysis-boundary')
            same(native('RGB Histogram Renderer',fields),(await _sdk.unwrap_outputs(refs,output)).result)
            plan=_sdk.ExecutionPlan('boundary','libraries-after','RuntimeProbe',node_module=boundary.RuntimeProbe.__module__,
                inputs={},input_mode='refs',permissions=(),tier='sandbox')
            after=json.loads((await guest.execute(plan,runtime,capabilities=(),tenant='jack-analysis-boundary')).result[0])
            assert after==observed and after['pyplot_loaded'] is False
            print(json.dumps({'boundary_pid':guest.pid,'outside_read_refusals':1,'outside_import_refusals':1,'recovery':True}))
        finally:await guest.kill()
    asyncio.run(run())

def test_manifest_pristine_resources_exact_pair_zip(tmp_path):
    reference=json.loads((V2/'tests/pristine-files.json').read_text())
    for name,record in reference.items():
        file=PACK/name
        assert hashlib.sha256(file.read_bytes()).hexdigest()==record['sha256']
        assert bool(file.stat().st_mode&0o111)==(record['git_mode']=='100755')
    assert len(reference)==20 and not (PACK/'LICENSE').exists()
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
    runtime=json.loads((V2/'DEVELOPMENT_RUNTIME.json').read_text())
    for name,digest in runtime['stubs'].items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==digest
    manifest=json.loads((V2/'secure-nodes.json').read_text())
    assert set(manifest['nodes'])==set(load(V2).NODE_CLASS_MAPPINGS)
    for node_id,cls in load(V2).NODE_CLASS_MAPPINGS.items():
        assert manifest['nodes'][node_id]['schema']==encode_schema(cls.GET_SCHEMA())
        assert manifest['nodes'][node_id]['permissions']==['inspect','raw']
    report=(V2/'SECURE_CONVERSION.md').read_text()
    assert '<!-- secure-conversion-report-v1 -->' in report
    assert all('| '+node_id+' |' in report for node_id in manifest['nodes'])
    patch,diff=packpatch.generate(SNAPSHOT)
    pair=CORPUS/'patches/comfyui-image-analysis-tools/x167e395';stem='comfyui-image-analysis-tools-x167e395'
    assert json.loads((pair/(stem+'.json')).read_text())==patch
    assert (pair/(stem+'.diff')).read_text()==diff
    for label in ('pair','zip'):
        fresh=tmp_path/label/'comfyui-image-analysis-tools/x167e395'
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if label=='pair':packpatch.apply(fresh,patch,diff)
        else:packpatch.apply_bundle(fresh,packpatch.bundle(patch,diff))
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
