"""Pinned source differentials, managed authored resources and actual guest seams."""
import asyncio, ast, copy, hashlib, importlib.util, io, json, os, random, shutil, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend',str(Path(__file__).parent)]
from comfy.cli_args import args
args.cpu=True
import execution,comfy.sd,folder_paths
import comfy.model_base,comfy.supported_models_base,comfy.latent_formats,comfy.model_patcher,comfy.sample
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
from pristine_controls import control,schemas,IDS,BUNDLED,FONTS
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-chibi-nodes/x9a9734f/comfyui-chibi-nodes-x9a9734f'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
NEW=load('ned_chibi',V2);CLASSES=NEW.NODE_CLASS_MAPPINGS;MOD=sys.modules[CLASSES['Loader'].__module__]
for cls in CLASSES.values():cls.GET_SCHEMA()
def manifest():
    return {'format':FORMAT,'runtime':manifest_declaration(V2),'web_directory':'js','nodes':{
        key:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':cls.SDK_REFS,'permissions':list(cls.SDK_PERMISSIONS),
             'methods':{k:k in cls.__dict__ for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},
             'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for key,cls in CLASSES.items()}}

class Tokenizer:
    def tokenize_with_weights(self,text,return_word_ids=False,**kwargs):return {'l':[[(ord(c),1.) for c in text]]}
class Stage:
    def __init__(self,dtype):self.dtype=dtype;self.encodes=[]
    def reset_clip_options(self):pass
    def set_clip_options(self,options):pass
    def encode_token_weights(self,tokens):
        self.encodes.append(copy.deepcopy(tokens));v=[t[0]*t[1] for chunk in tokens['l'] for t in chunk]
        return torch.tensor(v,dtype=self.dtype).reshape(1,len(v),1),torch.tensor([[sum(v)]],dtype=self.dtype),{'source_extra':7}
def clip(dtype=torch.float32):
    c=object.__new__(comfy.sd.CLIP);c.tokenizer=Tokenizer();c.tokenizer_options={};c.cond_stage_model=Stage(dtype)
    c.layer_idx=None;c.use_clip_schedule=False;c.patcher=SimpleNamespace(forced_hooks=None,load_device=torch.device('cpu'))
    c.load_model=lambda tokens:None;c.apply_hooks_to_conds=None
    c.patcher.clone=lambda **kwargs:c.patcher
    return c

class TinyFormat(comfy.latent_formats.LatentFormat):
    latent_channels=4
    latent_dimensions=2
class TinyConfig(comfy.supported_models_base.BASE):
    latent_format=TinyFormat
class Kernel(torch.nn.Module):
    def __init__(self):
        super().__init__();self.bias=torch.nn.Parameter(torch.zeros(()));self.dtype=torch.float32
    def forward(self,x,timesteps,context=None,**kwargs):
        shape=(x.shape[0],)+(1,)*(x.ndim-1)
        c=0 if context is None else context.mean()*.001
        return x*.125+timesteps.to(x).reshape(shape)*.00001+c+self.bias
def model():
    config=TinyConfig({'disable_unet_model_creation':True,'in_channels':4})
    value=comfy.model_base.BaseModel(config,comfy.model_base.ModelType.FLOW,device=torch.device('cpu'))
    value.diffusion_model=Kernel()
    return comfy.model_patcher.ModelPatcher(value,torch.device('cpu'),torch.device('cpu'))

class Decoder(torch.nn.Module):
    def __init__(self):
        super().__init__();self.conv=torch.nn.Conv2d(3,3,1,groups=3,bias=False)
        self.conv.weight.data.fill_(.75)
    def encode(self,value):return self.conv(value)
    def decode(self,value,**kwargs):return self.conv(value)
def vae(monkeypatch):
    from comfy import model_management
    monkeypatch.setattr(model_management,'load_models_gpu',lambda *a,**kw:None)
    monkeypatch.setattr(model_management,'soft_empty_cache',lambda *a,**kw:None)
    v=object.__new__(comfy.sd.VAE);v.first_stage_model=Decoder();v.device=v.output_device=torch.device('cpu')
    v.vae_dtype=torch.float32;v.vae_output_dtype=lambda:torch.float32;v.patcher=SimpleNamespace(get_free_memory=lambda device:4096)
    v.memory_used_decode=v.memory_used_encode=lambda *args:1;v.disable_offload=False;v.latent_dim=2;v.latent_channels=v.output_channels=3
    v.extra_1d_channel=None;v.handles_tiling=False;v.format_encoded=None;v.crop_input=False;v.pad_channel_value=None
    v.upscale_ratio=v.downscale_ratio=1;v.upscale_index_formula=None;v.process_output=v.process_input=lambda value:value
    return v

async def direct(key,values,ctx=None):
    refs=_sdk.InProcessRefResolver();cls=CLASSES[key]
    hints={i.id:i.io_type for i in cls.GET_SCHEMA().inputs}
    with _sdk.bind_runtime(refs,ctx,_sdk.InProcessOps()):
        wrapped=await _sdk.wrap_inputs(refs,values,hints)
        result=cls.execute(**wrapped)
        if hasattr(result,'__await__'):result=await result
        output=[]
        for v in result.result:
            if isinstance(v,_sdk.Ref):v=await refs.resolve(v)
            output.append(v)
        return tuple(output)

def same(a,b):
    if isinstance(a,torch.Tensor):assert a.shape==b.shape and a.dtype==b.dtype and torch.equal(a,b)
    elif isinstance(a,(tuple,list)):
        assert type(a)==type(b) and len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:same(a[k],b[k])
    else:assert a==b

def test_exact_source_census_schema_resources_and_workflow_readouts():
    expected=schemas();assert list(CLASSES)==IDS and len(IDS)==19
    tree=ast.parse((PACK/'__init__.py').read_text())
    mapping=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in n.targets))
    assert [ast.literal_eval(k) for k in mapping.keys]==IDS
    assert NEW.WEB_DIRECTORY=='js' and not hasattr(NEW,'NODE_DISPLAY_NAME_MAPPINGS')
    for key,cls in CLASSES.items():
        source=expected[key];schema=cls.GET_SCHEMA();schema.validate()
        assert schema.node_id==key and schema.category==source['category']
        assert tuple(o.io_type for o in schema.outputs)==tuple(source['outputs'])
        assert schema.is_output_node==source['output_node']
        assert [i.id for i in schema.inputs]==[name for section in ('required','optional') for name in source['inputs'].get(section,{})]
        for inp in schema.inputs:
            options=source['inputs']['optional' if inp.optional else 'required'][inp.id]
            if not isinstance(options[0],list):assert inp.io_type==options[0]
            if len(options)>1:
                for k,v in options[1].items():assert inp.as_dict()[k]==v
    wildcard=CLASSES['Wildcards'].GET_SCHEMA().inputs[0]
    assert wildcard.options==BUNDLED and wildcard.remote.static_options==BUNDLED
    assert wildcard.remote.route==MOD.schema('Wildcards').inputs[0].remote.route
    assert len(FONTS)==13 and len(BUNDLED)==10
    for p in (PACK/'extras').rglob('*'):
        if p.is_file():assert p.read_bytes()==(V2/p.relative_to(PACK)).read_bytes()

@pytest.mark.parametrize('text',['','plain','中文😀','\n<script>x</script>','a.b.c'])
def test_pure_text_int_embedding_textbox_exact(text):
    same(CLASSES['Int2String'].execute(-123).result,control('Int2String')().int2string(-123))
    same(CLASSES['LoadEmbedding'].execute(text,'fixture.pt',-0.0).result,control('LoadEmbedding')().load_embedding(text,'fixture.pt',-0.0))
    for passvalue in ('',text):
        actual=CLASSES['Textbox'].execute(text,passvalue)
        source=control('Textbox')().textbox(text,passvalue)
        assert actual.result==(source['result'] if isinstance(source,dict) else source)
        assert actual.ui==(source['ui'] if isinstance(source,dict) else None)

@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('half',['First Half','Second Half'])
@pytest.mark.parametrize('text',['a.b.c','','no_separator'])
def test_text_split_source_quirk_including_list_in_string_socket(reverse,half,text):
    same(CLASSES['TextSplit'].execute(text,'.',reverse,half).result,control('TextSplit')().do_split(text,'.',reverse,half))
    with pytest.raises(ValueError):CLASSES['TextSplit'].execute(text,'',reverse,half)

@pytest.mark.parametrize('seed',[0,1,37,2**64-1,None])
@pytest.mark.parametrize('name',BUNDLED)
def test_wildcard_exact_seeded_draws_and_global_rng_isolation(seed,name,monkeypatch):
    state=random.getstate()
    if seed is None:
        monkeypatch.setattr(MOD,'local_rng',lambda seed=None:random.Random(7))
        seed_control=7
    else:seed_control=seed
    source=control('Wildcards')().wildcards(name,'__wildcard__',5,seed=seed_control,text='pre __wildcard__ post __wildcard__')
    random.setstate(state)
    actual=asyncio.run(direct('Wildcards',dict(textfile=name,keyword='__wildcard__',entries_returned=5,seed=seed,text='pre __wildcard__ post __wildcard__')))
    same(actual,source);assert random.getstate()==state
    assert math_is_nan(CLASSES['Wildcards'].fingerprint_inputs()) and random.getstate()==state
def math_is_nan(v):return v!=v

@pytest.mark.parametrize('key,values',[('Prompts',dict(Positive='A🙂',Negative='')),('ConditionText',dict(text=None)),('ConditionTextPrompts',dict(positive='a',negative='b')),('ConditionTextMulti',dict(first='a',second='',third='中文',fourth=''))])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
def test_canonical_unscheduled_clip_node_output_order_metadata_exact(key,values,dtype):
    a,b=clip(dtype),clip(dtype)
    source=control(key)();expected=getattr(source,source.FUNCTION)(clip=a,**values)
    actual=asyncio.run(direct(key,dict(clip=b,**values)))
    for x,y in zip(actual,expected):
        if y is a:assert x is b
        else:same(x,y)
    assert a.cond_stage_model.encodes==b.cond_stage_model.encodes
    same(asyncio.run(direct('Prompts',dict(Positive='a',Negative='b'))),(None,None,None,'a','b'))

@pytest.mark.parametrize('crop',[False,True])
@pytest.mark.parametrize('rotate',[0,13,90,360])
@pytest.mark.parametrize('mirror,flip',[(False,False),(True,False),(False,True),(True,True)])
def test_image_tool_quantized_first_frame_exact(crop,rotate,mirror,flip):
    value=torch.linspace(-.1,1.1,2*13*19*3).reshape(2,13,19,3)
    values=dict(image=value,height=16,width=23,crop=crop,rotate=rotate,mirror=mirror,flip=flip,bgcolor='white')
    same(asyncio.run(direct('ImageTool',values)),control('ImageTool')().imagetools(**values))

@pytest.mark.parametrize('shape',[(17,29),(29,17),(17,17)])
@pytest.mark.parametrize('edge',['largest','smallest','all','width','height'])
@pytest.mark.parametrize('size',[8,32])
def test_resize_exact_native_geometry_and_all_edge_quirks(shape,edge,size):
    value=torch.linspace(0,1,2*shape[0]*shape[1]*3).reshape(2,*shape,3)
    values=dict(image=value,size=size,edge=edge,size_override=None)
    same(asyncio.run(direct('ImageSimpleResize',values)),control('ImageSimpleResize')().imagesimpleresize(**values))

@pytest.mark.parametrize('font',FONTS)
@pytest.mark.parametrize('invert_mask',[False,True])
def test_bundled_font_pixel_exact_resource_and_mask(font,invert_mask):
    values=dict(text='Hello\nWorld',width=96,height=64,font=font,font_size=12,position_x=3,position_y=2,font_colour='red',invert_mask=invert_mask)
    same(asyncio.run(direct('ImageAddText',values)),control('ImageAddText')().addtext(**values))

def test_bounds_before_allocations_text_fonts_and_unseeded_control_draws(monkeypatch):
    with pytest.raises(ValueError,match='budget'):CLASSES['Textbox'].execute('x'*(1024*1024+1))
    for key in ('SeedGenerator','RandomResolutionLatent','SimpleSampler','SaveImages'):
        state=random.getstate();assert math_is_nan(CLASSES[key].fingerprint_inputs());assert random.getstate()==state
    monkeypatch.setattr(MOD,'local_rng',lambda seed=None:random.Random(41))
    state=random.getstate();rng=random.Random(41)
    expected=int(rng.random()*10000000000000000)
    assert CLASSES['SeedGenerator'].execute('Random',5).result==(expected,str(expected))
    assert CLASSES['SeedGenerator'].execute('Fixed',2**64-1).result==(2**64-1,str(2**64-1))
    assert random.getstate()==state
    with pytest.raises(ValueError,match='allocation'):asyncio.run(direct('RandomResolutionLatent',dict(batch_size=4096)))
    with pytest.raises(ValueError,match='projected'):asyncio.run(direct('ImageTool',dict(image=torch.zeros(1,8,8,3),height=32768,width=32768,crop=False,rotate=0,mirror=False,flip=False,bgcolor='black')))

def test_actual_opaque_frontend_worker_lifecycle():
    result=subprocess.run(['node',str(V2/'tests/ned_chibi_browser.mjs')],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'PASS pinned' in result.stdout and 'QUALIFIED' in result.stdout

def roots(tmp_path,monkeypatch):
    result={}
    for name in ('input','output','temp'):
        path=tmp_path/name;path.mkdir(parents=True);result[name]=path
        monkeypatch.setattr(folder_paths,'get_'+name+'_directory',lambda p=path:str(p))
    return result

def png(value,metadata=None):
    stream=io.BytesIO();info=None
    if metadata is not None:
        info=PngInfo()
        for key,text in metadata.items():info.add_text(key,text)
    Image.fromarray(value).save(stream,format='PNG',compress_level=4,pnginfo=info)
    return stream.getvalue()

@pytest.mark.parametrize('mode',['RGB','RGBA','LA'])
@pytest.mark.parametrize('metadata',[{}, {'prompt':'{"hello":"中文"}'},{'parameters':'a dog\nNegative prompt: cat\nSteps: 20, Seed: 123, Size: 29x17'}])
def test_load_first_frame_metadata_parser_alpha_and_exact_png(mode,metadata,tmp_path,monkeypatch):
    dirs=roots(tmp_path,monkeypatch)
    channels=len(mode);value=np.arange(17*29*channels,dtype=np.uint8).reshape(17,29,channels)
    body=png(value,metadata);path=dirs['input']/'source.png';path.write_bytes(body)
    source=control('LoadImageExtended',folder_paths=SimpleNamespace(get_annotated_filepath=lambda name:str(path)))()
    expected=source.load_image('source.png')
    plan=_sdk.ExecutionPlan(prompt_id='load-control',node_id='1',node_type='LoadImageExtended')
    ctx=_sdk.InProcessCtxProvider().build(plan)
    same(asyncio.run(direct('LoadImageExtended',dict(image='source.png'),ctx)),expected)

@pytest.mark.parametrize('mode',['Timestamp','Fixed','Fixed Single'])
@pytest.mark.parametrize('override',[None,'chosen.with.dots.png'])
def test_save_native_counter_overwrite_filename_order_and_bytes(mode,override,tmp_path,monkeypatch):
    dirs=roots(tmp_path/'converted',monkeypatch);source_dir=tmp_path/'source';source_dir.mkdir()
    clock=SimpleNamespace(time=lambda:1000.4)
    monkeypatch.setattr(MOD,'time',clock)
    for directory in (dirs['output'],source_dir):
        for name in ('1000_007.png','1000_003_extra.png','1000_bad.png','unrelated_999.png'):
            (directory/name).write_bytes(b'counter fixture')
    folders=SimpleNamespace(get_output_directory=lambda:str(source_dir),get_save_image_path=folder_paths.get_save_image_path)
    source=control('SaveImages',folder_paths=folders,os=os,time=clock)()
    pixels=torch.linspace(0,1,2*13*19*3).reshape(2,13,19,3)
    values=dict(filename_type=mode,fixed_filename='fixed',fixed_filename_override=override,images=pixels)
    expected=source.saveimage(**values)
    ctx=_sdk.InProcessCtxProvider().build(_sdk.ExecutionPlan(prompt_id='save-native',node_id='1',node_type='SaveImages'))
    actual=asyncio.run(direct('SaveImages',values,ctx))
    assert actual[0] is pixels and actual[1]==expected['result'][1]
    for name in ast.literal_eval(actual[1]):assert (dirs['output']/name).read_bytes()==(source_dir/name).read_bytes()
    with pytest.raises(UnboundLocalError):source.saveimage(filename_type=mode,fixed_filename='missing')
    with pytest.raises(UnboundLocalError):asyncio.run(direct('SaveImages',dict(filename_type=mode,fixed_filename='missing'),ctx))

def test_native_malformed_parser_font_and_pillow_dtype_boundaries(tmp_path,monkeypatch):
    dirs=roots(tmp_path,monkeypatch)
    path=dirs['input']/'bad.png';path.write_bytes(png(np.zeros((8,8,3),dtype=np.uint8),{'prompt':'not JSON'}))
    native=control('LoadImageExtended',folder_paths=SimpleNamespace(get_annotated_filepath=lambda name:str(path)))()
    with pytest.raises(json.JSONDecodeError):native.load_image('bad.png')
    ctx=_sdk.InProcessCtxProvider().build(_sdk.ExecutionPlan(prompt_id='native-errors',node_id='1',node_type='SaveImages'))
    with pytest.raises(json.JSONDecodeError):asyncio.run(direct('LoadImageExtended',dict(image='bad.png'),ctx))
    with pytest.raises(ValueError,match='font'):asyncio.run(direct('ImageAddText',dict(text='x',width=8,height=8,font='../host.ttf',font_size=12,position_x=0,position_y=0,font_colour='red',invert_mask=False)))
    for dtype,channels in ((torch.bfloat16,3),(torch.float32,1),(torch.float32,5)):
        values=dict(filename_type='Fixed',fixed_filename='native-error',images=torch.zeros(1,8,8,channels,dtype=dtype))
        source=control('SaveImages',folder_paths=SimpleNamespace(get_output_directory=lambda:str(dirs['output']),get_save_image_path=folder_paths.get_save_image_path),os=os)()
        with pytest.raises(TypeError):source.saveimage(**values)
        with pytest.raises(TypeError):asyncio.run(direct('SaveImages',values,ctx))
    assert not list(dirs['output'].glob('native-error*'))

def test_default_latent_bounds_and_loader_refuses_before_service(monkeypatch):
    latent=asyncio.run(direct('RandomResolutionLatent',dict(batch_size=1)))[0]['samples']
    assert latent.dtype==torch.get_default_dtype() and latent.device.type=='cpu'
    class Models:
        async def load_checkpoint(self,*args,**kwargs):raise AssertionError('must refuse before loading')
    ctx=SimpleNamespace(models=Models())
    with pytest.raises(ValueError,match='allocation'):asyncio.run(direct('Loader',dict(Checkpoint='fixture',Vae='Included',stop_at_clip_layer=-1,width=32768,height=32768,batch_size=64),ctx))

@pytest.mark.parametrize('width',[512,768,1024])
@pytest.mark.parametrize('height',[512,768,1024])
def test_all_source_random_resolution_choices_exact_orientation(width,height,monkeypatch):
    monkeypatch.setattr(MOD,'local_rng',lambda seed=None:SimpleNamespace(choice=lambda choices:(width,height)))
    state=random.getstate();monkeypatch.setattr(random,'choice',lambda choices:(width,height))
    expected=control('RandomResolutionLatent')().random_resolution(2)
    random.setstate(state)
    same(asyncio.run(direct('RandomResolutionLatent',dict(batch_size=2))),expected)
    assert random.getstate()==state

@pytest.mark.parametrize('mode',['LA','RGBA'])
def test_save_native_supported_modes_exact_bytes(mode,tmp_path,monkeypatch):
    dirs=roots(tmp_path,monkeypatch)
    pixels=torch.linspace(0,1,2*8*13*len(mode)).reshape(2,8,13,len(mode))
    ctx=_sdk.InProcessCtxProvider().build(_sdk.ExecutionPlan(prompt_id='save-mode',node_id='1',node_type='SaveImages'))
    result=asyncio.run(direct('SaveImages',dict(filename_type='Fixed',fixed_filename=mode,images=pixels),ctx))
    assert result[0] is pixels
    for name,value in zip(ast.literal_eval(result[1]),pixels):
        assert (dirs['output']/name).read_bytes()==png(np.clip(255*value.numpy(),0,255).astype(np.uint8))

def test_actual_two_fresh_required_guests_nonmodel_ids_authored_edit_resource_denial_and_outer(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    dirs=roots(tmp_path/'managed',monkeypatch);author=dirs['input']/'chibi-wildcards';author.mkdir()
    imported=author/'animals.txt';imported.write_bytes(b'imported one\r\nimported two\n')
    pixels=torch.linspace(0,1,2*17*29*3).reshape(2,17,29,3)
    body=png(np.clip(255*pixels[0].numpy(),0,255).astype(np.uint8),{'prompt':'{"source":true}'})
    (dirs['input']/'source.png').write_bytes(body)
    async def run():
        prior=_sdk.providers.execution_backend;pids=[];allowed=()
        try:
            for render in range(2):
                fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
                classes=load('ned_chibi_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS
                for cls in classes.values():cls.GET_SCHEMA()
                session=await GuestSession('ned-chibi-'+str(render),guest_runtime_root=fresh).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=allowed,tenant='chibi-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(key,values,caps=None):
                    nonlocal allowed
                    allowed=tuple(classes[key].SDK_PERMISSIONS) if caps is None else caps
                    cls=classes[key]
                    r=await execution._async_map_node_over_list(prompt_id='chibi-outer',unique_id=key,obj=cls,input_data_all={k:[v] for k,v in values.items()},func=cls.FUNCTION,v3_data=None)
                    return r[0]
                try:
                    assert session.sandbox_kind=='seatbelt'
                    assert (await outer('Int2String',{'Int':-1})).result==('-1',)
                    assert (await outer('LoadEmbedding',{'text':'hello','embedding':'fixture.pt','weight':.5})).result==('hello, (embedding:fixture.pt:0.5)',)
                    assert (await outer('Textbox',{'text':'old','passthrough':'<img literal>中文'})).result==('<img literal>中文',)
                    assert (await outer('TextSplit',dict(text='a.b.c',separator='.',reverse=True,return_half='First Half'))).result==('a.b',)
                    assert (await outer('TextSplit',dict(text='no separator',separator='.',reverse=False,return_half='First Half'))).result==(['no separator'],)
                    assert (await outer('SeedGenerator',dict(mode='Fixed',fixed_seed=8008135))).result==(8008135,'8008135')
                    random_result=(await outer('SeedGenerator',dict(mode='Random',fixed_seed=0))).result
                    assert 0<=random_result[0]<10**16 and random_result[1]==str(random_result[0])
                    latent,width,height=(await outer('RandomResolutionLatent',dict(batch_size=2))).result
                    assert latent['samples'].shape==(2,4,width//8,height//8) and torch.count_nonzero(latent['samples'])==0
                    info=await outer('ImageSizeInfo',{'image':pixels})
                    assert info.result[0] is pixels and info.result[1:]==(29,17) and info.ui=={'width':[29],'height':[17]}
                    ignored=await outer('ImageSizeInfo',{'image':pixels,'width':9000,'height':-17})
                    assert ignored.result[0] is pixels and ignored.result[1:]==(29,17)
                    assert control('ImageSizeInfo')().imagesizeinfo(pixels,9000,-17)['result'][1:]==(29,17)
                    for key,values in [('Prompts',dict(Positive='yes',Negative='')),('ConditionText',dict(text='abc')),('ConditionTextPrompts',dict(positive='a',negative='b')),('ConditionTextMulti',dict(first='a',second='',third='b',fourth='c'))]:
                        c=clip();expected=getattr(control(key)(),control(key).FUNCTION)(clip=clip(),**values)
                        actual=(await outer(key,dict(clip=c,**values))).result
                        for a,e in zip(actual,expected):
                            if isinstance(e,comfy.sd.CLIP):assert a is c
                            else:same(a,e)
                    wild=dict(textfile='animals.txt',keyword='__wildcard__',entries_returned=3,seed=11,text='x __wildcard__')
                    state=random.getstate();expected=control('Wildcards')().wildcards(**wild);random.setstate(state)
                    same((await outer('Wildcards',wild)).result,expected)
                    authored=dict(wild,textfile='chibi-wildcards/animals.txt')
                    result=(await outer('Wildcards',authored)).result
                    assert result[1]!=expected[1]
                    if render==0:assert 'imported' in result[1]
                    else:assert result[1]=='x edited explicit artifact edited explicit artifact edited explicit artifact'
                    imported.write_bytes(b'edited explicit artifact\n')
                    link=author/'outside.txt';outside=tmp_path/'outside.txt';outside.write_bytes(b'forbidden')
                    link.symlink_to(outside)
                    with pytest.raises(Exception):await outer('Wildcards',dict(authored,textfile='chibi-wildcards/outside.txt'))
                    link.unlink()
                    imported.write_bytes(b'')
                    with pytest.raises(Exception,match='IndexError|empty sequence'):await outer('Wildcards',authored)
                    imported.write_bytes(b'edited explicit artifact\n')
                    assert (await outer('Wildcards',authored)).result[1]=='x edited explicit artifact edited explicit artifact edited explicit artifact'
                    for label in ('/etc/passwd','chibi-wildcards/../animals.txt','chibi-wildcards/missing.txt','animals-unknown.txt'):
                        with pytest.raises(Exception):await outer('Wildcards',dict(authored,textfile=label))
                    imported.write_bytes(b'\xffinvalid UTF8')
                    with pytest.raises(Exception,match='UnicodeDecodeError'):await outer('Wildcards',authored)
                    imported.write_bytes(b'x'*(1024*1024+1))
                    with pytest.raises(Exception,match='budget'):await outer('Wildcards',authored)
                    imported.write_bytes(b'edited explicit artifact\n')
                    with pytest.raises(Exception,match='assets|permission|capabil'):await outer('Wildcards',authored,())
                    assert (await outer('Wildcards',wild,())).result==expected
                    args_tool=dict(image=pixels,height=16,width=23,crop=True,rotate=13,mirror=True,flip=False,bgcolor='black')
                    same((await outer('ImageTool',args_tool)).result,control('ImageTool')().imagetools(**args_tool))
                    args_resize=dict(image=pixels,size=32,edge='smallest')
                    same((await outer('ImageSimpleResize',args_resize)).result,control('ImageSimpleResize')().imagesimpleresize(**args_resize))
                    fontargs=dict(text='Hello\nWorld',width=96,height=64,font='Ubuntu-Regular.ttf',font_size=12,position_x=3,position_y=2,font_colour='red',invert_mask=False)
                    same((await outer('ImageAddText',fontargs)).result,control('ImageAddText')().addtext(**fontargs))
                    for key,values in [('ImageTool',args_tool),('ImageAddText',fontargs),('RandomResolutionLatent',dict(batch_size=1))]:
                        with pytest.raises(Exception,match='raw|permission|capabil'):await outer(key,values,())
                    source=control('LoadImageExtended',folder_paths=SimpleNamespace(get_annotated_filepath=lambda name:str(dirs['input']/'source.png')))()
                    same((await outer('LoadImageExtended',dict(image='source.png'))).result,source.load_image('source.png'))
                    for caps in (('raw',),('assets',)):
                        with pytest.raises(Exception,match='raw|assets|permission|capabil'):await outer('LoadImageExtended',dict(image='source.png'),caps)
                    for mode in ('Timestamp','Fixed','Fixed Single'):
                        r=await outer('SaveImages',dict(filename_type=mode,fixed_filename='guest-'+str(render)+'-'+mode.replace(' ',''),images=pixels))
                        assert r.result[0] is pixels
                        names=ast.literal_eval(r.result[1]);assert names==[row['filename'] for row in r.ui['images']]
                        for filename,value in zip(names,pixels):
                            if mode!='Fixed Single':assert (dirs['output']/filename).read_bytes()==png(np.clip(value.numpy()*255,0,255).astype(np.uint8))
                        if mode=='Fixed Single':assert (dirs['output']/names[-1]).read_bytes()==png(np.clip(pixels[-1].numpy()*255,0,255).astype(np.uint8))
                    la=torch.linspace(0,1,2*8*13*2).reshape(2,8,13,2)
                    la_saved=await outer('SaveImages',dict(filename_type='Fixed',fixed_filename='LA-'+str(render),images=la))
                    assert la_saved.result[0] is la
                    for filename,value in zip(ast.literal_eval(la_saved.result[1]),la):
                        assert (dirs['output']/filename).read_bytes()==png(np.clip(value.numpy()*255,0,255).astype(np.uint8))
                    with pytest.raises(Exception,match='UnboundLocalError'):await outer('SaveImages',dict(filename_type='Fixed',fixed_filename='empty'))
                    with pytest.raises(Exception,match='output|permission|capabil'):await outer('SaveImages',dict(filename_type='Fixed',fixed_filename='denied',images=pixels),('assets','raw'))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())

def test_actual_consumer_catalogue_owner_hook_browser_and_queue_admission(tmp_path,monkeypatch):
    result=subprocess.run(['node',str(V2/'tests/ned_chibi_catalogue_browser.mjs')],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    browser=json.loads(result.stdout)
    assert browser['status']=='PASS' and browser['reads']==3
    dirs=roots(tmp_path,monkeypatch);author=dirs['input']/'chibi-wildcards';author.mkdir()
    (author/'current.txt').write_bytes(b'current')
    (author/'animals.txt').write_bytes(b'not bundled')
    (author/'ignore.png').write_bytes(b'not text')
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_chibi_catalogue')
    wildcard=proxy.node_mappings['Wildcards']
    options=wildcard.GET_SCHEMA().inputs[0].options
    assert options[:10]==BUNDLED and set(options[10:])=={'chibi-wildcards/animals.txt','chibi-wildcards/current.txt'}
    socket=wildcard.INPUT_TYPES()['required']['textfile']
    assert socket[0]=='COMBO' and socket[1]['options']==options
    (author/'current.txt').unlink()
    assert 'chibi-wildcards/current.txt' not in wildcard.define_schema().inputs[0].options
    (author/'animals.txt').unlink()
    assert wildcard.define_schema().inputs[0].options==BUNDLED

def test_manifest_pristine_identity_stubs_and_boundary_cache_hygiene():
    assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
    provenance=json.loads((V2/'source-provenance.json').read_text())
    paths={p.relative_to(PACK).as_posix():p for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert set(paths)==set(provenance['archive']['files']) and len(paths)==53
    for rel,p in paths.items():
        body=p.read_bytes();receipt=provenance['archive']['files'][rel]
        assert hashlib.sha256(body).hexdigest()==receipt['sha256']
        assert hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==receipt['git_blob']
        assert p.stat().st_mode&0o777==0o644
    for name,sha in [('comfy-api.pyi','7de9937e919d817f1ae1d5660a99b2fb90737f93946c17207452018730d687d6'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:
        assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
    for path in [V2/'__init__.py',V2/'_secure_nodes.py',*list((V2/'nodes').glob('*.py'))]:
        source=path.read_text()
        for forbidden in ('_from_raw','folder_paths','PromptServer','requests.','subprocess','os.','comfy.sample','common_ksampler'):
            assert forbidden not in source,(path,forbidden)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_exact_pair_zip_reconstruction_twice_and_wrong_pristine_refusal(tmp_path):
    expected,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text())==expected
    assert PAIR.with_suffix('.diff').read_bytes()==diff.encode()
    for index in range(2):
        fresh=tmp_path/str(index)/'comfyui-chibi-nodes/x9a9734f';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if index==0:packpatch.apply(fresh,expected,diff)
        else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    fresh=tmp_path/'bad/comfyui-chibi-nodes/x9a9734f';fresh.mkdir(parents=True)
    shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
    (fresh/PACK.name/'nodes/Wildcards.py').write_bytes(b'#wrong pristine')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
    assert not (fresh/PACK.name/'v2').exists()

@pytest.mark.parametrize('label',['Normal - euler','Normal - uni_pc','LCM Lora - lcm','SDXL Turbo - dpmpp_sde karras'])
@pytest.mark.parametrize('mode',['txt2img','img2img'])
def test_pinned_native_canonical_sampler_callback_noise_and_typo_outcome(label,mode):
    import latent_preview
    calls=[]
    def callback(model,steps):
        def cb(step,x0,x,total):calls.append((step,total))
        return cb
    source=control('SimpleSampler',comfy=sys.modules['comfy'],latent_preview=SimpleNamespace(prepare_callback=callback))()
    latent={'samples':torch.arange(64,dtype=torch.float32).reshape(1,4,4,4)/100,'kept':'source metadata'}
    values=dict(model=model(),sampler=label,positive=[[torch.ones(1,2,4),{}]],negative=[[torch.zeros(1,2,4),{}]],latents=latent,mode=mode,seed=11)
    state=random.getstate()
    try:result=source.sample(**values)
    finally:random.setstate(state)
    assert len(calls)==(8 if label.startswith(('LCM','SDXL')) else 20)
    assert result[0]['samples'].shape==latent['samples'].shape and result[0]['kept']==latent['kept']
    assert result[0] is not latent and random.getstate()==state

def test_actual_fresh_guests_loader_vae_native_model_refs_and_sampler_numerics(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    dirs=roots(tmp_path/'managed',monkeypatch)
    pixels=torch.linspace(0,1,17*29*3).reshape(1,17,29,3)
    (dirs['input']/'source.png').write_bytes(png(np.clip(255*pixels[0].numpy(),0,255).astype(np.uint8)))
    v=vae(monkeypatch);m=model();c=clip();calls=[];names_override=None;progress=[];zero_denoise=False
    async def update(self,value,total,preview=None):
        assert preview is None
        progress.append((value,total))
    monkeypatch.setattr(_sdk._InProcessProgress,'update',update)
    native_sample=comfy.sample.sample
    def measured_sample(*args,**kwargs):
        if zero_denoise:kwargs['denoise']=0
        return native_sample(*args,**kwargs)
    monkeypatch.setattr(comfy.sample,'sample',measured_sample)
    real_names=_sdk._InProcessModels.sampling_names
    async def sampling_names(self):
        if names_override is None:return await real_names(self)
        return {'samplers':names_override,'schedulers':['normal','karras']}
    monkeypatch.setattr(_sdk._InProcessModels,'sampling_names',sampling_names)
    async def checkpoint(self,name,**kwargs):
        if name!='fixture.safetensors':raise ValueError('unknown fixture checkpoint')
        calls.append(('checkpoint',name,kwargs))
        values=await _sdk.wrap_inputs(_sdk.current_runtime().refs,{'model':m,'clip':c,'vae':v},{'model':'MODEL','clip':'CLIP','vae':'VAE'})
        return values['model'],values['clip'],values['vae']
    async def load_vae(self,name,**kwargs):
        if name!='fixture.vae':raise ValueError('unknown fixture VAE')
        calls.append(('vae',name,kwargs))
        return (await _sdk.wrap_inputs(_sdk.current_runtime().refs,{'vae':v},{'vae':'VAE'}))['vae']
    monkeypatch.setattr(_sdk._InProcessModels,'load_checkpoint',checkpoint)
    monkeypatch.setattr(_sdk._InProcessModels,'load_vae',load_vae)
    # These load bindings are recording catalogue/service doubles. The model
    # and VAE execution that follows uses actual canonical tiny CPU objects.
    async def run():
        nonlocal names_override,zero_denoise
        prior=_sdk.providers.execution_backend;pids=[];allowed=()
        try:
            for render in range(2):
                fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
                classes=load('ned_chibi_models_'+str(render),fresh).NODE_CLASS_MAPPINGS
                for cls in classes.values():cls.GET_SCHEMA()
                session=await GuestSession('ned-chibi-models-'+str(render),guest_runtime_root=fresh).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=allowed,tenant='chibi-model-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(key,values,caps=None):
                    nonlocal allowed
                    allowed=tuple(classes[key].SDK_PERMISSIONS) if caps is None else caps
                    cls=classes[key]
                    r=await execution._async_map_node_over_list(prompt_id='chibi-model-outer',unique_id=key,obj=cls,input_data_all={k:[v] for k,v in values.items()},func=cls.FUNCTION,v3_data=None)
                    return r[0]
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for selected in ('Included','fixture.vae'):
                        result=(await outer('Loader',dict(Checkpoint='fixture.safetensors',Vae=selected,stop_at_clip_layer=-3,width=17,height=29,batch_size=2))).result
                        assert result[0] is m and result[1] is v and result[2] is not c
                        assert result[2].cond_stage_model is c.cond_stage_model and result[2].layer_idx==-3 and c.layer_idx is None
                        same(result[3],{'samples':torch.zeros(2,4,3,2)})
                    for caps in (('models',),('raw',)):
                        with pytest.raises(Exception,match='raw|models|permission|capabil'):await outer('Loader',dict(Checkpoint='fixture.safetensors',Vae='Included',stop_at_clip_layer=-1,width=512,height=512,batch_size=1),caps)
                    source=control('ImageSimpleResize')()
                    values=dict(image=pixels,size=32,edge='smallest',vae=v)
                    same((await outer('ImageSimpleResize',values)).result,source.imagesimpleresize(**values))
                    source=control('LoadImageExtended',folder_paths=SimpleNamespace(get_annotated_filepath=lambda name:str(dirs['input']/'source.png')))()
                    same((await outer('LoadImageExtended',dict(image='source.png',vae=v))).result,source.load_image('source.png',v))
                    for label in ('Normal - euler','Normal - uni_pc','LCM Lora - lcm','SDXL Turbo - dpmpp_sde karras'):
                        for mode in ('txt2img','img2img'):
                            latent={'samples':torch.arange(64,dtype=torch.float32).reshape(1,4,4,4)/100,'kept':'source metadata','batch_index':[0]}
                            values=dict(model=m,sampler=label,positive=[[torch.ones(1,2,4),{}]],negative=[[torch.zeros(1,2,4),{}]],latents=latent,mode=mode,seed=11)
                            state=random.getstate();callbacks=[]
                            source=control('SimpleSampler',comfy=sys.modules['comfy'],latent_preview=SimpleNamespace(prepare_callback=lambda model,steps:lambda step,x0,x,total:callbacks.append((step,total))))()
                            try:expected=source.sample(**values)
                            finally:random.setstate(state)
                            progress.clear()
                            actual=(await outer('SimpleSampler',values)).result
                            same(actual,expected);assert actual[0] is not latent and latent['kept']=='source metadata'
                            assert len(callbacks)==(8 if label.startswith(('LCM','SDXL')) else 20)
                            assert progress==[(step+1,total) for step,total in callbacks]
                    for caps in ((),('sample',),('models',)):
                        with pytest.raises(Exception,match='sample|models|permission|capabil'):
                            await outer('SimpleSampler',values,caps)
                    same((await outer('SimpleSampler',values)).result,expected)
                    # Literal membership remains exact: if the name service
                    # includes ddmpp_sde, the pack must NOT secretly use euler.
                    # Actual broker still refuses that unregistered name. This
                    # retains the source-call transport RED as a negative probe.
                    names_override=['ddmpp_sde']
                    with pytest.raises(Exception,match="unknown sampler.*ddmpp_sde"):
                        await outer('SimpleSampler',values)
                    names_override=[]
                    with pytest.raises(Exception,match='IndexError|list index'):
                        await outer('SimpleSampler',values)
                    names_override=None
                    same((await outer('SimpleSampler',values)).result,expected)
                    # Discriminating canonical no-step control: the host
                    # fixture forces denoise=0 on BOTH original and converted
                    # native sampling calls, not a new exposed pack setting.
                    zero_denoise=True;progress.clear();state=random.getstate();callbacks.clear()
                    try:no_steps=source.sample(**values)
                    finally:random.setstate(state)
                    same((await outer('SimpleSampler',values)).result,no_steps)
                    assert progress==callbacks==[]
                    zero_denoise=False
                    decoded=await outer('SaveImages',dict(filename_type='Fixed Single',fixed_filename='decoded-'+str(render),vae=v,latents={'samples':torch.ones(1,3,8,8)}))
                    same(decoded.result[0],v.decode(torch.ones(1,3,8,8)))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())
