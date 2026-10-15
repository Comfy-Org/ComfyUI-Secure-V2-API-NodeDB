"""Bounded pack-side lists; exact source iteration/rounding/list axes retained."""
import math
from itertools import product
import numpy as np
from comfy_api.latest import io
from .secure_schedules import _guard, _output

def _preflight(values):
    _guard(values)
    repeats=values.get('repeats',1);loops=values.get('loops',1)
    if type(repeats) is not int or type(loops) is not int or abs(repeats)>16384 or abs(loops)>16384:
        raise ValueError('List repetition count exceeds bound')
    length=1;byte_count=0
    for key in ('text','values','input_data'):
        if key in values:
            item=values[key]
            length=len(item) if isinstance(item,list) else item.count('\n')+1 if isinstance(item,str) and key!='input_data' else 1
            if isinstance(item,str):byte_count=len(item.encode('utf-8'))
    if length*max(0,repeats)*max(0,loops)>16384 or byte_count*max(0,repeats)*max(0,loops)>262144:
        raise ValueError('List projected repeat allocation exceeds bound')
    if 'text_x' in values:
        x=values['text_x'].strip().split('\n');y=values['text_y'].strip().split('\n')
        if len(x)*len(y)>16384 or sum(len(v.encode('utf-8')) for v in x)*len(y)+sum(len(v.encode('utf-8')) for v in y)*len(x)>262144:
            raise ValueError('List projected Cartesian allocation exceeds bound')
    if 'start' in values and 'end' in values and 'step' in values:
        start,end,step=values['start'],values['end'],values['step']
        if step!=0:
            projected=abs((end-start)/step)+2
            if not math.isfinite(projected) or projected>16384 or projected*max(0,loops)>16384:
                raise ValueError('List projected range allocation exceeds bound')
    if 'prepend_text' in values:
        lines=values['multiline_text'].split('\n')
        overhead=len(values['prepend_text'].encode('utf-8'))+len(values['append_text'].encode('utf-8'))
        if len(values['multiline_text'].encode('utf-8'))+len(lines)*overhead>262144:
            raise ValueError('List projected prompt allocation exceeds bound')
    if 'bit_string' in values and len(values['bit_string'])>16384:
        raise ValueError('List projected bit allocation exceeds bound')

class CR_TextList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text List', display_name='📜 CR Text List', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.String.Input('multiline_text', multiline=True, default='text'), io.Int.Input('start_index', default=0, min=0, max=9999), io.Int.Input('max_rows', default=1000, min=1, max=9999)], outputs=[io.String.Output(display_name='STRING', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, multiline_text, start_index, max_rows, loops=1):
        _preflight({'multiline_text': multiline_text, 'start_index': start_index, 'max_rows': max_rows, 'loops': loops})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-text-list'
        lines = multiline_text.split('\n')
        start_index = max(0, min(start_index, len(lines) - 1))
        end_index = min(start_index + max_rows, len(lines))
        selected_rows = lines[start_index:end_index]
        return _output((selected_rows, show_help))


class CR_PromptList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Prompt List', display_name='📜 CR Prompt List', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.String.Input('prepend_text', multiline=False, default=''), io.String.Input('multiline_text', multiline=True, default='body_text'), io.String.Input('append_text', multiline=False, default=''), io.Int.Input('start_index', default=0, min=0, max=9999), io.Int.Input('max_rows', default=1000, min=1, max=9999)], outputs=[io.String.Output(display_name='prompt', is_output_list=True), io.String.Output(display_name='body_text', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, multiline_text, prepend_text='', append_text='', start_index=0, max_rows=9999):
        _preflight({'multiline_text': multiline_text, 'prepend_text': prepend_text, 'append_text': append_text, 'start_index': start_index, 'max_rows': max_rows})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-prompt-list'
        lines = multiline_text.split('\n')
        start_index = max(0, min(start_index, len(lines) - 1))
        end_index = min(start_index + max_rows, len(lines))
        selected_rows = lines[start_index:end_index]
        prompt_list_out = [prepend_text + line + append_text for line in selected_rows]
        body_list_out = selected_rows
        return _output((prompt_list_out, body_list_out, show_help))


class CR_FloatRangeList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Float Range List', display_name='📜 CR Float Range List', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.Float.Input('start', default=0.0, min=-99999.99, max=99999.99, step=0.01), io.Float.Input('end', default=1.0, min=-99999.99, max=99999.99, step=0.01), io.Float.Input('step', default=1.0, min=-99999.99, max=99999.99, step=0.01), io.Combo.Input('operation', options=['none', 'sin', 'cos', 'tan']), io.Int.Input('decimal_places', default=2, min=0, max=10), io.Boolean.Input('ignore_first_value', default=True), io.Int.Input('max_values_per_loop', default=128, min=1, max=99999), io.Int.Input('loops', default=1, min=1, max=999), io.Boolean.Input('ping_pong', default=False)], outputs=[io.Float.Output(display_name='FLOAT', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, start, end, step, max_values_per_loop, operation, decimal_places, ignore_first_value, loops, ping_pong):
        _preflight({'start': start, 'end': end, 'step': step, 'max_values_per_loop': max_values_per_loop, 'operation': operation, 'decimal_places': decimal_places, 'ignore_first_value': ignore_first_value, 'loops': loops, 'ping_pong': ping_pong})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-float-range-list'
        range_values = list()
        for i in range(loops):
            if end < start and step > 0:
                step = -step
            current_range = list(np.arange(start, end + step, step))
            if operation == 'sin':
                current_range = [math.sin(value) for value in current_range]
            elif operation == 'cos':
                current_range = [math.cos(value) for value in current_range]
            elif operation == 'tan':
                current_range = [math.tan(value) for value in current_range]
            current_range = [round(value, decimal_places) for value in current_range]
            if ping_pong:
                if i % 2 == 1:
                    if ignore_first_value:
                        current_range = current_range[:-1]
                    current_range = current_range[:max_values_per_loop]
                    range_values += reversed(current_range)
                else:
                    if ignore_first_value:
                        current_range = current_range[1:]
                    current_range = current_range[:max_values_per_loop]
                    range_values += current_range
            else:
                if ignore_first_value:
                    current_range = current_range[1:]
                current_range = current_range[:max_values_per_loop]
                range_values += current_range
        return _output((range_values, show_help))


class CR_IntegerRangeList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Integer Range List', display_name='📜 CR Integer Range List', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.Int.Input('start', default=0, min=-99999, max=99999), io.Int.Input('end', default=0, min=-99999, max=99999), io.Int.Input('step', default=1, min=1, max=99999), io.Int.Input('loops', default=1, min=1, max=999), io.Boolean.Input('ping_pong', default=False)], outputs=[io.Int.Output(display_name='INT', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, start, end, step, loops, ping_pong):
        _preflight({'start': start, 'end': end, 'step': step, 'loops': loops, 'ping_pong': ping_pong})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-list-schedule'
        range_values = list()
        for i in range(loops):
            current_range = list(range(start, end, step))
            if ping_pong:
                if i % 2 == 1:
                    range_values += reversed(current_range)
                else:
                    range_values += current_range
            else:
                range_values += current_range
        return _output((range_values, show_help))


class CR_IntertwineLists(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Intertwine Lists', display_name='🛠️ CR Intertwine Lists', category='🧩 Comfyroll Studio/✨ Essential/📜 List/🛠️ Utils', is_input_list=False, inputs=[io.String.Input('list1', multiline=True, default='', force_input=True), io.String.Input('list2', multiline=True, default='', force_input=True)], outputs=[io.String.Output(display_name='STRING', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, list1, list2):
        _preflight({'list1': list1, 'list2': list2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-intertwine-lists'
        min_length = min(len(list1), len(list2))
        combined_list = []
        combined_element = str(list1) + ', ' + str(list2)
        combined_list.append(combined_element)
        return _output((combined_list, show_help))


class CR_BinaryToBitList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Binary To Bit List', display_name='📜 CR Binary To Bit List', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.String.Input('bit_string', multiline=True, default='')], outputs=[io.String.Output(display_name='STRING', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, bit_string):
        _preflight({'bit_string': bit_string})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-binary-to-list'
        list_out = [str(bit) for bit in bit_string]
        return _output((list_out, show_help))


class CR_TextListToString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text List To String', display_name='🛠️ CR Text List To String', category='🧩 Comfyroll Studio/✨ Essential/📜 List/🛠️ Utils', is_input_list=True, inputs=[io.String.Input('text_list', force_input=True)], outputs=[io.String.Output(display_name='STRING', is_output_list=False), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, text_list):
        _preflight({'text_list': text_list})
        string_out = '\n'.join(text_list)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text-list-to-string'
        return _output((string_out, show_help))


class CR_SimpleList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple List', display_name='📜 CR Simple List', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.String.Input('list_values', multiline=True, default='text')], outputs=[io.AnyType.Output(display_name='LIST', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, list_values):
        _preflight({'list_values': list_values})
        lines = list_values.split('\n')
        list_out = [i.strip() for i in lines if i.strip()]
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-simple-list'
        return _output((list_out, show_help))


class CR_XYProduct(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR XY Product', display_name='🛠️ CR XY Product', category='🧩 Comfyroll Studio/✨ Essential/📜 List/🛠️ Utils', is_input_list=False, inputs=[io.String.Input('text_x', multiline=True), io.String.Input('text_y', multiline=True)], outputs=[io.AnyType.Output(display_name='x_values', is_output_list=True), io.AnyType.Output(display_name='y_values', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, text_x, text_y):
        _preflight({'text_x': text_x, 'text_y': text_y})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-xy-product'
        list1 = text_x.strip().split('\n')
        list2 = text_y.strip().split('\n')
        cartesian_product = list(product(list1, list2))
        x_values, y_values = zip(*cartesian_product)
        return _output((list(x_values), list(y_values), show_help))


class CR_Repeater(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Repeater', display_name='🛠️ CR Repeater', category='🧩 Comfyroll Studio/✨ Essential/📜 List/🛠️ Utils', is_input_list=False, inputs=[io.AnyType.Input('input_data'), io.Int.Input('repeats', default=1, min=1, max=99999)], outputs=[io.AnyType.Output(display_name='list', is_output_list=True), io.String.Output(display_name='show_help', is_output_list=False)])

    @classmethod
    def execute(cls, input_data, repeats):
        _preflight({'input_data': input_data, 'repeats': repeats})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-repeater'
        new_list = []
        if isinstance(input_data, list):
            new_list = []
            for item in input_data:
                new_list.extend([item] * repeats)
            return _output((new_list, show_help))
        else:
            return _output(([input_data] * repeats, show_help))


class CR_TextCycler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Cycler', display_name='📜 CR Text Cycler', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.String.Input('text', multiline=True, default=''), io.Int.Input('repeats', default=1, min=1, max=99999), io.Int.Input('loops', default=1, min=1, max=99999)], outputs=[io.AnyType.Output(display_name='STRING', is_output_list=True), io.String.Output(display_name='show_text', is_output_list=False)])

    @classmethod
    def execute(cls, text, repeats, loops=1):
        _preflight({'text': text, 'repeats': repeats, 'loops': loops})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text-cycler'
        lines = text.split('\n')
        list_out = []
        for i in range(loops):
            for text_item in lines:
                for _ in range(repeats):
                    list_out.append(text_item)
        return _output((list_out, show_help))


class CR_ValueCycler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Value Cycler', display_name='📜 CR Value Cycler', category='🧩 Comfyroll Studio/✨ Essential/📜 List', is_input_list=False, inputs=[io.String.Input('values', multiline=True, default=''), io.Int.Input('repeats', default=1, min=1, max=99999), io.Int.Input('loops', default=1, min=1, max=99999)], outputs=[io.Float.Output(display_name='FLOAT', is_output_list=True), io.Int.Output(display_name='INT', is_output_list=True), io.String.Output(display_name='show_text', is_output_list=False)])

    @classmethod
    def execute(cls, values, repeats, loops=1):
        _preflight({'values': values, 'repeats': repeats, 'loops': loops})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-value-cycler'
        lines = values.split('\n')
        float_list_out = []
        int_list_out = []
        for i in range(loops):
            for _ in range(repeats):
                for text_item in lines:
                    if all((char.isdigit() or char == '.' for char in text_item.strip())):
                        float_list_out.append(float(text_item))
                        int_list_out.append(int(float(text_item)))
        return _output((float_list_out, int_list_out, show_help))


NODE_CLASS_MAPPINGS = {
    'CR Text List': CR_TextList,
    'CR Prompt List': CR_PromptList,
    'CR Float Range List': CR_FloatRangeList,
    'CR Integer Range List': CR_IntegerRangeList,
    'CR Intertwine Lists': CR_IntertwineLists,
    'CR Binary To Bit List': CR_BinaryToBitList,
    'CR Text List To String': CR_TextListToString,
    'CR Simple List': CR_SimpleList,
    'CR XY Product': CR_XYProduct,
    'CR Repeater': CR_Repeater,
    'CR Text Cycler': CR_TextCycler,
    'CR Value Cycler': CR_ValueCycler,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Text List': '📜 CR Text List', 'CR Prompt List': '📜 CR Prompt List', 'CR Float Range List': '📜 CR Float Range List', 'CR Integer Range List': '📜 CR Integer Range List', 'CR Intertwine Lists': '🛠️ CR Intertwine Lists', 'CR Binary To Bit List': '📜 CR Binary To Bit List', 'CR Text List To String': '🛠️ CR Text List To String', 'CR Simple List': '📜 CR Simple List', 'CR XY Product': '🛠️ CR XY Product', 'CR Repeater': '🛠️ CR Repeater', 'CR Text Cycler': '📜 CR Text Cycler', 'CR Value Cycler': '📜 CR Value Cycler'}
