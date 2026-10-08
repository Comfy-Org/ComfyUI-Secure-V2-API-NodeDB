"""Raw image algorithms and closed immutable pack-font resources; no ambient host font lookup."""
import math
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from comfy_api.latest import io

FONT_NAMES = ['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']
color_mapping = {'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'yellow': (255, 255, 0), 'cyan': (0, 255, 255), 'magenta': (255, 0, 255), 'orange': (255, 165, 0), 'purple': (128, 0, 128), 'pink': (255, 192, 203), 'brown': (160, 85, 15), 'gray': (128, 128, 128), 'lightgray': (211, 211, 211), 'darkgray': (102, 102, 102), 'olive': (128, 128, 0), 'lime': (0, 128, 0), 'teal': (0, 128, 128), 'navy': (0, 0, 128), 'maroon': (128, 0, 0), 'fuchsia': (255, 0, 128), 'aqua': (0, 255, 128), 'silver': (192, 192, 192), 'gold': (255, 215, 0), 'turquoise': (64, 224, 208), 'lavender': (230, 230, 250), 'violet': (238, 130, 238), 'coral': (255, 127, 80), 'indigo': (75, 0, 130)}
COLORS = ['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']

def _font_path(name):
    if type(name) is not str or name not in FONT_NAMES:
        raise ValueError('Font must be an immutable bundled resource')
    return str(Path(__file__).parent/'fonts'/name)

def _image_budget(image):
    if not isinstance(image,torch.Tensor) or image.ndim!=4:
        raise ValueError('Expected bounded BHWC tensor')
    batch,height,width,channels=image.shape
    if batch>16 or height>4096 or width>4096 or channels not in (1,3,4):
        raise ValueError('Image dimensions/batch/channels exceed bounded range')
    if image.numel()*image.element_size()>32*1024*1024 or batch*height*width*96>128*1024*1024:
        raise ValueError('Image projected temporary/output allocation exceeds bound')

def _text_budget(text,font_size,x_margin,y_margin):
    if not isinstance(text,str) or len(text.encode('utf-8'))>16384 or len(text)>4096:
        raise ValueError('Watermark text exceeds bounded range')
    if type(font_size) is not int or not 1<=font_size<=1024:
        raise ValueError('Font size exceeds bounded range')
    if any(type(v) is not int or abs(v)>1024 for v in (x_margin,y_margin)):
        raise ValueError('Watermark margins exceed bounded range')

def tensor2pil(image):
    return Image.fromarray(np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

def get_text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    return (text_width, text_height)

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

def reduce_opacity(img, opacity):
    """Returns an image with reduced opacity."""
    assert opacity >= 0 and opacity <= 1
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    else:
        img = img.copy()
    alpha = img.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    img.putalpha(alpha)
    return img

class CR_SimpleTextWatermark(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Text Watermark', display_name='🔤️ CR Simple Text Watermark', category='🧩 Comfyroll Studio/👾 Graphics/🔤 Text', inputs=[io.Image.Input('image'), io.String.Input('text', multiline=False, default='@ your name'), io.Combo.Input('align', options=['center', 'top left', 'top center', 'top right', 'bottom left', 'bottom center', 'bottom right']), io.Float.Input('opacity', default=0.3, min=0.0, max=1.0, step=0.01), io.Combo.Input('font_name', options=['Quicksand-Bold.ttf', 'YoungSerif-Regular.ttf', 'Oswald-Bold.ttf', 'Roboto-Regular.ttf', 'comic.ttf', 'impact.ttf', 'AlumniSansCollegiateOne-Regular.ttf', 'Caveat-VariableFont_wght.ttf', 'PixelifySans-Bold.ttf', 'NotoSansArabic-Regular.ttf']), io.Int.Input('font_size', default=50, min=1, max=1024), io.Combo.Input('font_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('x_margin', default=20, min=-1024, max=1024), io.Int.Input('y_margin', default=20, min=-1024, max=1024), io.String.Input('font_color_hex', multiline=False, default='#000000', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, text, align, font_name, font_size, font_color, opacity, x_margin, y_margin, font_color_hex='#000000'):
        _font_path(font_name)
        _text_budget(text, font_size, x_margin, y_margin)
        _image_budget(image)
        if image.shape[0]*len(text)*font_size*font_size>64*1024*1024:
            raise ValueError('Watermark projected glyph workload exceeds bound')
        if not isinstance(font_color_hex,str) or len(font_color_hex)>128:
            raise ValueError('Watermark color text exceeds bounded range')
        text_color = get_color_values(font_color, font_color_hex, color_mapping)
        total_images = []
        for img in image:
            img = tensor2pil(img)
            textlayer = Image.new('RGBA', img.size)
            draw = ImageDraw.Draw(textlayer)
            font_file = 'fonts/'+font_name
            resolved_font_path = _font_path(font_name)
            font = ImageFont.truetype(str(resolved_font_path), size=font_size)
            textsize = get_text_size(draw, text, font)
            if align == 'center':
                textpos = [(img.size[0] - textsize[0]) // 2, (img.size[1] - textsize[1]) // 2]
            elif align == 'top left':
                textpos = [x_margin, y_margin]
            elif align == 'top center':
                textpos = [(img.size[0] - textsize[0]) // 2, y_margin]
            elif align == 'top right':
                textpos = [img.size[0] - textsize[0] - x_margin, y_margin]
            elif align == 'bottom left':
                textpos = [x_margin, img.size[1] - textsize[1] - y_margin]
            elif align == 'bottom center':
                textpos = [(img.size[0] - textsize[0]) // 2, img.size[1] - textsize[1] - y_margin]
            elif align == 'bottom right':
                textpos = [img.size[0] - textsize[0] - x_margin, img.size[1] - textsize[1] - y_margin]
            draw.text(textpos, text, font=font, fill=text_color)
            if opacity != 1:
                textlayer = reduce_opacity(textlayer, opacity)
            out_image = Image.composite(textlayer, img, textlayer)
            out_image = np.array(out_image.convert('RGB')).astype(np.float32) / 255.0
            out_image = torch.from_numpy(out_image).unsqueeze(0)
            total_images.append(out_image)
        images_out = torch.cat(total_images, 0)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Text-Nodes#cr-simple-text-watermark'
        return io.NodeOutput(images_out, show_help)


class CR_ColorTint(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Color Tint', display_name='🎨 CR Color Tint', category='🧩 Comfyroll Studio/👾 Graphics/🎨 Filter', inputs=[io.Image.Input('image'), io.Float.Input('strength', default=1.0, min=0.1, max=1.0, step=0.1), io.Combo.Input('mode', options=['custom', 'white', 'black', 'sepia', 'red', 'green', 'blue', 'cyan', 'magenta', 'yellow', 'purple', 'orange', 'warm', 'cool', 'lime', 'navy', 'vintage', 'rose', 'teal', 'maroon', 'peach', 'lavender', 'olive']), io.String.Input('tint_color_hex', multiline=False, default='#000000', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image: torch.Tensor, strength, mode: str='sepia', tint_color_hex='#000000'):
        if isinstance(strength, bool) or not isinstance(strength, (int, float)) or (not math.isfinite(strength)) or (not 0 <= strength <= 1):
            raise ValueError('Tint strength exceeds bounded range')
        if not isinstance(tint_color_hex, str) or len(tint_color_hex) > 128:
            raise ValueError('Tint color text exceeds bounded range')
        _image_budget(image)
        if strength == 0:
            # Explicit coordinator-approved repair of source one-output defect.
            return io.NodeOutput(image, 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Filter-Nodes#cr-color-tint')
        tint_color = get_color_values(mode, tint_color_hex, color_mapping)
        color_rgb = tuple([value / 255 for value in tint_color])
        sepia_weights = torch.tensor([0.2989, 0.587, 0.114]).view(1, 1, 1, 3).to(image.device)
        mode_filters = {'custom': torch.tensor([color_rgb[0], color_rgb[1], color_rgb[2]]), 'white': torch.tensor([1, 1, 1]), 'black': torch.tensor([0, 0, 0]), 'sepia': torch.tensor([1.0, 0.8, 0.6]), 'red': torch.tensor([1.0, 0.6, 0.6]), 'green': torch.tensor([0.6, 1.0, 0.6]), 'blue': torch.tensor([0.6, 0.8, 1.0]), 'cyan': torch.tensor([0.6, 1.0, 1.0]), 'magenta': torch.tensor([1.0, 0.6, 1.0]), 'yellow': torch.tensor([1.0, 1.0, 0.6]), 'purple': torch.tensor([0.8, 0.6, 1.0]), 'orange': torch.tensor([1.0, 0.7, 0.3]), 'warm': torch.tensor([1.0, 0.9, 0.7]), 'cool': torch.tensor([0.7, 0.9, 1.0]), 'lime': torch.tensor([0.7, 1.0, 0.3]), 'navy': torch.tensor([0.3, 0.4, 0.7]), 'vintage': torch.tensor([0.9, 0.85, 0.7]), 'rose': torch.tensor([1.0, 0.8, 0.9]), 'teal': torch.tensor([0.3, 0.8, 0.8]), 'maroon': torch.tensor([0.7, 0.3, 0.5]), 'peach': torch.tensor([1.0, 0.8, 0.6]), 'lavender': torch.tensor([0.8, 0.6, 1.0]), 'olive': torch.tensor([0.6, 0.7, 0.4])}
        scale_filter = mode_filters[mode].view(1, 1, 1, 3).to(image.device)
        grayscale = torch.sum(image * sepia_weights, dim=-1, keepdim=True)
        tinted = grayscale * scale_filter
        result = tinted * strength + image * (1 - strength)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Filter-Nodes#cr-color-tint'
        return io.NodeOutput(result, show_help)


class CR_VignetteFilter(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Vignette Filter', display_name='🎨 CR Vignette Filter', category='🧩 Comfyroll Studio/👾 Graphics/🎨 Filter', inputs=[io.Image.Input('image'), io.Combo.Input('vignette_shape', options=['circle', 'oval', 'square', 'diamond']), io.Int.Input('feather_amount', default=100, min=0, max=1024), io.Int.Input('x_offset', default=0, min=-2048, max=2048), io.Int.Input('y_offset', default=0, min=-2048, max=2048), io.Float.Input('zoom', default=1.0, min=0.0, max=10.0, step=0.1), io.Combo.Input('reverse', options=['no', 'yes'])], outputs=[io.Image.Output(display_name='IMAGE'), io.Mask.Output(display_name='MASK'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image, feather_amount, reverse, vignette_shape='circle', x_offset=0, y_offset=0, zoom=1.0):
        if type(feather_amount) is not int or not 0 <= feather_amount <= 1024 or any((type(v) is not int or abs(v) > 2048 for v in (x_offset, y_offset))) or isinstance(zoom, bool) or (not isinstance(zoom, (int, float))) or (not math.isfinite(zoom)) or (not 0 <= zoom <= 10):
            raise ValueError('Vignette parameters exceed bounded range')
        _image_budget(image)
        images = []
        masks = []
        vignette_color = 'black'
        for img in image:
            im = tensor2pil(img)
            RADIUS = feather_amount
            alpha_mask = Image.new('L', im.size, 255)
            draw = ImageDraw.Draw(alpha_mask)
            center_x = im.size[0] // 2 + x_offset
            center_y = im.size[1] // 2 + y_offset
            radius = min(center_x, center_y) * zoom
            size_x = (im.size[0] - RADIUS) * zoom
            size_y = (im.size[1] - RADIUS) * zoom
            if vignette_shape == 'circle':
                if reverse == 'no':
                    draw.ellipse([(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)], fill=0)
                elif reverse == 'yes':
                    draw.rectangle([(0, 0), im.size], fill=0)
                    draw.ellipse([(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)], fill=255)
                else:
                    raise ValueError("Invalid value for reverse. Use 'yes' or 'no'.")
            elif vignette_shape == 'oval':
                if reverse == 'no':
                    draw.ellipse([(center_x - size_x / 2, center_y - size_y / 2), (center_x + size_x / 2, center_y + size_y / 2)], fill=0)
                elif reverse == 'yes':
                    draw.rectangle([(0, 0), im.size], fill=0)
                    draw.ellipse([(center_x - size_x / 2, center_y - size_y / 2), (center_x + size_x / 2, center_y + size_y / 2)], fill=255)
            elif vignette_shape == 'diamond':
                if reverse == 'no':
                    size = min(im.size[0] - x_offset, im.size[1] - y_offset) * zoom
                    draw.polygon([(center_x, center_y - size / 2), (center_x + size / 2, center_y), (center_x, center_y + size / 2), (center_x - size / 2, center_y)], fill=0)
                elif reverse == 'yes':
                    size = min(im.size[0] - x_offset, im.size[1] - y_offset) * zoom
                    draw.rectangle([(0, 0), im.size], fill=0)
                    draw.polygon([(center_x, center_y - size / 2), (center_x + size / 2, center_y), (center_x, center_y + size / 2), (center_x - size / 2, center_y)], fill=255)
            elif vignette_shape == 'square':
                if reverse == 'no':
                    size = min(im.size[0] - x_offset, im.size[1] - y_offset) * zoom
                    draw.rectangle([(center_x - size / 2, center_y - size / 2), (center_x + size / 2, center_y + size / 2)], fill=0)
                elif reverse == 'yes':
                    size = min(im.size[0] - x_offset, im.size[1] - y_offset) * zoom
                    draw.rectangle([(0, 0), im.size], fill=0)
                    draw.rectangle([(center_x - size / 2, center_y - size / 2), (center_x + size / 2, center_y + size / 2)], fill=255)
                else:
                    raise ValueError("Invalid value for reverse. Use 'yes' or 'no'.")
            else:
                raise ValueError("Invalid vignette_shape. Use 'circle', 'oval', or 'square'.")
            alpha_mask = alpha_mask.filter(ImageFilter.GaussianBlur(RADIUS))
            masks.append(pil2tensor(alpha_mask).unsqueeze(0))
            vignette_img = Image.new('RGBA', im.size, vignette_color)
            vignette_img.putalpha(alpha_mask)
            result_img = Image.alpha_composite(im.convert('RGBA'), vignette_img)
            images.append(pil2tensor(result_img.convert('RGB')))
        images = torch.cat(images, dim=0)
        masks = torch.cat(masks, dim=0)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Layout-Nodes#cr-vignette-filter'
        return io.NodeOutput(images, masks, show_help)


NODE_CLASS_MAPPINGS = {
    'CR Simple Text Watermark': CR_SimpleTextWatermark,
    'CR Color Tint': CR_ColorTint,
    'CR Vignette Filter': CR_VignetteFilter,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Simple Text Watermark': '🔤️ CR Simple Text Watermark', 'CR Color Tint': '🎨 CR Color Tint', 'CR Vignette Filter': '🎨 CR Vignette Filter'}
