"""Pinned seeded scalar random math, per-execution RNG, no global continuation mutation."""
import random
import string
import matplotlib.colors as mcolors
from comfy_api.latest import io
from .secure_schedules import _guard, _output

def _preflight(node_id,values):
    _guard(values)
    seed=values['seed']
    if isinstance(seed,(bytes,bytearray)) and len(seed)>262144:
        raise ValueError('Random seed workload exceeds bound')
    rows=values.get('rows',1);length=values.get('string_length',1)
    if isinstance(rows,int) and abs(rows)>2048:raise ValueError('Random rows exceed bound')
    if isinstance(length,int) and abs(length)>1024:raise ValueError('Random string length exceeds bound')
    if not isinstance(rows,int) or not isinstance(length,int):return
    if node_id=='CR Random Multiline Values':
        prefix=values['prepend_text'];custom=values['custom_values']
        max_char=max((len(c.encode('utf-8')) for c in custom),default=1)
        per_row=max(0,length)*max_char+len(prefix.encode('utf-8'))+1
    elif node_id=='CR Random Panel Codes':
        max_char=max((len(c.encode('utf-8')) for c in values['values']),default=1)
        per_row=max(0,length)*max_char+2
    else:per_row=128
    if max(0,rows)*per_row>262144:raise ValueError('Random projected output workload exceeds bound')

def random_hex_color(rng):
    r = rng.randint(0, 255)
    g = rng.randint(0, 255)
    b = rng.randint(0, 255)
    hex_color = '#{:02x}{:02x}{:02x}'.format(r, g, b)
    return hex_color

def random_rgb(rng):
    r = rng.randint(0, 255)
    g = rng.randint(0, 255)
    b = rng.randint(0, 255)
    rgb_string = '{},{},{}'.format(r, g, b)
    return rgb_string

class CR_RandomHexColor(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random Hex Color',display_name='🎲 CR Random Hex Color',category='🧩 Comfyroll Studio/🛠️ Utils/🎲 Random',is_output_node=False,inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615)],outputs=[io.String.Output(display_name='hex_color1'), io.String.Output(display_name='hex_color2'), io.String.Output(display_name='hex_color3'), io.String.Output(display_name='hex_color4'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, seed):
        _preflight('CR Random Hex Color', {'seed': seed})
        rng = random.Random(seed)
        hex_color1 = random_hex_color(rng)
        hex_color2 = random_hex_color(rng)
        hex_color3 = random_hex_color(rng)
        hex_color4 = random_hex_color(rng)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-random-hex-color'
        return _output((hex_color1, hex_color2, hex_color3, hex_color4, show_help))


class CR_RandomRGB(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random RGB',display_name='🎲 CR Random RGB',category='🧩 Comfyroll Studio/🛠️ Utils/🎲 Random',is_output_node=False,inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615)],outputs=[io.String.Output(display_name='rgb_1'), io.String.Output(display_name='rgb_2'), io.String.Output(display_name='rgb_3'), io.String.Output(display_name='rgb_4'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, seed):
        _preflight('CR Random RGB', {'seed': seed})
        rng = random.Random(seed)
        rgb_1 = random_rgb(rng)
        rgb_2 = random_rgb(rng)
        rgb_3 = random_rgb(rng)
        rgb_4 = random_rgb(rng)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-random-rgb'
        return _output((rgb_1, rgb_2, rgb_3, rgb_4, show_help))


class CR_RandomMultilineValues(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random Multiline Values',display_name='🎲 CR Random Multiline Values',category='🧩 Comfyroll Studio/🛠️ Utils/🎲 Random',is_output_node=False,inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615), io.Combo.Input('value_type', options=['binary', 'decimal', 'natural', 'hexadecimal', 'alphabetic', 'alphanumeric', 'custom']), io.Int.Input('rows', default=5, min=1, max=2048), io.Int.Input('string_length', default=5, min=1, max=1024), io.String.Input('custom_values', multiline=False, default='123ABC'), io.String.Input('prepend_text', multiline=False, default='')],outputs=[io.AnyType.Output(display_name='multiline_text'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, value_type, rows, string_length, custom_values, seed, prepend_text):
        _preflight('CR Random Multiline Values', {'value_type': value_type, 'rows': rows, 'string_length': string_length, 'custom_values': custom_values, 'seed': seed, 'prepend_text': prepend_text})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-random-multiline-values'
        rng = random.Random(seed)
        if value_type == 'binary':
            choice_str = '01'
        elif value_type == 'decimal':
            choice_str = '0123456789'
        elif value_type == 'natural':
            choice_str = '123456789'
        elif value_type == 'hexadecimal':
            choice_str = '0123456789ABCDEF'
        elif value_type == 'alphabetic':
            choice_str = string.ascii_letters
        elif value_type == 'alphanumeric':
            choice_str = string.ascii_letters + string.digits
        elif value_type == 'custom':
            choice_str = custom_values
        else:
            pass
        multiline_text = '\n'.join([prepend_text + ''.join((rng.choice(choice_str) for _ in range(string_length))) for _ in range(rows)])
        return _output((multiline_text, show_help))


class CR_RandomMultilineColors(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random Multiline Colors',display_name='🎲 CR Random Multiline Colors',category='🧩 Comfyroll Studio/🛠️ Utils/🎲 Random',is_output_node=False,inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615), io.Combo.Input('value_type', options=['rgb', 'hex color', 'matplotlib xkcd']), io.Int.Input('rows', default=5, min=1, max=2048)],outputs=[io.String.Output(display_name='multiline_text'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, value_type, rows, seed):
        _preflight('CR Random Multiline Colors', {'value_type': value_type, 'rows': rows, 'seed': seed})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-random-multiline-colors'
        rng = random.Random(seed)
        xkcd_colors = mcolors.XKCD_COLORS
        if value_type == 'hex color':
            choice_str = '0123456789ABCDEF'
        if value_type == 'hex color':
            multiline_text = '\n'.join(['#' + ''.join((rng.choice(choice_str) for _ in range(6))) for _ in range(rows)])
        elif value_type == 'rgb':
            multiline_text = '\n'.join([f'{rng.randint(0, 255)},{rng.randint(0, 255)},{rng.randint(0, 255)}' for _ in range(rows)])
        elif value_type == 'matplotlib xkcd':
            multiline_text = '\n'.join([rng.choice(list(xkcd_colors.keys())).replace('xkcd:', '') for _ in range(rows)])
        else:
            pass
        return _output((multiline_text, show_help))


class CR_RandomPanelCodes(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random Panel Codes',display_name='🎲 CR Random Panel Codes',category='🧩 Comfyroll Studio/🛠️ Utils/🎲 Random',is_output_node=False,inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615), io.Int.Input('rows', default=5, min=1, max=2048), io.Int.Input('string_length', default=5, min=1, max=1024), io.String.Input('values', multiline=False, default='123')],outputs=[io.String.Output(display_name='multiline_text'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, rows, string_length, values, seed):
        _preflight('CR Random Panel Codes', {'rows': rows, 'string_length': string_length, 'values': values, 'seed': seed})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-random-panel-codes'
        rng = random.Random(seed)
        start_letter = rng.choice('HV')
        value_range = rng.choice(values)
        codes = []
        for _ in range(rows):
            number = ''.join((rng.choice(values) for _ in range(string_length)))
            codes.append(f'{start_letter}{number}')
        multiline_text = '\n'.join(codes)
        return _output((multiline_text, show_help))


class CR_RandomRGBGradient(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random RGB Gradient',display_name='🎲 CR Random RGB Gradient',category='🧩 Comfyroll Studio/🛠️ Utils/🎲 Random',is_output_node=False,inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615), io.Int.Input('rows', default=5, min=1, max=2048)],outputs=[io.String.Output(display_name='multiline_text'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, rows, seed):
        _preflight('CR Random RGB Gradient', {'rows': rows, 'seed': seed})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-random-RGB-gradient'
        rng = random.Random(seed)
        temp = 0
        multiline_text = ''
        for i in range(1, rows + 1):
            print(temp)
            if temp <= 99 - rows + i:
                upper_bound = min(99, temp + (99 - temp) // (rows - i + 1))
                current_value = rng.randint(temp, upper_bound)
                multiline_text += f'{current_value}:{rng.randint(0, 255)},{rng.randint(0, 255)},{rng.randint(0, 255)}\n'
                temp = current_value + 1
        return _output((multiline_text, show_help))


NODE_CLASS_MAPPINGS={
    'CR Random Hex Color':CR_RandomHexColor,
    'CR Random RGB':CR_RandomRGB,
    'CR Random Multiline Values':CR_RandomMultilineValues,
    'CR Random Multiline Colors':CR_RandomMultilineColors,
    'CR Random Panel Codes':CR_RandomPanelCodes,
    'CR Random RGB Gradient':CR_RandomRGBGradient,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Random Hex Color': '🎲 CR Random Hex Color', 'CR Random RGB': '🎲 CR Random RGB', 'CR Random Multiline Values': '🎲 CR Random Multiline Values', 'CR Random Multiline Colors': '🎲 CR Random Multiline Colors', 'CR Random Panel Codes': '🎲 CR Random Panel Codes', 'CR Random RGB Gradient': '🎲 CR Random RGB Gradient'}

