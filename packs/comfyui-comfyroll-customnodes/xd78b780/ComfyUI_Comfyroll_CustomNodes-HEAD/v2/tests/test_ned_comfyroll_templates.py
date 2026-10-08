"""Exact pinned template pixels/errors, bounded resources and real raw guest transport."""
import ast,asyncio,copy,importlib.util,json,os,sys
from pathlib import Path
import numpy as np,pytest,torch
from PIL import Image,ImageDraw,ImageOps,ImageFont
sys.dont_write_bytecode=True;sys.argv=['ned-templates','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_templates',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'templates-draft-ledger.json').read_text())
FONTS=NEW.secure_graphics.FONT_NAMES
def pixels(dtype=torch.float32,batch=1,height=61,width=97,channels=3):
    x=torch.linspace(-.1,1.1,max(1,batch*height*width*channels))
    return x[:batch*height*width*channels].reshape(batch,height,width,channels).to(dtype)
def args_for(node_id,**changes):
    args={}
    for group,items in LEDGER[node_id]['source_inputs'].items():
        for k,v in items.items():
            if v[0]=='IMAGE':continue
            args[k]=v[0][0] if isinstance(v[0],list) else v[1]['default']
    if node_id in ('CR Simple Meme Template','CR Simple Banner'):
        args.update(image=pixels(),max_font_size=20)
    if node_id=='CR Simple Meme Template':args.update(text_top='Top',text_bottom='Bottom')
    if node_id=='CR Simple Banner':args.update(banner_text='Hello')
    if node_id=='CR Comic Panel Templates':args.update(page_width=193,page_height=157,images=pixels(batch=4),border_thickness=2,outline_thickness=1)
    if node_id=='CR Simple Image Compare':args.update(image1=pixels(),image2=pixels(width=83,height=47),text1='A',text2='B',font_size=12,footer_height=32,border_thickness=8)
    args.update(changes);return args
def source(node_id,args):
    path=PACK/'nodes/nodes_graphics_template.py'
    selected=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name==LEDGER[node_id]['class'])
    helpers=[copy.deepcopy(n) for n in ast.parse((PACK/'nodes/functions_graphics.py').read_text()).body if isinstance(n,ast.FunctionDef)]
    up=next(n for n in ast.parse((PACK/'nodes/functions_upscale.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='apply_resize_image')
    ns={'__file__':str(path),'os':os,'np':np,'torch':torch,'Image':Image,'ImageDraw':ImageDraw,'ImageOps':ImageOps,'ImageFont':ImageFont,'icons':{},'color_mapping':NEW.secure_graphics.color_mapping,'COLORS':NEW.secure_graphics.COLORS}
    exec(compile(ast.Module(body=helpers+[copy.deepcopy(up),copy.deepcopy(selected)],type_ignores=[]),str(path),'exec'),ns)
    old=ns[LEDGER[node_id]['class']]();return getattr(old,old.FUNCTION)(**args)
def compare(node_id,args):
    if node_id=='CR Simple Image Compare' and args['footer_height']==0 and args.get('image1') is not None and args.get('image2') is not None:
        with pytest.raises(UnboundLocalError,match='text_panel1'):source(node_id,args)
        actual=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result
        expected=footerless_expected(args)
        assert torch.equal(actual[0],expected[0]) and actual[0].dtype==expected[0].dtype and actual[1]==expected[1]
        return
    try:expected=('value',source(node_id,args))
    except Exception as e:expected=('error',type(e),str(e))
    try:actual=('value',NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result)
    except Exception as e:actual=('error',type(e),str(e))
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1:]==expected[1:]
    else:
        a,b=actual[1],expected[1];assert len(a)==len(b)==2 and a[1]==b[1] and type(a[1]) is str
        assert a[0].dtype==b[0].dtype and a[0].shape==b[0].shape and torch.equal(a[0],b[0])

def footerless_expected(args):
    ns={'Image':Image,'ImageOps':ImageOps,'np':np,'torch':torch}
    names={'tensor2pil','pil2tensor','combine_images'}
    helpers=[copy.deepcopy(n) for n in ast.parse((PACK/'nodes/functions_graphics.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
    resize=next(n for n in ast.parse((PACK/'nodes/functions_upscale.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='apply_resize_image')
    exec(compile(ast.Module(body=helpers+[copy.deepcopy(resize)],type_ignores=[]),'source-helper-footerless-intent','exec'),ns)
    a=ns['tensor2pil'](args['image1']);b=ns['tensor2pil'](args['image2'])
    if b.size!=a.size:b=ns['apply_resize_image'](b,a.width,a.height,8,'rescale','false',1,256,'lanczos')
    border=args['border_thickness']//2;color='white' if args['mode']=='normal' else 'black'
    if border>0:a=ImageOps.expand(a,border,fill=color);b=ImageOps.expand(b,border,fill=color)
    image=ns['combine_images']([a,b],'horizontal')
    if border>0:image=ImageOps.expand(image,border,fill=color)
    return ns['pil2tensor'](image),'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-simple-image-compare'

@pytest.mark.parametrize('preset',['custom','One Does Not Simply ... MEME IN COMFY','This is fine.','Good Morning ... No Such Thing!'])
@pytest.mark.parametrize('bars',['no bars','top','bottom','top and bottom','none'])
@pytest.mark.parametrize('outline',['none','thin','thick','extra thick'])
def test_meme_exact_presets_all_bar_branches_outline(preset,bars,outline):
    compare('CR Simple Meme Template',args_for('CR Simple Meme Template',preset=preset,bar_options=bars,font_outline=outline))
@pytest.mark.parametrize('node_id',['CR Simple Meme Template','CR Simple Banner','CR Simple Image Compare'])
@pytest.mark.parametrize('font',FONTS)
def test_all_bundled_fonts_exact_pixels(node_id,font):
    compare(node_id,args_for(node_id,font_name=font))
@pytest.mark.parametrize('node_id',['CR Simple Meme Template','CR Simple Banner'])
@pytest.mark.parametrize('text',['','a\nb','a\nb\nignored','abc🙂<script>','W'*100])
@pytest.mark.parametrize('margin',[0,5,100])
def test_first_two_lines_native_fitting_errors_and_banner_width_height_quirk(node_id,text,margin):
    changes={'text_top':text,'text_bottom':text} if node_id.endswith('Meme Template') else {'banner_text':text,'margin_size':margin}
    compare(node_id,args_for(node_id,**changes))
@pytest.mark.parametrize('outline',[0,1,4])
@pytest.mark.parametrize('color',['black','custom','unknown'])
def test_banner_strokes_custom_color_and_fallback(outline,color):
    compare('CR Simple Banner',args_for('CR Simple Banner',outline_thickness=outline,font_color=color,font_color_hex='#e010af',outline_color='custom',outline_color_hex='#104080'))

@pytest.mark.parametrize('node_id',['CR Simple Meme Template','CR Simple Banner','CR Simple Image Compare'])
@pytest.mark.parametrize('batch',[0,1,2,3])
def test_batch_order_empty_and_native_compare_squeeze(node_id,batch):
    image=pixels(batch=batch)
    changes={'image1':image,'image2':image} if node_id=='CR Simple Image Compare' else {'image':image}
    compare(node_id,args_for(node_id,**changes))
@pytest.mark.parametrize('template',LEDGER['CR Comic Panel Templates']['source_inputs']['required']['template'][0])
@pytest.mark.parametrize('direction',['left to right','right to left'])
@pytest.mark.parametrize('images',[None,0,1,5])
def test_comic_all_ordered_templates_crop_thumbnail_and_partial_panels(template,direction,images):
    compare('CR Comic Panel Templates',args_for('CR Comic Panel Templates',template=template,reading_direction=direction,images=None if images is None else pixels(batch=images)))
@pytest.mark.parametrize('layout',['','G00','G1','Gxx','G44','H','V','H0','H123','V321','X','G22extra'])
def test_comic_native_custom_parse_zero_empty_and_unknown(layout):
    compare('CR Comic Panel Templates',args_for('CR Comic Panel Templates',template='custom',custom_panel_layout=layout))
@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('dtype',[torch.float16,torch.bfloat16,torch.float64,torch.uint8])
@pytest.mark.parametrize('channels',[1,3,4])
def test_dtype_channels_exact_or_native_squeeze_error(node_id,dtype,channels):
    image=pixels(dtype,channels=channels)
    changes={'images':image} if node_id=='CR Comic Panel Templates' else {'image1':image,'image2':image} if node_id=='CR Simple Image Compare' else {'image':image}
    compare(node_id,args_for(node_id,**changes))
@pytest.mark.parametrize('mode',['normal','dark','unknown'])
@pytest.mark.parametrize('images',['both','first','second','none'])
@pytest.mark.parametrize('footer',[0,32])
def test_compare_native_missing_image_footer_error_and_distinct_geometry(mode,images,footer):
    args=args_for('CR Simple Image Compare',mode=mode,footer_height=footer)
    if images in ('second','none'):args['image1']=None
    if images in ('first','none'):args['image2']=None
    compare('CR Simple Image Compare',args)
@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_current_tokens_options_output_and_reload(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,v) for group,items in row['source_inputs'].items() for k,v in items.items()};assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,info=flat[inp.id];assert bool(inp.optional)==(group=='optional')
        if isinstance(info[0],list):assert inp.options==info[0]
        else:assert inp.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert inp.as_dict()[k]==v
    args=args_for(node_id);images={k:v for k,v in args.items() if isinstance(v,torch.Tensor)};scalars={k:v for k,v in args.items() if k not in images}
    compare(node_id,{**json.loads(json.dumps(scalars)),**images})
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
@pytest.mark.parametrize('node_id',list(LEDGER))
def test_bounds_before_pil_or_font_loading(node_id,monkeypatch):
    calls=[];monkeypatch.setattr(NEW.secure_templates,'tensor2pil',lambda *a,**k:calls.append((a,k)))
    args=args_for(node_id)
    if node_id=='CR Comic Panel Templates':args['page_width']=8193
    else:args['font_name']='../../host.ttf'
    with pytest.raises(ValueError,match='bound|immutable'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)
    assert not calls
@pytest.mark.parametrize('node_id',['CR Simple Meme Template','CR Simple Banner','CR Comic Panel Templates'])
def test_whole_batch_allocation_meta_denied_before_work(node_id,monkeypatch):
    calls=[];monkeypatch.setattr(NEW.secure_templates,'tensor2pil',lambda *a,**k:calls.append((a,k)))
    args=args_for(node_id);key='images' if node_id=='CR Comic Panel Templates' else 'image';args[key]=torch.empty(16,4096,4096,3,device='meta')
    with pytest.raises(ValueError,match='bound'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)
    assert not calls
def test_two_actual_fresh_raw_guests_outer_exact_pixels_caps_denial_and_production(tmp_path,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-templates-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        assert plan.input_mode=='values'
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(node_id,args):
                    cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                    r=await execution._async_map_node_over_list(prompt_id='templates',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None);return r[0]
                try:
                    for node_id in LEDGER:
                        for i in range(2):
                            args=args_for(node_id)
                            if i==1 and node_id=='CR Simple Image Compare':
                                args['footer_height']=0
                                with pytest.raises(UnboundLocalError,match='text_panel1'):source(node_id,args)
                                expected=footerless_expected(args)
                            else:expected=source(node_id,args)
                            result=(await execute(node_id,args)).result
                            assert type(result[0]) is torch.Tensor and result[0].dtype==expected[0].dtype and torch.equal(result[0],expected[0]) and result[1]==expected[1]
                        backend.caps=()
                        with pytest.raises(wire.WireError,match='raw'):await execute(node_id,args_for(node_id))
                        backend.caps=('raw',)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-templates-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                for node_id in LEDGER:
                    cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA();args=args_for(node_id)
                    r=await execution._async_map_node_over_list(prompt_id='templates-production',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    r=await execution.resolve_map_node_over_list_results(r);expected=source(node_id,args)
                    assert type(r[0].result[0]) is torch.Tensor and torch.equal(r[0].result[0],expected[0]) and r[0].result[1]==expected[1]
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
