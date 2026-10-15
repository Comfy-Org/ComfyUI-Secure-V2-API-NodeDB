"""Pinned text-mask algorithms; only the immutable bundled-font catalogue is readable."""
import math
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps
from comfy_api.latest import io
from .secure_schedules import _guard, _output
from .secure_graphics import _font_path, FONT_NAMES, tensor2pil, pil2tensor, get_text_size
from .secure_layout import COLORS, color_mapping, get_color_values

def _preflight(node_id,values):
    _guard(values)
    _font_path(values['font_name'])
    text=values['text'];font_size=values['font_size']
    if not isinstance(text,str) or len(text.encode('utf-8'))>16384 or len(text)>4096:
        raise ValueError('Masked text exceeds bound')
    if type(font_size) is not int or not 1<=font_size<=1024:
        raise ValueError('Masked font size exceeds bound')
    if len(text)*font_size*font_size>64*1024*1024:
        raise ValueError('Masked glyph workload exceeds bound')
    for key,limit in (('margins',1024),('line_spacing',1024),('position_x',4096),('position_y',4096)):
        value=values[key]
        if type(value) is not int or abs(value)>limit:raise ValueError('Masked text position/spacing exceeds bound')
    angle=values['rotation_angle']
    if isinstance(angle,bool) or not isinstance(angle,(int,float)) or not math.isfinite(angle) or abs(angle)>36000:
        raise ValueError('Masked text rotation exceeds bound')
    input_bytes=0;projected=0
    if node_id=='CR Draw Text':
        width=values['image_width'];height=values['image_height']
        if type(width) is not int or type(height) is not int or abs(width)>4096 or abs(height)>4096:
            raise ValueError('Masked text canvas dimensions exceed bound')
        projected=max(0,height)*max(0,width)*32
    else:
        for key,value in values.items():
            if key not in ('image','image_text','image_background'):continue
            if not isinstance(value,torch.Tensor) or value.layout!=torch.strided or value.ndim!=4:
                raise ValueError('Masked text requires bounded BHWC tensor')
            batch,height,width,channels=value.shape
            if batch>16 or height>4096 or width>4096 or not 1<=channels<=4:
                raise ValueError('Masked image dimensions exceed bound')
            input_bytes+=value.numel()*value.element_size()
            # Squeeze may transpose singleton width/channel geometry, never increase pixel count.
            projected+=height*width*max(1,channels)*32
    if input_bytes>32*1024*1024 or projected>64*1024*1024 or input_bytes+projected*2>128*1024*1024:
        raise ValueError('Masked text projected output/temporary workload exceeds bound')

def align_text(align, img_height, text_height, text_pos_y, margins):
    if align == 'center':
        text_plot_y = img_height / 2 - text_height / 2 + text_pos_y
    elif align == 'top':
        text_plot_y = text_pos_y + margins
    elif align == 'bottom':
        text_plot_y = img_height - text_height + text_pos_y - margins
    return text_plot_y

def justify_text(justify, img_width, line_width, margins):
    if justify == 'left':
        text_plot_x = 0 + margins
    elif justify == 'right':
        text_plot_x = img_width - line_width - margins
    elif justify == 'center':
        text_plot_x = img_width / 2 - line_width / 2
    return text_plot_x

def draw_masked_text(text_mask, text, font_name, font_size, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options):
    draw = ImageDraw.Draw(text_mask)
    resolved_font_path = _font_path(font_name)
    font = ImageFont.truetype(str(resolved_font_path), size=font_size)
    text_lines = text.split('\n')
    max_text_width = 0
    max_text_height = 0
    for line in text_lines:
        line_width, line_height = get_text_size(draw, line, font)
        line_height = line_height + line_spacing
        max_text_width = max(max_text_width, line_width)
        max_text_height = max(max_text_height, line_height)
    image_width, image_height = text_mask.size
    image_center_x = image_width / 2
    image_center_y = image_height / 2
    text_pos_y = position_y
    sum_text_plot_y = 0
    text_height = max_text_height * len(text_lines)
    for line in text_lines:
        line_width, _ = get_text_size(draw, line, font)
        text_plot_x = position_x + justify_text(justify, image_width, line_width, margins)
        text_plot_y = align_text(align, image_height, text_height, text_pos_y, margins)
        draw.text((text_plot_x, text_plot_y), line, fill=255, font=font)
        text_pos_y += max_text_height
        sum_text_plot_y += text_plot_y
    text_center_x = text_plot_x + max_text_width / 2
    text_center_y = sum_text_plot_y / len(text_lines)
    if rotation_options == 'text center':
        rotated_text_mask = text_mask.rotate(rotation_angle, center=(text_center_x, text_center_y))
    elif rotation_options == 'image center':
        rotated_text_mask = text_mask.rotate(rotation_angle, center=(image_center_x, image_center_y))
    return rotated_text_mask

class CR_OverlayText(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Overlay Text',display_name='🔤 CR Overlay Text',category='🧩 Comfyroll Studio/👾 Graphics/🔤 Text',is_output_node=False,inputs=[io.Image.Input('image'), io.String.Input('text', multiline=True, default='text'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('font_size', default=50, min=1, max=1024), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('align', options=['center', 'top', 'bottom']), io.Combo.Input('justify', options=['center', 'left', 'right']), io.Int.Input('margins', default=0, min=-1024, max=1024), io.Int.Input('line_spacing', default=0, min=-1024, max=1024), io.Int.Input('position_x', default=0, min=-4096, max=4096), io.Int.Input('position_y', default=0, min=-4096, max=4096), io.Float.Input('rotation_angle', default=0.0, min=-360.0, max=360.0, step=0.1), io.Combo.Input('rotation_options', options=['text center', 'image center']), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, text, font_name, font_size, font_color, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options, font_color_hex='#000000'):
        _preflight('CR Overlay Text', {'image': image, 'text': text, 'font_name': font_name, 'font_size': font_size, 'font_color': font_color, 'margins': margins, 'line_spacing': line_spacing, 'position_x': position_x, 'position_y': position_y, 'align': align, 'justify': justify, 'rotation_angle': rotation_angle, 'rotation_options': rotation_options, 'font_color_hex': font_color_hex})
        text_color = get_color_values(font_color, font_color_hex, color_mapping)
        image_3d = image[0, :, :, :]
        back_image = tensor2pil(image_3d)
        text_image = Image.new('RGB', back_image.size, text_color)
        text_mask = Image.new('L', back_image.size)
        rotated_text_mask = draw_masked_text(text_mask, text, font_name, font_size, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options)
        image_out = Image.composite(text_image, back_image, rotated_text_mask)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Text-Nodes#cr-overlay-text'
        return _output((pil2tensor(image_out), show_help))


class CR_DrawText(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Draw Text',display_name='🔤️ CR Draw Text',category='🧩 Comfyroll Studio/👾 Graphics/🔤 Text',is_output_node=False,inputs=[io.Int.Input('image_width', default=512, min=64, max=2048), io.Int.Input('image_height', default=512, min=64, max=2048), io.String.Input('text', multiline=True, default='text'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('font_size', default=50, min=1, max=1024), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('align', options=['center', 'top', 'bottom']), io.Combo.Input('justify', options=['center', 'left', 'right']), io.Int.Input('margins', default=0, min=-1024, max=1024), io.Int.Input('line_spacing', default=0, min=-1024, max=1024), io.Int.Input('position_x', default=0, min=-4096, max=4096), io.Int.Input('position_y', default=0, min=-4096, max=4096), io.Float.Input('rotation_angle', default=0.0, min=-360.0, max=360.0, step=0.1), io.Combo.Input('rotation_options', options=['text center', 'image center']), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image_width, image_height, text, font_name, font_size, font_color, background_color, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options, font_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Draw Text', {'image_width': image_width, 'image_height': image_height, 'text': text, 'font_name': font_name, 'font_size': font_size, 'font_color': font_color, 'background_color': background_color, 'margins': margins, 'line_spacing': line_spacing, 'position_x': position_x, 'position_y': position_y, 'align': align, 'justify': justify, 'rotation_angle': rotation_angle, 'rotation_options': rotation_options, 'font_color_hex': font_color_hex, 'bg_color_hex': bg_color_hex})
        text_color = get_color_values(font_color, font_color_hex, color_mapping)
        bg_color = get_color_values(background_color, bg_color_hex, color_mapping)
        size = (image_width, image_height)
        text_image = Image.new('RGB', size, text_color)
        back_image = Image.new('RGB', size, bg_color)
        text_mask = Image.new('L', back_image.size)
        rotated_text_mask = draw_masked_text(text_mask, text, font_name, font_size, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options)
        image_out = Image.composite(text_image, back_image, rotated_text_mask)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Text-Nodes#cr-draw-text'
        return _output((pil2tensor(image_out), show_help))


class CR_MaskText(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Mask Text',display_name='🔤️ CR Mask Text',category='🧩 Comfyroll Studio/👾 Graphics/🔤 Text',is_output_node=False,inputs=[io.Image.Input('image'), io.String.Input('text', multiline=True, default='text'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('font_size', default=50, min=1, max=1024), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('align', options=['center', 'top', 'bottom']), io.Combo.Input('justify', options=['center', 'left', 'right']), io.Int.Input('margins', default=0, min=-1024, max=1024), io.Int.Input('line_spacing', default=0, min=-1024, max=1024), io.Int.Input('position_x', default=0, min=-4096, max=4096), io.Int.Input('position_y', default=0, min=-4096, max=4096), io.Float.Input('rotation_angle', default=0.0, min=-360.0, max=360.0, step=0.1), io.Combo.Input('rotation_options', options=['text center', 'image center']), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, text, font_name, font_size, margins, line_spacing, position_x, position_y, background_color, align, justify, rotation_angle, rotation_options, bg_color_hex='#000000'):
        _preflight('CR Mask Text', {'image': image, 'text': text, 'font_name': font_name, 'font_size': font_size, 'margins': margins, 'line_spacing': line_spacing, 'position_x': position_x, 'position_y': position_y, 'background_color': background_color, 'align': align, 'justify': justify, 'rotation_angle': rotation_angle, 'rotation_options': rotation_options, 'bg_color_hex': bg_color_hex})
        bg_color = get_color_values(background_color, bg_color_hex, color_mapping)
        image_3d = image[0, :, :, :]
        text_image = tensor2pil(image_3d)
        text_mask = Image.new('L', text_image.size)
        background_image = Image.new('RGB', text_mask.size, bg_color)
        rotated_text_mask = draw_masked_text(text_mask, text, font_name, font_size, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options)
        text_mask = ImageOps.invert(rotated_text_mask)
        image_out = Image.composite(background_image, text_image, text_mask)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Text-Nodes#cr-mask-text'
        return _output((pil2tensor(image_out), show_help))


class CR_CompositeText(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Composite Text',display_name='🔤️ CR Composite Text',category='🧩 Comfyroll Studio/👾 Graphics/🔤 Text',is_output_node=False,inputs=[io.Image.Input('image_text'), io.Image.Input('image_background'), io.String.Input('text', multiline=True, default='text'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('font_size', default=50, min=1, max=1024), io.Combo.Input('align', options=['center', 'top', 'bottom']), io.Combo.Input('justify', options=['center', 'left', 'right']), io.Int.Input('margins', default=0, min=-1024, max=1024), io.Int.Input('line_spacing', default=0, min=-1024, max=1024), io.Int.Input('position_x', default=0, min=-4096, max=4096), io.Int.Input('position_y', default=0, min=-4096, max=4096), io.Float.Input('rotation_angle', default=0.0, min=-360.0, max=360.0, step=0.1), io.Combo.Input('rotation_options', options=['text center', 'image center'])],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image_text, image_background, text, font_name, font_size, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options):
        _preflight('CR Composite Text', {'image_text': image_text, 'image_background': image_background, 'text': text, 'font_name': font_name, 'font_size': font_size, 'margins': margins, 'line_spacing': line_spacing, 'position_x': position_x, 'position_y': position_y, 'align': align, 'justify': justify, 'rotation_angle': rotation_angle, 'rotation_options': rotation_options})
        image_text_3d = image_text[0, :, :, :]
        image_back_3d = image_background[0, :, :, :]
        text_image = tensor2pil(image_text_3d)
        back_image = tensor2pil(image_back_3d)
        text_mask = Image.new('L', back_image.size)
        rotated_text_mask = draw_masked_text(text_mask, text, font_name, font_size, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options)
        image_out = Image.composite(text_image, back_image, rotated_text_mask)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Text-Nodes#cr-composite-text'
        return _output((pil2tensor(image_out), show_help))


NODE_CLASS_MAPPINGS={
    'CR Overlay Text':CR_OverlayText,
    'CR Draw Text':CR_DrawText,
    'CR Mask Text':CR_MaskText,
    'CR Composite Text':CR_CompositeText,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Overlay Text': '🔤 CR Overlay Text', 'CR Draw Text': '🔤️ CR Draw Text', 'CR Mask Text': '🔤️ CR Mask Text', 'CR Composite Text': '🔤️ CR Composite Text'}
