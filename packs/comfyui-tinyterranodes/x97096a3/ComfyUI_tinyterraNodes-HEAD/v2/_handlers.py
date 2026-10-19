"""Boundary adaptations for output, diagnostics, asset and model nodes."""
from __future__ import annotations
import inspect
import re
import torch
import numpy as np
from comfy_api.latest import sdk
from ._merge_log import ttNl
from ._ops import loader,sampler,ttNsave,CC,MAX_RESOLUTION,common_upscale,vae_encode,materialize

async def image_output(image,image_output,output_path,save_prefix,number_padding,file_type,overwrite_existing,embed_workflow,prompt=None,extra_pnginfo=None,my_unique_id=None):
    save=ttNsave(my_unique_id,prompt,extra_pnginfo,number_padding,overwrite_existing,output_path)
    results=await save.images(image,save_prefix,image_output,embed_workflow,file_type)
    return (image,) if image_output in ['Hide','Hide/Save'] else {'ui':{'images':results},'result':(image,)}

async def debug_input(print_to_console,console_title,console_color,debug=None):
    text=str(debug)
    if print_to_console:print(f'{getattr(CC,console_color.upper())}{console_title}\n{text}{CC.CLEAN}')
    return {'ui':{'text':text},'result':()}

async def text_debug(print_to_console,console_title,execute,text,prompt=None,extra_pnginfo=None,my_unique_id=None):
    if print_to_console:
        title=console_title
        if title=='':
            if extra_pnginfo is None:
                title=await sdk.ctx().graph.source_output_label('text',default='')
            else:
                # Preserve the original reader when hidden data is present.
                linked=(prompt or {}).get(str(my_unique_id),{}).get('inputs',{}).get('text')
                for n in extra_pnginfo.get('workflow',{}).get('nodes',[]):
                    if isinstance(linked,list) and str(n.get('id'))==str(linked[0]):
                        outputs=n.get('outputs',[]);title=outputs[linked[1]].get('label') or outputs[linked[1]].get('name');break
        print(f'textDebug[{my_unique_id}] - {title}: {text}')
    return {'ui':{'text':text},'result':(text,)}

async def tiny_loader(ckpt_name,config_name,sampling,zsnr,cfg_rescale_mult,vae_name,clip_skip,empty_latent_aspect,empty_latent_width,empty_latent_height,batch_size,prompt=None,my_unique_id=None):
    model,clip,vae=await loader.load_checkpoint(ckpt_name,config_name,clip_skip)
    sd3=await sampler.get_model_type(model) in ['FLUX','FLOW']
    latent=sampler.emptyLatent(empty_latent_aspect,batch_size,empty_latent_width,empty_latent_height,sd3)
    if vae_name!='Baked VAE':vae=await loader.load_vae(vae_name)
    if sampling!='Default':
        model = await model.patch('model_sampling_discrete', sampling=sampling, zsnr=zsnr)
    if cfg_rescale_mult>0:
        model = await model.patch('rescale_cfg', multiplier=cfg_rescale_mult)
    return model,{'samples':latent},vae,clip,empty_latent_width,empty_latent_height

async def model_scale(model_name,vae,image,rescale_after_model,rescale_method,rescale,percent,width,height,longer_side,crop,image_output,save_prefix,output_latent,prompt=None,extra_pnginfo=None,my_unique_id=None):
    from ._ops import image_ref
    upscale_model=await sdk.ctx().models.load_upscale_model(model_name)
    s=await (await upscale_model.upscale(await image_ref(image))).raw()
    if rescale_after_model==True:
        samples=s.movedim(-1,1);orig_height,orig_width=samples.shape[-2:]
        if rescale=='by percentage' and percent!=0:
            width=sampler.enforce_mul_of_64(min(MAX_RESOLUTION,percent/100*orig_width))
            height=sampler.enforce_mul_of_64(min(MAX_RESOLUTION,percent/100*orig_height))
        elif rescale=='to longer side - maintain aspect':
            longer_side=sampler.enforce_mul_of_64(longer_side)
            if orig_width>orig_height:width,height=longer_side,sampler.enforce_mul_of_64(longer_side*orig_height/orig_width)
            else:width,height=sampler.enforce_mul_of_64(longer_side*orig_width/orig_height),longer_side
        s=(await common_upscale(samples,width,height,rescale_method,crop)).movedim(1,-1)
    if output_latent==True:
        x,y=(s.shape[1]//8)*8,(s.shape[2]//8)*8
        xo,yo=(s.shape[1]%8)//2,(s.shape[2]%8)//2
        pixels=s[:,xo:x+xo,yo:y+yo,:]
        t=await vae_encode(vae,pixels[:,:,:,:3])
        if image_output=='return latent':return {'samples':t}
    else:t=None
    save=ttNsave(my_unique_id,prompt,extra_pnginfo)
    results=await save.images(s,save_prefix,image_output)
    values=({'samples':t},s)
    return values if image_output in ['Hide','Hide/Save'] else {'ui':{'images':results},'result':values}

async def remove_background(image,image_output,save_prefix,prompt=None,extra_pnginfo=None,my_unique_id=None):
    from ._rembg_asset import remove

    image = await remove(sampler.tensor2pil(image))
    tensor = sampler.pil2tensor(image)
    if image.getbands() != ('R','G','B','A'):
        image = image.convert('RGBA')
    if 'A' in image.getbands():
        mask = np.array(image.getchannel('A')).astype(np.float32) / 255.0
        mask = 1. - torch.from_numpy(mask)
    else:
        mask = torch.zeros((64,64),dtype=torch.float32,device=sampler.device)
    if image_output == 'Disabled':
        results = []
    else:
        save = ttNsave(my_unique_id,prompt,extra_pnginfo)
        results = await save.images(tensor,save_prefix,image_output)
    if image_output in ('Hide','Hide/Save'):
        return tensor,mask
    return {'ui':{'images':results},'result':(tensor,mask)}

async def merge_models(
    ckpt_A_name, config_A_name, ckpt_B_name, config_B_name,
    ckpt_C_name, config_C_name, model_interpolation, model_multiplier,
    clip_interpolation, clip_multiplier, model_A_override=None,
    model_B_override=None, model_C_override=None, clip_A_override=None,
    clip_B_override=None, clip_C_override=None, prompt=None,
    extra_pnginfo=None, my_unique_id=None,
):
    weighted_sum = 'Weighted sum = (  A*(1-M) + B*M  )'
    add_difference = 'Add difference = (  A + (B-C)*M  )'
    follow = 'Follow model interp'
    required = {'model_A'}
    if clip_interpolation in ('A Only', 'B Only', 'C Only'):
        required.add(f'clip_{clip_interpolation[0]}')
    elif clip_interpolation in (weighted_sum, add_difference):
        required.update(f'clip_{letter}' for letter in 'ABC' if letter in clip_interpolation)
    elif clip_interpolation == follow:
        required.add('clip_A')
    if model_interpolation in (weighted_sum, add_difference):
        letters = [letter for letter in 'ABC' if letter in model_interpolation]
        required.update(f'model_{letter}' for letter in letters)
        if clip_interpolation == follow:
            required.update(f'clip_{letter}' for letter in letters)

    async def collect(letter, model_override, clip_override, ckpt_name, config_name):
        model, clip, loaded_clip = None, None, None
        if f'model_{letter}' in required:
            if model_override not in (None, 'None'):
                model = model_override
            elif ckpt_name not in (None, 'None'):
                model, loaded_clip, _ = await loader.load_checkpoint(ckpt_name, config_name)
            else:
                error = f'Checkpoint name or model override not provided for model_{letter}.\nUnable to merge models using the following interpolation: {model_interpolation}'
                ttNl(error).t(f'multiModelMerge [{my_unique_id}]').error().p().interrupt(error)
        if f'clip_{letter}' in required:
            if clip_override is not None:
                clip = clip_override
            elif loaded_clip is not None:
                clip = loaded_clip
            elif ckpt_name not in (None, 'None'):
                _, clip, _ = await loader.load_checkpoint(ckpt_name, config_name)
            else:
                error = f'Checkpoint name or clip override not provided for clip_{letter}.\nUnable to merge clips using the following interpolation: {clip_interpolation}'
                ttNl(error).t(f'multiModelMerge [{my_unique_id}]').error().p().interrupt(error)
        return model, clip

    model_A, clip_A = await collect('A', model_A_override, clip_A_override, ckpt_A_name, config_A_name)
    model_B, clip_B = await collect('B', model_B_override, clip_B_override, ckpt_B_name, config_B_name)
    model_C, clip_C = await collect('C', model_C_override, clip_C_override, ckpt_C_name, config_C_name)

    if model_interpolation == 'A Only':
        model = model_A
    elif model_interpolation == weighted_sum:
        model = await model_A.weighted_add(
            model_B, strength_self=1.0 - model_multiplier, strength_other=model_multiplier)
    elif model_interpolation == add_difference:
        difference = await model_B.weighted_add(model_C, strength_self=1.0, strength_other=-1.0)
        model = await model_A.weighted_add(difference, strength_self=1.0, strength_other=model_multiplier)
    if clip_interpolation == follow:
        clip_interpolation = model_interpolation
    if clip_interpolation == 'A Only':
        clip = clip_A
    elif clip_interpolation == 'B Only':
        clip = clip_B
    elif clip_interpolation == 'C Only':
        clip = clip_C
    elif clip_interpolation == weighted_sum:
        clip = await clip_A.weighted_add(
            clip_B, strength_self=1.0 - clip_multiplier, strength_other=clip_multiplier)
    elif clip_interpolation == add_difference:
        difference = await clip_B.weighted_add(clip_C, strength_self=1.0, strength_other=-1.0)
        clip = await clip_A.weighted_add(difference, strength_self=1.0, strength_other=clip_multiplier)
    return model, clip

async def plot_combo(node,widget,mode,start_from,end_with,select,selection,label_type,prompt=None):
    from ._runtime import SCHEMAS,CANONICAL
    if '[' not in node or ']' not in node:return {'ui':{'text':''},'result':('',)}
    nodeid=node.split('[',1)[1].split(']',1)[0]
    kind=(prompt or {}).get(nodeid,{}).get('class_type','')
    original=CANONICAL.get(kind,kind)
    if original in SCHEMAS:
        row=SCHEMAS[original]
        spec=row['inputs'].get('required',{}).get(widget) or row['inputs'].get('optional',{}).get(widget)
        if spec is None:raise KeyError(widget)
        options=list(spec[0])
        for marker in list(options):
            if isinstance(marker,str) and marker.startswith('@catalog:'):
                at=options.index(marker);options[at:at+1]=await sdk.ctx().assets.list(marker[9:])
    else:
        descriptor=await sdk.ctx().graph.input_options(str(nodeid),widget)
        if descriptor['type']!='COMBO':raise TypeError('selected widget is not a combo')
        options=descriptor['options']
    if mode=='all':vals=options
    elif mode=='range':
        a,b=options.index(start_from),options.index(end_with)+1
        if a>b:a,b=b,a
        vals=options[a:b]
    else:vals=[s for s in selection.split('\n') if s in options]
    label={'Values':'v_label','Title and Values':'tv_label','ID, Title and Values':'idtv_label'}[label_type]
    out='\n'.join(part for i,v in enumerate(vals) for part in [f'<{i+1}:{label}>',f"[{nodeid}:{widget}='{v}']"])
    return {'ui':{'text':out},'result':(out,)}

async def plot_images(enabled,image,image_output,save_prefix,file_type,embed_workflow,adv_xyPlot=None,prompt=None,extra_pnginfo=None,my_unique_id=None):
    if enabled==False or adv_xyPlot is None:return image,None
    from ._plot import expand_plot
    return await expand_plot(adv_xyPlot,prompt,extra_pnginfo,my_unique_id,
                             save_prefix,image_output,file_type,embed_workflow)

HANDLERS={'ttN imageOutput':image_output,'ttN debugInput':debug_input,'ttN textDebug':text_debug,'ttN tinyLoader':tiny_loader,'ttN hiresfixScale':model_scale,'ttN imageREMBG':remove_background,'ttN multiModelMerge':merge_models,'ttN advPlot combo':plot_combo,'ttN advPlot images':plot_images}


async def encode_concat(toggle,positive_token_normalization,positive_weight_interpretation,negative_token_normalization,negative_weight_interpretation,pipe=None,positive='',negative='',seed=None,my_unique_id=None,optional_positive_from=None,optional_negative_from=None,optional_clip=None):
    from ._ops import cond_ref
    from ._encoding import advanced_encode
    if toggle==False:return pipe,pipe['positive'],pipe['negative'],pipe['clip']
    pfrom=optional_positive_from if optional_positive_from is not None else pipe['positive']
    nfrom=optional_negative_from if optional_negative_from is not None else pipe['negative']
    clip=optional_clip if optional_clip is not None else pipe['clip']
    async def encode(text,normalization,interpretation,source):
        if '__' in text:text=await loader.nsp_parse(text,pipe['seed'],title='encodeConcat',my_unique_id=my_unique_id)
        emb,pooled=await advanced_encode(clip,text,normalization,interpretation,w_max=1.,apply_to_pooled='enable')
        target=await cond_ref([[emb,{'pooled_output':pooled}]])
        return await target.concat(await cond_ref(source))
    pos=await encode(positive,positive_token_normalization,positive_weight_interpretation,pfrom) if positive not in ['',None,' '] else pipe['positive']
    neg=await encode(negative,negative_token_normalization,negative_weight_interpretation,nfrom) if negative not in ['',None,' '] else pipe['negative']
    new_pipe={k:pipe[k] for k in ['model','vae','samples','images','seed','loader_settings']}
    new_pipe.update(positive=pos,negative=neg,clip=clip)
    return {'result':(new_pipe,pos,neg,clip),'ui':{'string':''}}
HANDLERS['ttN pipeEncodeConcat']=encode_concat
