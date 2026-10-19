from __future__ import annotations
from comfy_api.latest import io, sdk
from .._runtime import run, missing_api
import json
import re


class KeyValue(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__KeyValue_c919e0fa0b21277a9752b072', display_name='Light-Tool: Get values from JSON',
            category='ComfyUI-Light-Tool/DataProcessing', description='Get values from JSON string',
            inputs=[
                io.String.Input('data', default='{"key": "This is value"}', multiline=True),
                io.String.Input('key', default='key', multiline=False),
            ],
            outputs=[io.AnyType.Output(display_name='value', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def key_value(data, key):
        try:
            json_data = json.loads(data)
        except json.JSONDecodeError:
            return ''

        value = json_data
        parts = key.split('.')
        for part in parts:
            key_part = re.match(r'^([^\[]*)', part).group(1)
            indices = re.findall(r'\[(\d+)]', part)

            if key_part:
                if isinstance(value, dict):
                    value = value.get(key_part, '')
                else:
                    return ''
                if value == '':
                    return ''

            for index_str in indices:
                if isinstance(value, list):
                    try:
                        index = int(index_str)
                    except ValueError:
                        return ''
                    if 0 <= index < len(value):
                        value = value[index]
                    else:
                        return ''
                else:
                    return ''
        return (value if value != '' else '',)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().key_value, kwargs, ['*'], [False])


class SerializeJsonObject(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SerializeJsonObject_78aeb9142415cc25ed6d1a22', display_name='Light-Tool: Serialize a JSON object',
            category='ComfyUI-Light-Tool/DataProcessing', description='Convert a JSON object to a JSON string',
            inputs=[
                io.AnyType.Input('json_object', extra_dict={'default': {'key': 'This is value'}}),
            ],
            outputs=[io.AnyType.Output(display_name='json_str', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def get_json_str(json_object):
        try:
            json_str = json.dumps(json_object, ensure_ascii=False)
        except json.JSONDecodeError:
            return '{}'
        return (json_str,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().get_json_str, kwargs, ['*'], [False])


class DeserializeJsonString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__DeserializeJsonString_2544786ec2e4fd296dbe94f5', display_name='Light-Tool: Deserialize a JSON string',
            category='ComfyUI-Light-Tool/DataProcessing', description='Convert a JSON string to a JSON object',
            inputs=[
                io.String.Input('json_str', default='{"key": "This is value"}', multiline=True),
            ],
            outputs=[io.AnyType.Output(display_name='json_object', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def get_json(json_str):
        try:
            json_dict = json.loads(json_str)
            return (json_dict,)
        except json.JSONDecodeError:
            json_dict = {}
        return (json_dict,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().get_json, kwargs, ['*'], [False])


class Calculate(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__Calculate_0b29d0f4ca857f0ccb26c92d', display_name='Light-Tool: Calculate',
            category='ComfyUI-Light-Tool/DataProcessing', description='Simple numerical operations',
            inputs=[
                io.AnyType.Input('number1', extra_dict={'default': '1.0', 'multiline': False}),
                io.AnyType.Input('number2', extra_dict={'default': '1.0', 'multiline': False}),
                io.Combo.Input('operator', options=['+', '-', '*', '/', '%'], default='+'),
                io.String.Input('description', optional=True, default='', multiline=True),
            ],
            outputs=[io.String.Output(display_name='result_string', is_output_list=False), io.Int.Output(display_name='result_int', is_output_list=False), io.Float.Output(display_name='result_float', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def calculate(number1, number2, operator, description):

        def is_number(value):
            try:
                float(value)
                return True
            except ValueError:
                return False

        if not is_number(number1) or not is_number(number2):
            raise ValueError("Inputs 'a' and 'b' must be numbers or numeric strings.")

        number1 = float(number1)
        number2 = float(number2)

        if operator not in ['+', '-', '*', '/', '%']:
            raise ValueError("Unsupported operator. Supported operators are '+', '-', '*', '/', '%'.")

        if operator == '+':
            result = number1 + number2
        elif operator == '-':
            result = number1 - number2
        elif operator == '*':
            result = number1 * number2
        elif operator == '/':
            if number2 == 0:
                raise ZeroDivisionError("Division by zero is not allowed.")
            result = number1 / number2
        elif operator == "%":
            if number2 == 0:
                raise ZeroDivisionError("Modulo by zero is not allowed.")
            result = number1 % number2
        else:
            raise ValueError(f"Unsupported operator {operator}")

        return str(result), round(result), float(result)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().calculate, kwargs, ['STRING', 'INT', 'FLOAT'], [False, False, False])


class ConvertNumType(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ConvertNumType_89c01c038a91cc25aec8403b', display_name='Light-Tool: Convert Num Type',
            category='ComfyUI-Light-Tool/DataProcessing', description='Convert numeric types',
            inputs=[
                io.AnyType.Input('number', extra_dict={'default': '', 'multiline': False}),
                io.Combo.Input('return_type', options=['INT', 'FLOAT', 'STRING'], default='INT'),
            ],
            outputs=[io.AnyType.Output(display_name='number', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def convert(number, return_type):
        if return_type == "FLOAT":
            number = float(number)
        elif return_type == "INT":
            number = round(float(number))
        else:
            number = str(number)
        return (number,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().convert, kwargs, ['*'], [False])
