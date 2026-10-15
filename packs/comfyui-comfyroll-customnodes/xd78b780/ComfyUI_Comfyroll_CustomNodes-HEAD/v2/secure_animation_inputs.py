"""Managed frame selection; pinned index/pixel algorithms stay in pack, no filesystem glob."""
import fnmatch,re
import numpy as np
import torch
from comfy_api.latest import io,sdk
from .categories import icons
from .secure_schedules import _guard
from .secure_managed_image_lists import _logical,_prefix,_files,_open,_budget,WorkloadError
def _pattern(pattern):
    if pattern is None:return None
    if not isinstance(pattern,str) or len(pattern.encode('utf-8'))>512 or any(ord(c)<32 for c in pattern) or '/' in pattern or '\\' in pattern or ':' in pattern or pattern in ('.','..'):
        raise ValueError('Frame pattern must be a bounded immediate-name glob')
    return re.sub(r'#+','*',pattern)
def _sort(names,sort_by,pattern):
    pattern=_pattern(pattern)
    if pattern is not None:
        names=[name for name in names if (not name.startswith('.') or pattern.startswith('.')) and fnmatch.fnmatchcase(name,pattern)]
    if sort_by=='Index':return sorted(names,key=lambda s:sum(((s,int(n)) for s,n in re.findall(r'(\D+)(\d+)','a%s0'%s)),()))
    if sort_by=='Alphabetic':return sorted(names,key=lambda s:(re.split(r'(\d+)',s),s))
    raise ValueError("Invalid sort_by value. Use 'Index' or 'Alphabetic'.")
async def _frame(prefix,name,total,squeeze):
    with await _open(prefix,name,total) as image:
        _budget(image,1,total)
        value=np.array(image.convert('RGB')).astype(np.float32)/255.0
        value=torch.from_numpy(value)[None,]
        return value.squeeze() if squeeze else value
def _budget_selected(count):
    if count>64:raise WorkloadError('Selected frame count exceeds64')
class CR_LoadAnimationFrames(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load Animation Frames',display_name='⌨️ CR Load Animation Frames',category=icons['Comfyroll/Animation/IO'],inputs=[io.Combo.Input('image_sequence_folder',options=[],remote=io.RemoteOptions(route='/secure-nodes/assets/input?kind=directory',refresh_button=True)),io.Int.Input('start_index',default=1,min=1,max=10000),io.Int.Input('max_frames',default=1,min=1,max=10000)],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,image_sequence_folder,start_index,max_frames):
        _guard(dict(image_sequence_folder=image_sequence_folder,start_index=start_index,max_frames=max_frames))
        prefix=_logical(image_sequence_folder);files=await _files(prefix)
        sample_index=range(start_index-1,len(files),1)[:max_frames]
        _budget_selected(len(sample_index));total={'encoded':0,'pixels':0};sample_frames=[]
        for num in sample_index:sample_frames.append(await _frame(prefix,files[num],total,True))
        return io.NodeOutput(torch.stack(sample_frames),'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/IO-Nodes#cr-load-animation-frames')
class CR_LoadFlowFrames(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load Flow Frames',display_name='⌨️ CR Load Flow Frames',category=icons['Comfyroll/Animation/IO'],inputs=[io.Combo.Input('input_folder',options=[],remote=io.RemoteOptions(route='/secure-nodes/assets/input?kind=directory',refresh_button=True)),io.Combo.Input('sort_by',options=['Index','Alphabetic']),io.Int.Input('current_frame',default=0,min=0,max=10000,force_input=True),io.Int.Input('skip_start_frames',default=0,min=0,max=10000),io.String.Input('input_path',default='',multiline=False,optional=True),io.String.Input('file_pattern',default='*.png',multiline=False,optional=True)],outputs=[io.Image.Output(display_name='current_image'),io.Image.Output(display_name='previous_image'),io.Int.Output(display_name='current_frame'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,file_pattern,skip_start_frames,input_folder,sort_by,current_frame,input_path=''):
        _guard(dict(file_pattern=file_pattern,skip_start_frames=skip_start_frames,input_folder=input_folder,sort_by=sort_by,current_frame=current_frame,input_path=input_path))
        prefix=_prefix(input_folder,input_path);pattern=_pattern(file_pattern)
        current_frame=current_frame+skip_start_frames
        files=_sort(await _files(prefix),sort_by,pattern)
        if not files:return () # Native zero-output branch retained; release pending.
        total={'encoded':0,'pixels':0}
        cur_image=await _frame(prefix,files[current_frame],total,False)
        previous=current_frame if current_frame==0 and skip_start_frames==0 else current_frame-1
        pre_image=await _frame(prefix,files[previous],total,False)
        return io.NodeOutput(cur_image,pre_image,current_frame,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/IO-Nodes#cr-load-flow-frames')
NODE_CLASS_MAPPINGS={'CR Load Animation Frames':CR_LoadAnimationFrames,'CR Load Flow Frames':CR_LoadFlowFrames}
NODE_DISPLAY_NAME_MAPPINGS={id:'⌨️ '+id for id in NODE_CLASS_MAPPINGS}
