"""Original IMAGE-plot grid work in the pack; Core owns serial execution."""
import io as streams
import json
from PIL import Image,ImageDraw,ImageFont
import numpy as np
import torch
from comfy_api.latest import io,sdk
from ._plot_plan import (PlotProfilePending,background_dimensions,compile_axes,
                         row_major)


from ._runtime import SCHEMAS

_BASE=SCHEMAS['ttN advPlot images']['id']
CELL=_BASE+' Cell'
PLANE=_BASE+' Plane'
FINISH=_BASE+' Finish'
FAILURE=_BASE+' Failure'


class PlaneRenderer:
    def __init__(self,settings,font_bytes):
        self.settings=settings
        self.font_bytes=font_bytes

    def font(self,size):
        font=None
        if self.font_bytes is not None:
            try:font=ImageFont.truetype(streams.BytesIO(self.font_bytes),size)
            except Exception:pass
        return font if font is not None else ImageFont.load_default(size)

    def label(self,image,text,initial_size,is_x=True):
        width=image.width if is_x else image.height
        font=self.font(initial_size)
        left,top,right,bottom=font.getbbox(text)
        text_width=right-left
        size=(int(initial_size*(width/text_width)*0.9)
              if text_width>width*0.9 else initial_size)
        size=max(21,min(70,size));font=self.font(size)
        draw=ImageDraw.Draw(Image.new('RGBA',(width,0),color=(0,0,0,0)))
        def length(text):
            try:return draw.textsize(text,font=font)[0]
            except Exception:return draw.textlength(text,font=font)
        words=text.split()
        if words:
            lines=[];line=words[0]
            for word in words[1:]:
                if length(line+' '+word)<=width:line+=' '+word
                else:lines.append(line);line=word
            lines.append(line)
        else:lines=['None']
        line_height=int(size*1.2)
        result=Image.new('RGBA',(width,len(lines)*line_height),color=(0,0,0,0))
        draw=ImageDraw.Draw(result)
        for index,line in enumerate(lines):
            draw.text(((width-length(line))//2,index*line_height),line,
                fill='white' if self.settings['invert'] else 'black',font=font)
        return result

    def render(self,images,max_width,max_height):
        width,height,start_x,y=background_dimensions(max_width,max_height,self.settings)
        background=Image.new('RGBA',(int(width),int(height)),
            color=(0,0,0,255) if self.settings['invert'] else (255,255,255,255))
        for row in range(self.settings['rows']):
            x=start_x
            for column in range(self.settings['columns']):
                image=images[column*self.settings['rows']+row]
                background.paste(image,(x,y))
                if row==0 and self.settings['has_x']:
                    label=self.label(image,self.settings['x_labels'][column],int(48*image.width/512))
                    background.alpha_composite(label,(x,(y-label.height)//2))
                if column==0 and self.settings['has_y']:
                    label=self.label(image,self.settings['y_labels'][row],int(48*image.height/512),False)
                    label=label.rotate(90,expand=True)
                    background.alpha_composite(label,((x-label.width)//2,y+(image.height-label.height)//2))
                if self.settings['z_label'] is not None:
                    label=self.label(background,self.settings['z_label'],int(48*image.height/512))
                    background.alpha_composite(label,(0,background.height-label.height-label.height//2))
                x+=image.width+self.settings['spacing']
            y+=image.height+self.settings['spacing']
        return background


async def _pixels(cell):
    pixels=cell['pixels']
    if isinstance(pixels,sdk.ValueRef):pixels=(await pixels.value())['pixels']
    if isinstance(pixels,sdk.TensorRef):pixels=await pixels.raw()
    return Image.fromarray(pixels.cpu().numpy())


async def convert_cell(image):
    from ._ops import sampler
    value=image[0]
    if isinstance(value,sdk.ImageRef):value=await value.raw()
    pil=sampler.tensor2pil(value)
    # Preserve exact uint8 pixels between dispatches, avoiding a second float
    # quantization before labels/grid construction.
    pixels=await sdk.ValueRef.from_value({'pixels':torch.from_numpy(np.array(pil))})
    return dict(pixels=pixels,width=pil.width,height=pil.height)


async def render_plane(cells,metadata,previous=None):
    from ._ops import sampler
    settings=json.loads(metadata[0])
    prior=previous[0] if previous else None
    images=[await _pixels(cell) for cell in cells]
    width=max([prior['max_width'] if prior else 0,*[image.width for image in images]])
    height=max([prior['max_height'] if prior else 0,*[image.height for image in images]])
    # Check original dimensions/key failure before any font catalogue access.
    background_dimensions(width,height,settings)
    font_bytes=None
    if settings['has_x'] or settings['has_y'] or settings['z_label'] is not None:
        assets=sdk.ctx().assets
        if await assets.exists('tinyterra','arial.ttf'):
            font_bytes=await assets.read_bytes(await assets.resolve('tinyterra','arial.ttf'))
    renderer=PlaneRenderer(settings,font_bytes)
    grid=await sdk.ImageRef.from_value(sampler.pil2tensor(renderer.render(images,width,height)))
    return dict(grid=grid,cells=cells,max_width=width,max_height=height,
                columns=settings['columns'],rows=settings['rows'])


async def finish(planes,metadata):
    from ._ops import sampler,ttNsave
    settings=json.loads(metadata[0]);grids=[];images=[]
    for plane in planes:
        grid=plane['grid']
        grids.append(await grid.raw() if isinstance(grid,sdk.ImageRef) else grid)
        for cell in row_major(plane['cells'],plane['columns'],plane['rows']):
            images.append(sampler.pil2tensor(await _pixels(cell)))
    grid=torch.cat(grids,dim=0);images=torch.cat(images,dim=0)
    save=ttNsave(settings['caller_id'],settings['prompt'],settings['extra_pnginfo'])
    saved=await save.images(grid,settings['save_prefix'],settings['image_output'],
                            settings['embed_workflow'],settings['file_type'])
    image_ref=await sdk.ImageRef.from_value(images);grid_ref=await sdk.ImageRef.from_value(grid)
    return io.NodeOutput(image_ref,grid_ref,
        ui=None if settings['image_output'] in ('Hide','Hide/Save') else {'images':saved})



async def expand_plot(settings,prompt,extra_pnginfo,caller_id,save_prefix,image_output,file_type,embed_workflow):
    from ._runtime import CANONICAL
    caller_id=str(int(caller_id))
    # The host separately admits own configuration suppression; dependencies stay linked.
    source=prompt
    pending=[source[caller_id]['inputs']['image'][0]];seen=set();configuration_nodes=[]
    while pending:
        node_id=pending.pop()
        if node_id in seen:continue
        seen.add(node_id);node=source[node_id]
        if CANONICAL.get(node['class_type'],node['class_type'])=='ttN advanced xyPlot':
            configuration_nodes.append(node_id)
        pending.extend(value[0] for value in node['inputs'].values()
            if isinstance(value,list) and len(value)==2 and type(value[0]) is str and type(value[1]) is int)
    from ._plot_inputs import prepare_axis_schemas
    lookup=await prepare_axis_schemas(source,settings)
    plan=compile_axes(source,caller_id,settings,None,node_input_types=lookup)
    if plan is None:
        from ._ops import ttNsave
        saved=await ttNsave(caller_id,prompt,extra_pnginfo).images(None,save_prefix,image_output,embed_workflow,file_type)
        return io.NodeOutput(None,None,ui=None if image_output in ('Hide','Hide/Save') else {'images':saved})
    nodes=[];converted={};previous=None
    def link(name,output=0):return dict(node=name,output=output)
    def collect(name,values):
        level=0
        while len(values)>10:
            following=[]
            for offset in range(0,len(values),10):
                node_id=name+'-'+str(level)+'-'+str(offset//10)
                nodes.append(dict(id=node_id,class_type='CreateList',inputs={
                    'input'+str(number):value for number,value in enumerate(values[offset:offset+10])}))
                following.append(link(node_id))
            values=following;level+=1
        nodes.append(dict(id=name,class_type='CreateList',inputs={
            'input'+str(number):value for number,value in enumerate(values)}))
        return link(name)
    for variant in plan['variants']:
        node_id='convert-'+variant['id']
        inputs=dict(image={'variant':variant['id']})
        if previous is not None:inputs['prior']=link(previous)
        nodes.append(dict(id=node_id,class_type=CELL,inputs=inputs))
        converted[variant['id']]=node_id;previous=node_id
    rendered=[]
    for index,plane in enumerate(plan['planes']):
        render='plane-'+str(index)
        collected=collect('cells-'+str(index),[link(converted[variant_id]) for variant_id in plane['cells']])
        inputs=dict(cells=collected,metadata=json.dumps(plane,allow_nan=False))
        if rendered:inputs['previous']=link(rendered[-1])
        nodes.append(dict(id=render,class_type=PLANE,inputs=inputs));rendered.append(render)
    if plan['failure'] is not None:
        # Preserve prior conversions and completed plane effects before the
        # original later parse failure; never execute a partially built plane.
        inputs=dict(metadata=json.dumps(plan['failure'],allow_nan=False),prior=link(previous))
        if rendered:inputs['plane']=link(rendered[-1])
        nodes.append(dict(id='axis-error',class_type=FAILURE,inputs=inputs))
        output='axis-error'
    else:
        collected=collect('planes',[link(name) for name in rendered])
        final=dict(caller_id=caller_id,prompt=plan['prompt'],extra_pnginfo=extra_pnginfo,
            save_prefix=save_prefix,image_output=image_output,file_type=file_type,embed_workflow=embed_workflow)
        nodes.append(dict(id='finish',class_type=FINISH,inputs=dict(
            planes=collected,metadata=json.dumps(final,allow_nan=False))))
        output='finish'
    if not plan['variants']:
        # The original empty-Z path fails at its final torch.cat.
        torch.cat([],dim=0)
    expansion=await sdk.ctx().graph.expand_upstream_variants('image',
        plan['variants'],nodes,[link(output,0),link(output,1)],
        configuration_nodes=configuration_nodes)
    return io.NodeOutput(*expansion['result'],expand=expansion['expand'])
