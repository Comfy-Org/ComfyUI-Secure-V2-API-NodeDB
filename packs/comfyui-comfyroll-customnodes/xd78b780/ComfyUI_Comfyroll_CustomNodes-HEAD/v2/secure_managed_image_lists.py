"""Confined logical media names; bounded Pillow decoding stays inside raw guest compute."""
from io import BytesIO
import re
import numpy as np
import torch
from PIL import Image,ImageSequence
from comfy_api.latest import io,sdk
from .categories import icons
from .secure_schedules import _guard,_output

class WorkloadError(ValueError):pass
def _logical(value,empty=True):
    if not isinstance(value,str) or len(value.encode('utf-8'))>2048 or any(ord(c)<32 for c in value) or '\\' in value or ':' in value or value.startswith('/') or any(p in ('.','..','') for p in value.split('/') if value):
        raise ValueError('Media selection requires a bounded logical catalogue prefix/name')
    if not value and not empty:raise ValueError('Media logical filename must not be empty')
    return value
def _prefix(input_folder,input_path):
    return _logical(input_path if input_path not in ('',None) else input_folder)
def _key(filename):
    return sum(((s,int(n)) for s,n in re.findall(r'(\D+)(\d+)','a%s0'%filename)),())
async def _files(prefix):
    names=await sdk.ctx().assets.list('input',prefix=prefix,recursive=False)
    if len(names)>4096:raise WorkloadError('Media catalogue exceeds bounded names')
    marker=prefix+'/' if prefix else ''
    result=[]
    for name in names:
        _logical(name,False)
        if not name.startswith(marker) or '/' in name[len(marker):]:raise ValueError('Media broker returned a non-immediate logical filename')
        result.append(name[len(marker):])
    return sorted(result,key=_key)
async def _bytes(prefix,name,total):
    _logical(name,False)
    if '/' in name:raise ValueError('Media filename must select one immediate file')
    ref=await sdk.ctx().assets.resolve('input',prefix+'/'+name if prefix else name)
    size=await sdk.ctx().assets.size(ref)
    if size<0 or size>8*1024*1024 or total['encoded']+size>32*1024*1024:raise WorkloadError('Encoded media workload exceeds bound')
    data=await sdk.ctx().assets.read_bytes(ref)
    if len(data)!=size:raise ValueError('Media changed during bounded read')
    total['encoded']+=size
    return data
async def _open(prefix,name,total):
    return Image.open(BytesIO(await _bytes(prefix,name,total)))
def _budget(image,count,total):
    width,height=image.size
    if width<1 or height<1 or max(width,height)>4096 or width*height>4194304 or count>64:raise WorkloadError('Decoded image/frame shape exceeds bound')
    # RGB image+source mask output=16B/pixel, source four-channel temps<=32B.
    projected=width*height*max(0,count)*16
    if total['pixels']+projected>32*1024*1024:raise WorkloadError('Projected decoded image batch exceeds bound')
    total['pixels']+=projected
def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32)/255.0).unsqueeze(0)
def tensor2rgba(t):
    size=t.size()
    if len(size)<4:return t.unsqueeze(3).repeat(1,1,1,4)
    if size[3]==1:return t.repeat(1,1,1,4)
    if size[3]==3:return torch.cat((t,torch.ones((size[0],size[1],size[2],1))),dim=3)
    return t
def _list_schema(id,plus=False):
    max_index=99999 if plus else 9999
    outputs=[io.Image.Output(display_name='IMAGE',is_output_list=True)]
    if plus:outputs.extend([io.Mask.Output(display_name='MASK',is_output_list=True),io.Int.Output(display_name='index',is_output_list=True),io.String.Output(display_name='filename',is_output_list=True),io.Int.Output(display_name='width'),io.Int.Output(display_name='height'),io.Int.Output(display_name='list_length')])
    outputs.append(io.String.Output(display_name='show_help'))
    return io.Schema(node_id=id,display_name='⌨️ '+id,category=icons['Comfyroll/List/IO'],inputs=[io.Combo.Input('input_folder',options=[],remote=io.RemoteOptions(route='/secure-nodes/assets/input?kind=directory',refresh_button=True)),io.Int.Input('start_index',default=0,min=0,max=max_index),io.Int.Input('max_images',default=1,min=1,max=max_index),io.String.Input('input_path',default='',multiline=False,optional=True)],outputs=outputs)
async def _load(start_index,max_images,input_folder,input_path,plus):
    _guard(dict(start_index=start_index,max_images=max_images,input_folder=input_folder,input_path=input_path))
    prefix=_prefix(input_folder,input_path);files=await _files(prefix)
    if not files:return None
    start_index=max(0,min(start_index,len(files)-1))
    end_index=min(start_index+max_images,len(files)-1) # Pinned last-file exclusion.
    selected=range(start_index,end_index)
    if len(selected)>64:raise WorkloadError('Selected image count exceeds bound')
    images=[];masks=[];indices=[];filenames=[];total={'encoded':0,'pixels':0}
    for num in selected:
        with await _open(prefix,files[num],total) as img:
            _budget(img,1,total)
            if not images:width,height=img.size
            # No EXIF transpose: pinned Image.open(...).convert('RGB') pixels.
            images.append(pil2tensor(img.convert('RGB')))
            if plus:masks.append(tensor2rgba(pil2tensor(img))[:,:,:,0])
        indices.append(num);filenames.append(files[num])
    if not images:return None
    images=torch.cat(images,dim=0);images_out=[images[i:i+1,...] for i in range(images.shape[0])]
    help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-image-list'+('-plus' if plus else '')
    if not plus:return io.NodeOutput(images_out,help_url)
    masks=torch.cat(masks,dim=0);mask_out=[masks[i:i+1,...] for i in range(masks.shape[0])]
    # Approved duplicate-second-index removal ONLY: source returned9 vs declared8.
    return io.NodeOutput(images_out,mask_out,indices,filenames,width,height,end_index-start_index,help_url)
class CR_LoadImageList(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):return _list_schema('CR Load Image List')
    @classmethod
    async def execute(cls,start_index,max_images,input_folder,input_path=None):return await _load(start_index,max_images,input_folder,input_path,False)
class CR_LoadImageListPlus(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):return _list_schema('CR Load Image List Plus',True)
    @classmethod
    async def execute(cls,start_index,max_images,input_folder,input_path=None,vae=None):return await _load(start_index,max_images,input_folder,input_path,True)
class CR_LoadGIFAsList(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load GIF As List',display_name='⌨️ CR Load GIF As List',category=icons['Comfyroll/List/IO'],inputs=[io.Combo.Input('input_folder',options=[],remote=io.RemoteOptions(route='/secure-nodes/assets/input?kind=directory',refresh_button=True)),io.String.Input('gif_filename',default='text',multiline=False),io.Int.Input('start_frame',default=0,min=0,max=99999),io.Int.Input('max_frames',default=1,min=1,max=99999),io.String.Input('input_path',default='',multiline=False,optional=True)],outputs=[io.Image.Output(display_name='IMAGE',is_output_list=True),io.Mask.Output(display_name='MASK',is_output_list=True),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,input_folder,gif_filename,start_frame,max_frames,input_path=None):
        _guard(dict(input_folder=input_folder,gif_filename=gif_filename,start_frame=start_frame,max_frames=max_frames,input_path=input_path))
        prefix=_prefix(input_folder,input_path);_logical(gif_filename,False)
        if '/' in gif_filename:raise ValueError('GIF filename must select one immediate file')
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-load-gif-images'
        frames=[];masks=[];total={'encoded':0,'pixels':0}
        logical_name=prefix+'/'+gif_filename if prefix else gif_filename
        # Keep authority/read failures OUTSIDE the native decoder-error fallback.
        if not await sdk.ctx().assets.exists('input',logical_name):return io.NodeOutput(None,None,help_url)
        data=await _bytes(prefix,gif_filename,total)
        try:
            with Image.open(BytesIO(data)) as gif:
                _budget(gif,0,total)
                for i,frame in enumerate(ImageSequence.Iterator(gif)):
                    if i>=256:raise WorkloadError('GIF frame scan exceeds bound')
                    if i<start_frame:continue
                    if max_frames is not None and i>=start_frame+max_frames:break
                    if len(frames)>=64:raise WorkloadError('Selected GIF frame count exceeds bound')
                    _budget(frame,1,total)
                    img=frame.copy()
                    frames.append(pil2tensor(img.convert('RGB')))
                    masks.append(tensor2rgba(pil2tensor(img))[:,:,:,0])
            images=torch.cat(frames,dim=0);mask=torch.cat(masks,dim=0)
            return io.NodeOutput([images[i:i+1,...] for i in range(images.shape[0])],[mask[i:i+1,...] for i in range(mask.shape[0])],help_url)
        except WorkloadError:raise
        except Exception as error:
            print(f'Error: {error}')
            return io.NodeOutput(None,None,help_url)
NODE_CLASS_MAPPINGS={'CR Load Image List':CR_LoadImageList,'CR Load Image List Plus':CR_LoadImageListPlus,'CR Load GIF As List':CR_LoadGIFAsList}
NODE_DISPLAY_NAME_MAPPINGS={k:'⌨️ '+k for k in NODE_CLASS_MAPPINGS}
