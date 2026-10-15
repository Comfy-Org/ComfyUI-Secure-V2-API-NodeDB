"""Raw tensor-family evidence; no VAE/T5/diffusion inference occurs here."""
import ast
import asyncio
import copy
import importlib.util
import logging
import math
import os
from pathlib import Path
import shutil
import sys

import pytest
import torch
import numpy as np

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for root in (CORE, BACKEND):
    sys.path.insert(0, str(root))
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

NODES = {
    'nodes.py': ['WanVideoApplyNAG', 'WanVideoContextOptions',
        'WanVideoAddStandInLatent', 'WanVideoAddExtraLatent', 'WanVideoAddLucyEditLatents',
        'WanVideoMiniMaxRemoverEmbeds', 'WanVideoControlEmbeds', 'WanVideoAddControlEmbeds',
        'WanVideoAddPusaNoise', 'WanVideoEmptyEmbeds', 'WanVideoUniLumosEmbeds',
        'WanVideoPhantomEmbeds', 'WanVideoRealisDanceLatents', 'WanVideoAddMTVMotion',
        'WanVideoSVIProEmbeds', 'WanVideoAddTTMLatents'],
    'nodes_utility.py': ['ExtractStartFramesForContinuations', 'WanVideoLatentReScale',
        'WanVideoPassImagesFromSamples', 'WanVideoPreviewEmbeds'],
    'HuMo/nodes.py': ['WanVideoCombineEmbeds'],
    'Ovi/nodes_ovi.py': ['WanVideoAddOviAudioToLatents', 'WanVideoEmptyMMAudioLatents', 'WanVideoOviCFG'],
    'steadydancer/nodes.py': ['WanVideoAddSteadyDancerEmbeds'],
    'FlashVSR/flashvsr_nodes.py': ['WanVideoAddFlashVSRInput'],
    's2v/nodes.py': ['WanVideoAddS2VEmbeds'],
    'onetoall/nodes.py': ['WanVideoAddOneToAllPoseEmbeds','WanVideoAddOneToAllExtendEmbeds'],
}
IDS = [name for names in NODES.values() for name in names]


def load(name, root=V2):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def old():
    result = {}
    for file, names in NODES.items():
        tree=ast.parse((PACK/file).read_text())
        classes = [item for item in tree.body if isinstance(item, ast.ClassDef) and item.name in names]
        namespace = {'torch':torch, 'log':logging.getLogger('wan-pinned-pure'),
            'math':math, 'np':np, 'VAE_STRIDE':(4,8,8), 'F':torch.nn.functional}
        if file=='s2v/nodes.py':
            helpers=[item for item in tree.body if isinstance(item,ast.FunctionDef)
                and item.name in ('get_sample_indices','linear_interpolation')]
            assert len(helpers)==2
            classes=helpers+classes
        exec(compile(ast.Module(body=classes,type_ignores=[]),str(PACK/file),'exec'),namespace)
        result.update({name:namespace[name] for name in names})
    return result


def equal(left, right):
    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor)
        assert left.shape == right.shape and left.dtype == right.dtype and left.device == right.device
        assert torch.equal(left, right)
    elif isinstance(left, np.ndarray):
        assert isinstance(right,np.ndarray) and left.dtype==right.dtype and left.shape==right.shape
        np.testing.assert_array_equal(left,right)
    elif isinstance(left, dict):
        assert isinstance(right, dict) and left.keys() == right.keys()
        assert list(left.keys()) == list(right.keys())
        for key in left: equal(left[key],right[key])
    elif isinstance(left,(list,tuple)):
        assert type(left) is type(right) and len(left)==len(right)
        for a,b in zip(left,right): equal(a,b)
    else:
        assert left == right


def expected_transport_result(node_id, result):
    # ONLY this observed metadata subtype is normalized by the current wire.
    # Direct algorithm assertions above remain strict, including torch.Size.
    # This does not establish arbitrary consumer/type-checking equivalence.
    if node_id == 'WanVideoControlEmbeds':
        assert isinstance(result[0]['target_shape'],torch.Size)
        output=dict(result[0])
        output['target_shape']=list(output['target_shape'])
        return (output,)
    return result


def test_control_shape_wire_normalization_matches_exact_pinned_noise_shape_consumer():
    tree=ast.parse((PACK/'nodes_sampler.py').read_text())
    assignments=[item for item in ast.walk(tree) if isinstance(item,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='noise' for target in item.targets)
        and isinstance(item.value,ast.Call)
        and any(isinstance(name,ast.Name) and name.id=='target_shape' for name in ast.walk(item.value))]
    assert [item.lineno for item in assignments]==[336,2067]
    shape=torch.Size([16,3,4,6])
    for assignment in assignments:
        code=compile(ast.Module(body=[assignment],type_ignores=[]),str(PACK/'nodes_sampler.py'),'exec')
        for is_5b in [False,True]:
            for has_ref in [False,True]:
                results=[]
                for dimensions in [shape,list(shape)]:
                    namespace={'torch':torch,'target_shape':dimensions,'is_5b':is_5b,'has_ref':has_ref,
                        'lat_target_frames':5,'seed_g':torch.Generator(device='cpu').manual_seed(42)}
                    exec(code,namespace)
                    results.append(namespace['noise'])
                equal(*results)


def cases(node_id):
    tensor = torch.linspace(-3,3,3*4*5*3).reshape(3,4,5,3)
    latent = {'samples':torch.arange(1*16*3*4*5,dtype=torch.float32).reshape(1,16,3,4,5)/100}
    embeds = {'image_embeds':torch.ones(16,3,4,5),'tag':'keep'}
    if node_id == 'WanVideoAddOneToAllPoseEmbeds':
        return [dict(embeds={'tag':'keep','one_to_all_embeds':{'existing':'preserve'}},
            pose_images=tensor.to(dtype)[...,:channels],pose_prefix_image=prefix,
            strength=strength,start_percent=start,end_percent=end,pose_cfg_scale=cfg)
            for dtype in [torch.float32,torch.float64] for channels in [1,3]
            for prefix in [None,tensor[:1],torch.ones(2,4,5,4,dtype=torch.float64)]
            for strength,start,end,cfg in [(0.,0.,1.,1.5),(2.,.25,.75,0.),(100.,1.,0.,10.)]]
    if node_id == 'WanVideoAddOneToAllExtendEmbeds':
        images=torch.linspace(-2,2,12*3*4*4).reshape(12,3,4,4)
        return [dict(embeds={'tag':'keep','one_to_all_embeds':{'existing':'preserve'}},prev_latents=latent,
            if_not_enough_frames=policy,window_size=window,overlap=overlap,frames_processed=processed,
            pose_images=images.to(dtype))
            for dtype in [torch.float32,torch.float64]
            for window,overlap,processed,policy in [(1,0,0,'error'),(5,3,6,'error'),
                (12,0,0,'error'),(15,2,5,'pad_with_last'),(1,20,8,'pad_with_last'),
                (-1,0,0,'error'),(0,0,0,'error'),(5,-2,0,'error'),(2,1,-2,'error')]]+[
            dict(embeds={},prev_latents=latent,if_not_enough_frames='error',pose_images=None)]
    if node_id == 'WanVideoRealisDanceLatents':
        return [dict(ref_latent=latent,pose_cond_start_percent=start,pose_cond_end_percent=end,
            smpl_latent=smpl,hamer_latent=hamer)
            for start,end in [(0.,1.),(.25,.75),(1.,0.)]
            for smpl,hamer in [(latent,None),(None,latent),(latent,latent),
                ({'samples':latent['samples'].double()},latent)]]
    if node_id == 'WanVideoAddMTVMotion':
        return [dict(embeds=embeds,mtv_crafter_motion={'mtv_motion_tokens':torch.arange(6).reshape(2,3).to(dtype),
            'global_mean':torch.zeros(3,dtype=dtype),'global_std':torch.ones(3,dtype=dtype)},
            strength=strength,start_percent=start,end_percent=end)
            for dtype in [torch.float32,torch.float64]
            for strength,start,end in [(0.,0.,1.),(1.,.25,.75),(100.,1.,0.)]] + [
                dict(embeds=embeds,mtv_crafter_motion={'mtv_motion_tokens':torch.arange(6).reshape(2,3).to(torch.float32),
                    'global_mean':np.load(PACK/'MTV/data/mean.npy',allow_pickle=False),
                    'global_std':np.load(PACK/'MTV/data/std.npy',allow_pickle=False)},
                    strength=1.,start_percent=0.,end_percent=1.)]
    if node_id == 'WanVideoSVIProEmbeds':
        return [dict(anchor_samples={'samples':torch.arange(16*2*3*4,dtype=dtype).reshape(1,16,2,3,4)},
            num_frames=frames,prev_samples=prior,motion_latent_count=count)
            for dtype in [torch.float32,torch.float64] for frames in [13,17,81]
            for prior,count in [(None,0),(None,1),
                *[({'samples':torch.arange(16*2*3*4,dtype=prior_dtype).reshape(1,16,2,3,4)},count)
                    for prior_dtype in [torch.float32,torch.float64] for count in [0,1,2,100]]]]
    if node_id == 'WanVideoAddTTMLatents':
        return [dict(embeds=embeds,reference_latents={'samples':torch.arange(channels*2*3*4,dtype=dtype).reshape(1,channels,2,3,4)},
            mask=torch.arange(frames*height*width,dtype=dtype).reshape(frames,height,width),start_step=start,end_step=end)
            for channels in [16,48] for dtype in [torch.float32,torch.float64]
            for frames,height,width in [(1,32,32),(5,48,64),(9,64,32)]
            for start,end in [(-1,1),(0,1),(1,1),(100,1000)]]
    if node_id == 'WanVideoCombineEmbeds':
        return [dict(embeds_1={'keep':torch.ones(1,2,3,dtype=dtype),'shared':'old'},
            embeds_2={'shared':value,'new':torch.zeros(1,2,3,dtype=dtype)})
            for dtype in [torch.float32,torch.float64] for value in [None,'new',torch.ones(2,3)]]
    if node_id == 'WanVideoAddFlashVSRInput':
        return [dict(embeds={'keep':'metadata','flashvsr_strength':'replace','flashvsr_LQ_images':'replace'},
            images=images,strength=strength)
            for images in [tensor[:0],tensor[:1],tensor.double()]
            for strength in [0.,1.,2.,None]]
    if node_id == 'WanVideoAddS2VEmbeds':
        values=[dict(embeds={},frame_window_size=80),
            dict(embeds={'num_frames':1,'keep':'metadata'},frame_window_size=1,audio_scale=0.,
                ref_latent=latent,pose_latent=latent,enable_framepack=True)]
        values.extend(dict(embeds={'num_frames':frames,'keep':'metadata'},frame_window_size=window,
            audio_encoder_output={'encoded_audio_all_layers':[
                torch.arange(length*4,dtype=dtype).reshape(1,length,4)/100+index for index in range(layers)]},
            audio_scale=.5,pose_start_percent=.25,pose_end_percent=.75,ref_latent=latent,
            pose_latent=latent,enable_framepack=True)
            for layers in [1,2,3] for length in [10,50,95] for frames in [1,17,81]
            for window in [1,7,80] for dtype in [torch.float32,torch.float64])
        values.append(dict(embeds={'num_frames':17},frame_window_size=7,
            audio_encoder_output={'encoded_audio_all_layers':[torch.ones(1,50,4),torch.ones(1,50,4,dtype=torch.float64)]}))
        values.append(dict(embeds={'num_frames':81},frame_window_size=-1,
            audio_encoder_output={'encoded_audio_all_layers':[torch.ones(1,10,4)]}))
        values.append(dict(embeds={'num_frames':17},frame_window_size=7,
            audio_encoder_output={'encoded_audio_all_layers':[torch.ones(50,4),torch.ones(50,4,dtype=torch.float64)]}))
        return values
    if node_id == 'WanVideoAddOviAudioToLatents':
        return [dict(original_samples={'samples':latent['samples'].to(dtype),'keep':'video','shared':'old'},
            audio_samples={'latent_ovi_audio':torch.ones(5,20,dtype=dtype),'shared':'new',**extra})
            for dtype in [torch.float32,torch.float64] for extra in [{},{'samples':torch.zeros(2,3)}]]
    if node_id == 'WanVideoEmptyMMAudioLatents':
        return [dict(length=length) for length in [0,1,20,157,10000]]
    if node_id == 'WanVideoOviCFG':
        return [dict(original_text_embeds={'prompt_embeds':[torch.ones(1,2,3,dtype=dtype)],'tag':'keep'},
            ovi_audio_cfg=scale,ovi_negative_text_embeds=negative)
            for dtype in [torch.float32,torch.float64] for scale in [0.,3.,100.]
            for negative in [None,{}, {'prompt_embeds':None}, {'prompt_embeds':[torch.zeros(1,2,3,dtype=dtype)]}]]
    if node_id == 'WanVideoAddSteadyDancerEmbeds':
        return [dict(embeds=embeds,pose_latents_positive={'samples':latent['samples'].to(dtype)},
            pose_strength_spatial=spatial,pose_strength_temporal=temporal,start_percent=start,end_percent=end,
            pose_latents_negative=negative,clip_vision_embeds=clip)
            for dtype in [torch.float32,torch.float64]
            for spatial,temporal,start,end in [(0.,0.,0.,1.),(1.,2.,.25,.75),(100.,100.,1.,0.)]
            for negative in [None,{},latent] for clip in [None,{'clip_embeds':torch.ones(1,2,3)}]]
    if node_id == 'WanVideoEmptyEmbeds':
        return [dict(num_frames=frames,width=width,height=height,control_embeds=control,extra_latents=extra)
            for frames in [1,5,81] for width,height in [(64,64),(832,480)]
            for control in [None,{'control_embeds':{'tag':'keep'}}] for extra in [None,latent]]
    if node_id == 'WanVideoUniLumosEmbeds':
        return [dict(num_frames=frames,width=64,height=64,foreground_latents=foreground,background_latents=background)
            for frames in [1,5,9] for foreground in [None,latent] for background in [None,latent]]
    if node_id == 'WanVideoPhantomEmbeds':
        vace={'vace_context':torch.ones(1,2,3),'vace_scale':.5,'has_ref':True,'vace_start_percent':.1,
            'vace_end_percent':.9,'vace_seq_len':10,'additional_vace_inputs':[]}
        return [dict(num_frames=81,phantom_cfg_scale=5.,phantom_start_percent=.1,phantom_end_percent=.9,
            phantom_latent_1=latent,phantom_latent_2=second,phantom_latent_3=third,phantom_latent_4=fourth,vace_embeds=optional)
            for second,third,fourth in [(None,None,None),(latent,None,None),(None,latent,None),(None,None,latent),(latent,latent,latent)]
            for optional in [None,vace]]
    if node_id == 'WanVideoAddStandInLatent':
        return [dict(embeds=embeds,ip_image_latent=latent,freq_offset=freq) for freq in [0,1,100,-1]]
    if node_id == 'WanVideoAddExtraLatent':
        return [dict(embeds=dict(embeds,extra_latents=prior),extra_latents=latent,latent_index=index)
            for prior in [None,[],[{'samples':torch.zeros(1,16,1,2,3),'index':2}],{'legacy':'one'}]
            for index in [-1000,-1,0,1000]]
    if node_id == 'WanVideoAddLucyEditLatents':
        return [dict(embeds=embeds,extra_latents={'samples':latent['samples'].to(dtype)})
            for dtype in [torch.float32,torch.float64]]
    if node_id == 'WanVideoMiniMaxRemoverEmbeds':
        return [dict(num_frames=frames,width=width,height=height,latents=latent,mask_latents=latent)
            for frames in [1,5,81,10000] for width,height in [(64,64),(832,480),(8096,8096)]]
    if node_id == 'WanVideoControlEmbeds':
        return [dict(latents=latent,start_percent=start,end_percent=end,fun_ref_image=ref)
            for start,end in [(0,1),(.25,.75),(1,0)] for ref in [None,latent]]
    if node_id == 'WanVideoAddControlEmbeds':
        return [dict(embeds=embeds,start_percent=.25,end_percent=.75,fun_ref_image=ref,latents=value)
            for ref in [None,latent] for value in [None,latent]]
    if node_id == 'WanVideoAddPusaNoise':
        return [dict(embeds=embeds,noise_multipliers=noise,noisy_steps=steps)
            for noise in [0.,100.,[0.,.25,1.]] for steps in [-1,0,1000]]
    if node_id == 'ExtractStartFramesForContinuations':
        return [dict(input_video_frames=frames,num_frames=count) for frames in
            [None, tensor, tensor[:0], tensor.double()]
            for count in [1,2,3,9,0,-1]]
    if node_id == 'WanVideoLatentReScale':
        return [dict(samples={'samples':torch.arange(ch*2*3*4,dtype=dtype).reshape(1,ch,2,3,4)/100,'tag':'keep'},direction=direction)
            for ch in [16,48] for dtype in [torch.float32,torch.float64]
            for direction in ['comfy_to_wrapper','wrapper_to_comfy','unchanged']]
    if node_id == 'WanVideoPassImagesFromSamples':
        return [dict(samples={'samples':torch.zeros(1,16,1,1,1),'video':video,'output_path':path})
            for video in [tensor, tensor.double(), tensor[:1]] for path in ['', 'logical-output.webm']]
    if node_id == 'WanVideoPreviewEmbeds':
        return [dict(embeds={'image_embeds':torch.arange(16*2*3*4,dtype=dtype).reshape(16,2,3,4),
            'mask': mask}) for dtype in [torch.float32,torch.float64]
            for mask in [None,torch.ones(1,2,3,4),torch.zeros(1,2,3,4,dtype=torch.float64)]]
    if node_id == 'WanVideoApplyNAG':
        return [dict(original_text_embeds={'prompt_embeds':torch.ones(1,2,3),'tag':'keep'},
            nag_text_embeds={'prompt_embeds':torch.zeros(1,2,3)},nag_scale=scale,nag_tau=2.5,nag_alpha=.25,inplace=flag)
            for scale in [0,11,100] for flag in [True,False]]
    if node_id == 'WanVideoContextOptions':
        return [dict(context_schedule=schedule,context_frames=81,context_stride=4,context_overlap=16,
            freenoise=True,verbose=False,fuse_method=fuse,reference_latent=latent)
            for schedule in ['uniform_standard','uniform_looped','static_standard']
            for fuse in ['linear','pyramid']
            for latent in [None,{'samples':torch.ones(1,16,2,3,4)}]]
    raise AssertionError(node_id)


@pytest.mark.parametrize('node_id', IDS)
def test_exact_schema_and_raw_permission(node_id):
    original = old()[node_id]
    cls = load('_wan_tensor_schema').NODE_CLASS_MAPPINGS[node_id]
    schema = cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.category==original.CATEGORY
    assert schema.description==getattr(original,'DESCRIPTION','')
    assert schema.is_experimental==getattr(original,'EXPERIMENTAL',False)
    assert schema.is_output_node==getattr(original,'OUTPUT_NODE',False)
    source=next(file for file,names in NODES.items() if node_id in names)
    display_ast=next(item.value for item in ast.parse((PACK/source).read_text()).body
        if isinstance(item,ast.Assign) and any(isinstance(target,ast.Name)
        and target.id=='NODE_DISPLAY_NAME_MAPPINGS' for target in item.targets))
    assert schema.display_name==ast.literal_eval(display_ast).get(node_id,node_id)
    fields = original.INPUT_TYPES()
    assert [field.id for field in schema.inputs] == [name for group in fields.values() for name in group]
    for field in schema.inputs:
        spec = fields['optional' if field.optional else 'required'][field.id]
        assert (field.options if isinstance(spec[0],list) else field.io_type)==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items(): assert getattr(field,key)==value
    for index,output in enumerate(schema.outputs):
        assert output.io_type==original.RETURN_TYPES[index]
        assert output.display_name==original.RETURN_NAMES[index]
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)


@pytest.mark.parametrize('node_id', IDS)
def test_exact_tensor_layout_values_metadata_and_source_aliasing(node_id):
    original = old()[node_id]
    cls = load('_wan_tensor_diff').NODE_CLASS_MAPPINGS[node_id]
    for inputs in cases(node_id):
        expected = getattr(original(),original.FUNCTION)(**copy.deepcopy(inputs))
        actual = cls.execute(**copy.deepcopy(inputs)).result
        equal(expected,actual)
    if node_id == 'WanVideoApplyNAG':
        inputs=cases(node_id)[0]; out=cls.execute(**inputs).result[0]
        assert out is not inputs['original_text_embeds']
        assert out['nag_prompt_embeds'] is inputs['nag_text_embeds']['prompt_embeds']
        assert out['prompt_embeds'] is inputs['original_text_embeds']['prompt_embeds']
    if node_id == 'WanVideoContextOptions':
        inputs=cases(node_id)[-1];out=cls.execute(**inputs).result[0]
        assert out['reference_latent'] is inputs['reference_latent']['samples']
    if node_id == 'WanVideoPassImagesFromSamples':
        inputs=cases(node_id)[0];video=inputs['samples']['video'];before=video.clone()
        cls.execute(**inputs)
        assert torch.equal(video,before.clamp(-1,1).add(1).div(2))
    if node_id in ('WanVideoAddStandInLatent','WanVideoAddExtraLatent','WanVideoAddLucyEditLatents',
            'WanVideoAddControlEmbeds','WanVideoAddPusaNoise'):
        inputs=cases(node_id)[-1]; before=copy.deepcopy(inputs['embeds'])
        actual=cls.execute(**inputs).result[0]
        assert actual is not inputs['embeds']
        equal(inputs['embeds'],before)
        assert actual['image_embeds'] is inputs['embeds']['image_embeds']
    if node_id == 'WanVideoCombineEmbeds':
        inputs=cases(node_id)[-1]; before=copy.deepcopy(inputs)
        result=cls.execute(**inputs).result[0]
        assert result is not inputs['embeds_1'] and result is not inputs['embeds_2']
        assert result['keep'] is inputs['embeds_1']['keep']
        assert result['shared'] is inputs['embeds_2']['shared']
        equal(inputs,before)
    if node_id in ('WanVideoAddMTVMotion','WanVideoAddTTMLatents'):
        inputs=cases(node_id)[-1];before=copy.deepcopy(inputs)
        result=cls.execute(**inputs).result[0]
        assert result is not inputs['embeds']
        assert result['image_embeds'] is inputs['embeds']['image_embeds']
        equal(inputs,before)
        if node_id=='WanVideoAddMTVMotion':
            assert result['mtv_crafter_motion']['global_mean'] is inputs['mtv_crafter_motion']['global_mean']
            assert result['mtv_crafter_motion']['global_std'] is inputs['mtv_crafter_motion']['global_std']
    if node_id == 'WanVideoRealisDanceLatents':
        inputs=cases(node_id)[-1];result=cls.execute(**inputs).result[0]
        assert result['ref_latent'] is inputs['ref_latent']['samples']
    if node_id == 'WanVideoSVIProEmbeds':
        inputs=cases(node_id)[-1];before=copy.deepcopy(inputs)
        cls.execute(**inputs)
        equal(inputs,before)
    if node_id == 'WanVideoAddOviAudioToLatents':
        inputs=cases(node_id)[-1];before=copy.deepcopy(inputs)
        result=cls.execute(**inputs).result[0]
        assert result is not inputs['original_samples']
        assert result['samples'] is inputs['audio_samples']['samples']
        assert result['latent_ovi_audio'] is inputs['audio_samples']['latent_ovi_audio']
        equal(inputs,before)
    if node_id == 'WanVideoOviCFG':
        inputs=cases(node_id)[0]; result=cls.execute(**inputs).result[0]
        assert result is not inputs['original_text_embeds']
        assert result['ovi_negative_prompt_embeds'] is inputs['original_text_embeds']['prompt_embeds']
    if node_id == 'WanVideoAddSteadyDancerEmbeds':
        inputs=cases(node_id)[-1];before=copy.deepcopy(inputs)
        result=cls.execute(**inputs).result[0]
        assert result is not inputs['embeds']
        assert result['sdancer_embeds']['clip_fea'] is inputs['clip_vision_embeds']
        assert result['sdancer_embeds']['cond_pos'].data_ptr()==inputs['pose_latents_positive']['samples'].data_ptr()
        equal(inputs,before)


@pytest.mark.parametrize('node_id,inputs', [
    ('WanVideoLatentReScale',{'samples':{'samples':torch.ones(1,4,2,3,4)},'direction':'comfy_to_wrapper'}),
    ('WanVideoPassImagesFromSamples',{'samples':{}}),
    ('WanVideoPreviewEmbeds',{'embeds':{}}),
    ('WanVideoApplyNAG',{'original_text_embeds':{},'nag_text_embeds':{},'nag_scale':11,'nag_tau':2,'nag_alpha':.1}),
    ('WanVideoContextOptions',{'context_schedule':'static_standard','context_frames':81,'context_stride':4,
        'context_overlap':16,'freenoise':True,'verbose':False,'reference_latent':{}}),
    ('WanVideoAddStandInLatent',{'embeds':{},'ip_image_latent':{},'freq_offset':1}),
    ('WanVideoAddExtraLatent',{'embeds':{},'extra_latents':{},'latent_index':0}),
    ('WanVideoAddLucyEditLatents',{'embeds':{},'extra_latents':{}}),
    ('WanVideoMiniMaxRemoverEmbeds',{'num_frames':81,'width':832,'height':480,'latents':{},'mask_latents':{}}),
    ('WanVideoControlEmbeds',{'latents':{'samples':torch.ones(2,16,3,4,5)},'start_percent':0,'end_percent':1}),
    ('WanVideoAddControlEmbeds',{'embeds':{},'latents':{},'start_percent':0,'end_percent':1}),
    ('WanVideoAddPusaNoise',{'embeds':None,'noise_multipliers':1.,'noisy_steps':1}),
    ('WanVideoEmptyEmbeds',{'num_frames':81,'width':832,'height':480,'control_embeds':{}}),
    ('WanVideoUniLumosEmbeds',{'num_frames':81,'width':64,'height':64,'foreground_latents':{}}),
    ('WanVideoPhantomEmbeds',{'num_frames':81,'phantom_cfg_scale':5.,'phantom_start_percent':0.,
        'phantom_end_percent':1.,'phantom_latent_1':{'samples':torch.ones(1,16,2,3,4)},'phantom_latent_2':{'samples':torch.ones(1,16,2,2,4)}}),
    ('WanVideoCombineEmbeds',{'embeds_1':None,'embeds_2':{}}),
    ('WanVideoAddOviAudioToLatents',{'original_samples':None,'audio_samples':{}}),
    ('WanVideoEmptyMMAudioLatents',{'length':-1}),
    ('WanVideoOviCFG',{'original_text_embeds':{'prompt_embeds':[]},'ovi_audio_cfg':3.}),
    ('WanVideoAddSteadyDancerEmbeds',{'embeds':{},'pose_latents_positive':{},
        'pose_strength_spatial':1.,'pose_strength_temporal':1.}),
    ('WanVideoRealisDanceLatents',{'ref_latent':{},'pose_cond_start_percent':0.,'pose_cond_end_percent':1.}),
    ('WanVideoRealisDanceLatents',{'ref_latent':{},'pose_cond_start_percent':0.,'pose_cond_end_percent':1.,'smpl_latent':{}}),
    ('WanVideoAddMTVMotion',{'embeds':{},'mtv_crafter_motion':{},'strength':1.,'start_percent':0.,'end_percent':1.}),
    ('WanVideoSVIProEmbeds',{'anchor_samples':{'samples':torch.ones(1,16,1,2,3)},'num_frames':2}),
    ('WanVideoSVIProEmbeds',{'anchor_samples':{'samples':torch.ones(1,16,3,2,3)},'num_frames':1}),
    ('WanVideoSVIProEmbeds',{'anchor_samples':{'samples':torch.ones(1,16,2,3,4)},'num_frames':13,
        'prev_samples':{'samples':torch.ones(1,16,3,4,5)},'motion_latent_count':1}),
    ('WanVideoAddTTMLatents',{'embeds':{},'reference_latents':{},'mask':torch.ones(1,32,32),'start_step':2,'end_step':1}),
    ('WanVideoAddTTMLatents',{'embeds':{},'reference_latents':{},'mask':torch.ones(1,32,32),'start_step':0,'end_step':1}),
    ('WanVideoAddFlashVSRInput',{'embeds':None,'images':torch.ones(1,2,3,3),'strength':1.}),
    ('WanVideoAddS2VEmbeds',{'embeds':{},'frame_window_size':80,'audio_encoder_output':{}}),
    ('WanVideoAddS2VEmbeds',{'embeds':{},'frame_window_size':80,'audio_encoder_output':{'encoded_audio_all_layers':[]}}),
    ('WanVideoAddS2VEmbeds',{'embeds':{},'frame_window_size':80,'audio_encoder_output':{'encoded_audio_all_layers':[torch.ones(1,10,4)]}}),
    ('WanVideoAddS2VEmbeds',{'embeds':{'num_frames':81},'frame_window_size':0,'audio_encoder_output':{'encoded_audio_all_layers':[torch.ones(1,10,4)]}}),
    ('WanVideoAddS2VEmbeds',{'embeds':{'num_frames':81},'frame_window_size':80,'audio_encoder_output':{'encoded_audio_all_layers':[torch.ones(1,1,4)]}}),
    ('WanVideoAddS2VEmbeds',{'embeds':{},'frame_window_size':80,'ref_latent':{}}),
    ('WanVideoAddOneToAllPoseEmbeds',{'embeds':None,'pose_images':torch.ones(1,2,3,3),'strength':1.}),
    ('WanVideoAddOneToAllPoseEmbeds',{'embeds':{},'pose_images':torch.ones(2,3,3),'strength':1.}),
    ('WanVideoAddOneToAllExtendEmbeds',{'embeds':{},'prev_latents':{},'if_not_enough_frames':'error'}),
    ('WanVideoAddOneToAllExtendEmbeds',{'embeds':{},'prev_latents':{'samples':torch.ones(1,16,1,2,3)},
        'if_not_enough_frames':'error','pose_images':torch.ones(3,2,3,3),'window_size':5}),
    ('WanVideoAddOneToAllExtendEmbeds',{'embeds':{},'prev_latents':{'samples':torch.ones(1,16,1,2,3)},
        'if_not_enough_frames':'pad_with_last','pose_images':torch.ones(3,2,3,3),'frames_processed':3,'overlap':0}),
    ('WanVideoAddOneToAllExtendEmbeds',{'embeds':{},'prev_latents':{'samples':torch.ones(1,16,1,2,3)},
        'if_not_enough_frames':'error','pose_images':torch.empty(0,2,3,3),'window_size':5}),
])
def test_native_malformed_error_equivalence(node_id, inputs):
    original=old()[node_id]
    cls=load('_wan_tensor_error').NODE_CLASS_MAPPINGS[node_id]
    def failure(fn):
        try:fn(**copy.deepcopy(inputs))
        except Exception as exc:return type(exc).__name__,str(exc)
        raise AssertionError('Expected native error')
    assert failure(cls.execute)==failure(getattr(original(),original.FUNCTION))


def test_bounds_precede_latent_rescale_allocation():
    cls=load('_wan_tensor_bounds').NODE_CLASS_MAPPINGS['WanVideoLatentReScale']
    # Expand has a single physical storage scalar; refusal does not allocate
    # a large output or tensor-shaped mean/std materialization.
    oversized=torch.ones(1).expand(1,16,1024,1025,1)
    with pytest.raises(ValueError,match='16777216'):
        cls.execute({'samples':oversized},'comfy_to_wrapper')
    deep={}; cursor=deep
    for index in range(18): cursor['child']={};cursor=cursor['child']
    with pytest.raises(ValueError,match='depth'):
        cls.execute(deep,'comfy_to_wrapper')
    with pytest.raises(ValueError,match='64 MiB'):
        cls.execute({'samples':torch.ones(1,dtype=torch.float64).expand(1,16,1024,1024,1)},'comfy_to_wrapper')
    with pytest.raises(ValueError,match='8192 visited'):
        cls.execute({'fanout':[[0]*4096]*3},'comfy_to_wrapper')


def test_projected_latent_bounds_before_any_tensor_allocation(monkeypatch):
    mapping=load('_wan_projected_bounds').NODE_CLASS_MAPPINGS
    def allocation_forbidden(*args,**kwargs):
        raise AssertionError('Projection should refuse before tensor allocation')
    monkeypatch.setattr(torch,'zeros',allocation_forbidden)
    with pytest.raises(ValueError,match='projected'):
        mapping['WanVideoUniLumosEmbeds'].execute(10000,8096,8096)
    with pytest.raises(ValueError,match='projected'):
        mapping['WanVideoEmptyMMAudioLatents'].execute(10000000)
    with pytest.raises(ValueError,match='projected'):
        mapping['WanVideoSVIProEmbeds'].execute({'samples':torch.ones(1).expand(1,16,1,128,128)},10000)
    # Each leaf is within the input-element limit; only concatenating both
    # would exceed the output projection budget.
    latent={'samples':torch.ones(1).expand(1,16,9,256,256)}
    monkeypatch.setattr(torch,'cat',allocation_forbidden)
    with pytest.raises(ValueError,match='projected'):
        mapping['WanVideoPhantomEmbeds'].execute(81,5.,0.,1.,latent,latent)
    with pytest.raises(ValueError,match='projected'):
        mapping['WanVideoRealisDanceLatents'].execute({},0.,1.,smpl_latent=latent)


def test_mtv_native_numpy_statistics_and_array_quota_denials():
    cls=load('_wan_mtv_native_array_bounds').NODE_CLASS_MAPPINGS['WanVideoAddMTVMotion']
    inputs=copy.deepcopy(cases('WanVideoAddMTVMotion')[-1])
    motion=inputs['mtv_crafter_motion']
    for field in ('global_mean','global_std'):
        assert isinstance(motion[field],np.ndarray)
        assert motion[field].shape==(24,3) and motion[field].dtype==np.float32
    equal(getattr(old()['WanVideoAddMTVMotion'](),'add')(**copy.deepcopy(inputs)),cls.execute(**inputs).result)
    for dtype in (object,np.complex64,np.str_):
        malformed=copy.deepcopy(inputs)
        malformed['mtv_crafter_motion']['global_mean']=np.array([1],dtype=dtype)
        with pytest.raises(TypeError,match='non-object numeric dtype'):
            cls.execute(**malformed)
    oversized=copy.deepcopy(inputs)
    oversized['mtv_crafter_motion']['global_mean']=np.broadcast_to(np.array(1,dtype=np.float32),(16777217,))
    with pytest.raises(ValueError,match='16777216'):
        cls.execute(**oversized)
    oversized['mtv_crafter_motion']['global_mean']=np.broadcast_to(np.array(1,dtype=np.float64),(8388609,))
    with pytest.raises(ValueError,match='64 MiB'):
        cls.execute(**oversized)


def test_s2v_projected_bucket_bounds_before_stack_and_no_mutable_node_state(monkeypatch):
    cls=load('_wan_s2v_projection').NODE_CLASS_MAPPINGS['WanVideoAddS2VEmbeds']
    def allocation_forbidden(*args,**kwargs):
        raise AssertionError('S2V projection must refuse before stacking/allocating audio')
    monkeypatch.setattr(torch,'stack',allocation_forbidden)
    for dimension,window in [(4,10002),(1677721,80)]:
        audio=torch.ones(1).expand(1,10,dimension)
        with pytest.raises(ValueError,match='projected'):
            cls.execute({'num_frames':81},window,audio_encoder_output={'encoded_audio_all_layers':[audio]})
    with pytest.raises(ValueError,match='projected stack'):
        cls.execute({'num_frames':1},1,audio_encoder_output={'encoded_audio_all_layers':[
            torch.ones(1).expand(1,1024,8192),torch.ones(1,dtype=torch.float64).expand(1,1024,8192)]})


def test_s2v_exact_audio_buckets_rng_and_interleaved_calls_without_class_state():
    cls=load('_wan_s2v_interleaved').NODE_CLASS_MAPPINGS['WanVideoAddS2VEmbeds']
    original=old()['WanVideoAddS2VEmbeds']
    first=cases('WanVideoAddS2VEmbeds')[-1]
    second=cases('WanVideoAddS2VEmbeds')[2]
    before=np.random.get_state()
    equal(original().add(**copy.deepcopy(first)),cls.execute(**copy.deepcopy(first)).result)
    equal(original().add(**copy.deepcopy(second)),cls.execute(**copy.deepcopy(second)).result)
    equal(original().add(**copy.deepcopy(first)),cls.execute(**copy.deepcopy(first)).result)
    after=np.random.get_state()
    assert before[0]==after[0] and np.array_equal(before[1],after[1]) and before[2:]==after[2:]
    assert 'video_rate' not in vars(cls)


def test_flash_and_s2v_direct_payload_identity_and_input_immutability():
    mapping=load('_wan_audio_payload_identity').NODE_CLASS_MAPPINGS
    images=torch.arange(36,dtype=torch.float32).reshape(1,3,4,3)
    embeds={'keep':'original','flashvsr_strength':'old'}
    result=mapping['WanVideoAddFlashVSRInput'].execute(embeds,images,2.).result[0]
    assert result is not embeds and embeds=={'keep':'original','flashvsr_strength':'old'}
    assert result['flashvsr_LQ_images'] is images and result['flashvsr_strength']==2.
    input_audio=torch.arange(200,dtype=torch.float64).reshape(1,50,4)
    before=input_audio.clone()
    latent={'samples':torch.ones(1,16,1,2,3)}
    result,count=mapping['WanVideoAddS2VEmbeds'].execute({'num_frames':17},7,
        audio_encoder_output={'encoded_audio_all_layers':[input_audio]},ref_latent=latent,pose_latent=latent).result
    assert torch.equal(input_audio,before)
    assert result['audio_embeds']['ref_latent'] is latent['samples']
    assert result['audio_embeds']['pose_latent'] is latent['samples']
    assert count==result['audio_embeds']['audio_embed_bucket'].shape[-1]


def test_onetoall_nested_source_aliases_and_projected_padding_before_allocations(monkeypatch):
    mapping=load('_wan_onetoall_alias').NODE_CLASS_MAPPINGS
    cls=mapping['WanVideoAddOneToAllPoseEmbeds']
    pose=torch.linspace(-1,1,3*4*5*3).reshape(3,4,5,3)
    prefix=torch.ones(2,4,5,4)
    before=pose.clone();nested={'existing':'keep'};embeds={'one_to_all_embeds':nested}
    result=cls.execute(embeds,pose,1.,pose_prefix_image=prefix).result[0]
    assert result is not embeds and result['one_to_all_embeds'] is nested
    assert nested['pose_prefix_image'].shape==(1,4,2,4,5)
    assert torch.equal(pose,before)
    # The shallow nested-dict mutation is a pinned source behavior, not a
    # grant to mutate host dictionaries through copied guest transport.
    expected_nested={'existing':'keep'}
    expected=old()['WanVideoAddOneToAllPoseEmbeds']().add({'one_to_all_embeds':expected_nested},pose,1.,pose_prefix_image=prefix)
    equal(expected,(result,));equal(nested,expected_nested)
    previous={'samples':torch.ones(1,16,2,3,4)}
    nested={};embeds={'one_to_all_embeds':nested}
    ext=mapping['WanVideoAddOneToAllExtendEmbeds']
    result,slice_images=ext.execute(embeds,previous,'pad_with_last',window_size=5,overlap=0,pose_images=pose).result
    assert result['one_to_all_embeds'] is nested
    assert nested['prev_latents'].data_ptr()==previous['samples'].data_ptr()
    assert slice_images.shape==(5,4,5,3) and torch.equal(slice_images[-1],pose[-1])
    def forbidden(*args,**kwargs):raise AssertionError('Projected refusal must precede clone/repeat/cat')
    monkeypatch.setattr(torch.Tensor,'clone',forbidden)
    monkeypatch.setattr(torch.Tensor,'repeat',forbidden)
    monkeypatch.setattr(torch,'cat',forbidden)
    with pytest.raises(ValueError,match='projected'):
        ext.execute({},previous,'pad_with_last',window_size=10000000,overlap=0,pose_images=pose)
    with pytest.raises(ValueError,match='projected'):
        cls.execute({},torch.tensor(1.).expand(1,1024,1025,4),1.,pose_prefix_image=torch.tensor(1.).expand(1,1024,1025,4))


def test_real_raw_guest_all_tensor_ids_and_capability_denial_fresh_render(tmp_path):
    original=old()
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        failures=[]
        for index,root in enumerate((V2,fresh)):
            mapping=load(f'_wan_tensor_render{index}',root).NODE_CLASS_MAPPINGS
            refs=_sdk.InProcessRefResolver()
            session=await GuestSession('wan-tensors',guest_runtime_root=root).start()
            try:
                for node_id in IDS:
                    try:
                        inputs=copy.deepcopy(cases(node_id)[-1])
                        expected=getattr(original[node_id](),original[node_id].FUNCTION)(**copy.deepcopy(inputs))
                        cls=mapping[node_id]
                        plan=_sdk.ExecutionPlan(prompt_id='wan-tensors',node_id='1',node_type=cls.__name__,
                            node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,inputs),input_mode='values',
                            permissions=('raw',),tier='sandbox')
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match='raw'):
                            await session.execute(plan,runtime,capabilities=())
                        actual=await session.execute(plan,runtime,capabilities=('raw',))
                        value=await _sdk.unwrap_outputs(refs,actual)
                        equal(expected_transport_result(node_id,expected),value.result)
                        print(f'WAN_GUEST_PASS render={index} id={node_id} raw-denial=verified')
                    except Exception as error:
                        failure=f'render={index} id={node_id}: {type(error).__name__}: {error}'
                        failures.append(failure)
                        print(f'WAN_GUEST_FAIL {failure}')
                assert session.last_guest_pid not in (None,os.getpid())
            finally:await session.kill()
        # A failed ID must not hide later IDs, but remains a hard gate failure.
        assert not failures, '\n'.join(failures)
    asyncio.run(run())


def test_public_outer_mask_latent_image_custom_types_and_values(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    from comfy_secure_nodes import packdb
    mapping=packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_tensor_outer').node_mappings
    original=old()
    async def run():
        previous=_sdk.providers.execution_backend
        class Backend:
            sessions=[]
            async def dispatch(self,plan,local_call,runtime):
                # Production CloudExecutionBackend.dispatch performs this
                # value-mode wrapping at execution.py374-377. The narrow
                # adapter must do the same before sending to the real guest.
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                session=await GuestSession('wan-tensor-outer',guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=('raw',))
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        failures=[]
        try:
            for node_id in IDS:
                try:
                    cls=mapping[node_id];cls.GET_SCHEMA()
                    inputs=copy.deepcopy(cases(node_id)[-1])
                    expected=getattr(original[node_id](),original[node_id].FUNCTION)(**copy.deepcopy(inputs))
                    finalized,missing,data=execution.get_input_data(inputs,cls,'1',None)
                    assert not missing
                    values=await execution._async_map_node_over_list(prompt_id='wan-tensor-outer',unique_id='1',obj=cls,
                        input_data_all=finalized,func='execute',v3_data=data)
                    equal(expected_transport_result(node_id,expected),values[0].result)
                    assert tuple(cls.RETURN_TYPES)==original[node_id].RETURN_TYPES
                    print(f'WAN_OUTER_PASS id={node_id} types={cls.RETURN_TYPES}')
                except Exception as error:
                    failure=f'id={node_id}: {type(error).__name__}: {error}'
                    failures.append(failure)
                    print(f'WAN_OUTER_FAIL {failure}')
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:await session.kill()
        assert not failures, '\n'.join(failures)
    asyncio.run(run())
