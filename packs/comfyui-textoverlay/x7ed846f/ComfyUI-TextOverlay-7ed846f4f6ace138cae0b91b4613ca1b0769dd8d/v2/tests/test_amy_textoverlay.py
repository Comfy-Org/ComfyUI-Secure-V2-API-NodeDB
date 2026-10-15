"""Exact native pixels/errors, bounded font transport and pre-op sentinels."""
import asyncio,ast,hashlib,importlib.util,os,sys,types
from pathlib import Path
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
BACKEND=Path(os.environ['TEXTOVERLAY_BACKEND_ROOT'])
sys.path[:0]=[str(CORE),str(BACKEND)]
from comfy.cli_args import args
args.cpu=True
from comfy_api.latest import _sdk,io
import folder_paths
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
FONT=Path(os.environ['TEXTOVERLAY_TEST_FONT'])
FONT_SHA=os.environ['TEXTOVERLAY_TEST_FONT_SHA256']
assert FONT.is_file() and not FONT.is_symlink()
FONT_BYTES=FONT.read_bytes()
assert len(FONT_BYTES)<=2*1024*1024 and hashlib.sha256(FONT_BYTES).hexdigest()==FONT_SHA

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

OLD=load('amy_textoverlay_native',PACK)
NEW=load('amy_textoverlay_v2',V2)
SOURCE=sys.modules['amy_textoverlay_native.nodes']
CONVERTED=sys.modules['amy_textoverlay_v2.nodes']
GUARD=sys.modules['amy_textoverlay_v2._bounds']
NODE=NEW.NODE_CLASS_MAPPINGS['Text Overlay']
NODE.GET_SCHEMA().validate()

def defaults(dtype=torch.float32,shape=(2,48,80,3)):
    values={name:(spec[1]['default'] if len(spec)>1 and 'default' in spec[1] else spec[0][0]) for name,spec in SOURCE.TextOverlay.INPUT_TYPES()['required'].items() if name!='image'}
    count=int(np.prod(shape));values['image']=torch.linspace(0,1,count).reshape(shape).to(dtype)
    return values

def native(values):
    instance=SOURCE.TextOverlay()
    return instance.batch_process(**values)

def same(a,b):
    assert type(a)==type(b) and len(a)==len(b)
    for x,y in zip(a,b):
        assert x.shape==y.shape and x.dtype==y.dtype and x.device==y.device
        assert torch.equal(x.contiguous().reshape(-1).view(torch.uint8),y.contiguous().reshape(-1).view(torch.uint8))

@pytest.fixture(autouse=True)
def inputs(tmp_path,monkeypatch):
    root=tmp_path/'inputs';(root/'textoverlay').mkdir(parents=True)
    (root/'textoverlay/positive.ttf').write_bytes(FONT_BYTES)
    (root/'textoverlay/invalid.ttf').write_bytes(b'not a font')
    monkeypatch.setattr(folder_paths,'get_input_directory',lambda:str(root))
    return root

async def typed(values):
    resolver=_sdk.InProcessRefResolver()
    wrapped=await _sdk.wrap_inputs(resolver,values,{item.id:item.io_type for item in NODE.GET_SCHEMA().inputs})
    with _sdk.bind_runtime(resolver,types.SimpleNamespace(assets=_sdk._InProcessAssets()),_sdk.InProcessOps()):
        output=await NODE.execute(**wrapped)
        return (await _sdk.unwrap_outputs(resolver,output)).result

def test_one_backend_no_frontend_schema_options_defaults_and_only_font_delta():
    assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['Text Overlay']
    schema=NODE.GET_SCHEMA();source=SOURCE.TextOverlay.INPUT_TYPES()['required']
    assert [item.id for item in schema.inputs]==list(source)
    assert schema.category==SOURCE.TextOverlay.CATEGORY and len(schema.outputs)==1
    assert schema.outputs[0].io_type=='IMAGE' and NODE.SDK_REFS is True
    assert NODE.SDK_PERMISSIONS==('inspect','raw','assets')
    normalized=NODE.INPUT_TYPES()['required']
    for name,spec in source.items():
        if isinstance(spec[0],list):
            assert normalized[name][0]=='COMBO' and normalized[name][1]['options']==spec[0]
        else:assert normalized[name][0]==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert normalized[name][1][key]==value
    assert normalized['font'][1]['default']=='ariblk.ttf'
    def cls(path):return next(node for node in ast.parse(path.read_text()).body if isinstance(node,ast.ClassDef) and node.name=='TextOverlay')
    old,new=cls(PACK/'nodes.py'),cls(V2/'nodes.py')
    for item in (old,new):
        draw=next(node for node in item.body if isinstance(node,ast.FunctionDef) and node.name=='draw_text')
        assert isinstance(draw.body[1],ast.If)
        draw.body[1]=ast.Pass()
    assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
    assert not list(V2.rglob('*.js')) and not hasattr(NEW,'WEB_DIRECTORY')

@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.uint8,torch.int16,torch.int64,torch.bool])
@pytest.mark.parametrize('custom',[False,True])
def test_bit_exact_source_dtypes_and_font_pixels(dtype,custom):
    fields=defaults(dtype);source=dict(fields)
    if custom:fields['font']='positive.ttf';source['font']=str(FONT)
    same(asyncio.run(typed(fields)),native(source))

@pytest.mark.parametrize('horizontal',['left','center','right'])
@pytest.mark.parametrize('vertical',['top','middle','bottom'])
def test_align_wrap_newlines_utf8_stroke_shifts_spacing_source(horizontal,vertical):
    fields=defaults()|dict(text='Hello\nwrap words \n世界 😀 end',font='positive.ttf',font_size=14,
        horizontal_alignment=horizontal,vertical_alignment=vertical,padding=5,x_shift=-3,y_shift=4,
        stroke_thickness=.6,line_spacing=3.5,fill_color_hex='#ABC',stroke_color_hex='123456')
    source=fields|{'font':str(FONT)}
    same(asyncio.run(typed(fields)),native(source))

@pytest.mark.parametrize('text',['','Hello','\n','a\n\nb','longword'*5,'   spaces   '])
def test_default_missing_font_fallback_native_text(text):
    fields=defaults()|{'text':text}
    same(asyncio.run(typed(fields)),native(fields))

def test_invalid_font_fallback_and_three_digit_hex_bug(inputs):
    fields=defaults()|{'font':'invalid.ttf','fill_color_hex':'#ABC'}
    same(asyncio.run(typed(fields)),native(fields|{'font':str(inputs/'textoverlay/invalid.ttf')}))
    assert SOURCE.TextOverlay().hex_to_rgb('#ABC')==(0xAB,0xCA,0xBC)
    assert CONVERTED.TextOverlay().hex_to_rgb('#ABC')==(0xAB,0xCA,0xBC)

@pytest.mark.parametrize('shape',[(48,80,3),(1,48,80,4),(0,48,80,3),(1,0,80,3),(1,48,80,1),(1,48,80,2)])
def test_single_batch_rgba_empty_channel_native_result_or_error(shape):
    fields=defaults(shape=shape)
    try:expected=native(fields)
    except Exception as original:
        with pytest.raises(type(original)) as error:asyncio.run(typed(fields))
        assert str(error.value)==str(original)
    else:same(asyncio.run(typed(fields)),expected)

def test_native_bfloat_numpy_and_color_error_preserved():
    for fields in (defaults(torch.bfloat16),defaults()|{'fill_color_hex':'badhex'}):
        with pytest.raises(Exception) as old:native(fields)
        with pytest.raises(type(old.value)) as new:asyncio.run(typed(fields))
        assert str(old.value)==str(new.value)

def test_batch_cache_font_loaded_once_and_layout_reused(monkeypatch):
    fields=defaults(shape=(3,48,80,3))|{'font':'positive.ttf'}
    calls=[];real=CONVERTED.ImageFont.truetype
    def recorded(*args,**kwargs):calls.append(args);return real(*args,**kwargs)
    monkeypatch.setattr(CONVERTED.ImageFont,'truetype',recorded)
    result=asyncio.run(typed(fields));assert len(calls)==1
    monkeypatch.setattr(CONVERTED.ImageFont,'truetype',real)
    same(result,native(fields|{'font':str(FONT)}))

@pytest.mark.parametrize('update',[{'text':'x'*4097},{'font':'../escape.ttf'},{'font':'/absolute.ttf'},
    {'font':'bad\\name.ttf'},{'font_size':9999},{'line_spacing':float('nan')},{'image':torch.empty(0,1_000_000,1_000_000,0)},
    {'text':{'object':'not string'}}])
def test_preoperation_sentinel_before_assets_raw_or_font(update,monkeypatch):
    fields=defaults()|update
    def forbidden(*args,**kwargs):raise AssertionError('native formatting/allocation was reached')
    async def no_buffers(*args,**kwargs):raise AssertionError('font/raw buffers were reached before preflight')
    monkeypatch.setattr(CONVERTED.TextOverlay,'batch_process',forbidden)
    monkeypatch.setattr(GUARD,'font_bytes',no_buffers)
    monkeypatch.setattr(GUARD,'raw',no_buffers)
    with pytest.raises((GUARD.ProfileError,TypeError)):asyncio.run(typed(fields))

def test_font_bounds_changed_size_permissions_and_no_whole_read(monkeypatch):
    class Assets:
        calls=[];size_value=4;data=b'abcd';tail=b'';final_size=4
        async def exists(self,*args):self.calls.append(('exists',args));return True
        async def resolve(self,*args):self.calls.append(('resolve',args));return object()
        async def size(self,asset):return self.final_size if any(row[0]=='range' for row in self.calls) else self.size_value
        async def read_bytes(self,*args):raise AssertionError('whole file read forbidden')
        async def read_range(self,asset,offset,length):self.calls.append(('range',offset,length));return self.data if offset==0 else self.tail
    asset=Assets();monkeypatch.setattr(GUARD.sdk,'ctx',lambda:types.SimpleNamespace(assets=asset))
    assert asyncio.run(GUARD.font_bytes('fixture.ttf'))==b'abcd'
    assert ('resolve',('input','textoverlay/fixture.ttf')) in asset.calls
    for size,data,tail,final in [(GUARD.MAX_FONT+1,b'',b'',0),(4,b'abc',b'',4),(4,b'abcd',b'x',5),(4,b'abcd',b'',5)]:
        asset.calls=[];asset.size_value=size;asset.data=data;asset.tail=tail;asset.final_size=final
        with pytest.raises(GUARD.ProfileError):asyncio.run(GUARD.font_bytes('fixture.ttf'))
    async def denied(*args):raise PermissionError('assets refused')
    asset.exists=denied
    with pytest.raises(PermissionError):asyncio.run(GUARD.font_bytes('fixture.ttf'))

def test_font_label_and_glyph_limit_before_native_font_allocation():
    fields=defaults();shape=tuple(fields['image'].shape)
    for label in ('..','.', 'x:y','x\n.ttf','x'*256):
        with pytest.raises(GUARD.ProfileError):GUARD.font_label(label)
    assert GUARD.font_label('positive.ttf')=='textoverlay/positive.ttf'
    for shape in ((0,2**30,2**30,0),(1,2048,2048,4)):
        with pytest.raises(GUARD.ProfileError):GUARD.plan(shape,fields)
    assert GUARD.plan((1,48,80,3),fields)['glyph_work']<=GUARD.MAX_GLYPH_WORK
