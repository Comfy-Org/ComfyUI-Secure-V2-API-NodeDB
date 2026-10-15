"""Bounded managed-output XY reader; source grid math and immutable Roboto stay pack-side."""
from io import BytesIO
import numpy as np
import torch
from PIL import Image,ImageFont
from comfy_api.latest import io,sdk
from .secure_graphics import _font_path
from .secure_managed_image_lists import _logical,_key,_budget,WorkloadError
from .secure_schedules import _guard
from .nodes.functions_xygrid import Annotation,create_images_grid_by_columns

async def _files(prefix):
    names=await sdk.ctx().assets.list('output',prefix=prefix,recursive=False)
    if len(names)>4096:raise WorkloadError('XY media catalogue exceeds bound')
    marker=prefix+'/' if prefix else '';result=[]
    for name in names:
        _logical(name,False)
        if not name.startswith(marker) or '/' in name[len(marker):]:raise ValueError('XY broker returned non-immediate logical filename')
        result.append(name[len(marker):])
    return sorted(result,key=_key)
async def _open(prefix,name,total):
    _logical(name,False)
    if '/' in name:raise ValueError('XY filename requires immediate managed file')
    ref=await sdk.ctx().assets.resolve('output',prefix+'/'+name if prefix else name)
    size=await sdk.ctx().assets.size(ref)
    if size<0 or size>8*1024*1024 or total['encoded']+size>32*1024*1024:raise WorkloadError('XY encoded media exceeds bound')
    data=await sdk.ctx().assets.read_bytes(ref)
    if len(data)!=size:raise ValueError('XY media changed during bounded read')
    total['encoded']+=size
    return Image.open(BytesIO(data))
def tensor_to_pillow(image):
    return Image.fromarray(np.clip(255.*image.cpu().numpy().squeeze(),0,255).astype(np.uint8))
def pillow_to_tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32)/255.).unsqueeze(0)
def _parameters(max_columns,font_size,gap,x_annotation,y_annotation):
    if type(max_columns) is not int or not 0<=max_columns<=256:raise WorkloadError('XY columns exceed bounded grid range')
    if type(font_size) is not int or abs(font_size)>1024 or type(gap) is not int or abs(gap)>1024:raise WorkloadError('XY font/gap workload exceeds bound')
    text=x_annotation+y_annotation
    if len(text)>4096 or len(text.encode('utf8'))>16384 or len(text)*font_size*font_size>64*1024*1024:raise WorkloadError('XY annotation/glyph workload exceeds bound')
def _grid_budget(images,gap,max_columns,annotation,total):
    width,height=images[0].size
    rows=(len(images)+max_columns-1)//max_columns
    gw=width*max_columns+(max_columns-1)*gap;gh=height*rows+(rows-1)*gap
    left=0;top=0
    if annotation.row_texts:left=int(max(annotation.font.getlength(s) for raw in annotation.row_texts for s in raw.split('\n'))+annotation.font.getlength('W')*2)
    if annotation.column_texts:top=int(annotation.font.size*2)
    final_width=gw+left;final_height=gh+top
    # Preserve admitted native negative/empty errors; positive projections bounded BEFORE Image.new.
    if max(gw,gh,final_width,final_height)>8192:raise WorkloadError('XY projected grid axes exceed bound')
    pixels=max(0,final_width)*max(0,final_height)
    if pixels*12>32*1024*1024 or total['pixels']+pixels*96>128*1024*1024:raise WorkloadError('XY projected grid allocation exceeds bound')

class CR_XYFromFolder(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR XY From Folder',display_name='📉 CR XY From Folder',category='🧩 Comfyroll Studio/✨ Essential/📉 XY Grid',inputs=[io.Combo.Input('image_folder',options=[],remote=io.RemoteOptions(route='/secure-nodes/assets/output?kind=directory',refresh_button=True)),io.Int.Input('start_index',default=1,min=0,max=10000),io.Int.Input('end_index',default=1,min=1,max=10000),io.Int.Input('max_columns',default=1,min=1,max=10000),io.String.Input('x_annotation',multiline=True),io.String.Input('y_annotation',multiline=True),io.Int.Input('font_size',default=50,min=1),io.Int.Input('gap',default=0,min=0),io.Boolean.Input('trigger',default=False,optional=True)],outputs=[io.Image.Output(display_name='IMAGE'),io.Boolean.Output(display_name='trigger'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, image_folder, start_index, end_index, max_columns, x_annotation, y_annotation, font_size, gap, trigger=False):
        _guard(dict(image_folder=image_folder, start_index=start_index, end_index=end_index, max_columns=max_columns, x_annotation=x_annotation, y_annotation=y_annotation, font_size=font_size, gap=gap, trigger=trigger))
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/XY-Grid-Nodes#cr-xy-from-folder'
        if trigger == False:
            return io.NodeOutput((), False, show_help)
        _parameters(max_columns, font_size, gap, x_annotation, y_annotation)
        prefix = _logical(image_folder)
        total = {'encoded': 0, 'pixels': 0}
        file_list = await _files(prefix)
        sample_frames = []
        pillow_images = []
        if len(file_list) < end_index:
            end_index = len(file_list)
        selected = range(start_index, end_index + 1)
        if len(selected) > 64:
            raise WorkloadError('XY selected image count exceeds bound')
        for num in selected:
            i = await _open(prefix, file_list[num - 1], total)
            try:
                _budget(i, 1, total)
                image = i.convert('RGB')
                image = np.array(image).astype(np.float32) / 255.0
                image = torch.from_numpy(image)[None,]
                image = image.squeeze()
                sample_frames.append(image)
            finally:
                i.close()
        resolved_font_path = _font_path('Roboto-Regular.ttf')
        font = ImageFont.truetype(str(resolved_font_path), size=font_size)
        start_x_ann = start_index % max_columns - 1
        start_y_ann = int(start_index / max_columns)
        column_list = x_annotation.split(';')[start_x_ann:]
        row_list = y_annotation.split(';')[start_y_ann:]
        column_list = [item.strip() for item in column_list]
        row_list = [item.strip() for item in row_list]
        annotation = Annotation(column_texts=column_list, row_texts=row_list, font=font)
        images = torch.stack(sample_frames)
        pillow_images = [tensor_to_pillow(i) for i in images]
        _grid_budget(pillow_images, gap, max_columns, annotation, total)
        pillow_grid = create_images_grid_by_columns(images=pillow_images, gap=gap, annotation=annotation, max_columns=max_columns)
        tensor_grid = pillow_to_tensor(pillow_grid)
        return io.NodeOutput(tensor_grid, trigger, show_help)

NODE_CLASS_MAPPINGS={'CR XY From Folder':CR_XYFromFolder}
NODE_DISPLAY_NAME_MAPPINGS={'CR XY From Folder':'📉 CR XY From Folder'}

