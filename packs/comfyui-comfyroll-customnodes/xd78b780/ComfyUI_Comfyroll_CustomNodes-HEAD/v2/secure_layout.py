"""Bounded pack-side PIL panels/layouts; no ambient files, fonts or durable state."""
import math
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageOps, ImageFilter
from comfy_api.latest import io
from .secure_schedules import _guard, _output

def _preflight(node_id, values):
    _guard(values)
    if node_id=='CR Select ISO Size':return
    dimensions={};input_bytes=0
    for key,value in values.items():
        if isinstance(value,torch.Tensor):
            if value.layout!=torch.strided or value.ndim not in (3,4):
                raise ValueError('Layout requires bounded HWC/BHWC tensors')
            batch,height,width,channels=(1,*value.shape) if value.ndim==3 else tuple(value.shape)
            if batch>16 or height>4096 or width>4096 or not 1<=channels<=4:
                raise ValueError('Layout image dimensions exceed bound')
            input_bytes+=value.numel()*value.element_size()
            if value.ndim==3 and node_id in ('CR Image Grid Panel','CR Image Border','CR Feathered Border'):
                # Pinned loop iterates HWC rows rather than treating HWC as one batch.
                # Keep that native direct-input behavior within a bounded row workload.
                batch,height,width,channels=height,width,channels,1
                if batch>16:raise ValueError('Layout HWC row workload exceeds bound')
            if height==1 or width==1:
                # tensor2pil squeezes singleton axes; its PIL geometry can swap axes
                # or promote the channel axis. A square upper bound prevents undercount.
                side=max(height,width,channels)
                height=width=side
            dimensions[key]=(batch,height,width,channels)
        if key.endswith('_thickness') or key=='feather_amount':
            if type(value) is not int or abs(value)>1024:raise ValueError('Layout thickness exceeds bound')
        if key in ('offset_x','offset_y') and (type(value) is not int or abs(value)>4096):
            raise ValueError('Layout offset exceeds bound')
    if input_bytes>32*1024*1024:raise ValueError('Layout image inputs exceed 32MiB')
    canvases=[]
    if node_id=='CR Color Panel':
        width=values['panel_width'];height=values['panel_height']
        if type(width) is not int or type(height) is not int or abs(width)>4096 or abs(height)>4096:
            raise ValueError('Layout panel dimensions exceed bound')
        canvases=[(1,height,width)]
    elif node_id in ('CR Image Panel','CR Image Grid Panel'):
        padding=2*(max(0,values['border_thickness'])+max(0,values['outline_thickness']))
        if node_id=='CR Image Panel':
            sizes=[(height+padding,width+padding) for _,height,width,_ in dimensions.values()]
            if sizes:
                if values['layout_direction']=='horizontal':canvases=[(1,max(h for h,w in sizes),sum(w for h,w in sizes))]
                else:canvases=[(1,sum(h for h,w in sizes),max(w for h,w in sizes))]
        else:
            count,height,width,_=dimensions['images'];columns=values['max_columns']
            if type(columns) is not int or abs(columns)>256:raise ValueError('Layout columns exceed bound')
            if count and columns>0:canvases=[(1,(height+padding)*((count-1)//columns+1),(width+padding)*min(columns,count))]
    elif node_id in ('CR Image Border','CR Feathered Border'):
        count,height,width,_=dimensions['image']
        feather=max(0,values.get('feather_amount',0))*2
        outline=max(0,values.get('outline_thickness',0))*2
        canvases=[(count,height+feather+outline+max(0,values['top_thickness'])+max(0,values['bottom_thickness']),width+feather+outline+max(0,values['left_thickness'])+max(0,values['right_thickness']))]
    elif node_id in ('CR Half Drop Panel','CR Diamond Panel'):
        count,height,width,_=dimensions['image'];factor=1 if values['pattern']=='none' else 2
        if 'drop_percentage' in values and abs(values['drop_percentage'])>10:raise ValueError('Layout drop exceeds bound')
        canvases=[(count,height*factor,width*factor)]
    elif node_id=='CR Overlay Transparent Image':
        _,height,width,_=dimensions['back_image'];canvases=[(1,height,width)]
        _,oh,ow,_=dimensions['overlay_image'];scale=values['overlay_scale_factor']
        if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not math.isfinite(scale) or abs(scale)>100:
            raise ValueError('Layout overlay scale exceeds bound')
        angle=values['rotation_angle']
        if abs(angle)>36000 or not -10<=values['transparency']<=10:raise ValueError('Layout overlay parameters exceed bound')
        # Expanded rotated canvas is bounded above by the width+height diagonal box.
        rotated=oh+ow+2
        canvases.extend([(1,rotated,rotated),(1,int(rotated*abs(scale)),int(rotated*abs(scale)))])
    projected=0
    for batch,height,width in canvases:
        if abs(height)>8192 or abs(width)>8192:raise ValueError('Layout projected dimensions exceed bound')
        projected+=max(0,batch)*max(0,height)*max(0,width)*16
    if projected>32*1024*1024 or input_bytes+3*projected>128*1024*1024:
        raise ValueError('Layout projected output/temporary workload exceeds bound')

color_mapping = {'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'yellow': (255, 255, 0), 'cyan': (0, 255, 255), 'magenta': (255, 0, 255), 'orange': (255, 165, 0), 'purple': (128, 0, 128), 'pink': (255, 192, 203), 'brown': (160, 85, 15), 'gray': (128, 128, 128), 'lightgray': (211, 211, 211), 'darkgray': (102, 102, 102), 'olive': (128, 128, 0), 'lime': (0, 128, 0), 'teal': (0, 128, 128), 'navy': (0, 0, 128), 'maroon': (128, 0, 0), 'fuchsia': (255, 0, 128), 'aqua': (0, 255, 128), 'silver': (192, 192, 192), 'gold': (255, 215, 0), 'turquoise': (64, 224, 208), 'lavender': (230, 230, 250), 'violet': (238, 130, 238), 'coral': (255, 127, 80), 'indigo': (75, 0, 130)}
COLORS = ['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']
iso_sizes = {'A0 - 9933x14043': (9933, 14043), 'A1 - 7016x9933': (7016, 9933), 'A2 - 4960x7016': (4960, 7016), 'A3 - 3508x4960': (3508, 4960), 'A4 - 2480x3508': (2480, 3508), 'A5 - 1748x2480': (1748, 2480), 'A6 - 1240x1748': (1240, 1748), 'A7 - 874x1240': (874, 1240), 'A8 - 614x874': (614, 874), 'A9 - 437x614': (437, 614), 'A10 - 307x437': (307, 437), 'A11 - 213x307': (213, 307), 'A12 - 154x213': (154, 213), 'A13 - 106x154': (106, 154), 'B0 - 11811x16701': (11811, 16701), 'B1 - 8350x11811': (8350, 11811), 'B2 - 5906x8350': (5906, 8350), 'B3 - 4169x5906': (4169, 5906), 'B4 - 2953x4169': (2953, 4169), 'B5 - 2079x2953': (2079, 2953), 'B6 - 1476x2079': (1476, 2079), 'B7 - 1039x1476': (1039, 1476), 'B8 - 732x1039': (732, 1039), 'B9 - 520x732': (520, 732), 'B10 - 366x520': (366, 520), 'C0 - 10831x15319': (10831, 15319), 'C1 - 7654x10831': (7654, 10831), 'C2 - 5409x7654': (5409, 7654), 'C3 - 3827x5409': (3827, 5409), 'C4 - 2705x3827': (2705, 3827), 'C5 - 1913x2705': (1913, 2705), 'C6 - 1346x1913': (1346, 1913), 'C7 - 957x1346': (957, 1346), 'C8 - 673x957': (673, 957), 'C9 - 472x673': (472, 673), 'C10 - 331x472': (331, 472)}

def tensor2pil(image):
    return Image.fromarray(np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)

def combine_images(images, layout_direction='horizontal'):
    """
    Combine a list of PIL Image objects either horizontally or vertically.

    Args:
    images (list of PIL.Image.Image): List of PIL Image objects to combine.
    layout_direction (str): 'horizontal' for horizontal layout, 'vertical' for vertical layout.

    Returns:
    PIL.Image.Image: Combined image.
    """
    if layout_direction == 'horizontal':
        combined_width = sum((image.width for image in images))
        combined_height = max((image.height for image in images))
    else:
        combined_width = max((image.width for image in images))
        combined_height = sum((image.height for image in images))
    combined_image = Image.new('RGB', (combined_width, combined_height))
    x_offset = 0
    y_offset = 0
    for image in images:
        combined_image.paste(image, (x_offset, y_offset))
        if layout_direction == 'horizontal':
            x_offset += image.width
        else:
            y_offset += image.height
    return combined_image

def apply_outline_and_border(images, outline_thickness, outline_color, border_thickness, border_color):
    for i, image in enumerate(images):
        if outline_thickness > 0:
            image = ImageOps.expand(image, outline_thickness, fill=outline_color)
        if border_thickness > 0:
            image = ImageOps.expand(image, border_thickness, fill=border_color)
        images[i] = image
    return images

def get_color_values(color, color_hex, color_mapping):
    if color == 'custom':
        color_rgb = hex_to_rgb(color_hex)
    else:
        color_rgb = color_mapping.get(color, (0, 0, 0))
    return color_rgb

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)

def make_grid_panel(images, max_columns):
    num_images = len(images)
    num_rows = (num_images - 1) // max_columns + 1
    combined_width = max((image.width for image in images)) * min(max_columns, num_images)
    combined_height = max((image.height for image in images)) * num_rows
    combined_image = Image.new('RGB', (combined_width, combined_height))
    x_offset, y_offset = (0, 0)
    for image in images:
        combined_image.paste(image, (x_offset, y_offset))
        x_offset += image.width
        if x_offset >= max_columns * image.width:
            x_offset = 0
            y_offset += image.height
    return combined_image

class CR_ImagePanel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Panel',display_name='🌁 CR Image Panel',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('image_1'), io.Int.Input('border_thickness', default=0, min=0, max=1024), io.Combo.Input('border_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('outline_thickness', default=0, min=0, max=1024), io.Combo.Input('outline_color', options=['white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('layout_direction', options=['horizontal', 'vertical']), io.Image.Input('image_2', optional=True), io.Image.Input('image_3', optional=True), io.Image.Input('image_4', optional=True), io.String.Input('border_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image_1, border_thickness, border_color, outline_thickness, outline_color, layout_direction, image_2=None, image_3=None, image_4=None, border_color_hex='#000000'):
        _preflight('CR Image Panel', {'image_1': image_1, 'border_thickness': border_thickness, 'border_color': border_color, 'outline_thickness': outline_thickness, 'outline_color': outline_color, 'layout_direction': layout_direction, 'image_2': image_2, 'image_3': image_3, 'image_4': image_4, 'border_color_hex': border_color_hex})
        border_color = get_color_values(border_color, border_color_hex, color_mapping)
        images = []
        images.append(tensor2pil(image_1))
        if image_2 is not None:
            images.append(tensor2pil(image_2))
        if image_3 is not None:
            images.append(tensor2pil(image_3))
        if image_4 is not None:
            images.append(tensor2pil(image_4))
        images = apply_outline_and_border(images, outline_thickness, outline_color, border_thickness, border_color)
        combined_image = combine_images(images, layout_direction)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-image-panel'
        return _output((pil2tensor(combined_image), show_help))


class CR_ImageGridPanel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Grid Panel',display_name='🌁 CR Image Grid Panel',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('images'), io.Int.Input('border_thickness', default=0, min=0, max=1024), io.Combo.Input('border_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('outline_thickness', default=0, min=0, max=1024), io.Combo.Input('outline_color', options=['white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('max_columns', default=5, min=0, max=256), io.String.Input('border_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, images, border_thickness, border_color, outline_thickness, outline_color, max_columns, border_color_hex='#000000'):
        _preflight('CR Image Grid Panel', {'images': images, 'border_thickness': border_thickness, 'border_color': border_color, 'outline_thickness': outline_thickness, 'outline_color': outline_color, 'max_columns': max_columns, 'border_color_hex': border_color_hex})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-image-grid-panel'
        border_color = get_color_values(border_color, border_color_hex, color_mapping)
        images = [tensor2pil(image) for image in images]
        images = apply_outline_and_border(images, outline_thickness, outline_color, border_thickness, border_color)
        combined_image = make_grid_panel(images, max_columns)
        image_out = pil2tensor(combined_image)
        return _output((image_out, show_help))


class CR_ImageBorder(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Border',display_name='🌁 CR Image Border',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('image'), io.Int.Input('top_thickness', default=0, min=0, max=4096), io.Int.Input('bottom_thickness', default=0, min=0, max=4096), io.Int.Input('left_thickness', default=0, min=0, max=4096), io.Int.Input('right_thickness', default=0, min=0, max=4096), io.Combo.Input('border_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('outline_thickness', default=0, min=0, max=1024), io.Combo.Input('outline_color', options=['white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.String.Input('border_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, top_thickness, bottom_thickness, left_thickness, right_thickness, border_color, outline_thickness, outline_color, border_color_hex='#000000'):
        _preflight('CR Image Border', {'image': image, 'top_thickness': top_thickness, 'bottom_thickness': bottom_thickness, 'left_thickness': left_thickness, 'right_thickness': right_thickness, 'border_color': border_color, 'outline_thickness': outline_thickness, 'outline_color': outline_color, 'border_color_hex': border_color_hex})
        images = []
        border_color = get_color_values(border_color, border_color_hex, color_mapping)
        for img in image:
            img = tensor2pil(img)
            if outline_thickness > 0:
                img = ImageOps.expand(img, outline_thickness, fill=outline_color)
            if left_thickness > 0 or right_thickness > 0 or top_thickness > 0 or (bottom_thickness > 0):
                img = ImageOps.expand(img, (left_thickness, top_thickness, right_thickness, bottom_thickness), fill=border_color)
            images.append(pil2tensor(img))
        images = torch.cat(images, dim=0)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-image-border'
        return _output((images, show_help))


class CR_ColorPanel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Color Panel',display_name='🌁 CR Color Panel',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Int.Input('panel_width', default=512, min=8, max=4096), io.Int.Input('panel_height', default=512, min=8, max=4096), io.Combo.Input('fill_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.String.Input('fill_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, panel_width, panel_height, fill_color, fill_color_hex='#000000'):
        _preflight('CR Color Panel', {'panel_width': panel_width, 'panel_height': panel_height, 'fill_color': fill_color, 'fill_color_hex': fill_color_hex})
        fill_color = get_color_values(fill_color, fill_color_hex, color_mapping)
        size = (panel_width, panel_height)
        panel = Image.new('RGB', size, fill_color)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-color-panel'
        return _output((pil2tensor(panel), show_help))


class CR_OverlayTransparentImage(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Overlay Transparent Image',display_name='🌁 CR Overlay Transparent Image',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('back_image'), io.Image.Input('overlay_image'), io.Float.Input('transparency', default=0.0, min=0.0, max=1.0, step=0.1), io.Int.Input('offset_x', default=0, min=-4096, max=4096), io.Int.Input('offset_y', default=0, min=-4096, max=4096), io.Float.Input('rotation_angle', default=0.0, min=-360.0, max=360.0, step=0.1), io.Float.Input('overlay_scale_factor', default=1.0, min=0.0, max=100.0, step=0.001)],outputs=[io.Image.Output(display_name='IMAGE')])

    @classmethod
    def execute(cls, back_image, overlay_image, transparency, offset_x, offset_y, rotation_angle, overlay_scale_factor=1.0):
        _preflight('CR Overlay Transparent Image', {'back_image': back_image, 'overlay_image': overlay_image, 'transparency': transparency, 'offset_x': offset_x, 'offset_y': offset_y, 'rotation_angle': rotation_angle, 'overlay_scale_factor': overlay_scale_factor})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-overlay-transparent-image'
        back_image = tensor2pil(back_image)
        overlay_image = tensor2pil(overlay_image)
        overlay_image.putalpha(int(255 * (1 - transparency)))
        overlay_image = overlay_image.rotate(rotation_angle, expand=True)
        overlay_width, overlay_height = overlay_image.size
        new_size = (int(overlay_width * overlay_scale_factor), int(overlay_height * overlay_scale_factor))
        overlay_image = overlay_image.resize(new_size, Image.Resampling.LANCZOS)
        center_x = back_image.width // 2
        center_y = back_image.height // 2
        position_x = center_x - overlay_image.width // 2 + offset_x
        position_y = center_y - overlay_image.height // 2 + offset_y
        back_image.paste(overlay_image, (position_x, position_y), overlay_image)
        return _output((pil2tensor(back_image),))


class CR_FeatheredBorder(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Feathered Border',display_name='🌁 CR Feathered Border',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('image'), io.Int.Input('top_thickness', default=0, min=0, max=4096), io.Int.Input('bottom_thickness', default=0, min=0, max=4096), io.Int.Input('left_thickness', default=0, min=0, max=4096), io.Int.Input('right_thickness', default=0, min=0, max=4096), io.Combo.Input('border_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('feather_amount', default=0, min=0, max=1024), io.String.Input('border_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, top_thickness, bottom_thickness, left_thickness, right_thickness, border_color, feather_amount, border_color_hex='#000000'):
        _preflight('CR Feathered Border', {'image': image, 'top_thickness': top_thickness, 'bottom_thickness': bottom_thickness, 'left_thickness': left_thickness, 'right_thickness': right_thickness, 'border_color': border_color, 'feather_amount': feather_amount, 'border_color_hex': border_color_hex})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-feathered-border'
        images = []
        border_color = get_color_values(border_color, border_color_hex, color_mapping)
        for img in image:
            im = tensor2pil(img)
            RADIUS = feather_amount
            diam = 2 * RADIUS
            back = Image.new('RGB', (im.size[0] + diam, im.size[1] + diam), border_color)
            back.paste(im, (RADIUS, RADIUS))
            mask = Image.new('L', back.size, 0)
            draw = ImageDraw.Draw(mask)
            x0, y0 = (0, 0)
            x1, y1 = back.size
            for d in range(diam + RADIUS):
                x1, y1 = (x1 - 1, y1 - 1)
                alpha = 255 if d < RADIUS else int(255 * (diam + RADIUS - d) / diam)
                draw.rectangle([x0, y0, x1, y1], outline=alpha)
                x0, y0 = (x0 + 1, y0 + 1)
            blur = back.filter(ImageFilter.GaussianBlur(RADIUS / 2))
            back.paste(blur, mask=mask)
            if left_thickness > 0 or right_thickness > 0 or top_thickness > 0 or (bottom_thickness > 0):
                img = ImageOps.expand(back, (left_thickness, top_thickness, right_thickness, bottom_thickness), fill=border_color)
            else:
                img = back
            images.append(pil2tensor(img))
        images = torch.cat(images, dim=0)
        return _output((images, show_help))


class CR_HalfDropPanel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Half Drop Panel',display_name='🌁 CR Half Drop Panel',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('image'), io.Combo.Input('pattern', options=['none', 'half drop', 'quarter drop', 'custom drop %']), io.Float.Input('drop_percentage', default=0.5, min=0.0, max=1.0, step=0.01, optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, pattern, drop_percentage=0.5):
        _preflight('CR Half Drop Panel', {'image': image, 'pattern': pattern, 'drop_percentage': drop_percentage})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-half-drop-panel'
        if pattern == 'none':
            return _output((image, show_help))
        pil_img = tensor2pil(image)
        pil_img = pil_img.convert('RGBA')
        x, y = pil_img.size
        aspect_ratio = x / y
        d = int(drop_percentage * 100)
        panel_image = Image.new('RGBA', (x * 2, y * 2))
        if pattern == 'half drop':
            panel_image.paste(pil_img, (0, 0))
            panel_image.paste(pil_img, (0, y))
            panel_image.paste(pil_img, (x, -y // 2))
            panel_image.paste(pil_img, (x, y // 2))
            panel_image.paste(pil_img, (x, 3 * y // 2))
        elif pattern == 'quarter drop':
            panel_image.paste(pil_img, (0, 0))
            panel_image.paste(pil_img, (0, y))
            panel_image.paste(pil_img, (x, -3 * y // 4))
            panel_image.paste(pil_img, (x, y // 4))
            panel_image.paste(pil_img, (x, 5 * y // 4))
        elif pattern == 'custom drop %':
            panel_image.paste(pil_img, (0, 0))
            panel_image.paste(pil_img, (0, y))
            panel_image.paste(pil_img, (x, (d - 100) * y // 100))
            panel_image.paste(pil_img, (x, d * y // 100))
            panel_image.paste(pil_img, (x, y + d * y // 100))
        image_out = pil2tensor(panel_image.convert('RGB'))
        return _output((image_out, show_help))


class CR_DiamondPanel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Diamond Panel',display_name='🌁 CR Diamond Panel',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Image.Input('image'), io.Combo.Input('pattern', options=['none', 'diamond'])],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, pattern, drop_percentage=0.5):
        _preflight('CR Diamond Panel', {'image': image, 'pattern': pattern, 'drop_percentage': drop_percentage})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-diamond-panel'
        if pattern == 'none':
            return _output((image, show_help))
        pil_img = tensor2pil(image)
        pil_img = pil_img.convert('RGBA')
        x, y = pil_img.size
        aspect_ratio = x / y
        d = int(drop_percentage * 100)
        panel_image = Image.new('RGBA', (x * 2, y * 2))
        if pattern == 'diamond':
            diamond_size = min(x, y)
            diamond_width = min(x, y * aspect_ratio)
            diamond_height = min(y, x / aspect_ratio)
            diamond_mask = Image.new('L', (x, y), 0)
            draw = ImageDraw.Draw(diamond_mask)
            draw.polygon([(x // 2, 0), (x, y // 2), (x // 2, y), (0, y // 2)], fill=255)
            diamond_image = pil_img.copy()
            diamond_image.putalpha(diamond_mask)
            panel_image.paste(diamond_image, (-x // 2, (d - 100) * y // 100), diamond_image)
            panel_image.paste(diamond_image, (-x // 2, d * y // 100), diamond_image)
            panel_image.paste(diamond_image, (-x // 2, y + d * y // 100), diamond_image)
            panel_image.paste(diamond_image, (0, 0), diamond_image)
            panel_image.paste(diamond_image, (0, y), diamond_image)
            panel_image.paste(diamond_image, (x // 2, (d - 100) * y // 100), diamond_image)
            panel_image.paste(diamond_image, (x // 2, d * y // 100), diamond_image)
            panel_image.paste(diamond_image, (x // 2, y + d * y // 100), diamond_image)
            panel_image.paste(diamond_image, (x, 0), diamond_image)
            panel_image.paste(diamond_image, (x, y), diamond_image)
            panel_image.paste(diamond_image, (3 * x // 2, (d - 100) * y // 100), diamond_image)
            panel_image.paste(diamond_image, (3 * x // 2, d * y // 100), diamond_image)
            panel_image.paste(diamond_image, (3 * x // 2, y + d * y // 100), diamond_image)
        image_out = pil2tensor(panel_image.convert('RGB'))
        return _output((image_out, show_help))


class CR_SelectISOSize(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Select ISO Size',display_name='⚙️ CR Select ISO Size',category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other',is_output_node=False,inputs=[io.Combo.Input('iso_size', options=['A0 - 9933x14043', 'A1 - 7016x9933', 'A2 - 4960x7016', 'A3 - 3508x4960', 'A4 - 2480x3508', 'A5 - 1748x2480', 'A6 - 1240x1748', 'A7 - 874x1240', 'A8 - 614x874', 'A9 - 437x614', 'A10 - 307x437', 'A11 - 213x307', 'A12 - 154x213', 'A13 - 106x154', 'B0 - 11811x16701', 'B1 - 8350x11811', 'B2 - 5906x8350', 'B3 - 4169x5906', 'B4 - 2953x4169', 'B5 - 2079x2953', 'B6 - 1476x2079', 'B7 - 1039x1476', 'B8 - 732x1039', 'B9 - 520x732', 'B10 - 366x520', 'C0 - 10831x15319', 'C1 - 7654x10831', 'C2 - 5409x7654', 'C3 - 3827x5409', 'C4 - 2705x3827', 'C5 - 1913x2705', 'C6 - 1346x1913', 'C7 - 957x1346', 'C8 - 673x957', 'C9 - 472x673', 'C10 - 331x472'])],outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, iso_size):
        _preflight('CR Select ISO Size', {'iso_size': iso_size})
        if iso_size in iso_sizes:
            width, height = iso_sizes[iso_size]
        else:
            print('Size not found.')
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-select-iso-size'
        return _output((width, height, show_help))


NODE_CLASS_MAPPINGS={
    'CR Image Panel':CR_ImagePanel,
    'CR Image Grid Panel':CR_ImageGridPanel,
    'CR Image Border':CR_ImageBorder,
    'CR Color Panel':CR_ColorPanel,
    'CR Overlay Transparent Image':CR_OverlayTransparentImage,
    'CR Feathered Border':CR_FeatheredBorder,
    'CR Half Drop Panel':CR_HalfDropPanel,
    'CR Diamond Panel':CR_DiamondPanel,
    'CR Select ISO Size':CR_SelectISOSize,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Image Panel': '🌁 CR Image Panel', 'CR Image Grid Panel': '🌁 CR Image Grid Panel', 'CR Image Border': '🌁 CR Image Border', 'CR Color Panel': '🌁 CR Color Panel', 'CR Overlay Transparent Image': '🌁 CR Overlay Transparent Image', 'CR Feathered Border': '🌁 CR Feathered Border', 'CR Half Drop Panel': '🌁 CR Half Drop Panel', 'CR Diamond Panel': '🌁 CR Diamond Panel', 'CR Select ISO Size': '⚙️ CR Select ISO Size'}
