"""Pinned rendering algorithms using bounded raw values and immutable bundled fonts."""
import math
import numpy as np
import torch
from PIL import Image,ImageDraw,ImageOps,ImageFont
from comfy_api.latest import io
from .secure_schedules import _guard,_output
from .secure_graphics import _font_path,FONT_NAMES,tensor2pil,pil2tensor,get_text_size,get_color_values,color_mapping,COLORS
from .secure_layout import combine_images
from .secure_text_panels import text_panel
from .secure_template_previews import apply_resize_image

def _preflight(node_id,values):
    _guard(values)
    if 'font_name' in values:_font_path(values['font_name'])
    batch=1;h=w=512;input_bytes=0
    for key in ('image','image1','image2','images'):
        image=values.get(key)
        if image is None:continue
        if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim not in (3,4):
            raise ValueError('Template requires bounded dense HWC/BHWC')
        b,ih,iw,c=(1,*image.shape) if image.ndim==3 else tuple(image.shape)
        if b>16 or ih>4096 or iw>4096 or c>4:raise ValueError('Template image dimensions exceed bound')
        input_bytes+=image.numel()*image.element_size()
        batch=max(batch,b);h=max(h,ih);w=max(w,iw)
        if ih==1 or iw==1 or c==1:h=w=max(h,w,ih,iw,c)
    size=values.get('max_font_size',values.get('font_size',0))
    if type(size) is not int or abs(size)>1024:raise ValueError('Template font size exceeds bound')
    glyphs=0
    texts=dict(values)
    if node_id=='CR Simple Meme Template':
        preset=values['preset']
        fixed={'One Does Not Simply ... MEME IN COMFY':('One Does Not Simply','MEME IN COMFY'),'This is fine.':('This is fine.',''),'Good Morning ... No Such Thing!':('Good Morning','"No Such Thing!"')}
        if preset in fixed:texts['text_top'],texts['text_bottom']=fixed[preset]
    for key in ('text_top','text_bottom','banner_text','text1','text2'):
        if key not in values:continue
        text=texts[key]
        if not isinstance(text,str) or len(text.encode('utf-8'))>16384 or len(text)>4096:
            raise ValueError('Template text exceeds bound')
        glyphs+=len(text)*abs(size)**2*batch
    if glyphs>64*1024*1024:raise ValueError('Template glyph workload exceeds bound')
    for key in ('border_thickness','outline_thickness','margin_size','footer_height'):
        if key in values and (type(values[key]) is not int or abs(values[key])>1024):
            raise ValueError('Template border/outline/footer exceeds bound')
    if node_id=='CR Comic Panel Templates':
        w=values['page_width'];h=values['page_height'];batch=1
        if type(w) is not int or type(h) is not int or abs(w)>4096 or abs(h)>4096:
            raise ValueError('Comic page dimensions exceed bound')
        layout=values['custom_panel_layout'] if values['template']=='custom' else values['template']
        if not isinstance(layout,str) or len(layout)>128 or len(layout.encode('utf-8'))>512:
            raise ValueError('Comic layout exceeds bound')
        if sum(int(v) for v in layout if v in '0123456789')>512:
            raise ValueError('Comic panel work exceeds bound')
        w+=2*abs(values['border_thickness']);h+=2*abs(values['border_thickness'])
    elif node_id=='CR Simple Meme Template':h=int(h*1.4)+4
    elif node_id=='CR Simple Image Compare':
        w=w*2+4*abs(values['border_thickness'])
        h+=max(0,values['footer_height'])+4*abs(values['border_thickness']);batch=1
    if abs(w)>8192 or abs(h)>8192:raise ValueError('Template projected dimensions exceed bound')
    projected=max(0,w)*max(0,h)*batch*16
    if input_bytes>32*1024*1024 or projected>32*1024*1024 or input_bytes+projected*3>128*1024*1024:
        raise ValueError('Template projected output/temporary workload exceeds bound')

def draw_text_on_image(draw, y_position, bar_width, bar_height, text, font, text_color, font_outline):
    text_width, text_height = get_text_size(draw, text, font)
    if font_outline == 'thin':
        outline_thickness = text_height // 40
    elif font_outline == 'thick':
        outline_thickness = text_height // 20
    elif font_outline == 'extra thick':
        outline_thickness = text_height // 10
    outline_color = (0, 0, 0)
    text_lines = text.split('\n')
    if len(text_lines) == 1:
        x = (bar_width - text_width) // 2
        y = y_position + (bar_height - text_height) // 2 - bar_height * 0.1
        if font_outline == 'none':
            draw.text((x, y), text, fill=text_color, font=font)
        else:
            draw.text((x, y), text, fill=text_color, font=font, stroke_width=outline_thickness, stroke_fill='black')
    elif len(text_lines) > 1:
        text_width, text_height = get_text_size(draw, text_lines[0], font)
        x = (bar_width - text_width) // 2
        y = y_position + (bar_height - text_height * 2) // 2 - bar_height * 0.15
        if font_outline == 'none':
            draw.text((x, y), text_lines[0], fill=text_color, font=font)
        else:
            draw.text((x, y), text_lines[0], fill=text_color, font=font, stroke_width=outline_thickness, stroke_fill='black')
        text_width, text_height = get_text_size(draw, text_lines[1], font)
        x = (bar_width - text_width) // 2
        y = y_position + (bar_height - text_height * 2) // 2 + text_height - bar_height * 0.0
        if font_outline == 'none':
            draw.text((x, y), text_lines[1], fill=text_color, font=font)
        else:
            draw.text((x, y), text_lines[1], fill=text_color, font=font, stroke_width=outline_thickness, stroke_fill='black')

def get_font_size(draw, text, max_width, max_height, font_path, max_font_size):
    max_width = max_width * 0.9
    font_size = max_font_size
    font = ImageFont.truetype(str(font_path), size=font_size)
    text_lines = text.split('\n')[:2]
    if len(text_lines) == 2:
        font_size = min(max_height // 2, max_font_size)
        font = ImageFont.truetype(str(font_path), size=font_size)
    max_text_width = 0
    longest_line = text_lines[0]
    for line in text_lines:
        line_width, line_height = get_text_size(draw, line, font)
        if line_width > max_text_width:
            longest_line = line
        max_text_width = max(max_text_width, line_width)
    text_width, text_height = get_text_size(draw, text, font)
    while max_text_width > max_width or text_height > 0.88 * max_height / len(text_lines):
        font_size -= 1
        font = ImageFont.truetype(str(font_path), size=font_size)
        max_text_width, text_height = get_text_size(draw, longest_line, font)
    return font

def crop_and_resize_image(image, target_width, target_height):
    width, height = image.size
    aspect_ratio = width / height
    target_aspect_ratio = target_width / target_height
    if aspect_ratio > target_aspect_ratio:
        crop_width = int(height * target_aspect_ratio)
        crop_height = height
        left = (width - crop_width) // 2
        top = 0
    else:
        crop_height = int(width / target_aspect_ratio)
        crop_width = width
        left = 0
        top = (height - crop_height) // 2
    cropped_image = image.crop((left, top, left + crop_width, top + crop_height))
    return cropped_image

def create_and_paste_panel(page, border_thickness, outline_thickness, panel_width, panel_height, page_width, panel_color, bg_color, outline_color, images, i, j, k, len_images, reading_direction):
    panel = Image.new('RGB', (panel_width, panel_height), panel_color)
    if k < len_images:
        img = images[k]
        image = crop_and_resize_image(img, panel_width, panel_height)
        image.thumbnail((panel_width, panel_height), Image.Resampling.LANCZOS)
        panel.paste(image, (0, 0))
    panel = ImageOps.expand(panel, border=outline_thickness, fill=outline_color)
    panel = ImageOps.expand(panel, border=border_thickness, fill=bg_color)
    new_panel_width, new_panel_height = panel.size
    if reading_direction == 'right to left':
        page.paste(panel, (page_width - (j + 1) * new_panel_width, i * new_panel_height))
    else:
        page.paste(panel, (j * new_panel_width, i * new_panel_height))

class CR_SimpleMemeTemplate(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Meme Template',display_name='📱 CR Simple Meme Template',category='🧩 Comfyroll Studio/👾 Graphics/📱 Template',inputs=[io.Image.Input('image'), io.Combo.Input('preset', options=['custom', 'One Does Not Simply ... MEME IN COMFY', 'This is fine.', 'Good Morning ... No Such Thing!']), io.String.Input('text_top', multiline=True, default='text_top'), io.String.Input('text_bottom', multiline=True, default='text_bottom'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('max_font_size', default=150, min=20, max=2048), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('font_outline', options=['none', 'thin', 'thick', 'extra thick']), io.Combo.Input('bar_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('bar_options', options=['no bars', 'top', 'bottom', 'top and bottom']), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bar_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, preset, text_top, text_bottom, font_name, max_font_size, font_color, font_outline, bar_color, bar_options, font_color_hex='#000000', bar_color_hex='#000000'):
        _preflight('CR Simple Meme Template', {'image': image, 'preset': preset, 'text_top': text_top, 'text_bottom': text_bottom, 'font_name': font_name, 'max_font_size': max_font_size, 'font_color': font_color, 'font_outline': font_outline, 'bar_color': bar_color, 'bar_options': bar_options, 'font_color_hex': font_color_hex, 'bar_color_hex': bar_color_hex})
        text_color = get_color_values(font_color, font_color_hex, color_mapping)
        bar_color = get_color_values(bar_color, bar_color_hex, color_mapping)
        total_images = []
        for img in image:
            if bar_options == 'top':
                height_factor = 1.2
            elif bar_options == 'bottom':
                height_factor = 1.2
            elif bar_options == 'top and bottom':
                height_factor = 1.4
            else:
                height_factor = 1.0
            if preset == 'One Does Not Simply ... MEME IN COMFY':
                text_top = 'One Does Not Simply'
                text_bottom = 'MEME IN COMFY'
            if preset == 'This is fine.':
                text_top = 'This is fine.'
                text_bottom = ''
            if preset == 'Good Morning ... No Such Thing!':
                text_top = 'Good Morning'
                text_bottom = '"No Such Thing!"'
            back_image = tensor2pil(img)
            size = (back_image.width, int(back_image.height * height_factor))
            result_image = Image.new('RGB', size)
            resolved_font_path = _font_path(font_name)
            draw = ImageDraw.Draw(result_image)
            bar_width = back_image.width
            bar_height = back_image.height // 5
            top_bar = Image.new('RGB', (bar_width, bar_height), bar_color)
            bottom_bar = Image.new('RGB', (bar_width, bar_height), bar_color)
            if bar_options == 'top' or bar_options == 'top and bottom':
                image_out = result_image.paste(back_image, (0, bar_height))
            else:
                image_out = result_image.paste(back_image, (0, 0))
            if bar_options == 'top' or bar_options == 'top and bottom':
                result_image.paste(top_bar, (0, 0))
                font_top = get_font_size(draw, text_top, bar_width, bar_height, resolved_font_path, max_font_size)
                draw_text_on_image(draw, 0, bar_width, bar_height, text_top, font_top, text_color, font_outline)
            if bar_options == 'bottom' or bar_options == 'top and bottom':
                result_image.paste(bottom_bar, (0, result_image.height - bar_height))
                font_bottom = get_font_size(draw, text_bottom, bar_width, bar_height, resolved_font_path, max_font_size)
                if bar_options == 'bottom':
                    y_position = back_image.height
                else:
                    y_position = bar_height + back_image.height
                draw_text_on_image(draw, y_position, bar_width, bar_height, text_bottom, font_bottom, text_color, font_outline)
            if bar_options == 'bottom' and text_top > '':
                font_top = get_font_size(draw, text_top, bar_width, bar_height, resolved_font_path, max_font_size)
                draw_text_on_image(draw, 0, bar_width, bar_height, text_top, font_top, text_color, font_outline)
            if (bar_options == 'top' or bar_options == 'none') and text_bottom > '':
                font_bottom = get_font_size(draw, text_bottom, bar_width, bar_height, resolved_font_path, max_font_size)
                y_position = back_image.height
                draw_text_on_image(draw, y_position, bar_width, bar_height, text_bottom, font_bottom, text_color, font_outline)
            if bar_options == 'no bars' and text_bottom > '':
                font_bottom = get_font_size(draw, text_bottom, bar_width, bar_height, resolved_font_path, max_font_size)
                y_position = back_image.height - bar_height
                draw_text_on_image(draw, y_position, bar_width, bar_height, text_bottom, font_bottom, text_color, font_outline)
            if bar_options == 'no bars' and text_top > '':
                font_top = get_font_size(draw, text_top, bar_width, bar_height, resolved_font_path, max_font_size)
                draw_text_on_image(draw, 0, bar_width, bar_height, text_top, font_top, text_color, font_outline)
            out_image = np.array(result_image.convert('RGB')).astype(np.float32) / 255.0
            out_image = torch.from_numpy(out_image).unsqueeze(0)
            total_images.append(out_image)
        images_out = torch.cat(total_images, 0)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Template-Nodes#cr-simple-meme-template'
        return _output((images_out, show_help))

class CR_SimpleBanner(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Banner',display_name='📱 CR Simple Banner',category='🧩 Comfyroll Studio/👾 Graphics/📱 Template',inputs=[io.Image.Input('image'), io.String.Input('banner_text', multiline=True, default='text'), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('max_font_size', default=150, min=20, max=2048), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('outline_thickness', default=0, min=0, max=500), io.Combo.Input('outline_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('margin_size', default=0, min=0, max=500), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('outline_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, banner_text, font_name, max_font_size, font_color, outline_thickness, outline_color, margin_size, font_color_hex='#000000', outline_color_hex='#000000'):
        _preflight('CR Simple Banner', {'image': image, 'banner_text': banner_text, 'font_name': font_name, 'max_font_size': max_font_size, 'font_color': font_color, 'outline_thickness': outline_thickness, 'outline_color': outline_color, 'margin_size': margin_size, 'font_color_hex': font_color_hex, 'outline_color_hex': outline_color_hex})
        text_color = get_color_values(font_color, font_color_hex, color_mapping)
        outline_color = get_color_values(outline_color, outline_color_hex, color_mapping)
        total_images = []
        for img in image:
            back_image = tensor2pil(img).convert('RGBA')
            size = (back_image.width, back_image.height)
            resolved_font_path = _font_path(font_name)
            draw = ImageDraw.Draw(back_image)
            area_width = back_image.width - margin_size * 2
            area_height = back_image.width - margin_size * 2
            font = get_font_size(draw, banner_text, area_width, area_height, resolved_font_path, max_font_size)
            x = back_image.width // 2
            y = back_image.height // 2
            if outline_thickness > 0:
                draw.text((x, y), banner_text, fill=text_color, font=font, anchor='mm', stroke_width=outline_thickness, stroke_fill=outline_color)
            else:
                draw.text((x, y), banner_text, fill=text_color, font=font, anchor='mm')
            out_image = np.array(back_image.convert('RGB')).astype(np.float32) / 255.0
            out_image = torch.from_numpy(out_image).unsqueeze(0)
            total_images.append(out_image)
        images_out = torch.cat(total_images, 0)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Template-Nodes#cr-simple-banner'
        return _output((images_out, show_help))

class CR_ComicPanelTemplates(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Comic Panel Templates',display_name='📱 CR Comic Panel Templates',category='🧩 Comfyroll Studio/👾 Graphics/📱 Template',inputs=[io.Int.Input('page_width', default=512, min=8, max=4096), io.Int.Input('page_height', default=512, min=8, max=4096), io.Combo.Input('template', options=['custom', 'G22', 'G33', 'H2', 'H3', 'H12', 'H13', 'H21', 'H23', 'H31', 'H32', 'V2', 'V3', 'V12', 'V13', 'V21', 'V23', 'V31', 'V32']), io.Combo.Input('reading_direction', options=['left to right', 'right to left']), io.Int.Input('border_thickness', default=5, min=0, max=1024), io.Int.Input('outline_thickness', default=2, min=0, max=1024), io.Combo.Input('outline_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('panel_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Image.Input('images', optional=True), io.String.Input('custom_panel_layout', multiline=False, default='H123', optional=True), io.String.Input('outline_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('panel_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, page_width, page_height, template, reading_direction, border_thickness, outline_thickness, outline_color, panel_color, background_color, images=None, custom_panel_layout='G44', outline_color_hex='#000000', panel_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Comic Panel Templates', {'page_width': page_width, 'page_height': page_height, 'template': template, 'reading_direction': reading_direction, 'border_thickness': border_thickness, 'outline_thickness': outline_thickness, 'outline_color': outline_color, 'panel_color': panel_color, 'background_color': background_color, 'images': images, 'custom_panel_layout': custom_panel_layout, 'outline_color_hex': outline_color_hex, 'panel_color_hex': panel_color_hex, 'bg_color_hex': bg_color_hex})
        panels = []
        k = 0
        len_images = 0
        if images is not None:
            images = [tensor2pil(image) for image in images]
            len_images = len(images)
        outline_color = get_color_values(outline_color, outline_color_hex, color_mapping)
        panel_color = get_color_values(panel_color, panel_color_hex, color_mapping)
        bg_color = get_color_values(background_color, bg_color_hex, color_mapping)
        size = (page_width - 2 * border_thickness, page_height - 2 * border_thickness)
        page = Image.new('RGB', size, bg_color)
        draw = ImageDraw.Draw(page)
        if template == 'custom':
            template = custom_panel_layout
        first_char = template[0]
        if first_char == 'G':
            rows = int(template[1])
            columns = int(template[2])
            panel_width = (page.width - 2 * columns * (border_thickness + outline_thickness)) // columns
            panel_height = (page.height - 2 * rows * (border_thickness + outline_thickness)) // rows
            for i in range(rows):
                for j in range(columns):
                    create_and_paste_panel(page, border_thickness, outline_thickness, panel_width, panel_height, page.width, panel_color, bg_color, outline_color, images, i, j, k, len_images, reading_direction)
                    k += 1
        elif first_char == 'H':
            rows = len(template) - 1
            panel_height = (page.height - 2 * rows * (border_thickness + outline_thickness)) // rows
            for i in range(rows):
                columns = int(template[i + 1])
                panel_width = (page.width - 2 * columns * (border_thickness + outline_thickness)) // columns
                for j in range(columns):
                    create_and_paste_panel(page, border_thickness, outline_thickness, panel_width, panel_height, page.width, panel_color, bg_color, outline_color, images, i, j, k, len_images, reading_direction)
                    k += 1
        elif first_char == 'V':
            columns = len(template) - 1
            panel_width = (page.width - 2 * columns * (border_thickness + outline_thickness)) // columns
            for j in range(columns):
                rows = int(template[j + 1])
                panel_height = (page.height - 2 * rows * (border_thickness + outline_thickness)) // rows
                for i in range(rows):
                    create_and_paste_panel(page, border_thickness, outline_thickness, panel_width, panel_height, page.width, panel_color, bg_color, outline_color, images, i, j, k, len_images, reading_direction)
                    k += 1
        if border_thickness > 0:
            page = ImageOps.expand(page, border_thickness, bg_color)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Template-Nodes#cr-comic-panel-templates'
        return _output((pil2tensor(page), show_help))

class CR_SimpleImageCompare(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Image Compare',display_name='📱 CR Simple Image Compare',category='🧩 Comfyroll Studio/👾 Graphics/📱 Template',inputs=[io.String.Input('text1', multiline=True, default='text'), io.String.Input('text2', multiline=True, default='text'), io.Int.Input('footer_height', default=100, min=0, max=1024), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('font_size', default=50, min=0, max=1024), io.Combo.Input('mode', options=['normal', 'dark']), io.Int.Input('border_thickness', default=20, min=0, max=1024), io.Image.Input('image1', optional=True), io.Image.Input('image2', optional=True)],outputs=[io.Image.Output(display_name='image'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text1, text2, footer_height, font_name, font_size, mode, border_thickness, image1=None, image2=None):
        _preflight('CR Simple Image Compare', {'text1': text1, 'text2': text2, 'footer_height': footer_height, 'font_name': font_name, 'font_size': font_size, 'mode': mode, 'border_thickness': border_thickness, 'image1': image1, 'image2': image2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-simple-image-compare'
        if mode == 'normal':
            font_color = 'black'
            bg_color = 'white'
        else:
            font_color = 'white'
            bg_color = 'black'
        if image1 is not None and image2 is not None:
            img1 = tensor2pil(image1)
            img2 = tensor2pil(image2)
            image_width, image_height = (img1.width, img1.height)
            if img2.width != img1.width or img2.height != img1.height:
                img2 = apply_resize_image(img2, image_width, image_height, 8, 'rescale', 'false', 1, 256, 'lanczos')
            margins = 50
            line_spacing = 0
            position_x = 0
            position_y = 0
            align = 'center'
            rotation_angle = 0
            rotation_options = 'image center'
            font_outline_thickness = 0
            font_outline_color = 'black'
            align = 'center'
            footer_align = 'center'
            outline_thickness = border_thickness // 2
            border_thickness = border_thickness // 2
            if footer_height > 0:
                text_panel1 = text_panel(image_width, footer_height, text1, font_name, font_size, font_color, font_outline_thickness, font_outline_color, bg_color, margins, line_spacing, position_x, position_y, align, footer_align, rotation_angle, rotation_options)
            combined_img1 = img1 if footer_height == 0 else combine_images([img1, text_panel1], 'vertical')
            if outline_thickness > 0:
                combined_img1 = ImageOps.expand(combined_img1, outline_thickness, fill=bg_color)
            if footer_height > 0:
                text_panel2 = text_panel(image_width, footer_height, text2, font_name, font_size, font_color, font_outline_thickness, font_outline_color, bg_color, margins, line_spacing, position_x, position_y, align, footer_align, rotation_angle, rotation_options)
            combined_img2 = img2 if footer_height == 0 else combine_images([img2, text_panel2], 'vertical')
            if outline_thickness > 0:
                combined_img2 = ImageOps.expand(combined_img2, outline_thickness, fill=bg_color)
            result_img = combine_images([combined_img1, combined_img2], 'horizontal')
        else:
            result_img = Image.new('RGB', (512, 512), bg_color)
        if border_thickness > 0:
            result_img = ImageOps.expand(result_img, border_thickness, bg_color)
        return _output((pil2tensor(result_img), show_help))

NODE_CLASS_MAPPINGS={'CR Simple Meme Template':CR_SimpleMemeTemplate, 'CR Simple Banner':CR_SimpleBanner, 'CR Comic Panel Templates':CR_ComicPanelTemplates, 'CR Simple Image Compare':CR_SimpleImageCompare}
NODE_DISPLAY_NAME_MAPPINGS={'CR Simple Meme Template': '📱 CR Simple Meme Template', 'CR Simple Banner': '📱 CR Simple Banner', 'CR Comic Panel Templates': '📱 CR Comic Panel Templates', 'CR Simple Image Compare': '📱 CR Simple Image Compare'}
