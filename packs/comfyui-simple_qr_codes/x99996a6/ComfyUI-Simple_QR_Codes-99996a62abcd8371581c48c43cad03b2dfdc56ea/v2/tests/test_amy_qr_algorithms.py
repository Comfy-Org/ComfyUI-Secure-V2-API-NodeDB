"""Pinned native algorithms and exact schema; no pristine bytecode writes."""
import ast,hashlib,importlib.util,json,os,sys,types
from pathlib import Path
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1]; PACK=V2.parent
def load(name,root):
 spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
# Source server import is inert; capture only the native requested event.
server=types.ModuleType('server');events=[]
server.PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(send_sync=lambda *args:events.append(args)))
previous=sys.modules.get('server');sys.modules['server']=server
try:OLD=load('amy_qr_old',PACK)
finally:
 if previous is None:sys.modules.pop('server',None)
 else:sys.modules['server']=previous
NEW=load('amy_qr_new',V2)
IDS=list(OLD.NODE_CLASS_MAPPINGS)
def cls(name):return next(i for i,c in OLD.NODE_CLASS_MAPPINGS.items() if c.__name__==name)
def image(dtype=torch.float32,shape=(1,9,13,3)):
 return (torch.arange(int(np.prod(shape))).reshape(shape)%251/250).to(dtype)
def values(node_id,small=True):
 source=OLD.NODE_CLASS_MAPPINGS[node_id];out={}
 for name,spec in source.INPUT_TYPES()['required'].items():
  kind=spec[0];options=spec[1] if len(spec)>1 else {}
  if isinstance(kind,list):out[name]=options.get('default',kind[0])
  elif str(kind)=='IMAGE':out[name]=image()
  elif str(kind)=='*':out[name]=['alpha',' beta ',42]
  else:out[name]=options['default']
 if 'text' in out:out['text']='AMY QR'
 if small:
  if 'width' in out:out.update(width=67,height=53)
  if 'box_size' in out:out['box_size']=3
  if 'width_height_logo' in out:out['width_height_logo']=11
 return out
def same(a,b):
 assert len(a)==len(b)
 for x,y in zip(a,b):
  if isinstance(x,torch.Tensor):
   assert type(y) is torch.Tensor and x.shape==y.shape and x.dtype==y.dtype
   assert torch.equal(x,y)
  else:assert x==y
def differential(node_id,value):
 source=OLD.NODE_CLASS_MAPPINGS[node_id]
 try:expected=getattr(source(),source.FUNCTION)(**value)
 except Exception as error:
  with pytest.raises(type(error)):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**value)
 else:
  actual=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**value)
  if source.__name__=='ShowData':assert actual.ui==expected['ui']
  else:same(actual.result,expected)

def test_complete_census_source_schema_and_capabilities():
 assert IDS==list(NEW.NODE_CLASS_MAPPINGS) and len(IDS)==12
 for node_id,converted in NEW.NODE_CLASS_MAPPINGS.items():
  source=OLD.NODE_CLASS_MAPPINGS[node_id];schema=converted.GET_SCHEMA();schema.validate()
  assert schema.node_id==node_id and schema.category==source.CATEGORY
  assert schema.is_output_node==source.OUTPUT_NODE
  assert schema.is_input_list==bool(getattr(source,'INPUT_IS_LIST',False))
  assert [i.id for i in schema.inputs]==[name for group in ('required','optional') for name in source.INPUT_TYPES().get(group,{})]
  assert [o.io_type for o in schema.outputs]==list(source.RETURN_TYPES)
  assert [o.display_name for o in schema.outputs]==list(getattr(source,'RETURN_NAMES',source.RETURN_TYPES))
  assert converted.SDK_PERMISSIONS==('raw',) and not converted.SDK_REFS
  for field in schema.inputs:
   raw=next(source.INPUT_TYPES()[group][field.id] for group in ('required','optional') if field.id in source.INPUT_TYPES().get(group,{}))
   options=raw[1] if len(raw)>1 else {}
   encoded=field.as_dict()
   for key,value in options.items():
    if key=='forceInput':assert field.extra_dict['forceInput']==value
    else:assert encoded[key]==value
   if isinstance(raw[0],list):assert field.options==raw[0]

@pytest.mark.parametrize('node_id',IDS)
def test_all_twelve_default_source_controls(node_id):
 value=values(node_id,small=False)
 if node_id==cls('ShowData'):value['unique_id']=['own']
 differential(node_id,value)

@pytest.mark.parametrize('name',['QRCodesLogo','QRCodesSimple','QRCodesSimpleBW','QRCodesStyle','QRCodesSegnoFull','QRCodesSegnoSimple','QRCodesSegnoLogo'])
@pytest.mark.parametrize('text',['','HELLO','0123456789','A😀é中文'])
def test_generation_text_pixels_and_masks(name,text):
 node_id=cls(name);value=values(node_id);value['text']=text;differential(node_id,value)

@pytest.mark.parametrize('style',['CircleModuleDrawer','RoundedModuleDrawer','SquareModuleDrawer','GappedSquareModuleDrawer','VerticalBarsDrawer','HorizontalBarsDrawer'])
@pytest.mark.parametrize('color',['RadialGradiantColorMask','SolidFillColorMask','SquareGradiantColorMask','HorizontalGradiantColorMask','VerticalGradiantColorMask'])
def test_all_native_style_and_color_combinations(style,color):
 node_id=cls('QRCodesStyle');value=values(node_id);value.update(style=style,color=color,radius=4)
 differential(node_id,value)

@pytest.mark.parametrize('name',['QRCodesLogo','QRCodesSegnoLogo'])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
@pytest.mark.parametrize('shape',[(1,9,13,3),(1,7,11,4),(1,5,8,1),(2,5,8,3)])
def test_logo_source_aspect_channels_and_native_errors(name,dtype,shape):
 node_id=cls(name);value=values(node_id);value['image']=image(dtype,shape);differential(node_id,value)

@pytest.mark.parametrize('name',['CreateCornerFrame','CreateSolidFrame','CreateTextFrame'])
@pytest.mark.parametrize('frame',[2,3,40])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
def test_frame_exact_pixels_native_source_errors(name,frame,dtype):
 node_id=cls(name);value=values(node_id);value.update(image=image(dtype),frame_size=frame,thickness=3)
 differential(node_id,value)

@pytest.mark.parametrize('items',[[],[''],['one'],['a',' b ',1],['<script>&😀','newline\n'],[torch.arange(12).reshape(3,4)], [np.arange(4,dtype=np.int16)], [np.float32(.25)]])
def test_showdata_native_format_and_owned_event(items):
 node_id=cls('ShowData');events.clear()
 differential(node_id,dict(input=items,data=['unused'],unique_id=['own']))
 assert events[0][0]=='zentrocdot.data_updater.node_processed'
 assert events[0][1]['node']==['own'] and events[0][1]['widget']=='data'

def test_reader_actual_qr_and_blank_output_list():
 generated=OLD.NODE_CLASS_MAPPINGS[cls('QRCodesSimpleBW')]().qr_code_creation('AMY exact reader',290,290)[0]
 # Source squeeze-to-PIL admits its native grayscale BW1HW result directly.
 reader=cls('QRCodeReader');im=generated
 expected=OLD.NODE_CLASS_MAPPINGS[reader]().qr_code_reader(im)
 assert expected[0]==('AMY exact reader',)
 same(NEW.NODE_CLASS_MAPPINGS[reader].execute(image=im).result,expected)
 differential(reader,{'image':generated.permute(1,2,0).repeat(1,1,3).unsqueeze(0)})
 differential(reader,{'image':torch.ones(1,71,73,3)})

def test_pristine_and_source_algorithm_AST_whitelist():
 p=json.loads((V2/'source-provenance.json').read_bytes())
 pristine={f.relative_to(PACK).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in PACK.rglob('*') if f.is_file() and not f.is_relative_to(V2)}
 assert pristine==p['source_hashes'] and len(pristine)==19 and p['git_blob_path_mode_match']
 assert len(p['known_cache_omissions'])==2 and not (PACK/'js').exists()
 for path in (PACK/'nodes').glob('*.py'):
  if path.name=='show_data.py':continue
  old=ast.parse(path.read_text());new=ast.parse((V2/'nodes'/path.name).read_text())
  new.body=[n for n in new.body if not(isinstance(n,ast.ImportFrom) and n.module=='_bounds')]
  for node in ast.walk(new):
   if hasattr(node,'body') and isinstance(node.body,list):
    node.body=[n for n in node.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='qr_pixels')]
  assert ast.dump(old)==ast.dump(new)
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_preallocation_work_limits_and_display_aggregate(monkeypatch):
 from amy_qr_new import _bounds
 with pytest.raises(ValueError,match='pixel'):_bounds.qr_pixels(177,8192,8192)
 with pytest.raises(ValueError,match='pixel'):_bounds.pixels(8192,8192)
 with pytest.raises(ValueError,match='byte'):_bounds.dense(torch.zeros(1).expand(9_000_000))
 with pytest.raises(ValueError,match='byte'):_bounds.dense(np.broadcast_to(np.float32(0),(9_000_000,)))
 with pytest.raises(ValueError,match='aggregate'):_bounds.value_work(['x'*33000,'x'*33000])
 with pytest.raises(ValueError,match='tree'):_bounds.value_work([0]*4096)
 cycle=[];cycle.append(cycle)
 with pytest.raises(ValueError,match='tree'):_bounds.value_work(cycle)
 node_id=cls('QRCodesSimple');value=values(node_id);value.update(box_size=8192)
 module=sys.modules[NEW.NODE_CLASS_MAPPINGS[node_id].__module__]
 import PIL.Image
 monkeypatch.setattr(PIL.Image,'new',lambda *a,**k:(_ for _ in ()).throw(AssertionError('allocated before refusal')))
 with pytest.raises(ValueError,match='intermediate'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**value)

@pytest.mark.parametrize('name',['QRCodesSimple','QRCodesSegnoSimple'])
@pytest.mark.parametrize('field,bad',[('border',-1),('border',1.5),('version',0),('version',41)])
def test_native_invalid_QR_constructor_errors(name,field,bad):
 node_id=cls(name);value=values(node_id);value[field]=bad;differential(node_id,value)

@pytest.mark.parametrize('name',['QRCodesSimple','QRCodesSegnoSimple'])
@pytest.mark.parametrize('factor',[np.int64(8192),'8192',8192])
def test_numpy_and_native_coercible_scaling_cannot_bypass_before_raster(name,factor,monkeypatch):
 node_id=cls(name);value=values(node_id)
 value['box_size' if name=='QRCodesSimple' else 'scale']=factor
 import PIL.Image
 monkeypatch.setattr(PIL.Image,'new',lambda *a,**k:(_ for _ in ()).throw(AssertionError('allocated before refusal')))
 with pytest.raises(ValueError,match='intermediate'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**value)
