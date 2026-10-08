"""Pinned text-mask algorithms; only the immutable bundled-font catalogue is readable."""
import math
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps
from comfy_api.latest import io
from .secure_schedules import _guard, _output
from .secure_graphics import _font_path, FONT_NAMES, tensor2pil, pil2tensor, get_text_size
from .secure_layout import COLORS, color_mapping, get_color_values, combine_images
from .secure_masked_text import align_text, justify_text

def _preflight(node_id,values):
    _guard(values)
    _font_path(values['font_name'])
    glyph_work=0
    for key in ('text','header_text','footer_text'):
        if key not in values:continue
        text=values[key]
        if not isinstance(text,str) or len(text.encode('utf-8'))>16384 or len(text)>4096:
            raise ValueError('Text panel text exceeds bound')
        size=values.get('font_size',0) if key=='text' else values.get(key.replace('_text','_font_size'),0)
        if type(size) is not int or abs(size)>1024:raise ValueError('Text panel font size exceeds bound')
        glyph_work+=len(text)*(abs(size)+2*abs(values.get('font_outline_thickness',0)))**2
    if glyph_work>64*1024*1024:raise ValueError('Text panel glyph workload exceeds bound')
    for key in ('border_thickness','header_height','footer_height','font_outline_thickness'):
        if key in values and (type(values[key]) is not int or abs(values[key])>1024):
            raise ValueError('Text panel border/height/outline exceeds bound')
    input_bytes=0
    if node_id=='CR Simple Text Panel':
        width=values['panel_width'];height=values['panel_height']
        if type(width) is not int or type(height) is not int or abs(width)>4096 or abs(height)>4096:
            raise ValueError('Text panel dimensions exceed bound')
    else:
        image=values['image_panel']
        if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim not in (3,4):
            raise ValueError('Text panel requires bounded HWC/BHWC tensor')
        batch,h,w,c=(1,*image.shape) if image.ndim==3 else tuple(image.shape)
        if batch>16 or h>4096 or w>4096 or not 1<=c<=4:raise ValueError('Text panel image dimensions exceed bound')
        input_bytes=image.numel()*image.element_size()
        width=w;height=h
        # tensor2pil squeezes singleton axes; conservatively cover swapped geometry.
        if h==1 or w==1 or c==1:width=height=max(h,w,c)
        height+=max(0,values['header_height'])+max(0,values['footer_height'])
        border=max(0,values['border_thickness'])*2;width+=border;height+=border
    if abs(width)>8192 or abs(height)>8192:raise ValueError('Text panel projected dimensions exceed bound')
    projected=max(0,width)*max(0,height)*32
    if input_bytes>32*1024*1024 or projected>64*1024*1024 or input_bytes+projected*2>128*1024*1024:
        raise ValueError('Text panel projected output/temporary workload exceeds bound')

def text_panel(image_width, image_height, text, font_name, font_size, font_color, font_outline_thickness, font_outline_color, background_color, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options):
    """
    Create an image with text overlaid on a background.
    
    Returns:
    PIL.Image.Image: Image with text overlaid on the background.
    """
    size = (image_width, image_height)
    panel = Image.new('RGB', size, background_color)
    image_out = draw_text(panel, text, font_name, font_size, font_color, font_outline_thickness, font_outline_color, background_color, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options)
    return image_out

def draw_text(panel, text, font_name, font_size, font_color, font_outline_thickness, font_outline_color, bg_color, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options):
    draw = ImageDraw.Draw(panel)
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
    image_center_x = panel.width / 2
    image_center_y = panel.height / 2
    text_pos_y = position_y
    sum_text_plot_y = 0
    text_height = max_text_height * len(text_lines)
    for line in text_lines:
        line_width, line_height = get_text_size(draw, line, font)
        text_plot_x = position_x + justify_text(justify, panel.width, line_width, margins)
        text_plot_y = align_text(align, panel.height, text_height, text_pos_y, margins)
        draw.text((text_plot_x, text_plot_y), line, fill=font_color, font=font, stroke_width=font_outline_thickness, stroke_fill=font_outline_color)
        text_pos_y += max_text_height
        sum_text_plot_y += text_plot_y
    text_center_x = text_plot_x + max_text_width / 2
    text_center_y = sum_text_plot_y / len(text_lines)
    if rotation_options == 'text center':
        rotated_panel = panel.rotate(rotation_angle, center=(text_center_x, text_center_y), resample=Image.BILINEAR)
    elif rotation_options == 'image center':
        rotated_panel = panel.rotate(rotation_angle, center=(image_center_x, image_center_y), resample=Image.BILINEAR)
    return rotated_panel

class CR_PageLayout(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Page Layout',display_name='🌁 CR Page Layout',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Combo.Input('layout_options', options=['header', 'footer', 'header and footer', 'no header or footer']), io.Image.Input('image_panel'), io.Int.Input('header_height', default=0, min=0, max=1024), io.String.Input('header_text', multiline=True, default='text'), io.Combo.Input('header_align', options=['left', 'center', 'right']), io.Int.Input('footer_height', default=0, min=0, max=1024), io.String.Input('footer_text', multiline=True, default='text'), io.Combo.Input('footer_align', options=['left', 'center', 'right']), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('header_font_size', default=150, min=0, max=1024), io.Int.Input('footer_font_size', default=50, min=0, max=1024), io.Int.Input('border_thickness', default=0, min=0, max=1024), io.Combo.Input('border_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('border_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, layout_options, image_panel, border_thickness, border_color, background_color, header_height, header_text, header_align, footer_height, footer_text, footer_align, font_name, font_color, header_font_size, footer_font_size, font_color_hex='#000000', border_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Page Layout', {'layout_options': layout_options, 'image_panel': image_panel, 'border_thickness': border_thickness, 'border_color': border_color, 'background_color': background_color, 'header_height': header_height, 'header_text': header_text, 'header_align': header_align, 'footer_height': footer_height, 'footer_text': footer_text, 'footer_align': footer_align, 'font_name': font_name, 'font_color': font_color, 'header_font_size': header_font_size, 'footer_font_size': footer_font_size, 'font_color_hex': font_color_hex, 'border_color_hex': border_color_hex, 'bg_color_hex': bg_color_hex})
        font_color = get_color_values(font_color, font_color_hex, color_mapping)
        border_color = get_color_values(border_color, border_color_hex, color_mapping)
        bg_color = get_color_values(background_color, bg_color_hex, color_mapping)
        main_panel = tensor2pil(image_panel)
        image_width = main_panel.width
        image_height = main_panel.height
        margins = 50
        line_spacing = 0
        position_x = 0
        position_y = 0
        align = 'center'
        rotation_angle = 0
        rotation_options = 'image center'
        font_outline_thickness = 0
        font_outline_color = 'black'
        images = []
        if layout_options == 'header' or layout_options == 'header and footer':
            header_panel = text_panel(image_width, header_height, header_text, font_name, header_font_size, font_color, font_outline_thickness, font_outline_color, bg_color, margins, line_spacing, position_x, position_y, align, header_align, rotation_angle, rotation_options)
            images.append(header_panel)
        images.append(main_panel)
        if layout_options == 'footer' or layout_options == 'header and footer':
            footer_panel = text_panel(image_width, footer_height, footer_text, font_name, footer_font_size, font_color, font_outline_thickness, font_outline_color, bg_color, margins, line_spacing, position_x, position_y, align, footer_align, rotation_angle, rotation_options)
            images.append(footer_panel)
        combined_image = combine_images(images, 'vertical')
        if border_thickness > 0:
            combined_image = ImageOps.expand(combined_image, border_thickness, border_color)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-page-layout'
        return _output((pil2tensor(combined_image), show_help))


class CR_SimpleTextPanel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Text Panel',display_name='🌁 CR Simple Text Panel',category='🧩 Comfyroll Studio/👾 Graphics/🌁 Layout',is_output_node=False,inputs=[io.Int.Input('panel_width', default=512, min=8, max=4096), io.Int.Input('panel_height', default=512, min=8, max=4096), io.String.Input('text', multiline=True, default='text'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('font_size', default=100, min=0, max=1024), io.Int.Input('font_outline_thickness', default=0, min=0, max=50), io.Combo.Input('font_outline_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('align', options=['top', 'center', 'bottom']), io.Combo.Input('justify', options=['left', 'center', 'right']), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, panel_width, panel_height, text, align, justify, font_name, font_color, font_size, font_outline_thickness, font_outline_color, background_color, font_color_hex='#000000', font_outline_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Simple Text Panel', {'panel_width': panel_width, 'panel_height': panel_height, 'text': text, 'align': align, 'justify': justify, 'font_name': font_name, 'font_color': font_color, 'font_size': font_size, 'font_outline_thickness': font_outline_thickness, 'font_outline_color': font_outline_color, 'background_color': background_color, 'font_color_hex': font_color_hex, 'font_outline_color_hex': font_outline_color_hex, 'bg_color_hex': bg_color_hex})
        font_color = get_color_values(font_color, font_color_hex, color_mapping)
        outline_color = get_color_values(font_outline_color, font_outline_color_hex, color_mapping)
        bg_color = get_color_values(background_color, bg_color_hex, color_mapping)
        margins = 50
        line_spacing = 0
        position_x = 0
        position_y = 0
        rotation_angle = 0
        rotation_options = 'image center'
        panel = text_panel(panel_width, panel_height, text, font_name, font_size, font_color, font_outline_thickness, outline_color, bg_color, margins, line_spacing, position_x, position_y, align, justify, rotation_angle, rotation_options)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-simple-text-panel'
        return _output((pil2tensor(panel), show_help))


NODE_CLASS_MAPPINGS={
    'CR Page Layout':CR_PageLayout,
    'CR Simple Text Panel':CR_SimpleTextPanel,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Page Layout': '🌁 CR Page Layout', 'CR Simple Text Panel': '🌁 CR Simple Text Panel'}
