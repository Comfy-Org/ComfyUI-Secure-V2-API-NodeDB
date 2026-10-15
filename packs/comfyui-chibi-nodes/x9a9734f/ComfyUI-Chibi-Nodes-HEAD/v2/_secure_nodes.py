"""Chibi's pinned algorithms over public opaque services and bounded raw values."""
import io as binary_io
import json
import math
from pathlib import Path
import random
import time
import torch
from comfy_api.latest import io, sdk
from ._schema import schema,SCHEMAS,BUNDLED,FONTS
from ._bounds import text as text_bound,tensor as tensor_bound,image_work,latent_work,TEXT_BYTES
from .nodes.ImageTool import ImageTool as NativeImageTool
from .nodes.ImageSimpleResize import ImageSimpleResize as NativeResize
from .nodes.ImageAddText import ImageAddText as NativeTextImage
from .nodes.LoadImageExtended import parse_image

ROOT=Path(__file__).parent

class Base(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):return schema(cls.__name__)

async def encode(clip,text):
    text_bound(text)
    return await clip.encode_from_tokens(await clip.tokenize(text))

def local_rng(seed=None):return random.Random(seed)

def nan(cls,**kwargs):return float('NaN')

def sampler_fallback(selected,names):
    return selected if selected in names else names[0]

class Loader(Base):
    SDK_PERMISSIONS=('models','raw')
    @classmethod
    async def execute(cls,Checkpoint,Vae,stop_at_clip_layer,width,height,batch_size):
        latent_work(batch_size,height,width)
        model,clip,vae=await sdk.ctx().models.load_checkpoint(Checkpoint)
        if Vae!='Included':vae=await sdk.ctx().models.load_vae(Vae)
        clip=await clip.set_last_layer(stop_at_clip_layer)
        latent=await sdk.LatentRef.from_value({'samples':torch.zeros([batch_size,4,height//8,width//8])})
        return io.NodeOutput(model,vae,clip,latent)

class SimpleSampler(Base):
    SDK_PERMISSIONS=('sample','models')
    fingerprint_inputs=classmethod(nan)
    @classmethod
    async def execute(cls,model,sampler,positive,negative,latents,mode,seed=None,
                      scheduler='normal',sampler_name='euler'):
        steps,cfg=20,7
        if sampler in ('Normal - euler','Normal - uni_pc'):sampler_name='uni_pc'
        elif sampler=='LCM Lora - lcm':sampler_name,steps,cfg='lcm',8,1.8
        elif sampler=='SDXL Turbo - dpmpp_sde karras':
            sampler_name,steps,cfg,scheduler='ddmpp_sde',8,1.8,'karras'
        # Canonical KSampler silently uses its FIRST registered sampler for
        # absent names, including pinned ddmpp_sde. The closed broker refuses
        # unknown strings, so reproduce that fallback through its name service.
        names=(await sdk.ctx().models.sampling_names())['samplers']
        sampler_name=sampler_fallback(sampler_name,names)
        denoise=0.6 if mode=='img2img' else 1.0
        if seed is None:seed=math.floor(local_rng().random()*10000000000000000)
        ctx=sdk.ctx()
        async def on_step(step,total):
            # Closed scalar progress only; no x0/model preview object escapes.
            # Native prepare_callback reports the completed step (step + 1).
            await ctx.progress.update(step+1,total)
            return None
        result=await ctx.sample(latent=latents,model=model,positive=positive,
            negative=negative,steps=steps,cfg=cfg,seed=seed,sampler_name=sampler_name,
            scheduler=scheduler,denoise=denoise,disable_noise=False,start_step=0,
            last_step=steps,force_full_denoise=True,on_step=on_step)
        return io.NodeOutput(result)

class Prompts(Base):
    @classmethod
    async def execute(cls,Positive,Negative,clip=None):
        text_bound(Positive);text_bound(Negative)
        if not clip:return io.NodeOutput(None,None,None,Positive,Negative)
        # Native source tokenizes both before encoding either.
        positive=await clip.tokenize(Positive);negative=await clip.tokenize(Negative)
        return io.NodeOutput(await clip.encode_from_tokens(positive),
            await clip.encode_from_tokens(negative),clip,Positive,Negative)

class ImageTool(Base):
    SDK_PERMISSIONS=('raw',)
    @classmethod
    async def execute(cls,image,height,width,crop,rotate,mirror,flip,bgcolor):
        value=await image.raw();image_work(value,width,height)
        result=NativeImageTool().imagetools(value,height,width,crop,rotate,mirror,flip,bgcolor)[0]
        return io.NodeOutput(await sdk.ImageRef.from_value(result))

class Wildcards(Base):
    SDK_PERMISSIONS=('assets',)
    fingerprint_inputs=classmethod(nan)
    @classmethod
    async def execute(cls,textfile,keyword,entries_returned,clip=None,seed=None,text=''):
        text_bound(text);text_bound(keyword)
        if isinstance(entries_returned,bool) or not isinstance(entries_returned,int):
            raise TypeError('entries_returned must be integer')
        if not 0<=entries_returned<=10:raise ValueError('wildcard draw budget exceeded')
        if textfile in BUNDLED:
            body=(ROOT/'extras/chibi-wildcards'/textfile).read_bytes()
        else:
            if not isinstance(textfile,str) or not textfile.startswith('chibi-wildcards/') or not textfile.endswith('.txt'):
                raise ValueError('unknown wildcard label')
            parts=textfile.split('/')
            if any(not p or p in ('.','..') or '\\' in p or any(ord(c)<32 for c in p) for p in parts):
                raise ValueError('invalid wildcard label')
            asset=await sdk.ctx().assets.resolve('input',textfile)
            size=await sdk.ctx().assets.size(asset)
            if size>TEXT_BYTES:raise ValueError('wildcard file byte budget exceeded')
            body=await sdk.ctx().assets.read_bytes(asset)
            if len(body)!=size:raise ValueError('wildcard file changed during read')
        if len(body)>TEXT_BYTES:raise ValueError('wildcard file byte budget exceeded')
        # Native open() on the admitted UTF-8 runtime includes universal-newline
        # translation, unlike str.splitlines() on vertical tabs/Unicode separators.
        with binary_io.TextIOWrapper(binary_io.BytesIO(body),encoding='utf-8',newline=None) as stream:
            lines=stream.readlines()
        if len(lines)>16384:raise ValueError('wildcard line budget exceeded')
        rng=local_rng(seed);entries=''
        for _ in range(entries_returned):
            line=rng.choice(lines).rstrip()
            projected=len(line.encode('utf-8'))+(len(entries.encode('utf-8'))+1 if entries else 0)
            if projected>TEXT_BYTES:raise ValueError('wildcard draw text byte budget exceeded')
            entries=line if entries=='' else entries+' '+line
        projected=len(text.encode('utf-8'))+text.count(keyword)*(len(entries.encode('utf-8'))-len(keyword.encode('utf-8')))
        if projected>TEXT_BYTES:raise ValueError('wildcard replacement work budget exceeded')
        raw=text.replace(keyword,entries) if text!='' else entries
        text_bound(raw)
        return io.NodeOutput(await encode(clip,raw) if clip else None,raw)

class LoadEmbedding(Base):
    @classmethod
    def execute(cls,text,embedding,weight):
        output=text_bound(text)+', (embedding:'+text_bound(embedding)+':'+str(weight)+')'
        return io.NodeOutput(text_bound(output))

class ConditionText(Base):
    @classmethod
    async def execute(cls,clip,text=None):return io.NodeOutput(clip,await encode(clip,text if text is not None else ''))

class ConditionTextPrompts(Base):
    @classmethod
    async def execute(cls,clip,positive,negative):
        return io.NodeOutput(clip,await encode(clip,positive),await encode(clip,negative))

class ConditionTextMulti(Base):
    @classmethod
    async def execute(cls,clip,first='',second='',third='',fourth=''):
        conds=[await encode(clip,value) for value in (first,second,third,fourth)]
        return io.NodeOutput(clip,*conds)

class Textbox(Base):
    @classmethod
    def execute(cls,text='',passthrough=''):
        text_bound(text);text_bound(passthrough)
        if passthrough!='':return io.NodeOutput(passthrough,ui={'text':passthrough})
        return io.NodeOutput(text)

class ImageSizeInfo(Base):
    @classmethod
    async def execute(cls,image,width=0,height=0):
        height,width=await image.spatial_shape()
        return io.NodeOutput(image,width,height,ui={'width':[width],'height':[height]})

class ImageSimpleResize(Base):
    SDK_PERMISSIONS=('raw',)
    @classmethod
    async def execute(cls,image,size,edge,size_override=None,vae=None):
        value=await image.raw();height,width=value.shape[1:3]
        requested=size_override if size_override else size
        if requested>32768:raise ValueError('resize dimension bound exceeded')
        ratio=height/width
        if edge=='largest':
            projected=(requested,round(requested*ratio)) if width>height else (round(requested/ratio),requested)
        elif edge=='smallest':
            projected=(round(requested/ratio),requested) if width>height else (requested,round(requested*ratio))
        elif edge=='all':projected=(requested,requested)
        elif edge=='width':projected=(requested,height)
        elif edge=='height':projected=(width,requested)
        else:projected=(width,height)
        image_work(value,*projected)
        result=NativeResize().imagesimpleresize(value,size,edge,size_override,None)[0]
        output=await sdk.ImageRef.from_value(result)
        latent=None
        if vae is not None:
            h,w=result.shape[1:3];x=(h//8)*8;y=(w//8)*8
            cropped=result[:,(h%8)//2:x+(h%8)//2,(w%8)//2:y+(w%8)//2,:3]
            latent=await vae.encode(await sdk.ImageRef.from_value(cropped))
        return io.NodeOutput(output,latent)

class ImageAddText(Base):
    SDK_PERMISSIONS=('raw',)
    @classmethod
    async def execute(cls,text,width,height,font,font_size,position_x,position_y,font_colour,invert_mask,image=None):
        text_bound(text)
        if font not in FONTS:raise ValueError('unknown immutable font')
        value=await image.raw() if image is not None else None
        if value is not None:height,width=value.shape[1:3]
        image_work(value,width,height)
        result,mask,label=NativeTextImage().addtext(text,width,height,font,font_size,position_x,position_y,font_colour,invert_mask,value)
        return io.NodeOutput(await sdk.ImageRef.from_value(result),await sdk.MaskRef.from_value(mask),label)

class Int2String(Base):
    @classmethod
    def execute(cls,Int):return io.NodeOutput(str(Int))

class LoadImageExtended(Base):
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    async def execute(cls,image,vae=None):
        asset=await sdk.ctx().assets.resolve('input',image)
        size=await sdk.ctx().assets.size(asset)
        if size>16*1024*1024:raise ValueError('image encoded byte budget exceeded')
        body=await sdk.ctx().assets.read_bytes(asset)
        if len(body)!=size:raise ValueError('image changed during read')
        values=parse_image(body,image.rsplit('/',1)[-1])
        pixels,mask,_,filename,info,width,height=values
        output=await sdk.ImageRef.from_value(pixels);latent=None
        if vae is not None:
            x=(height//8)*8;y=(width//8)*8
            crop=pixels[:,(height%8)//2:x+(height%8)//2,(width%8)//2:y+(width%8)//2,:3]
            latent=await vae.encode(await sdk.ImageRef.from_value(crop))
        return io.NodeOutput(output,await sdk.MaskRef.from_value(mask),latent,filename,info,width,height)
    @classmethod
    async def fingerprint_inputs(cls,image,vae=None):
        asset=await sdk.ctx().assets.resolve('input',image)
        return await sdk.ctx().assets.digest(asset)
    @classmethod
    async def validate_inputs(cls,image,vae=None):
        return True if await sdk.ctx().assets.exists('input',image) else 'Invalid image file: {}'.format(image)

class SeedGenerator(Base):
    fingerprint_inputs=classmethod(nan)
    @classmethod
    def execute(cls,mode,fixed_seed):
        if mode=='Random':
            value=math.floor(local_rng().random()*10000000000000000)
            return io.NodeOutput(value,str(value))
        if mode=='Fixed':return io.NodeOutput(fixed_seed,str(fixed_seed))

class SaveImages(Base):
    SDK_PERMISSIONS=('assets','output','raw')
    fingerprint_inputs=classmethod(nan)
    @classmethod
    async def execute(cls,filename_type,fixed_filename,fixed_filename_override=None,vae=None,latents=None,images=None):
        if fixed_filename_override is not None:fixed_filename=fixed_filename_override.rsplit('.',1)[0]
        now=str(round(time.time()));results=[];names=[]
        async def write(batch):
            values=await batch.raw()
            if not values.shape[0]:raise IndexError('index 0 is out of bounds for empty image batch')
            size=tensor_bound(values)
            if values.ndim==4:
                count,height,width,channels=values.shape
                if count>64 or size+count*height*width*channels*20>192*1024*1024:
                    raise ValueError('saved aggregate workspace byte budget exceeded')
            # Preflight every source Pillow dtype/mode before publishing any
            # frame; no partial writes due to later unsupported channel/dtype.
            from PIL import Image
            import numpy as np
            for pixels in values:
                Image.fromarray(np.clip(255.0*pixels.cpu().numpy(),0,255).astype(np.uint8))
            # Source counts the TIMESTAMP prefix even when naming fixed files.
            listing=await sdk.ctx().assets.list('output',recursive=False)
            maximum=0
            for name in listing:
                try:
                    if name.startswith(now+'_'):maximum=max(maximum,int(name[len(now)+1:].split('_')[0].split('.')[0]))
                except ValueError:pass
            counter=maximum+1
            for frame in await batch.unbatch():
                # Preserve source Pillow/NumPy native dtype/channel failures,
                # including BF16, before asking the common saver to encode.
                if filename_type=='Timestamp':filename=f'{now}_{counter:03}.png'
                elif filename_type=='Fixed':filename=f'{fixed_filename}_{counter:03}.png'
                elif filename_type=='Fixed Single':filename=f'{fixed_filename}.png'
                else:raise UnboundLocalError("local variable 'file' referenced before assignment")
                saved=await sdk.ctx().output.save_images(frame,filenames=[filename],overwrite=True,compress_level=4)
                results.extend(saved['images']);names.append(filename);counter+=1
        if images is not None:
            await write(images)
            return_results=images
        if vae is not None and latents is not None:
            decoded=await vae.decode(latents);await write(decoded);return_results=decoded
        return io.NodeOutput(return_results,str(names),ui={'images':results})

class TextSplit(Base):
    @classmethod
    def execute(cls,text,separator,reverse,return_half):
        text_bound(text);text_bound(separator)
        value=text.rsplit(separator,1) if reverse else text.split(separator,1)
        if len(value)==2:
            if return_half=='First Half':value=value[0]
            if return_half=='Second Half':value=value[1]
        return io.NodeOutput(value)

class RandomResolutionLatent(Base):
    SDK_PERMISSIONS=('raw',)
    fingerprint_inputs=classmethod(nan)
    @classmethod
    async def execute(cls,batch_size):
        choices=[]
        for x in (512,768,1024):
            for y in (512,768,1024):
                for choice in ((x,y),(y,x)):
                    if choice not in choices:choices.append(choice)
        width,height=local_rng().choice(choices)
        # Pinned source uses width on axis2, height on axis3 (not corrected).
        latent_work(batch_size,width,height)
        value=await sdk.LatentRef.from_value({'samples':torch.zeros([batch_size,4,width//8,height//8])})
        return io.NodeOutput(value,width,height)

NODE_CLASS_MAPPINGS={name:globals()[name] for name in SCHEMAS}
