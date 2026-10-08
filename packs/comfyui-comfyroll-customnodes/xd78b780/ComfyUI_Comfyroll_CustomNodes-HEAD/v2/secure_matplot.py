"""Pinned bounded CPU rendering; no installation, host routes or filesystem images."""
import io as buffers
import threading
import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
from comfy_api.latest import io
from .secure_schedules import _guard, _output

_render_lock=threading.RLock()

def _preflight(node_id,values):
    _guard(values)
    width=values['width'];height=values['height']
    if type(width) is not int or type(height) is not int or abs(width)>4096 or abs(height)>4096:
        raise ValueError('Matplotlib canvas axes exceed bound')
    pixels=max(0,width)*max(0,height)
    # Includes renderer canvas, PNG conversion and Torch output, not just RGB bytes.
    if pixels*24>32*1024*1024 or pixels*96>128*1024*1024:
        raise ValueError('Matplotlib projected output/temporary workload exceeds bound')
    for key,value in values.items():
        if isinstance(value,str) and len(value.encode('utf-8'))>256:
            raise ValueError('Matplotlib color/style text exceeds bound')
    bounds={'dot_frequency':200,'bar_frequency':200,'grid_frequency':200,'step':200,
            'rows':512,'columns':512,'num_lines':500,'num_triangles':512,
            'line_width':512,'line_length':100,'center_x':4096,'center_y':4096,
            'rotation':36000,'offset':20,'gradient_distance':2,'linear_transition':1,
            'radial_center_x':1,'radial_center_y':1,'x_pos':1,'y_pos':1,'bbox_factor':2}
    for key,limit in bounds.items():
        if key in values and (type(values[key]) not in (int,float) or abs(values[key])>limit):
            raise ValueError('Matplotlib '+key+' exceeds bound')
    if node_id=='CR Polygons' and max(0,values['rows']+2)*max(0,values['columns']+2)>4096:
        raise ValueError('Matplotlib projected polygon count exceeds bound')

color_mapping={'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'yellow': (255, 255, 0), 'cyan': (0, 255, 255), 'magenta': (255, 0, 255), 'orange': (255, 165, 0), 'purple': (128, 0, 128), 'pink': (255, 192, 203), 'brown': (165, 42, 42), 'gray': (128, 128, 128), 'lightgray': (211, 211, 211), 'darkgray': (169, 169, 169), 'olive': (128, 128, 0), 'lime': (0, 128, 0), 'teal': (0, 128, 128), 'navy': (0, 0, 128), 'maroon': (128, 0, 0), 'fuchsia': (255, 0, 128), 'aqua': (0, 255, 128), 'silver': (192, 192, 192), 'gold': (255, 215, 0), 'turquoise': (64, 224, 208), 'lavender': (230, 230, 250), 'violet': (238, 130, 238), 'coral': (255, 127, 80), 'indigo': (75, 0, 130)}
COLORS=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']
STYLES=['Accent', 'afmhot', 'autumn', 'binary', 'Blues', 'bone', 'BrBG', 'brg', 'BuGn', 'BuPu', 'bwr', 'cividis', 'CMRmap', 'cool', 'coolwarm', 'copper', 'cubehelix', 'Dark2', 'flag', 'gist_earth', 'gist_gray', 'gist_heat', 'gist_rainbow', 'gist_stern', 'gist_yarg', 'GnBu', 'gnuplot', 'gnuplot2', 'gray', 'Greens', 'Greys', 'hot', 'hsv', 'inferno', 'jet', 'magma', 'nipy_spectral', 'ocean', 'Oranges', 'OrRd', 'Paired', 'Pastel1', 'Pastel2', 'pink', 'PiYG', 'plasma', 'PRGn', 'prism', 'PuBu', 'PuBuGn', 'PuOr', 'PuRd', 'Purples', 'rainbow', 'RdBu', 'RdGy', 'RdPu', 'RdYlBu', 'RdYlGn', 'Reds', 'seismic', 'Set1', 'Set2', 'Set3', 'Spectral', 'spring', 'summer', 'tab10', 'tab20', 'tab20b', 'tab20c', 'terrain', 'turbo', 'twilight', 'twilight_shifted', 'viridis', 'winter', 'Wistia', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd']

def rgb_to_hex(rgb):
    r, g, b = rgb
    return '#{:02X}{:02X}{:02X}'.format(r, g, b)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)

def tensor2pil(image):
    return Image.fromarray(np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

class CR_HalftoneGrid(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Halftone Grid',display_name='🟫 CR Halftone Grid',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('dot_style', options=['Accent', 'afmhot', 'autumn', 'binary', 'Blues', 'bone', 'BrBG', 'brg', 'BuGn', 'BuPu', 'bwr', 'cividis', 'CMRmap', 'cool', 'coolwarm', 'copper', 'cubehelix', 'Dark2', 'flag', 'gist_earth', 'gist_gray', 'gist_heat', 'gist_rainbow', 'gist_stern', 'gist_yarg', 'GnBu', 'gnuplot', 'gnuplot2', 'gray', 'Greens', 'Greys', 'hot', 'hsv', 'inferno', 'jet', 'magma', 'nipy_spectral', 'ocean', 'Oranges', 'OrRd', 'Paired', 'Pastel1', 'Pastel2', 'pink', 'PiYG', 'plasma', 'PRGn', 'prism', 'PuBu', 'PuBuGn', 'PuOr', 'PuRd', 'Purples', 'rainbow', 'RdBu', 'RdGy', 'RdPu', 'RdYlBu', 'RdYlGn', 'Reds', 'seismic', 'Set1', 'Set2', 'Set3', 'Spectral', 'spring', 'summer', 'tab10', 'tab20', 'tab20b', 'tab20c', 'terrain', 'turbo', 'twilight', 'twilight_shifted', 'viridis', 'winter', 'Wistia', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd']), io.Combo.Input('reverse_dot_style', options=['No', 'Yes']), io.Int.Input('dot_frequency', default=50, min=1, max=200, step=1), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Float.Input('x_pos', default=0.5, min=0, max=1, step=0.01), io.Float.Input('y_pos', default=0.5, min=0, max=1, step=0.01), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, dot_style, reverse_dot_style, dot_frequency, background_color, x_pos, y_pos, bg_color_hex='#000000'):
        _preflight('CR Halftone Grid', {'width': width, 'height': height, 'dot_style': dot_style, 'reverse_dot_style': reverse_dot_style, 'dot_frequency': dot_frequency, 'background_color': background_color, 'x_pos': x_pos, 'y_pos': y_pos, 'bg_color_hex': bg_color_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if background_color == 'custom':
                    bgc = bg_color_hex
                else:
                    bgc = background_color
                reverse = ''
                if reverse_dot_style == 'Yes':
                    reverse = '_r'
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                dotsx = np.linspace(0, 1, dot_frequency)
                dotsy = np.linspace(0, 1, dot_frequency)
                X, Y = np.meshgrid(dotsx, dotsy)
                dist = np.sqrt((X - x_pos) ** 2 + (Y - y_pos) ** 2)
                fig.patch.set_facecolor(bgc)
                ax.scatter(X, Y, c=dist, cmap=dot_style + reverse)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(tight=True)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-halftone-grid'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_ColorBars(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Color Bars',display_name='🟫 CR Color Bars',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Combo.Input('mode', options=['2-color']), io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('color_1', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('color_2', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('orientation', options=['vertical', 'horizontal', 'diagonal', 'alt_diagonal']), io.Int.Input('bar_frequency', default=5, min=1, max=200, step=1), io.Float.Input('offset', default=0, min=0, max=20, step=0.05), io.String.Input('color1_hex', multiline=False, default='#000000', optional=True), io.String.Input('color2_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, width, height, color_1, color_2, orientation, bar_frequency, offset=0, color1_hex='#000000', color2_hex='#000000'):
        _preflight('CR Color Bars', {'mode': mode, 'width': width, 'height': height, 'color_1': color_1, 'color_2': color_2, 'orientation': orientation, 'bar_frequency': bar_frequency, 'offset': offset, 'color1_hex': color1_hex, 'color2_hex': color2_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if color_1 == 'custom':
                    color1_rgb = hex_to_rgb(color1_hex)
                else:
                    color1_rgb = color_mapping.get(color_1, (255, 255, 255))
                if color_2 == 'custom':
                    color2_rgb = hex_to_rgb(color2_hex)
                else:
                    color2_rgb = color_mapping.get(color_2, (0, 0, 0))
                canvas = np.zeros((height, width, 3), dtype=np.uint8)
                bar_width = width / bar_frequency
                bar_height = height / bar_frequency
                offset_pixels = int(offset * max(width, height))
                if orientation == 'vertical':
                    for j in range(height):
                        for i in range(width):
                            if (i + offset_pixels) // bar_width % 2 == 0:
                                canvas[j, i] = color1_rgb
                            else:
                                canvas[j, i] = color2_rgb
                elif orientation == 'horizontal':
                    for j in range(height):
                        for i in range(width):
                            if (j + offset_pixels) // bar_height % 2 == 0:
                                canvas[j, i] = color1_rgb
                            else:
                                canvas[j, i] = color2_rgb
                elif orientation == 'diagonal':
                    bar_width = int(bar_height / np.tan(np.pi / 4)) * 2
                    for j in range(height):
                        for i in range(width):
                            bar_number = (i + j + offset_pixels) // bar_width
                            if bar_number % 2 == 0:
                                canvas[j, i] = color1_rgb
                            else:
                                canvas[j, i] = color2_rgb
                elif orientation == 'alt_diagonal':
                    bar_width = int(bar_height / np.tan(np.pi / 4)) * 2
                    for j in range(height):
                        for i in range(width):
                            bar_number = (i - j + width + offset_pixels) // bar_width
                            if bar_number % 2 == 0:
                                canvas[j, i] = color1_rgb
                            else:
                                canvas[j, i] = color2_rgb
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                ax.imshow(canvas)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(tight=True)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-color-bars'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_ColorGradient(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Color Gradient',display_name='🟨 CR Color Gradient',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('start_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('end_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Float.Input('gradient_distance', default=1, min=0, max=2, step=0.05), io.Float.Input('linear_transition', default=0.5, min=0, max=1, step=0.05), io.Combo.Input('orientation', options=['vertical', 'horizontal']), io.String.Input('start_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('end_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, start_color, end_color, orientation, linear_transition=0.5, gradient_distance=1, start_color_hex='#000000', end_color_hex='#000000'):
        _preflight('CR Color Gradient', {'width': width, 'height': height, 'start_color': start_color, 'end_color': end_color, 'orientation': orientation, 'linear_transition': linear_transition, 'gradient_distance': gradient_distance, 'start_color_hex': start_color_hex, 'end_color_hex': end_color_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if start_color == 'custom':
                    color1_rgb = hex_to_rgb(start_color_hex)
                else:
                    color1_rgb = color_mapping.get(start_color, (255, 255, 255))
                if end_color == 'custom':
                    color2_rgb = hex_to_rgb(end_color_hex)
                else:
                    color2_rgb = color_mapping.get(end_color, (0, 0, 0))
                canvas = np.zeros((height, width, 3), dtype=np.uint8)
                transition_pixel = int(linear_transition * (width if orientation == 'horizontal' else height))
    
                def get_gradient_value(pos, length, linear_transition, gradient_distance):
                    transition_length = length * gradient_distance
                    transition_start = linear_transition * length - transition_length / 2
                    transition_end = linear_transition * length + transition_length / 2
                    if pos < transition_start:
                        return _output(0)
                    elif pos > transition_end:
                        return _output(1)
                    else:
                        return _output((pos - transition_start) / transition_length)
                if orientation == 'horizontal':
                    x = [0, width * linear_transition - 0.5 * width * gradient_distance, width * linear_transition + 0.5 * width * gradient_distance, width]
                    y = [0, 0, 1, 1]
                    t_values = np.interp(np.arange(width), x, y)
                    for i, t in enumerate(t_values):
                        interpolated_color = [int(c1 * (1 - t) + c2 * t) for c1, c2 in zip(color1_rgb, color2_rgb)]
                        canvas[:, i] = interpolated_color
                elif orientation == 'vertical':
                    x = [0, height * linear_transition - 0.5 * height * gradient_distance, height * linear_transition + 0.5 * height * gradient_distance, height]
                    y = [0, 0, 1, 1]
                    t_values = np.interp(np.arange(height), x, y)
                    for j, t in enumerate(t_values):
                        interpolated_color = [int(c1 * (1 - t) + c2 * t) for c1, c2 in zip(color1_rgb, color2_rgb)]
                        canvas[j, :] = interpolated_color
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                ax.imshow(canvas)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(tight=True)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-color-gradient'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_RadialGradient(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Radial Gradient',display_name='🟨 CR Radial Gradient',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('start_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('end_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Float.Input('gradient_distance', default=1, min=0, max=2, step=0.05), io.Float.Input('radial_center_x', default=0.5, min=0, max=1, step=0.05), io.Float.Input('radial_center_y', default=0.5, min=0, max=1, step=0.05), io.String.Input('start_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('end_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_Help')])

    @classmethod
    def execute(cls, width, height, start_color, end_color, radial_center_x=0.5, radial_center_y=0.5, gradient_distance=1, start_color_hex='#000000', end_color_hex='#000000'):
        _preflight('CR Radial Gradient', {'width': width, 'height': height, 'start_color': start_color, 'end_color': end_color, 'radial_center_x': radial_center_x, 'radial_center_y': radial_center_y, 'gradient_distance': gradient_distance, 'start_color_hex': start_color_hex, 'end_color_hex': end_color_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if start_color == 'custom':
                    color1_rgb = hex_to_rgb(start_color_hex)
                else:
                    color1_rgb = color_mapping.get(start_color, (255, 255, 255))
                if end_color == 'custom':
                    color2_rgb = hex_to_rgb(end_color_hex)
                else:
                    color2_rgb = color_mapping.get(end_color, (0, 0, 0))
                canvas = np.zeros((height, width, 3), dtype=np.uint8)
                center_x = int(radial_center_x * width)
                center_y = int(radial_center_y * height)
                max_distance = np.sqrt(max(center_x, width - center_x) ** 2 + max(center_y, height - center_y) ** 2) * gradient_distance
                for i in range(width):
                    for j in range(height):
                        distance_to_center = np.sqrt((i - center_x) ** 2 + (j - center_y) ** 2)
                        t = distance_to_center / max_distance
                        t = max(0, min(t, 1))
                        interpolated_color = [int(c1 * (1 - t) + c2 * t) for c1, c2 in zip(color1_rgb, color2_rgb)]
                        canvas[j, i] = interpolated_color
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                ax.imshow(canvas)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(tight=True)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-radial-gradiant'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_CheckerPattern(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Checker Pattern',display_name='🟦 CR Checker Pattern',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Combo.Input('mode', options=['regular', 'stepped']), io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('color_1', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('color_2', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('grid_frequency', default=8, min=1, max=200, step=1), io.Int.Input('step', default=2, min=2, max=200, step=1), io.String.Input('color1_hex', multiline=False, default='#000000', optional=True), io.String.Input('color2_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, width, height, color_1, color_2, grid_frequency, step, color1_hex='#000000', color2_hex='#000000'):
        _preflight('CR Checker Pattern', {'mode': mode, 'width': width, 'height': height, 'color_1': color_1, 'color_2': color_2, 'grid_frequency': grid_frequency, 'step': step, 'color1_hex': color1_hex, 'color2_hex': color2_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if color_1 == 'custom':
                    color1_rgb = hex_to_rgb(color1_hex)
                else:
                    color1_rgb = color_mapping.get(color_1, (255, 255, 255))
                if color_2 == 'custom':
                    color2_rgb = hex_to_rgb(color2_hex)
                else:
                    color2_rgb = color_mapping.get(color_2, (0, 0, 0))
                canvas = np.zeros((height, width, 3), dtype=np.uint8)
                grid_size = width / grid_frequency
                for i in range(width):
                    for j in range(height):
                        if mode == 'regular':
                            if i // grid_size % 2 == j // grid_size % 2:
                                canvas[j, i] = color1_rgb
                            else:
                                canvas[j, i] = color2_rgb
                        elif mode == 'stepped':
                            if i // grid_size % step != j // grid_size % step:
                                canvas[j, i] = color1_rgb
                            else:
                                canvas[j, i] = color2_rgb
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                ax.imshow(canvas)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(tight=True)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-checker-pattern'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_Polygons(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Polygons',display_name='🟩 CR Polygons',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Combo.Input('mode', options=['hexagons', 'triangles']), io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Int.Input('rows', default=5, min=1, max=512), io.Int.Input('columns', default=5, min=1, max=512), io.Combo.Input('face_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('line_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('line_width', default=2, min=0, max=512), io.String.Input('face_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('line_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, width, height, rows, columns, face_color, background_color, line_color, line_width, face_color_hex='#000000', bg_color_hex='#000000', line_color_hex='#000000'):
        _preflight('CR Polygons', {'mode': mode, 'width': width, 'height': height, 'rows': rows, 'columns': columns, 'face_color': face_color, 'background_color': background_color, 'line_color': line_color, 'line_width': line_width, 'face_color_hex': face_color_hex, 'bg_color_hex': bg_color_hex, 'line_color_hex': line_color_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if face_color == 'custom':
                    face_color = face_color_hex
                if line_color == 'custom':
                    line_color = line_color_hex
                if background_color == 'custom':
                    background_color = bg_color_hex
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                fig.set_facecolor(background_color)
                plt.xlim(0, width / 100)
                plt.ylim(0, height / 100)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(False)
                if mode == 'hexagons':
                    vertices = 6
                elif mode == 'triangles':
                    vertices = 3
                cell_width = width / 100 / columns
                cell_height = width / height * np.sqrt(3) * (height / 100) / (2 * columns)
                for row in range(rows + 2):
                    for col in range(columns + 2):
                        x = col * cell_width
                        y = row * cell_height
                        if row % 2 == 1:
                            x += cell_width / 2
                        hexagon = RegularPolygon((x, y), numVertices=vertices, radius=cell_width / 1.732, edgecolor=line_color, linewidth=line_width, facecolor=face_color)
                        ax.add_patch(hexagon)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-polygons'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_StarburstLines(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Starburst Lines',display_name='🟧 CR Starburst Lines',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Int.Input('num_lines', default=6, min=1, max=500), io.Float.Input('line_length', default=5, min=0, max=100, step=0.1), io.Int.Input('line_width', default=5, min=1, max=512), io.Combo.Input('line_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('center_x', default=0, min=0, max=1024), io.Int.Input('center_y', default=0, min=0, max=1024), io.Float.Input('rotation', default=0, min=0, max=720), io.String.Input('line_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, num_lines, line_length, line_width, line_color, background_color, center_x, center_y, rotation=0, line_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Starburst Lines', {'width': width, 'height': height, 'num_lines': num_lines, 'line_length': line_length, 'line_width': line_width, 'line_color': line_color, 'background_color': background_color, 'center_x': center_x, 'center_y': center_y, 'rotation': rotation, 'line_color_hex': line_color_hex, 'bg_color_hex': bg_color_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if line_color == 'custom':
                    line_color = line_color_hex
                else:
                    line_color = line_color
                if background_color == 'custom':
                    bgc = bg_color_hex
                else:
                    bgc = background_color
                angle = 360 / num_lines
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                plt.xlim(-width / 100, width / 100)
                plt.ylim(-height / 100, height / 100)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(False)
                center_x = center_x / 100
                center_y = center_y / 100
                for i in range(num_lines):
                    x_unrotated = center_x + line_length * np.cos(np.radians(i * angle))
                    y_unrotated = center_y + line_length * np.sin(np.radians(i * angle))
                    x = center_x + x_unrotated * np.cos(np.radians(rotation)) - y_unrotated * np.sin(np.radians(rotation))
                    y = center_y + x_unrotated * np.sin(np.radians(rotation)) + y_unrotated * np.cos(np.radians(rotation))
                    fig.patch.set_facecolor(bgc)
                    ax.plot([center_x, x], [center_y, y], color=line_color, linewidth=line_width)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-starburst-lines'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


class CR_StarburstColors(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Starburst Colors',display_name='🟧 CR Starburst Colors',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Int.Input('num_triangles', default=6, min=1, max=512), io.Combo.Input('color_1', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('color_2', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('center_x', default=0, min=0, max=512), io.Int.Input('center_y', default=0, min=0, max=512), io.Float.Input('rotation', default=0, min=0, max=720), io.Float.Input('bbox_factor', default=2, min=0, max=2, step=0.01), io.String.Input('color1_hex', multiline=False, default='#000000', optional=True), io.String.Input('color2_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, num_triangles, color_1, color_2, center_x, center_y, bbox_factor, rotation=0, color1_hex='#000000', color2_hex='#000000'):
        _preflight('CR Starburst Colors', {'width': width, 'height': height, 'num_triangles': num_triangles, 'color_1': color_1, 'color_2': color_2, 'center_x': center_x, 'center_y': center_y, 'bbox_factor': bbox_factor, 'rotation': rotation, 'color1_hex': color1_hex, 'color2_hex': color2_hex})
        with _render_lock:
            before = set(plt.get_fignums())
            try:
                if color_1 == 'custom':
                    color_1 = color1_hex
                else:
                    color_1 = color_1
                if color_2 == 'custom':
                    color_2 = color2_hex
                else:
                    color_2 = color_2
                fig, ax = plt.subplots()
                x = width / 100
                y = height / 100
                fig, ax = plt.subplots(figsize=(x, y))
                plt.xlim(-x / 2, x / 2)
                plt.ylim(-y / 2, y / 2)
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(False)
                box_width = bbox_factor * x
                box_height = bbox_factor * y
                colors = [color_1, color_2]
                tri = num_triangles
                for i in range(tri):
                    x1 = center_x / 100
                    y1 = center_y / 100
                    x2_unrotated = box_width / 2 * np.cos(np.radians(i * 360 / tri))
                    y2_unrotated = box_height / 2 * np.sin(np.radians(i * 360 / tri))
                    x3_unrotated = box_width / 2 * np.cos(np.radians((i + 1) * 360 / tri))
                    y3_unrotated = box_height / 2 * np.sin(np.radians((i + 1) * 360 / tri))
                    x2 = x2_unrotated * np.cos(np.radians(rotation)) - y2_unrotated * np.sin(np.radians(rotation))
                    y2 = x2_unrotated * np.sin(np.radians(rotation)) + y2_unrotated * np.cos(np.radians(rotation))
                    x3 = x3_unrotated * np.cos(np.radians(rotation)) - y3_unrotated * np.sin(np.radians(rotation))
                    y3 = x3_unrotated * np.sin(np.radians(rotation)) + y3_unrotated * np.cos(np.radians(rotation))
                    ax.fill([x1, x2, x3, x1], [y1, y2, y3, y1], color=colors[i % 2])
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-starburst-colors'
                return _output((image_out, show_help))
            finally:
                for figure in set(plt.get_fignums()) - before:
                    plt.close(figure)


NODE_CLASS_MAPPINGS={
    'CR Halftone Grid':CR_HalftoneGrid,
    'CR Color Bars':CR_ColorBars,
    'CR Color Gradient':CR_ColorGradient,
    'CR Radial Gradient':CR_RadialGradient,
    'CR Checker Pattern':CR_CheckerPattern,
    'CR Polygons':CR_Polygons,
    'CR Starburst Lines':CR_StarburstLines,
    'CR Starburst Colors':CR_StarburstColors,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Halftone Grid': '🟫 CR Halftone Grid', 'CR Color Bars': '🟫 CR Color Bars', 'CR Color Gradient': '🟨 CR Color Gradient', 'CR Radial Gradient': '🟨 CR Radial Gradient', 'CR Checker Pattern': '🟦 CR Checker Pattern', 'CR Polygons': '🟩 CR Polygons', 'CR Starburst Lines': '🟧 CR Starburst Lines', 'CR Starburst Colors': '🟧 CR Starburst Colors'}

