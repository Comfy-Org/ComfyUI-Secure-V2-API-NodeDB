"""Guest computations and bounded SDK operations for tinyterra nodes.

Only buffers materialize here. Live model, CLIP and VAE objects stay in the host.
"""
from __future__ import annotations
import contextvars
import datetime
import hashlib
import io as byteio
import json
import re
import random
from pathlib import PurePosixPath
import torch
import numpy as np
from PIL import Image, ImageFont
from comfy_api.latest import sdk
from ._encoding import advanced_encode
MAX_RESOLUTION = 16384

class CC:
    BLACK='\033[30m'; RED='\033[31m'; GREEN='\033[32m'; YELLOW='\033[33m'
    BLUE='\033[34m'; VIOLET='\033[35m'; CYAN='\033[36m'; WHITE='\033[37m'
    GREY='\033[90m'; LIGHTRED='\033[91m'; LIGHTGREEN='\033[92m'; LIGHTYELLOW='\033[93m'
    LIGHTBLUE='\033[94m'; LIGHTVIOLET='\033[95m'; LIGHTCYAN='\033[96m'; LIGHTWHITE='\033[97m'; CLEAN='\033[0m'
class ttNl:
    def __init__(self,text):self.text=text;self.title=''
    def t(self,title):self.title=title;return self
    def warn(self):return self
    def error(self):return self
    def full(self):return self
    def p(self):print(f'{self.title}: {self.text}');return self
    def interrupt(self,e):raise ValueError(e)

async def image_ref(x):
    return x if isinstance(x,sdk.ImageRef) else await sdk.ImageRef.from_value(x)
async def latent_ref(x):
    return x if isinstance(x,sdk.LatentRef) else await sdk.LatentRef.from_value(x)
async def cond_ref(x):
    return x if isinstance(x,sdk.CondRef) else await sdk.CondRef.from_value(x)
async def materialize(x):
    if isinstance(x,(sdk.ImageRef,sdk.MaskRef,sdk.TensorRef)):return await x.raw()
    if isinstance(x,sdk.LatentRef):return await x.value()
    if isinstance(x,dict):return {k:await materialize(v) for k,v in x.items()}
    if isinstance(x,list):return [await materialize(v) for v in x]
    if isinstance(x,tuple):return tuple([await materialize(v) for v in x])
    return x
async def vae_decode(vae,latent):
    if not isinstance(latent,(dict,sdk.LatentRef)):latent={'samples':latent}
    return await (await vae.decode(await latent_ref(latent))).raw()
async def vae_encode(vae,image):
    return (await (await vae.encode(await image_ref(image))).value())['samples']
async def clip_layer(clip,layer):return await clip.set_last_layer(layer)
async def clip_encode(clip,tokens,return_pooled=False):
    c=await (await clip.encode_from_tokens_scheduled(tokens)).value()
    return (c[0][0],c[0][1].get('pooled_output')) if return_pooled else c[0][0]

# Pack-owned font data is supplied as bytes by the immutable asset catalogue.
async def font_bytes():
    asset=await sdk.ctx().assets.resolve('tinyterra','arial.ttf')
    return await sdk.ctx().assets.read_bytes(asset)
def pack_font(font_size):
    data=_services.get().get('font')
    if data is None:
        raise RuntimeError('Plot labels require the bundled arial.ttf pack asset')
    return ImageFont.truetype(byteio.BytesIO(data),font_size)

class Loader:
    def clear_cache(self,*a,**kw):pass # The host owns model caching and resource lifetime.
    @staticmethod
    def string_to_seed(s):return int.from_bytes(hashlib.sha256(s.encode()).digest(),'big') & 0xffffffffffffffff
    @staticmethod
    async def nsp_parse(text,seed=0,noodle_key='__',nspterminology=None,pantry_path=None,title=None,my_unique_id=None):
        if '__' not in text:return text
        if nspterminology is None:
            # No network acquisition or source-adjacent mutable state in a guest.
            asset=await sdk.ctx().assets.resolve('input','nsp_pantry.json')
            nspterminology=json.loads((await sdk.ctx().assets.read_bytes(asset)).decode())
        rng=random.Random(seed) if seed else random.Random()
        for term in nspterminology:
            key=f'{noodle_key}{term}{noodle_key}'
            for _ in range(text.count(key)):
                text=text.replace(key,rng.choice(nspterminology[term]),1)
                seed+=1;rng.seed(seed)
        return text
    async def load_checkpoint(self,ckpt_name,config_name=None,clip_skip=0,output_vae=True,output_clip=True):
        if config_name in [None,'Default']:
            model,clip,vae=await sdk.ctx().models.load_checkpoint(ckpt_name)
        else:
            model,clip,vae=await sdk.ctx().models.load_checkpoint(ckpt_name,config_name=config_name)
        if clip_skip and clip is not None:
            if await sampler.get_model_type(model) in ['FLUX','FLOW']:
                raise Exception('FLOW and FLUX do not support clip_skip. Set clip_skip to 0.')
            clip=await clip.set_last_layer(clip_skip)
        return model,clip if output_clip else None,vae if output_vae else None
    async def load_vae(self,vae_name):return await sdk.ctx().models.load_vae(vae_name)
    async def load_lora(self,lora_name,model,clip,strength_model,strength_clip):
        if strength_model==0 and strength_clip==0:return model,clip
        if not await sdk.ctx().assets.exists('loras',lora_name):
            ttNl(lora_name).t('Skipping missing lora').p();return model,clip
        asset=await sdk.ctx().assets.resolve('loras',lora_name)
        return await model.apply_lora(asset,clip,strength_model,strength_clip)
    async def load_lora_text(self,loras,model,clip):
        names=await sdk.ctx().assets.list('loras')
        lookup={n.split('\\')[-1]:n for n in names}
        for match in re.findall(r'<lora:[^>]+>',loras):
            if not re.match(r'^<lora:.*?:[-0-9.]+(:[-0-9.]+)*>$',match):continue
            parts=match[6:-1].split(':');name=parts[0]
            if name not in lookup:continue
            wm=float(parts[1]);wc=float(parts[2]) if len(parts)>2 else wm
            model,clip=await self.load_lora(lookup[name],model,clip,wm,wc)
        return model,clip
    async def load_main3(self,ckpt_name,config_name,vae_name,loras,clip_skip,model_override=None,clip_override=None,optional_lora_stack=None,unique_id=None):
        if model_override is None or clip_override is None or vae_name=='Baked VAE':
            model,clip,vae=await self.load_checkpoint(ckpt_name,config_name,clip_skip)
        else:model,clip,vae=model_override,clip_override,None
        if model_override is not None:model=model_override
        if clip_override is not None:
            clip=clip_override
            if clip_skip:
                if await sampler.get_model_type(model) in ['FLUX','FLOW']:raise Exception('FLOW and FLUX do not support clip_skip. Set clip_skip to 0.')
                clip=await clip.set_last_layer(clip_skip)
        if vae_name!='Baked VAE':vae=await self.load_vae(vae_name)
        for row in optional_lora_stack or []:model,clip=await self.load_lora(row[0],model,clip,row[1],row[2])
        if loras not in [None,'None']:model,clip=await self.load_lora_text(loras,model,clip)
        if not clip:raise Exception('No CLIP found')
        return model,clip,vae
    async def load_controlNet(self,positive,negative,controlnet_name,image,strength,start_percent,end_percent):
        control=await sdk.ctx().models.load_controlnet(controlnet_name) if isinstance(controlnet_name,str) else controlnet_name
        p,n=await control.apply(await cond_ref(positive),await cond_ref(negative),await image_ref(image),strength,start_percent,end_percent)
        return p,n
    async def embedding_encode(self,text,token_normalization,weight_interpretation,clip,seed=None,title=None,my_unique_id=None,prepend_text=None,zero_out=False):
        text=f'{prepend_text} {text}' if prepend_text is not None else text
        text=await self.nsp_parse(text,self.string_to_seed(text) if seed is None else seed,title=title,my_unique_id=my_unique_id)
        embedding,pooled=await advanced_encode(clip,text,token_normalization,weight_interpretation,w_max=1.0,apply_to_pooled='enable')
        c=[[embedding,{'pooled_output':pooled}]]
        if zero_out is True and text.strip()=='':return await (await (await cond_ref(c)).zero_out()).value()
        return c
    async def embedding_encodeXL(self,text,clip,seed=0,title=None,my_unique_id=None,prepend_text=None,text2=None,prepend_text2=None,width=None,height=None,crop_width=0,crop_height=0,target_width=None,target_height=None,refiner_clip=None,ascore=None):
        text=f'{prepend_text} {text}' if prepend_text is not None else text
        text=await self.nsp_parse(text,seed,title=title,my_unique_id=my_unique_id)
        target_width=target_width if target_width is not None else width
        target_height=target_height if target_height is not None else height
        refiner=None
        if text2 is not None and refiner_clip is not None:
            text2=f'{prepend_text2} {text2}' if prepend_text2 is not None else text2
            text2=await self.nsp_parse(text2,seed,title=title,my_unique_id=my_unique_id)
            refiner=await (await refiner_clip.encode_from_tokens_scheduled(await refiner_clip.tokenize(text2),{'aesthetic_score':ascore,'width':width,'height':height})).value()
        if text2 is None or text2.strip()=='':text2=text
        tokens=await clip.tokenize(text);tokens['l']=(await clip.tokenize(text2))['l']
        if len(tokens['l'])!=len(tokens['g']):
            empty=await clip.tokenize('')
            while len(tokens['l'])<len(tokens['g']):tokens['l']+=empty['l']
            while len(tokens['l'])>len(tokens['g']):tokens['g']+=empty['g']
        c=await clip.encode_from_tokens_scheduled(tokens,{'width':width,'height':height,'crop_w':crop_width,'crop_h':crop_height,'target_width':target_width,'target_height':target_height})
        return await c.value(),refiner

class Sampler:
    def __init__(self,legacy=False):self.legacy=legacy;self.state={}
    @staticmethod
    def tensor2pil(image):return Image.fromarray(np.clip(255.*image.cpu().numpy().squeeze(),0,255).astype(np.uint8))
    @staticmethod
    def pil2tensor(image):return torch.from_numpy(np.array(image).astype(np.float32)/255.).unsqueeze(0)
    @staticmethod
    def enforce_mul_of_64(d):
        d=int(d)
        if d<=7:d=8
        leftover=d%8
        if leftover!=0:d=d-leftover if leftover<4 else d+8-leftover
        return int(d)
    @staticmethod
    def safe_split(to_split,delimiter):
        parts=[p for p in to_split.split(delimiter) if p not in ('',' ','  ')]
        while len(parts)<2:parts.append('None')
        return parts
    @staticmethod
    async def get_model_type(model):
        if await model.is_flow():return 'FLOW'
        return (await model.family()).upper()
    def emptyLatent(self,empty_latent_aspect,batch_size,width=None,height=None,sd3=False):
        if empty_latent_aspect and empty_latent_aspect!='width x height [custom]':width,height=empty_latent_aspect.replace(' ','').split('[')[0].split('x')
        return torch.ones([batch_size,16,int(height)//8,int(width)//8])*0.0609 if sd3 else torch.zeros([batch_size,4,int(height)//8,int(width)//8])
    async def common_ksampler(self,model,seed,steps,cfg,sampler_name,scheduler,positive,negative,latent,denoise=1.,disable_noise=False,start_step=None,last_step=None,force_full_denoise=False,preview_latent=True,disable_pbar=False):
        sigma_schedule=None
        if scheduler.startswith('AYS '):sigma_schedule={'kind':'ays','model_type':scheduler.split(' ')[1],'denoise':denoise};scheduler='normal'
        elif scheduler.startswith('GITS '):sigma_schedule={'kind':'gits','coeff':1.2,'denoise':denoise};scheduler='normal'
        result=await sdk.ctx().sample(model=model,latent=await latent_ref(latent),positive=await cond_ref(positive),negative=await cond_ref(negative),seed=seed,steps=steps,cfg=cfg,sampler_name=sampler_name,scheduler=scheduler,denoise=denoise,disable_noise=disable_noise,start_step=start_step,last_step=last_step,force_full_denoise=force_full_denoise,sigma_schedule=sigma_schedule)
        return await result.value()
    async def upscale(self,samples,upscale_method,scale_by,crop):
        s=samples.copy();h,w=s['samples'].shape[-2:]
        w=min(MAX_RESOLUTION,self.enforce_mul_of_64(round(w*scale_by)));h=min(MAX_RESOLUTION,self.enforce_mul_of_64(round(h*scale_by)))
        s['samples']=await common_upscale(s['samples'],w,h,upscale_method,crop)
        return (s,)
    async def handle_upscale(self,samples,upscale_method,factor,crop,upscale_model_name=None,vae=None,images=None,rescale=None,percent=None,width=None,height=None,longer_side=None):
        if self.legacy:
            return (await self.upscale(samples,upscale_method,factor,crop))[0] if upscale_method!='None' else samples
        parts=upscale_method.split(' ',1)
        if parts[0]=='[latent]' and parts[1]!='None':samples=(await self.upscale(samples,parts[1],factor,crop))[0]
        if parts[0]=='[hiresFix]':
            if images is None:images=await vae_decode(vae,samples['samples'])
            if upscale_model_name=='None':raise ValueError('Unable to model upscale. Please install an upscale model and try again.')
            from ._handlers import model_scale
            samples=await model_scale(upscale_model_name,vae,images,rescale!='None',parts[1],rescale,percent,width,height,longer_side,crop,'return latent',None,True)
        return samples
    def get_output(self,pipe):return (pipe,*(pipe.get(k) for k in ['model','positive','negative','samples','vae','clip','images','seed']))
    def get_output_sdxl(self,p,pipe=None):
        if self.legacy and pipe is None:return (p,*(p.get(k) for k in ['model','positive','negative','vae','refiner_model','refiner_positive','refiner_negative','refiner_vae','samples','clip','images','seed']))
        return (p,pipe,*(p.get(k) for k in ['model','positive','negative','refiner_model','refiner_positive','refiner_negative','samples','vae','clip','images','seed']))
    def update_value_by_id(self,key,uid,value):self.state[(key,uid)]=value
    def init_state(self,uid,key,default):return self.state.get((key,uid),default)

async def common_upscale(samples,width,height,method,crop):
    # The host owns canonical bislerp and Lanczos; no interpolation substitution.
    if samples.ndim!=4:raise ValueError('Expected BCHW tensor')
    old_h,old_w=samples.shape[-2:]
    if crop=='center':
        aspect=width/height;old_aspect=old_w/old_h
        x=round((old_w-old_w*(aspect/old_aspect))/2) if old_aspect>aspect else 0
        y=round((old_h-old_h*(old_aspect/aspect))/2) if old_aspect<aspect else 0
        samples=samples[:,:,y:old_h-y,x:old_w-x]
    ref=await sdk.LatentRef.from_value({'samples':samples})
    return (await (await ref.resize(int(width),int(height),method)).value())['samples']

_services=contextvars.ContextVar('tinyterra_services')
class Service:
    def __init__(self,name):self.name=name
    def __getattr__(self,name):return getattr(_services.get()[self.name],name)
loader=Service('loader');sampler=Service('sampler');ttNsampler=Sampler

def begin(legacy=False):return _services.set({'loader':Loader(),'sampler':Sampler(legacy)})
def end(token):_services.reset(token)

class ttNsave:
    def __init__(self,my_unique_id=0,prompt=None,extra_pnginfo=None,number_padding=5,overwrite_existing=False,output_dir='temp'):
        self.uid=my_unique_id;self.prompt=prompt;self.extra=extra_pnginfo
        self.padding=int(number_padding) if number_padding not in [None,'None',0] else None
        self.overwrite=overwrite_existing;self.output_dir=output_dir

    async def filename(self,prefix,ext,group_id=0):
        # The catalogue returns logical names; counter computation stays pack-side.
        prefix=parse_prefix(prefix,self.prompt,self.uid)
        destination=logical_subfolder(parse_prefix(self.output_dir,self.prompt,self.uid))
        logical=PurePosixPath(logical_subfolder(prefix))
        subfolder=str(logical.parent)
        if subfolder=='.':subfolder=''
        subfolder='/'.join(p for p in [destination,subfolder] if p)
        stem=re.sub(r'[^a-zA-Z0-9_\-. ]','',logical.name)[:240-len(ext)]
        names=await sdk.ctx().assets.list('output',prefix=subfolder,recursive=False)
        mapped=[map_filename(PurePosixPath(n).name,stem) for n in names]
        return numbered_filename(stem,self.padding,group_id,ext,mapped),subfolder

    async def images(self,images,filename_prefix,output_type,embed_workflow=True,ext='png',group_id=0):
        if ext not in ['png','jpg','jpeg','tiff','tif','webp','bmp']:raise ValueError(f'Unsupported file extension {ext}')
        if output_type in ['Hide','Disabled']:return []
        if output_type=='Preview':
            # Preview is host-managed; no user-selected path leaves this guest.
            ref=await image_ref(images)
            return (await sdk.ctx().ui.preview_images(ref)).get('images',[])
        ref=await image_ref(images);raw=await ref.raw();results=[]
        prefix=filename_prefix.replace('%width%',str(raw.shape[2])).replace('%height%',str(raw.shape[1]))
        # Source calculates the next counter separately for every image.
        for image in raw:
            filename,subfolder=await self.filename(prefix,ext,group_id)
            name='/'.join(p for p in [subfolder,filename] if p)
            if not self.overwrite and await sdk.ctx().assets.exists('output',name):
                results.append({'filename':filename,'subfolder':subfolder,'type':'output'})
                continue
            overwrite_options={'overwrite':True} if self.overwrite else {}
            result=await sdk.ctx().output.save_images(await image_ref(image.unsqueeze(0)),filenames=[name],compress_level=6,save_metadata=embed_workflow in [True,'True'] and ext in ['png','webp'],image_format=ext,quality=75 if ext in ['jpg','jpeg','webp'] else 95,**overwrite_options)
            results.extend(result.get('ui',result).get('images',[]))
        return results
    async def textfile(self,text,filename_prefix,ext='txt'):
        filename,subfolder=await self.filename(filename_prefix,ext)
        name='/'.join(p for p in [subfolder,filename] if p)
        if not self.overwrite and await sdk.ctx().assets.exists('output',name):return name
        return await sdk.ctx().output.write_text(text,filename=name,mode='overwrite' if self.overwrite else 'new_only')

def map_filename(filename,filename_prefix):
    prefix_len=len(filename_prefix)
    digits=re.search(r'(\d+)',filename[prefix_len:])
    group=re.search(r'\((\d+)\)',filename[prefix_len:])
    return int(digits.group()) if digits else 0,filename[:prefix_len],int(group.group(1)) if group else 0

def numbered_filename(stem,padding,group_id,ext,mapped):
    filtered=[row for row in mapped if row[1]==stem]
    counter=1
    if filtered:
        counter=max(filtered)[0]
        for row in filtered:
            if row[0]==counter and row[2] in [0,group_id]:counter+=1
    numbered=stem if padding is None else f'{stem}_{counter:0{padding}}'
    return f'{numbered}.{ext}' if group_id==0 else f'{numbered}_({group_id}).{ext}'

def logical_subfolder(value):
    if value in [None,'','output','temp']:return ''
    p=PurePosixPath(str(value).replace('\\','/'))
    if p.is_absolute() or '..' in p.parts or ':' in str(p):raise ValueError('Output destinations must be logical subfolders of managed output storage')
    return str(p)

def parse_prefix(prefix,prompt,uid):
    # Date/widget substitution is pure formatting; destinations remain confined.
    def date(m):
        return format_date(m.group(1),datetime.datetime.now())
    prefix=re.sub(r'%date:(.*?)%',date,prefix)
    values={}
    def gather(nid,link='',seen=None):
        seen=set() if seen is None else seen
        if str(nid) in seen:return
        seen.add(str(nid));node=(prompt or {}).get(str(nid),{})
        for k,v in node.get('inputs',{}).items():
            key=f'{link}>{k}' if link else k
            if isinstance(v,list) and len(v)==2:gather(v[0],key,seen.copy())
            else:
                existing=values.get(key)
                if existing is None:values[key]=v
                elif v not in existing:values[key]=existing+'; '+v
    gather(uid)
    return re.sub(r'%(.*?)%',lambda m:re.sub(r'[^a-zA-Z0-9_\-. ]','',str(values.get(m.group(1),''))),prefix)

def format_date(text,date):
    formats={'d':str(date.day),'dd':f'{date.day:02d}','M':str(date.month),'MM':f'{date.month:02d}','h':str(date.hour),'hh':f'{date.hour:02d}','m':str(date.minute),'mm':f'{date.minute:02d}','s':str(date.second),'ss':f'{date.second:02d}','y':str(date.year),'yy':str(date.year)[2:],'yyy':str(date.year)[1:],'yyyy':str(date.year)}
    for key in sorted(formats,key=len,reverse=True):text=text.replace(key,formats[key])
    return text
