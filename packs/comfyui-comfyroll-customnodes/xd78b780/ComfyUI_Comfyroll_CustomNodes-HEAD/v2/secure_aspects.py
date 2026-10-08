"""Bounded raw/value-mode pack-side aspect tensors; public allocator cannot express zero grids."""
import math
import torch
from comfy_api.latest import io

def _preflight(width,height,batch_size,scale):
    if any(type(v) is not int for v in (width,height,batch_size)):
        raise TypeError('Comfyroll dimensions and batch must be integers')
    if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not math.isfinite(scale) or abs(scale)>100:
        raise ValueError('Comfyroll prescale exceeds bounded range')
    if abs(width)>16384 or abs(height)>16384 or not -64<=batch_size<=64:
        raise ValueError('Comfyroll dimensions/batch exceed bounded range')

def _bounded_zeros(shape):
    if len(shape)!=4 or any(type(v) is not int for v in shape):
        raise TypeError('Comfyroll latent shape must contain four integers')
    if any(v<0 for v in shape):
        # Preserve the pinned Torch error before any memory allocation.
        raise RuntimeError('Trying to create tensor with negative dimension '+str(shape))
    if shape[0]>64 or shape[1]!=4 or any(v>2048 for v in shape[2:]):
        raise ValueError('Comfyroll latent dimensions exceed bounded range')
    output_bytes=math.prod(shape)*4
    if output_bytes>64*1024*1024:
        raise ValueError('Comfyroll whole-batch latent exceeds 64MiB')
    # Explicit dtype means accounting and pinned normal default agree.
    return torch.zeros(shape,dtype=torch.float32)

PRINT_SIZES = {'A4 - 2480x3508': (2480, 3508), 'A5 - 1748x2480': (1748, 2480), 'A6 - 1240x1748': (1240, 1748), 'A7 - 874x1240': (874, 1240), 'A8 - 614x874': (614, 874), 'A9 - 437x614': (437, 614), 'A10 - 307x437': (307, 437), 'B4 - 2953x4169': (2953, 4169), 'B5 - 2079x2953': (2079, 2953), 'B6 - 1476x2079': (1476, 2079), 'B7 - 1039x1476': (1039, 1476), 'B8 - 732x1039': (732, 1039), 'B9 - 520x732': (520, 732), 'B10 - 366x520': (366, 520), 'C4 - 2705x3827': (2705, 3827), 'C5 - 1913x2705': (1913, 2705), 'C6 - 1346x1913': (1346, 1913), 'C7 - 957x1346': (957, 1346), 'C8 - 673x957': (673, 957), 'C9 - 472x673': (472, 673), 'C10 - 331x472': (331, 472), 'Letter (8.5 x 11 inches) - 2550x3300': (2550, 3300), 'Legal (8.5 x 14 inches) - 2550x4200': (2550, 4200)}

class CR_AspectRatioSD15(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR SD1.5 Aspect Ratio', display_name='🔳 CR SD1.5 Aspect Ratio', category='🧩 Comfyroll Studio/✨ Essential/🔳 Aspect Ratio', inputs=[io.Int.Input('width', default=512, min=64, max=8192), io.Int.Input('height', default=512, min=64, max=8192), io.Combo.Input('aspect_ratio', options=['custom', '1:1 square 512x512', '1:1 square 1024x1024', '2:3 portrait 512x768', '3:4 portrait 512x682', '3:2 landscape 768x512', '4:3 landscape 682x512', '16:9 cinema 910x512', '1.85:1 cinema 952x512', '2:1 cinema 1024x512', '2.39:1 anamorphic 1224x512']), io.Combo.Input('swap_dimensions', options=['Off', 'On']), io.Float.Input('upscale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Int.Input('batch_size', default=1, min=1, max=64)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.Int.Output(display_name='batch_size'), io.Latent.Output(display_name='empty_latent'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, aspect_ratio, swap_dimensions, upscale_factor, batch_size):
        _preflight(width, height, batch_size, 1.0)
        if aspect_ratio == '2:3 portrait 512x768':
            width, height = (512, 768)
        elif aspect_ratio == '3:2 landscape 768x512':
            width, height = (768, 512)
        elif aspect_ratio == '1:1 square 512x512':
            width, height = (512, 512)
        elif aspect_ratio == '1:1 square 1024x1024':
            width, height = (1024, 1024)
        elif aspect_ratio == '16:9 cinema 910x512':
            width, height = (910, 512)
        elif aspect_ratio == '3:4 portrait 512x682':
            width, height = (512, 682)
        elif aspect_ratio == '4:3 landscape 682x512':
            width, height = (682, 512)
        elif aspect_ratio == '1.85:1 cinema 952x512':
            width, height = (952, 512)
        elif aspect_ratio == '2:1 cinema 1024x512':
            width, height = (1024, 512)
        elif aspect_ratio == '2.39:1 anamorphic 1224x512':
            width, height = (1224, 512)
        if swap_dimensions == 'On':
            width, height = (height, width)
        latent = _bounded_zeros([batch_size, 4, height // 8, width // 8])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Aspect-Ratio-Nodes#cr-sd15-aspect-ratio'
        return io.NodeOutput(width, height, upscale_factor, batch_size, {'samples': latent}, show_help)


class CR_SDXLAspectRatio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR SDXL Aspect Ratio', display_name='🔳 CR SDXL Aspect Ratio', category='🧩 Comfyroll Studio/✨ Essential/🔳 Aspect Ratio', inputs=[io.Int.Input('width', default=1024, min=64, max=8192), io.Int.Input('height', default=1024, min=64, max=8192), io.Combo.Input('aspect_ratio', options=['custom', '1:1 square 1024x1024', '3:4 portrait 896x1152', '5:8 portrait 832x1216', '9:16 portrait 768x1344', '9:21 portrait 640x1536', '4:3 landscape 1152x896', '3:2 landscape 1216x832', '16:9 landscape 1344x768', '21:9 landscape 1536x640']), io.Combo.Input('swap_dimensions', options=['Off', 'On']), io.Float.Input('upscale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Int.Input('batch_size', default=1, min=1, max=64)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.Int.Output(display_name='batch_size'), io.Latent.Output(display_name='empty_latent'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, aspect_ratio, swap_dimensions, upscale_factor, batch_size):
        _preflight(width, height, batch_size, 1.0)
        if aspect_ratio == '1:1 square 1024x1024':
            width, height = (1024, 1024)
        elif aspect_ratio == '3:4 portrait 896x1152':
            width, height = (896, 1152)
        elif aspect_ratio == '5:8 portrait 832x1216':
            width, height = (832, 1216)
        elif aspect_ratio == '9:16 portrait 768x1344':
            width, height = (768, 1344)
        elif aspect_ratio == '9:21 portrait 640x1536':
            width, height = (640, 1536)
        elif aspect_ratio == '4:3 landscape 1152x896':
            width, height = (1152, 896)
        elif aspect_ratio == '3:2 landscape 1216x832':
            width, height = (1216, 832)
        elif aspect_ratio == '16:9 landscape 1344x768':
            width, height = (1344, 768)
        elif aspect_ratio == '21:9 landscape 1536x640':
            width, height = (1536, 640)
        if swap_dimensions == 'On':
            width, height = (height, width)
        latent = _bounded_zeros([batch_size, 4, height // 8, width // 8])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Aspect-Ratio-Nodes#cr-sdxl-aspect-ratio'
        return io.NodeOutput(width, height, upscale_factor, batch_size, {'samples': latent}, show_help)


class CR_AspectRatio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Aspect Ratio', display_name='🔳 CR Aspect Ratio', category='🧩 Comfyroll Studio/✨ Essential/🔳 Aspect Ratio', inputs=[io.Int.Input('width', default=1024, min=64, max=8192), io.Int.Input('height', default=1024, min=64, max=8192), io.Combo.Input('aspect_ratio', options=['custom', 'SD1.5 - 1:1 square 512x512', 'SD1.5 - 2:3 portrait 512x768', 'SD1.5 - 3:4 portrait 512x682', 'SD1.5 - 3:2 landscape 768x512', 'SD1.5 - 4:3 landscape 682x512', 'SD1.5 - 16:9 cinema 910x512', 'SD1.5 - 1.85:1 cinema 952x512', 'SD1.5 - 2:1 cinema 1024x512', 'SDXL - 1:1 square 1024x1024', 'SDXL - 3:4 portrait 896x1152', 'SDXL - 5:8 portrait 832x1216', 'SDXL - 9:16 portrait 768x1344', 'SDXL - 9:21 portrait 640x1536', 'SDXL - 4:3 landscape 1152x896', 'SDXL - 3:2 landscape 1216x832', 'SDXL - 16:9 landscape 1344x768', 'SDXL - 21:9 landscape 1536x640']), io.Combo.Input('swap_dimensions', options=['Off', 'On']), io.Float.Input('upscale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Float.Input('prescale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Int.Input('batch_size', default=1, min=1, max=64)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.Float.Output(display_name='prescale_factor'), io.Int.Output(display_name='batch_size'), io.Latent.Output(display_name='empty_latent'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, aspect_ratio, swap_dimensions, upscale_factor, prescale_factor, batch_size):
        _preflight(width, height, batch_size, prescale_factor)
        if aspect_ratio == 'SD1.5 - 1:1 square 512x512':
            width, height = (512, 512)
        elif aspect_ratio == 'SD1.5 - 2:3 portrait 512x768':
            width, height = (512, 768)
        elif aspect_ratio == 'SD1.5 - 16:9 cinema 910x512':
            width, height = (910, 512)
        elif aspect_ratio == 'SD1.5 - 3:4 portrait 512x682':
            width, height = (512, 682)
        elif aspect_ratio == 'SD1.5 - 3:2 landscape 768x512':
            width, height = (768, 512)
        elif aspect_ratio == 'SD1.5 - 4:3 landscape 682x512':
            width, height = (682, 512)
        elif aspect_ratio == 'SD1.5 - 1.85:1 cinema 952x512':
            width, height = (952, 512)
        elif aspect_ratio == 'SD1.5 - 2:1 cinema 1024x512':
            width, height = (1024, 512)
        elif aspect_ratio == 'SD1.5 - 2.39:1 anamorphic 1224x512':
            width, height = (1224, 512)
        if aspect_ratio == 'SDXL - 1:1 square 1024x1024':
            width, height = (1024, 1024)
        elif aspect_ratio == 'SDXL - 3:4 portrait 896x1152':
            width, height = (896, 1152)
        elif aspect_ratio == 'SDXL - 5:8 portrait 832x1216':
            width, height = (832, 1216)
        elif aspect_ratio == 'SDXL - 9:16 portrait 768x1344':
            width, height = (768, 1344)
        elif aspect_ratio == 'SDXL - 9:21 portrait 640x1536':
            width, height = (640, 1536)
        elif aspect_ratio == 'SDXL - 4:3 landscape 1152x896':
            width, height = (1152, 896)
        elif aspect_ratio == 'SDXL - 3:2 landscape 1216x832':
            width, height = (1216, 832)
        elif aspect_ratio == 'SDXL - 16:9 landscape 1344x768':
            width, height = (1344, 768)
        elif aspect_ratio == 'SDXL - 21:9 landscape 1536x640':
            width, height = (1536, 640)
        if swap_dimensions == 'On':
            width, height = (height, width)
        width = int(width * prescale_factor)
        height = int(height * prescale_factor)
        latent = _bounded_zeros([batch_size, 4, height // 8, width // 8])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Aspect-Ratio-Nodes#cr-aspect-ratio'
        return io.NodeOutput(width, height, upscale_factor, prescale_factor, batch_size, {'samples': latent}, show_help)


class CR_AspectRatioBanners(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Aspect Ratio Banners', display_name='🔳 CR Aspect Ratio Banners', category='🧩 Comfyroll Studio/✨ Essential/🔳 Aspect Ratio', inputs=[io.Int.Input('width', default=1024, min=64, max=8192), io.Int.Input('height', default=1024, min=64, max=8192), io.Combo.Input('aspect_ratio', options=['custom', 'Large Rectangle - 336x280', 'Medium Rectangle - 300x250', 'Small Rectangle - 180x150', 'Square - 250x250', 'Small Square - 200x200', 'Button - 125x125', 'Half Page - 300x600', 'Vertical Banner - 120x240', 'Wide Skyscraper - 160x600', 'Skyscraper - 120x600', 'Billboard - 970x250', 'Portrait - 300x1050', 'Banner - 468x60', 'Leaderboard - 728x90']), io.Combo.Input('swap_dimensions', options=['Off', 'On']), io.Float.Input('upscale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Float.Input('prescale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Int.Input('batch_size', default=1, min=1, max=64)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.Float.Output(display_name='prescale_factor'), io.Int.Output(display_name='batch_size'), io.Latent.Output(display_name='empty_latent'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, aspect_ratio, swap_dimensions, upscale_factor, prescale_factor, batch_size):
        _preflight(width, height, batch_size, prescale_factor)
        if aspect_ratio == 'Large Rectangle - 336x280':
            width, height = (336, 280)
        elif aspect_ratio == 'Medium Rectangle - 300x250':
            width, height = (300, 250)
        elif aspect_ratio == 'Small Rectangle - 180x150':
            width, height = (180, 150)
        elif aspect_ratio == 'Square - 250x250':
            width, height = (250, 250)
        elif aspect_ratio == 'Small Square - 200x200':
            width, height = (200, 200)
        elif aspect_ratio == 'Button - 125x125':
            width, height = (125, 125)
        elif aspect_ratio == 'Half Page - 300x600':
            width, height = (300, 600)
        elif aspect_ratio == 'Vertical Banner - 120x240':
            width, height = (120, 240)
        elif aspect_ratio == 'Wide Skyscraper - 160x600':
            width, height = (160, 600)
        elif aspect_ratio == 'Skyscraper - 120x600':
            width, height = (120, 600)
        elif aspect_ratio == 'Billboard - 970x250':
            width, height = (970, 250)
        elif aspect_ratio == 'Portrait - 300x1050':
            width, height = (300, 1050)
        elif aspect_ratio == 'Banner - 468x60':
            width, height = (168, 60)
        elif aspect_ratio == 'Leaderboard - 728x90':
            width, height = (728, 90)
        if swap_dimensions == 'On':
            width, height = (height, width)
        width = int(width * prescale_factor)
        height = int(height * prescale_factor)
        latent = _bounded_zeros([batch_size, 4, height // 8, width // 8])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Aspect-Ratio-Nodes#cr-aspect-ratio-banners'
        return io.NodeOutput(width, height, upscale_factor, prescale_factor, batch_size, {'samples': latent}, show_help)


class CR_AspectRatioSocialMedia(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Aspect Ratio Social Media', display_name='🔳 CR Aspect Ratio Social Media', category='🧩 Comfyroll Studio/✨ Essential/🔳 Aspect Ratio', inputs=[io.Int.Input('width', default=1024, min=64, max=8192), io.Int.Input('height', default=1024, min=64, max=8192), io.Combo.Input('aspect_ratio', options=['custom', 'Instagram Portrait - 1080x1350', 'Instagram Square - 1080x1080', 'Instagram Landscape - 1080x608', 'Instagram Stories/Reels - 1080x1920', 'Facebook Landscape - 1080x1350', 'Facebook Marketplace - 1200x1200', 'Facebook Stories - 1080x1920', 'TikTok - 1080x1920', 'YouTube Banner - 2560×1440', 'LinkedIn Profile Banner - 1584x396', 'LinkedIn Page Cover - 1128x191', 'LinkedIn Post - 1200x627', 'Pinterest Pin Image - 1000x1500', 'CivitAI Cover - 1600x400', 'OpenArt App - 1500x1000']), io.Combo.Input('swap_dimensions', options=['Off', 'On']), io.Float.Input('upscale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Float.Input('prescale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Int.Input('batch_size', default=1, min=1, max=64)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.Float.Output(display_name='prescale_factor'), io.Int.Output(display_name='batch_size'), io.Latent.Output(display_name='empty_latent'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, aspect_ratio, swap_dimensions, upscale_factor, prescale_factor, batch_size):
        _preflight(width, height, batch_size, prescale_factor)
        if aspect_ratio == 'Instagram Portrait - 1080x1350':
            width, height = (1080, 1350)
        elif aspect_ratio == 'Instagram Square - 1080x1080':
            width, height = (1080, 1080)
        elif aspect_ratio == 'Instagram Landscape - 1080x608':
            width, height = (1080, 608)
        elif aspect_ratio == 'Instagram Stories/Reels - 1080x1920':
            width, height = (1080, 1920)
        elif aspect_ratio == 'Facebook Landscape - 1080x1350':
            width, height = (1080, 1350)
        elif aspect_ratio == 'Facebook Marketplace - 1200x1200':
            width, height = (1200, 1200)
        elif aspect_ratio == 'Facebook Stories - 1080x1920':
            width, height = (1080, 1920)
        elif aspect_ratio == 'TikTok - 1080x1920':
            width, height = (1080, 1920)
        elif aspect_ratio == 'YouTube Banner - 2560×1440':
            width, height = (2560, 1440)
        elif aspect_ratio == 'LinkedIn Profile Banner - 1584x396':
            width, height = (1584, 396)
        elif aspect_ratio == 'LinkedIn Page Cover - 1128x191':
            width, height = (1584, 396)
        elif aspect_ratio == 'LinkedIn Post - 1200x627':
            width, height = (1200, 627)
        elif aspect_ratio == 'Pinterest Pin Image - 1000x1500':
            width, height = (1000, 1500)
        elif aspect_ratio == 'Pinterest Cover Image - 1920x1080':
            width, height = (1920, 1080)
        elif aspect_ratio == 'CivitAI Cover - 1600x400':
            width, height = (1600, 400)
        elif aspect_ratio == 'OpenArt App - 1500x1000':
            width, height = (1500, 1000)
        if swap_dimensions == 'On':
            width, height = (height, width)
        width = int(width * prescale_factor)
        height = int(height * prescale_factor)
        latent = _bounded_zeros([batch_size, 4, height // 8, width // 8])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Aspect-Ratio-Nodes#cr-aspect-ratio-scial-media'
        return io.NodeOutput(width, height, upscale_factor, prescale_factor, batch_size, {'samples': latent}, show_help)


class CR_AspectRatioForPrint(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR_Aspect Ratio For Print', display_name='🔳 CR_Aspect Ratio For Print', category='🧩 Comfyroll Studio/✨ Essential/🔳 Aspect Ratio', inputs=[io.Int.Input('width', default=1024, min=64, max=8192), io.Int.Input('height', default=1024, min=64, max=8192), io.Combo.Input('aspect_ratio', options=['A4 - 2480x3508', 'A5 - 1748x2480', 'A6 - 1240x1748', 'A7 - 874x1240', 'A8 - 614x874', 'A9 - 437x614', 'A10 - 307x437', 'B4 - 2953x4169', 'B5 - 2079x2953', 'B6 - 1476x2079', 'B7 - 1039x1476', 'B8 - 732x1039', 'B9 - 520x732', 'B10 - 366x520', 'C4 - 2705x3827', 'C5 - 1913x2705', 'C6 - 1346x1913', 'C7 - 957x1346', 'C8 - 673x957', 'C9 - 472x673', 'C10 - 331x472', 'Letter (8.5 x 11 inches) - 2550x3300', 'Legal (8.5 x 14 inches) - 2550x4200']), io.Combo.Input('swap_dimensions', options=['Off', 'On']), io.Float.Input('upscale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Float.Input('prescale_factor', default=1.0, min=0.1, max=100.0, step=0.1), io.Int.Input('batch_size', default=1, min=1, max=64)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.Float.Output(display_name='prescale_factor'), io.Int.Output(display_name='batch_size'), io.Latent.Output(display_name='empty_latent'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, aspect_ratio, swap_dimensions, upscale_factor, prescale_factor, batch_size):
        _preflight(width, height, batch_size, prescale_factor)
        if aspect_ratio in PRINT_SIZES:
            width, height = PRINT_SIZES[aspect_ratio]
        if swap_dimensions == 'On':
            width, height = (height, width)
        width = int(width * prescale_factor)
        height = int(height * prescale_factor)
        print(f'Width: {width}, Height: {height}')
        latent = _bounded_zeros([batch_size, 4, height // 8, width // 8])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Aspect-Ratio-Nodes#cr-aspect-ratio-scial-media'
        return io.NodeOutput(width, height, upscale_factor, prescale_factor, batch_size, {'samples': latent}, show_help)


NODE_CLASS_MAPPINGS = {
    'CR SD1.5 Aspect Ratio': CR_AspectRatioSD15,
    'CR SDXL Aspect Ratio': CR_SDXLAspectRatio,
    'CR Aspect Ratio': CR_AspectRatio,
    'CR Aspect Ratio Banners': CR_AspectRatioBanners,
    'CR Aspect Ratio Social Media': CR_AspectRatioSocialMedia,
    'CR_Aspect Ratio For Print': CR_AspectRatioForPrint,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR SD1.5 Aspect Ratio': '🔳 CR SD1.5 Aspect Ratio', 'CR SDXL Aspect Ratio': '🔳 CR SDXL Aspect Ratio', 'CR Aspect Ratio': '🔳 CR Aspect Ratio', 'CR Aspect Ratio Banners': '🔳 CR Aspect Ratio Banners', 'CR Aspect Ratio Social Media': '🔳 CR Aspect Ratio Social Media', 'CR_Aspect Ratio For Print': '🔳 CR_Aspect Ratio For Print'}
