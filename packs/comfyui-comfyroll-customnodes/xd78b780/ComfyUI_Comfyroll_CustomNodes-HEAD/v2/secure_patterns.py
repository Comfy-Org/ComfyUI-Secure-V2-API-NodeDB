"""Bounded PIL patterns/shapes; stochastic draws are local to this execution."""
import math
import random
import numpy as np
import torch
from PIL import Image, ImageDraw
from comfy_api.latest import io
from .secure_schedules import _guard, _output
from .secure_layout import COLORS, color_mapping, get_color_values, pil2tensor

def _new_rng():
    # No seed input exists upstream. Preserve distributions, not shared process state.
    return random.Random()

def _preflight(node_id, values):
    _guard(values)
    width=values['width'];height=values['height']
    if type(width) is not int or type(height) is not int or abs(width)>4096 or abs(height)>4096:
        raise ValueError('Pattern canvas dimensions exceed bound')
    projected=max(0,width)*max(0,height)*16
    if projected>32*1024*1024 or projected*3>128*1024*1024:
        raise ValueError('Pattern projected output/temporary workload exceeds bound')
    pattern=values.get('binary_pattern')
    if isinstance(pattern,str) and (len(pattern.encode('utf-8'))>16384 or len(pattern)>16384):
        raise ValueError('Pattern parse/draw workload exceeds bound')
    for key in ('num_rows','num_cols'):
        if key in values and (type(values[key]) is not int or abs(values[key])>128):
            raise ValueError('Pattern rows/columns exceed bound')
    if 'num_rows' in values and max(0,values['num_rows'])*max(0,values['num_cols'])>16384:
        raise ValueError('Pattern draw count exceeds bound')
    for key in ('x_offset','y_offset'):
        if key in values and (type(values[key]) is not int or abs(values[key])>2048):
            raise ValueError('Pattern offset exceeds bound')
    for key in ('outline_thickness','jitter_distance'):
        if key in values and (type(values[key]) is not int or abs(values[key])>1024):
            raise ValueError('Pattern line/jitter exceeds bound')
    for key,limit in (('zoom',10),('rotation',36000),('pie_start',36000),('pie_stop',36000),('bias',10)):
        if key in values:
            value=values[key]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>limit:
                raise ValueError('Pattern finite scalar exceeds bound')

def draw_circle(draw, center_x, center_y, size, aspect_ratio, color):
    radius = size / 2
    draw.ellipse([(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)], fill=color)

def draw_oval(draw, center_x, center_y, size, aspect_ratio, color):
    aspect_ratio = aspect_ratio
    draw.ellipse([(center_x - size / 2, center_y - size / 2 / aspect_ratio), (center_x + size / 2, center_y + size / 2 / aspect_ratio)], fill=color)

def draw_diamond(draw, center_x, center_y, size, aspect_ratio, color):
    aspect_ratio = aspect_ratio
    draw.polygon([(center_x, center_y - size / 2 / aspect_ratio), (center_x + size / 2, center_y), (center_x, center_y + size / 2 / aspect_ratio), (center_x - size / 2, center_y)], fill=color)

def draw_square(draw, center_x, center_y, size, aspect_ratio, color):
    draw.rectangle([(center_x - size / 2, center_y - size / 2), (center_x + size / 2, center_y + size / 2)], fill=color)

def draw_triangle(draw, center_x, center_y, size, aspect_ratio, color):
    draw.polygon([(center_x, center_y - size / 2), (center_x + size / 2, center_y + size / 2), (center_x - size / 2, center_y + size / 2)], fill=color)

def draw_hexagon(draw, center_x, center_y, size, aspect_ratio, color):
    hexagon_points = [(center_x - size / 2, center_y), (center_x - size / 4, center_y - size / 2), (center_x + size / 4, center_y - size / 2), (center_x + size / 2, center_y), (center_x + size / 4, center_y + size / 2), (center_x - size / 4, center_y + size / 2)]
    draw.polygon(hexagon_points, fill=color)

def draw_octagon(draw, center_x, center_y, size, aspect_ratio, color):
    octagon_points = [(center_x - size / 2, center_y - size / 4), (center_x - size / 4, center_y - size / 2), (center_x + size / 4, center_y - size / 2), (center_x + size / 2, center_y - size / 4), (center_x + size / 2, center_y + size / 4), (center_x + size / 4, center_y + size / 2), (center_x - size / 4, center_y + size / 2), (center_x - size / 2, center_y + size / 4)]
    draw.polygon(octagon_points, fill=color)

def draw_quarter_circle(draw, center_x, center_y, size, aspect_ratio, color):
    draw.pieslice([(center_x - size / 2, center_y - size / 2), (center_x + size / 2, center_y + size / 2)], start=0, end=90, fill=color)

def draw_half_circle(draw, center_x, center_y, size, aspect_ratio, color):
    draw.pieslice([(center_x - size / 2, center_y - size / 2), (center_x + size / 2, center_y + size / 2)], start=0, end=180, fill=color)

def draw_starburst(draw, center_x, center_y, size, aspect_ratio, color):
    num_rays = 16
    for i in range(num_rays):
        angle_ray = math.radians(i * (360 / num_rays))
        x_end = center_x + size / 2 * math.cos(angle_ray)
        y_end = center_y + size / 2 * math.sin(angle_ray)
        draw.line([(center_x, center_y), (x_end, y_end)], fill=color, width=int(size / 20))

def draw_star(draw, center_x, center_y, size, aspect_ratio, color):
    outer_radius = size / 4
    inner_radius = outer_radius * math.cos(math.radians(36)) / math.cos(math.radians(72))
    angle = -math.pi / 2
    star_points = []
    for _ in range(5):
        x_outer = center_x + outer_radius * math.cos(angle)
        y_outer = center_y + outer_radius * math.sin(angle)
        star_points.extend([x_outer, y_outer])
        angle += math.radians(72)
        x_inner = center_x + inner_radius * math.cos(angle)
        y_inner = center_y + inner_radius * math.sin(angle)
        star_points.extend([x_inner, y_inner])
        angle += math.radians(72)
    draw.polygon(star_points, fill=color)

def draw_cross(draw, center_x, center_y, size, aspect_ratio, color):
    cross_points = [(center_x - size / 6, center_y - size / 2), (center_x + size / 6, center_y - size / 2), (center_x + size / 6, center_y - size / 6), (center_x + size / 2, center_y - size / 6), (center_x + size / 2, center_y + size / 6), (center_x + size / 6, center_y + size / 6), (center_x + size / 6, center_y + size / 2), (center_x - size / 6, center_y + size / 2), (center_x - size / 6, center_y + size / 6), (center_x - size / 2, center_y + size / 6), (center_x - size / 2, center_y - size / 6), (center_x - size / 6, center_y - size / 6)]
    draw.polygon(cross_points, fill=color)

class CR_BinaryPatternSimple(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Binary Pattern',display_name='🟥 CR Simple Binary Pattern',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.String.Input('binary_pattern', multiline=True, default='10101'), io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, binary_pattern, width, height):
        _preflight('CR Simple Binary Pattern', {'binary_pattern': binary_pattern, 'width': width, 'height': height})
        rows = binary_pattern.strip().split('\n')
        grid = [[int(bit) for bit in row.strip()] for row in rows]
        square_width = width // len(rows[0])
        square_height = height // len(rows)
        image = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(image)
        for row_index, row in enumerate(grid):
            for col_index, bit in enumerate(row):
                x1 = col_index * square_width
                y1 = row_index * square_height
                x2 = x1 + square_width
                y2 = y1 + square_height
                color = 'black' if bit == 1 else 'white'
                draw.rectangle([x1, y1, x2, y2], fill=color, outline='black')
        image_out = pil2tensor(image)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes-2#cr-simple-binary-pattern'
        return _output((image_out, show_help))


class CR_BinaryPattern(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Binary Pattern',display_name='🟥 CR Binary Pattern',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',is_output_node=False,inputs=[io.String.Input('binary_pattern', multiline=True, default='10101'), io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('background_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('color_0', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('color_1', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('outline_thickness', default=0, min=0, max=1024), io.Combo.Input('outline_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('jitter_distance', default=0, min=0, max=1024), io.Float.Input('bias', default=0.5, min=0.0, max=1.0, step=0.05), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('color0_hex', multiline=False, default='#000000', optional=True), io.String.Input('color1_hex', multiline=False, default='#000000', optional=True), io.String.Input('outline_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, binary_pattern, width, height, background_color, outline_color, color_0='white', color_1='black', outline_thickness=0, color0_hex='#000000', color1_hex='#000000', bg_color_hex='#000000', outline_color_hex='#000000', jitter_distance=0, bias=0.5):
        _preflight('CR Binary Pattern', {'binary_pattern': binary_pattern, 'width': width, 'height': height, 'background_color': background_color, 'outline_color': outline_color, 'color_0': color_0, 'color_1': color_1, 'outline_thickness': outline_thickness, 'color0_hex': color0_hex, 'color1_hex': color1_hex, 'bg_color_hex': bg_color_hex, 'outline_color_hex': outline_color_hex, 'jitter_distance': jitter_distance, 'bias': bias})
        rng = _new_rng()
        color0 = get_color_values(color_0, color0_hex, color_mapping)
        color1 = get_color_values(color_1, color1_hex, color_mapping)
        bg_color = get_color_values(background_color, bg_color_hex, color_mapping)
        outline_color = get_color_values(outline_color, outline_color_hex, color_mapping)
        rows = binary_pattern.strip().split('\n')
        grid = [[int(bit) for bit in row.strip()] for row in rows]
        square_width = width / len(rows[0])
        square_height = height / len(rows)
        image = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(image)
        x_jitter = 0
        y_jitter = 0
        for row_index, row in enumerate(grid):
            for col_index, bit in enumerate(row):
                if jitter_distance != 0:
                    x_jitter = rng.uniform(0, jitter_distance)
                    y_jitter = rng.uniform(0, jitter_distance)
                x1 = col_index * square_width + x_jitter
                y1 = row_index * square_height + y_jitter
                x2 = x1 + square_width + x_jitter
                y2 = y1 + square_height + y_jitter
                if rng.uniform(0, 1) < abs(bias):
                    color = color1
                else:
                    color = color0
                draw.rectangle([x1, y1, x2, y2], fill=color, outline=outline_color, width=outline_thickness)
        image_out = pil2tensor(image)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes-2#cr-binary-pattern'
        return _output((image_out, show_help))


class CR_DrawShape(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Draw Shape',display_name='🟡 CR Draw Shape',category='🧩 Comfyroll Studio/👾 Graphics/🟣 Shape',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Combo.Input('shape', options=['circle', 'oval', 'square', 'diamond', 'triangle', 'hexagon', 'octagon', 'quarter circle', 'half circle', 'quarter circle', 'starburst', 'star', 'cross', 'diagonal regions']), io.Combo.Input('shape_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('back_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('x_offset', default=0, min=-2048, max=2048), io.Int.Input('y_offset', default=0, min=-2048, max=2048), io.Float.Input('zoom', default=1.0, min=0.0, max=10.0, step=0.05), io.Float.Input('rotation', default=0.0, min=0.0, max=3600.0, step=0.1), io.String.Input('shape_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, rotation, shape, shape_color, back_color, x_offset=0, y_offset=0, zoom=1.0, shape_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Draw Shape', {'width': width, 'height': height, 'rotation': rotation, 'shape': shape, 'shape_color': shape_color, 'back_color': back_color, 'x_offset': x_offset, 'y_offset': y_offset, 'zoom': zoom, 'shape_color_hex': shape_color_hex, 'bg_color_hex': bg_color_hex})
        bg_color = get_color_values(back_color, bg_color_hex, color_mapping)
        shape_color = get_color_values(shape_color, shape_color_hex, color_mapping)
        back_img = Image.new('RGB', (width, height), color=bg_color)
        shape_img = Image.new('RGB', (width, height), color=shape_color)
        shape_mask = Image.new('L', (width, height))
        draw = ImageDraw.Draw(shape_mask)
        center_x = width // 2 + x_offset
        center_y = height // 2 + y_offset
        size = min(width - x_offset, height - y_offset) * zoom
        aspect_ratio = width / height
        color = 'white'
        shape_functions = {'circle': draw_circle, 'oval': draw_oval, 'diamond': draw_diamond, 'square': draw_square, 'triangle': draw_triangle, 'hexagon': draw_hexagon, 'octagon': draw_octagon, 'quarter circle': draw_quarter_circle, 'half circle': draw_half_circle, 'starburst': draw_starburst, 'star': draw_star, 'cross': draw_cross}
        if shape in shape_functions:
            shape_function = shape_functions.get(shape)
            shape_function(draw, center_x, center_y, size, aspect_ratio, color)
        if shape == 'diagonal regions':
            draw.polygon([(width, 0), (width, height), (0, height)], fill=color)
        shape_mask = shape_mask.rotate(rotation, center=(center_x, center_y))
        result_image = Image.composite(shape_img, back_img, shape_mask)
        image_out = pil2tensor(result_image)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes-2#cr-draw-shape'
        return _output((image_out, show_help))


class CR_DrawPie(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Draw Pie',display_name='🟢 CR Draw Pie',category='🧩 Comfyroll Studio/👾 Graphics/🟣 Shape',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Float.Input('pie_start', default=30.0, min=0.0, max=9999.0, step=0.1), io.Float.Input('pie_stop', default=330.0, min=0.0, max=9999.0, step=0.1), io.Combo.Input('shape_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('back_color', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Int.Input('x_offset', default=0, min=-2048, max=2048), io.Int.Input('y_offset', default=0, min=-2048, max=2048), io.Float.Input('zoom', default=1.0, min=0.0, max=10.0, step=0.05), io.Float.Input('rotation', default=0.0, min=0.0, max=3600.0, step=0.1), io.String.Input('shape_color_hex', multiline=False, default='#000000', optional=True), io.String.Input('bg_color_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, width, height, rotation, pie_start, pie_stop, shape_color, back_color, x_offset=0, y_offset=0, zoom=1.0, shape_color_hex='#000000', bg_color_hex='#000000'):
        _preflight('CR Draw Pie', {'width': width, 'height': height, 'rotation': rotation, 'pie_start': pie_start, 'pie_stop': pie_stop, 'shape_color': shape_color, 'back_color': back_color, 'x_offset': x_offset, 'y_offset': y_offset, 'zoom': zoom, 'shape_color_hex': shape_color_hex, 'bg_color_hex': bg_color_hex})
        bg_color = get_color_values(back_color, bg_color_hex, color_mapping)
        shape_color = get_color_values(shape_color, shape_color_hex, color_mapping)
        back_img = Image.new('RGB', (width, height), color=bg_color)
        shape_img = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(shape_img, 'RGBA')
        center_x = width // 2 + x_offset
        center_y = height // 2 + y_offset
        size = min(width - x_offset, height - y_offset) * zoom
        aspect_ratio = width / height
        num_rays = 16
        color = 'white'
        draw.pieslice([(center_x - size / 2, center_y - size / 2), (center_x + size / 2, center_y + size / 2)], start=pie_start, end=pie_stop, fill=color, outline=None)
        shape_img = shape_img.rotate(rotation, center=(center_x, center_y))
        result_image = Image.alpha_composite(back_img.convert('RGBA'), shape_img)
        image_out = pil2tensor(result_image.convert('RGB'))
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes-2#cr-draw-pie'
        return _output((image_out, show_help))


class CR_RandomShapePattern(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random Shape Pattern',display_name='🔵 CR Random Shape Pattern',category='🧩 Comfyroll Studio/👾 Graphics/🟣 Shape',is_output_node=False,inputs=[io.Int.Input('width', default=512, min=64, max=4096), io.Int.Input('height', default=512, min=64, max=4096), io.Int.Input('num_rows', default=5, min=1, max=128), io.Int.Input('num_cols', default=5, min=1, max=128), io.Combo.Input('color1', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.Combo.Input('color2', options=['custom', 'white', 'black', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'pink', 'brown', 'gray', 'lightgray', 'darkgray', 'olive', 'lime', 'teal', 'navy', 'maroon', 'fuchsia', 'aqua', 'silver', 'gold', 'turquoise', 'lavender', 'violet', 'coral', 'indigo']), io.String.Input('color1_hex', multiline=False, default='#000000', optional=True), io.String.Input('color2_hex', multiline=False, default='#000000', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, num_rows, num_cols, width, height, color1, color2, color1_hex='#000000', color2_hex='#000000'):
        _preflight('CR Random Shape Pattern', {'num_rows': num_rows, 'num_cols': num_cols, 'width': width, 'height': height, 'color1': color1, 'color2': color2, 'color1_hex': color1_hex, 'color2_hex': color2_hex})
        rng = _new_rng()
        color1 = get_color_values(color1, color1_hex, color_mapping)
        color2 = get_color_values(color2, color2_hex, color_mapping)
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        shape_functions = [draw_circle, draw_oval, draw_diamond, draw_square, draw_triangle, draw_hexagon, draw_octagon, draw_half_circle, draw_quarter_circle, draw_starburst, draw_star, draw_cross]
        for row in range(num_rows):
            for col in range(num_cols):
                shape_function = rng.choice(shape_functions)
                color = rng.choice([color1, color2])
                size = rng.uniform(20, min(width, height) / 2)
                aspect_ratio = rng.uniform(0.5, 2.0)
                center_x = col * (width / num_cols) + width / num_cols / 2
                center_y = row * (height / num_rows) + height / num_rows / 2
                shape_function(draw, center_x, center_y, size, aspect_ratio, color)
        image_out = pil2tensor(image)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes-2#cr-random-shape-pattern'
        return _output((image_out, show_help))


NODE_CLASS_MAPPINGS={
    'CR Simple Binary Pattern':CR_BinaryPatternSimple,
    'CR Binary Pattern':CR_BinaryPattern,
    'CR Draw Shape':CR_DrawShape,
    'CR Draw Pie':CR_DrawPie,
    'CR Random Shape Pattern':CR_RandomShapePattern,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Simple Binary Pattern': '🟥 CR Simple Binary Pattern', 'CR Binary Pattern': '🟥 CR Binary Pattern', 'CR Draw Shape': '🟡 CR Draw Shape', 'CR Draw Pie': '🟢 CR Draw Pie', 'CR Random Shape Pattern': '🔵 CR Random Shape Pattern'}
