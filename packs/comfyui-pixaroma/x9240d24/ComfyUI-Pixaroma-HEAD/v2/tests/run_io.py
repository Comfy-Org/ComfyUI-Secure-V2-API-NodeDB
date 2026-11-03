"""Finite IO differential; all generated inputs live in a gate temporary tree."""
import asyncio
from dataclasses import replace
import importlib
import inspect
import json
from pathlib import Path
import signal
import struct
import sys
import tempfile
import traceback
import types

sys.path.insert(0, '/tests')
import run_round1 as base
import run_images as images
import numpy as np
from PIL import Image, PngImagePlugin
import folder_paths
from comfy_api.latest import _sdk as sdk, _execution_metadata
from comfy_execution.graph import DynamicPrompt

CASES=json.loads(Path('/tests/io-cases.json').read_text())
RECEIPT={'status':'RUNNING','evidence':'gate, B13 sources 38f28c98','scheduled_cases':len(CASES),'execution':'in-process SDK IO differential','nodes':{},'failures':[],
 'qualification':'decoded pixels, values, UI and metadata; broker filename/absolute-path/metadata additions are separately recorded boundaries; LoRA uses trusted recording operation, not real model weights'}

class Store:
    def __init__(self):self.values={}
    async def get(self,key):return self.values.get(key)
    async def set(self,key,value):assert isinstance(value,str);self.values[key]=value
STORE=Store()
ACTIVE_LORA=[]
LIFECYCLE_CHECKS=0
XY_REFUSAL_EVIDENCE=[]
XY_REFUSAL="comfyui-pixaroma/PixaromaXYPlot is not yet converted to Secure Nodes V2"

def set_dirs(root):
    for name in ('input','output','temp'):
        path=Path(root)/name;path.mkdir(parents=True,exist_ok=True)
        getattr(folder_paths,'set_'+name+'_directory')(str(path))

def assets(root):
    root=Path(root);set_dirs(root)
    (root/'user').mkdir();folder_paths.set_user_directory(str(root/'user'))
    arr=(np.indices((19,27,3)).sum(axis=0)*37%256).astype(np.uint8)
    rgb=Image.fromarray(arr,'RGB');rgb.save(root/'input/rgb.png')
    rgba=rgb.convert('RGBA');rgba.putalpha(Image.fromarray((np.indices((19,27)).sum(axis=0)*13%256).astype(np.uint8),'L'));rgba.save(root/'input/rgba.png')
    rgb.convert('L').save(root/'input/gray.png')
    pal=rgb.convert('P');pal.info['transparency']=0;pal.save(root/'input/palette.png')
    Image.fromarray((np.arange(19*27).reshape(19,27)*111).astype(np.uint16)).save(root/'input/i16.png')
    rgb.save(root/'input/animated.gif',save_all=True,append_images=[rgba.convert('RGB')],duration=50,loop=0)
    rgb.save(root/'input/photo.jpg');rgba.save(root/'input/photo.webp',lossless=True)
    positive={'1':{'class_type':'CLIPTextEncode','inputs':{'text':'synthetic positive α'}},'2':{'class_type':'KSampler','inputs':{'positive':['1',0]}}}
    for filename,chunks in [('comfy.png',{'prompt':json.dumps(positive)}),('a1111.png',{'parameters':'a vivid scene\nNegative prompt: blur\nSteps: 20, Sampler: Euler, CFG scale: 7, Seed: 42, Size: 27x19'}),('nested.png',{'prompt':json.dumps({'1':{'class_type':'PixaromaPromptReader','inputs':{'image':'comfy.png'}}})})]:
        info=PngImagePlugin.PngInfo()
        for key,value in chunks.items():info.add_text(key,value)
        rgb.save(root/'input'/filename,pnginfo=info)
    (root/'input/sub').mkdir();(root/'input/sub/comfy.png').write_bytes((root/'input/comfy.png').read_bytes())
    loras=root/'loras';loras.mkdir();folder_paths.add_model_folder_path('loras',str(loras),is_default=True)
    for name in ('tiny.safetensors','second.safetensors','corrupt.safetensors'):
        (loras/name).write_bytes(b'fixture')

def metadata_plan(node,fields,cls,index,clean=False,deep_ui=False):
    plan=base.plan_for(node,fields,current=str(100+index))
    extra={'workflow':{'nodes':[{'id':17,'type':'PixaromaSaveImage','properties':{'pixSiLastRun':{'old':'preview'},'keep':'yes'}}]},'other':'α'}
    if clean:extra['workflow']['nodes'][0]['properties'].pop('pixSiLastRun')
    if node in ('PixaromaPreview','PixaromaXYPlot') and not deep_ui:extra['workflow']={'nodes':[],'label':'synthetic bounded workflow'}
    dynamic=DynamicPrompt(plan.prompt)
    scope=_execution_metadata.ExecutionMetadataScope(plan.prompt_id,dynamic,extra,observe=True)
    return replace(plan,permissions=tuple(cls.SDK_PERMISSIONS),extra_pnginfo=extra,dynamic_prompt=dynamic,execution_metadata=scope),scope

async def in_runtime(plan,scope,operation):
    refs=sdk.InProcessRefResolver();ctx=sdk.InProcessCtxProvider().build(plan);ctx.storage=STORE;ops=sdk.InProcessOps()
    async def recording(ref,**params):
        asset=await refs.resolve(params['asset']);name=Path(asset.path if hasattr(asset,'path') else str(asset)).name
        # The broker owns AssetRef internals; fixture names can also be read from its public description.
        if isinstance(asset,dict):name=Path(asset.get('name') or asset.get('path','')).name
        ACTIVE_LORA.append((name,params['strength_model'],params['strength_clip']))
        if name=='corrupt.safetensors':raise ValueError('synthetic corrupt fixture')
        model=await refs.resolve(ref);clip=await refs.resolve(params['clip']) if params.get('clip') else None
        model=model+((name,params['strength_model']),)
        clip=clip+((name,params['strength_clip']),) if clip is not None else None
        mr=await refs.create('MODEL',model);cr=await refs.create('CLIP',clip) if clip is not None else None
        return sdk.ModelRef(kind=mr.kind,id=mr.id),sdk.ClipRef(kind=cr.kind,id=cr.id) if cr else None
    ops.register_op('model.apply_lora',recording)
    try:
        with scope,sdk.bind_runtime(refs,ctx,ops):return await operation()
    finally:refs.clear()

def norm(value,previews):
    result=images.normalize_ui(value,previews)
    def visit(item):
        if isinstance(item,list):return [visit(v) for v in item]
        if not isinstance(item,dict):return item
        return {k:'<managed-output>' if k=='folder' and 'saved' in item else visit(v) for k,v in item.items()}
    return visit(result)

async def compare(case,new,root,index):
    global LIFECYCLE_CHECKS
    node=case['node'];fields=images.fixture(case['fields']);cls=new.NODE_CLASS_MAPPINGS[node]
    if node=='PixaromaXYPlot':
        # Retain every R1 input, but qualify full refusal instead of the faulty
        # per-session KV approximation. Do not execute source for a parity claim.
        plan,scope=metadata_plan(node,fields,cls,index,case.get('clean_workflow',False),case.get('deep_ui',False))
        before=dict(STORE.values)
        async def refused():
            validation=cls.validate_inputs(**fields)
            if inspect.isawaitable(validation):validation=await validation
            assert validation==XY_REFUSAL,validation
            for method in ('execute','fingerprint_inputs'):
                try:await getattr(cls,method)(**fields)
                except RuntimeError as error:
                    assert str(error).startswith(XY_REFUSAL+': '),str(error)
                    assert 'eight-session LRU' in str(error),str(error)
                else:raise AssertionError('XY '+method+' must refuse by name')
            assert STORE.values==before,'XY refusal wrote storage'
            XY_REFUSAL_EVIDENCE.append({'label':case['label'],'input_case_index':index,
                'validation':'NAMED-REFUSAL','execute':'NAMED-REFUSAL',
                'fingerprint':'NAMED-LIFECYCLE-REFUSAL','storage_unchanged':True})
            return 'REFUSED-AS-DESIGNED'
        return await in_runtime(plan,scope,refused)
    plan,scope=metadata_plan(node,fields,cls,index,case.get('clean_workflow',False),case.get('deep_ui',False))
    source=getattr(importlib.import_module('pixaroma_recovery_original.'+base.ROWS[node]['module']),node)
    hidden=base.ROWS[node]['input_types'].get('hidden',{})
    original_fields=dict(fields)
    for key,spec in hidden.items():
        if spec=='PROMPT':original_fields[key]=plan.prompt
        if spec=='EXTRA_PNGINFO':original_fields[key]=plan.extra_pnginfo
        if spec=='UNIQUE_ID':original_fields[key]=plan.node_id
    old_root=Path(root)/str(index)/'original';new_root=Path(root)/str(index)/'secure'
    for target in (old_root,new_root):
        for name in ('output','temp'):(target/name).mkdir(parents=True)
        for name in case.get('preexisting',[]):
            p=target/'output'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'preexisting')
    def output_dirs(target):folder_paths.set_output_directory(str(target/'output'));folder_paths.set_temp_directory(str(target/'temp'))
    expected=None;old_previews=[];old_calls=[]
    if not case.get('refused_match'):
        output_dirs(old_root)
        if case.get('lora'):
            import comfy.sd
            original_fields['model']=('MODEL',);original_fields['clip']=('CLIP',) if case['clip'] else None
            instance=source()
            instance._get_lora=lambda path: (Path(path).name,None)
            original_loader=comfy.sd.load_lora_for_models
            def load(model,clip,lora,sm,sc,**kwargs):
                old_calls.append((lora,sm,sc))
                if lora=='corrupt.safetensors':raise ValueError('synthetic corrupt fixture')
                return model+((lora,sm),),clip+((lora,sc),) if clip is not None else None
            comfy.sd.load_lora_for_models=load
            try:expected=instance.apply(**original_fields)
            finally:comfy.sd.load_lora_for_models=original_loader
        else:expected=getattr(source(),base.ROWS[node]['function'])(**original_fields)
        expected_ui=norm(expected.get('ui') if isinstance(expected,dict) else None,old_previews)
        expected_values=expected.get('result',()) if isinstance(expected,dict) else expected
    output_dirs(new_root)
    arguments={key:value for key,value in fields.items() if key not in hidden}
    async def execute():
        global LIFECYCLE_CHECKS
        wrapped=await sdk.wrap_inputs(sdk.current_runtime().refs,arguments)
        if case.get('lora'):
            mr=await sdk.current_runtime().refs.create('MODEL',('MODEL',));wrapped['model']=sdk.ModelRef(kind=mr.kind,id=mr.id)
            if case['clip']:
                cr=await sdk.current_runtime().refs.create('CLIP',('CLIP',));wrapped['clip']=sdk.ClipRef(kind=cr.kind,id=cr.id)
        if case.get('refused_match'):
            try:await cls.execute(**wrapped)
            except RuntimeError as error:
                assert case['refused_match'] in str(error),str(error);return 'REFUSED-AS-DESIGNED'
            raise AssertionError('expected named refusal')
        ACTIVE_LORA.clear();output=await cls.execute(**wrapped)
        if case.get('lora'):
            values=tuple([await sdk.current_runtime().refs.resolve(v) if isinstance(v,sdk.Ref) else v for v in output.args])
            base.equivalent(values,expected_values);base.equivalent(ACTIVE_LORA,old_calls)
            return 'ORCHESTRATION-EXACT-RECORDING-OP'
        base.equivalent(await base.read_output(output.args),expected_values)
        previews=[];actual_ui=norm(output.ui,previews);base.equivalent(actual_ui,expected_ui,'ui')
        assert len(previews)==len(old_previews)
        for (am,aa,ai),(em,ea,ei) in zip(previews,old_previews):
            assert am==em,(am,em);assert aa.dtype==ea.dtype and aa.shape==ea.shape;assert np.array_equal(aa,ea),'decoded pixels'
            if node in ('PixaromaSaveImage','PixaromaPreview','PixaromaXYPlot'):
                for key in ('prompt','workflow','other'):
                    a,e=ai.get(key),ei.get(key)
                    if key in ('prompt','workflow'):
                        a=json.loads(a) if a else a;e=json.loads(e) if e else e
                    base.equivalent(a,e,'metadata/'+key)
        if node=='PixaromaSaveImage' and json.loads(fields['SaveImageState']).get('saveOnRun',True):
            actual=sorted(str(p.relative_to(new_root/'output')) for p in (new_root/'output').rglob('*') if p.is_file())
            wanted=sorted(str(p.relative_to(old_root/'output')) for p in (old_root/'output').rglob('*') if p.is_file())
            assert actual==wanted,(actual,wanted)
        if node in ('PixaromaLoadImage','PixaromaLoadImageMini'):
            base.equivalent(await cls.fingerprint_inputs(**wrapped),source.IS_CHANGED(**original_fields),'fingerprint')
            LIFECYCLE_CHECKS+=1
        if node=='PixaromaPreview':
            base.equivalent(await cls.fingerprint_inputs(**wrapped),source.IS_CHANGED(**original_fields),'fingerprint-before-delete')
            LIFECYCLE_CHECKS+=1
            if fields['save_mode']=='preview':
                for path in (new_root/'temp').rglob('*.png'):path.unlink()
                for path in (old_root/'temp').rglob('*.png'):path.unlink()
                base.equivalent(await cls.fingerprint_inputs(**wrapped),source.IS_CHANGED(**original_fields),'fingerprint-after-delete')
                LIFECYCLE_CHECKS+=1
        return 'PIXELS-VALUES-METADATA-EXACT-MANAGED-UI' if case.get('ui_boundary') and node in ('PixaromaSaveImage','PixaromaPreview','PixaromaXYPlot') else 'PIXELS-AND-VALUES-EXACT-UI-BOUNDARY' if case.get('ui_boundary') else 'EXACT'
    return await in_runtime(plan,scope,execute)

async def main():
    base.namespace('pixaroma_recovery_original',base.PACK);base.namespace('pixaroma_recovery_original.nodes',base.PACK/'nodes')
    with tempfile.TemporaryDirectory(prefix='pixaroma-io-fixtures-') as root:
        assets(root);new=base.load_v2();RECEIPT['schemas']=base.encode_and_check(new)
        for index,case in enumerate(CASES):
            row=RECEIPT['nodes'].setdefault(case['node'],{})
            try:
                verdict=await compare(case,new,root,index);row[verdict]=row.get(verdict,0)+1
            except Exception as error:
                row['MISMATCH']=row.get('MISMATCH',0)+1
                RECEIPT['failures'].append({'index':index,'node':case['node'],'label':case['label'],'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()})
                if len(RECEIPT['failures'])>=12:break
        RECEIPT['status']='PASS' if not RECEIPT['failures'] else 'FAIL'
        RECEIPT['lifecycle_checks']=LIFECYCLE_CHECKS

if __name__=='__main__':
    try:asyncio.run(main())
    except BaseException as error:RECEIPT['status']='FAIL';RECEIPT['failures'].append({'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()})
    finally:
        signal.alarm(0);Path('/results/io-receipt.json').write_text(json.dumps(RECEIPT,indent=2,sort_keys=True)+'\n');print(json.dumps(RECEIPT,indent=2),flush=True)
    if RECEIPT['status']!='PASS':raise SystemExit(1)
