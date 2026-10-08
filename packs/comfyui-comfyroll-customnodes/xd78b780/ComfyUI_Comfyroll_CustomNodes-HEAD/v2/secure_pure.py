"""Comfyroll pack-side pure draft; full 199-node release remains pending."""
import csv
import io as stdlib_io
import math
from comfy_api.latest import io

def _guard(values):
    for value in values.values():
        if isinstance(value,str) and len(value.encode('utf-8')) > 262144:
            raise ValueError('Comfyroll text input exceeds 256KiB')
        if type(value) is int and value.bit_length() > 4096:
            raise ValueError('Comfyroll scalar exceeds 4096 bits')
    if 'blacklist_words' in values:
        lines=values['blacklist_words'].count('\n')+1
        if lines > 4096 or lines * len(values['text']) > 16777216:
            raise ValueError('Comfyroll blacklist exceeds bounded parse workload')

def _bounded_replace(value, old, new, count=-1):
    matches=value.count(old) if count < 0 else min(value.count(old),count)
    if len(value.encode('utf-8')) + matches * max(0,len(new.encode('utf-8'))-len(old.encode('utf-8'))) > 262144:
        raise ValueError('Comfyroll replacement exceeds 256KiB output')
    return value.replace(old,new,count)

def _output(value):
    if isinstance(value,tuple):
        _guard({str(i):v for i,v in enumerate(value)})
        return io.NodeOutput(*value)
    # Retain native invalid-input outcomes (e.g. {} / invalid-operation string).
    # These are not promises of a valid V3 output contract.
    return value

class CR_SplitString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Split String', display_name='🔤 CR Split String', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='text'), io.String.Input('delimiter', optional=True, multiline=False, default=',')], outputs=[io.AnyType.Output(display_name='string_1'), io.AnyType.Output(display_name='string_2'), io.AnyType.Output(display_name='string_3'), io.AnyType.Output(display_name='string_4'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, delimiter=''):
        _guard({'text': text, 'delimiter': delimiter})
        parts = text.split(delimiter)
        strings = [part.strip() for part in parts[:4]]
        string_1, string_2, string_3, string_4 = strings + [''] * (4 - len(strings))
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-split-string'
        return _output((string_1, string_2, string_3, string_4, show_help))


class CR_Text(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text', display_name='🔤 CR Text', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', default='', multiline=True)], outputs=[io.AnyType.Output(display_name='text'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text):
        _guard({'text': text})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-text'
        return _output((text, show_help))


class CR_MultilineText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Multiline Text', display_name='🔤 CR Multiline Text', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', default='', multiline=True), io.Boolean.Input('convert_from_csv', default=False), io.String.Input('csv_quote_char', default="'", extra_dict={'choices': ["'", '"']}), io.Boolean.Input('remove_chars', default=False), io.String.Input('chars_to_remove', multiline=False, default=''), io.Boolean.Input('split_string', default=False)], outputs=[io.AnyType.Output(display_name='multiline_text'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, chars_to_remove, split_string=False, remove_chars=False, convert_from_csv=False, csv_quote_char="'"):
        _guard({'text': text, 'chars_to_remove': chars_to_remove, 'split_string': split_string, 'remove_chars': remove_chars, 'convert_from_csv': convert_from_csv, 'csv_quote_char': csv_quote_char})
        new_text = []
        text = text.rstrip(',')
        if convert_from_csv:
            csv_reader = csv.reader(stdlib_io.StringIO(text), quotechar=csv_quote_char)
            for row in csv_reader:
                new_text.extend(row)
        if split_string:
            if text.startswith("'") and text.endswith("'"):
                text = text[1:-1]
                values = [value.strip() for value in text.split("', '")]
                new_text.extend(values)
            elif text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
                values = [value.strip() for value in text.split('", "')]
                new_text.extend(values)
            elif ',' in text and text.count("'") % 2 == 0:
                text = _bounded_replace(text, "'", '')
                values = [value.strip() for value in text.split(',')]
                new_text.extend(values)
            elif ',' in text and text.count('"') % 2 == 0:
                text = _bounded_replace(text, '"', '')
                values = [value.strip() for value in text.split(',')]
                new_text.extend(values)
        if convert_from_csv == False and split_string == False:
            for line in stdlib_io.StringIO(text):
                if not line.strip().startswith('#'):
                    if not line.strip().startswith('\n'):
                        line = _bounded_replace(line, '\n', '')
                    if remove_chars:
                        line = _bounded_replace(line, chars_to_remove, '')
                    new_text.append(line)
        new_text = '\n'.join(new_text)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-multiline-text'
        return _output((new_text, show_help))


class CR_TextConcatenate(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Concatenate', display_name='🔤 CR Text Concatenate', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text1', optional=True, multiline=False, default='', force_input=True), io.String.Input('text2', optional=True, multiline=False, default='', force_input=True), io.String.Input('separator', optional=True, multiline=False, default='')], outputs=[io.AnyType.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text1='', text2='', separator=''):
        _guard({'text1': text1, 'text2': text2, 'separator': separator})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-save-text-to-file'
        return _output((text1 + separator + text2, show_help))


class CR_TextReplace(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Replace', display_name='🔤 CR Text Replace', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', multiline=True, default='', force_input=True), io.String.Input('find1', optional=True, multiline=False, default=''), io.String.Input('replace1', optional=True, multiline=False, default=''), io.String.Input('find2', optional=True, multiline=False, default=''), io.String.Input('replace2', optional=True, multiline=False, default=''), io.String.Input('find3', optional=True, multiline=False, default=''), io.String.Input('replace3', optional=True, multiline=False, default='')], outputs=[io.AnyType.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, find1='', replace1='', find2='', replace2='', find3='', replace3=''):
        _guard({'text': text, 'find1': find1, 'replace1': replace1, 'find2': find2, 'replace2': replace2, 'find3': find3, 'replace3': replace3})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text-replace'
        text = _bounded_replace(text, find1, replace1)
        text = _bounded_replace(text, find2, replace2)
        text = _bounded_replace(text, find3, replace3)
        return _output((text, show_help))


class CR_TextBlacklist(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Blacklist', display_name='🔤 Text Blacklist', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', multiline=True, default='', force_input=True), io.String.Input('blacklist_words', multiline=True, default=''), io.String.Input('replacement_text', optional=True, multiline=False, default='')], outputs=[io.AnyType.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, blacklist_words, replacement_text=''):
        _guard({'text': text, 'blacklist_words': blacklist_words, 'replacement_text': replacement_text})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text-blacklist'
        text_out = text
        remaining_work = 16777216
        for line in blacklist_words.split('\n'):
            if line.strip():
                remaining_work -= len(text_out)
                if remaining_work < 0:
                    raise ValueError('Comfyroll blacklist exceeds bounded replacement workload')
                text_out = _bounded_replace(text_out, line.strip(), replacement_text)
        return _output((text_out, show_help))


class CR_TextOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Operation', display_name='🔤 CR Text Operation', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='', force_input=True), io.Combo.Input('operation', options=['uppercase', 'lowercase', 'capitalize', 'invert_case', 'reverse', 'trim', 'remove_spaces'])], outputs=[io.AnyType.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, operation):
        _guard({'text': text, 'operation': operation})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text_operation'
        if operation == 'uppercase':
            text_out = text.upper()
        elif operation == 'lowercase':
            text_out = text.lower()
        elif operation == 'capitalize':
            text_out = text.capitalize()
        elif operation == 'invert_case':
            text_out = text.swapcase()
        elif operation == 'reverse':
            text_out = text[::-1]
        elif operation == 'trim':
            text_out = text.strip()
        elif operation == 'remove_spaces':
            text_out = _bounded_replace(text, ' ', '')
        else:
            return _output('CR Text Operation: Invalid operation.')
        return _output((text_out, show_help))


class CR_TextLength(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Length', display_name='🔤 CR Text Length', category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='', force_input=True)], outputs=[io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text):
        _guard({'text': text})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text-length'
        int_out = len(text)
        return _output((int_out, show_help))


class CR_StringToNumber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR String To Number', display_name='🔧 CR String To Number', category='🧩 Comfyroll Studio/🛠️ Utils/🔧 Conversion', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='text', force_input=True), io.Combo.Input('round_integer', options=['round', 'round down', 'round up'])], outputs=[io.Int.Output(display_name='INT'), io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, round_integer):
        _guard({'text': text, 'round_integer': round_integer})
        if text.startswith('-') and _bounded_replace(text[1:], '.', '', 1).isdigit():
            float_out = -float(text[1:])
        elif _bounded_replace(text, '.', '', 1).isdigit():
            float_out = float(text)
        else:
            print(f'[Error] CR String To Number. Not a number.')
            return _output({})
        if round_integer == 'round up':
            if text.startswith('-'):
                int_out = int(float_out)
            else:
                int_out = int(float_out) + 1
        elif round_integer == 'round down':
            if text.startswith('-'):
                int_out = int(float_out) - 1
            else:
                int_out = int(float_out)
        else:
            int_out = round(float_out)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Conversion-Nodes#cr-string-to-number'
        return _output((int_out, float_out, show_help))


class CR_StringToCombo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR String To Combo', display_name='🔧 CR String To Combo', category='🧩 Comfyroll Studio/🛠️ Utils/🔧 Conversion', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='', force_input=True)], outputs=[io.AnyType.Output(display_name='any'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text):
        _guard({'text': text})
        text_list = list()
        if text != '':
            values = text.split(',')
            text_list = values[0]
            print(text_list)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Conversion-Nodes#cr-string-to-combo'
        return _output((text_list, show_help))


class CR_StringToBoolean(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR String To Boolean', display_name='🔧 CR String To Boolean', category='🧩 Comfyroll Studio/🛠️ Utils/🔧 Conversion', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='', force_input=True)], outputs=[io.Boolean.Output(display_name='BOOLEAN'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text):
        _guard({'text': text})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Conversion-Nodes#cr-string-to-boolean'
        if text == 'True' or text == 'true':
            boolean_out = True
        if text == 'False' or text == 'false':
            boolean_out = False
        else:
            pass
        return _output((boolean_out, show_help))


class CR_IntegerToString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Integer To String', display_name='🔧 CR Integer To String', category='🧩 Comfyroll Studio/🛠️ Utils/🔧 Conversion', is_output_node=False, inputs=[io.Int.Input('int_', default=0, min=0, max=18446744073709551615, force_input=True)], outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, int_):
        _guard({'int_': int_})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Conversion-Nodes#cr-integer-to-string'
        return _output((f'{int_}', show_help))


class CR_FloatToString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Float To String', display_name='🔧 CR Float To String', category='🧩 Comfyroll Studio/🛠️ Utils/🔧 Conversion', is_output_node=False, inputs=[io.Float.Input('float_', default=0.0, min=0.0, max=1000000.0, force_input=True)], outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, float_):
        _guard({'float_': float_})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Conversion-Nodes#cr-float-to-string'
        return _output((f'{float_}', show_help))


class CR_FloatToInteger(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Float To Integer', display_name='🔧 CR Float To Integer', category='🧩 Comfyroll Studio/🛠️ Utils/🔧 Conversion', is_output_node=False, inputs=[io.Float.Input('_float', default=0.0, force_input=True)], outputs=[io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, _float):
        _guard({'_float': _float})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Conversion-Nodes#cr-float-to-integer'
        return _output((int(_float), show_help))


class CR_ImageInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Input Switch', display_name='🔀 CR Image Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Image.Input('image1', optional=True), io.Image.Input('image2', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, image1=None, image2=None):
        _guard({'Input': Input, 'image1': image1, 'image2': image2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-image-input-switch'
        if Input == 1:
            return _output((image1, show_help))
        else:
            return _output((image2, show_help))


class CR_LatentInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Latent Input Switch', display_name='🔀 CR Latent Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Latent.Input('latent1', optional=True), io.Latent.Input('latent2', optional=True)], outputs=[io.Latent.Output(display_name='LATENT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, latent1=None, latent2=None):
        _guard({'Input': Input, 'latent1': latent1, 'latent2': latent2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-latent-input-switch'
        if Input == 1:
            return _output((latent1, show_help))
        else:
            return _output((latent2, show_help))


class CR_ConditioningInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Conditioning Input Switch', display_name='🔀 CR Conditioning Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Conditioning.Input('conditioning1', optional=True), io.Conditioning.Input('conditioning2', optional=True)], outputs=[io.Conditioning.Output(display_name='CONDITIONING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, conditioning1=None, conditioning2=None):
        _guard({'Input': Input, 'conditioning1': conditioning1, 'conditioning2': conditioning2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-conditioning-input-switch'
        if Input == 1:
            return _output((conditioning1, show_help))
        else:
            return _output((conditioning2, show_help))


class CR_ClipInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Clip Input Switch', display_name='🔀 CR Clip Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Clip.Input('clip1', optional=True), io.Clip.Input('clip2', optional=True)], outputs=[io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, clip1=None, clip2=None):
        _guard({'Input': Input, 'clip1': clip1, 'clip2': clip2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-clip-input-switch'
        if Input == 1:
            return _output((clip1, show_help))
        else:
            return _output((clip2, show_help))


class CR_ModelInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Model Input Switch', display_name='🔀 CR Model Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Model.Input('model1', optional=True), io.Model.Input('model2', optional=True)], outputs=[io.Model.Output(display_name='MODEL'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, model1=None, model2=None):
        _guard({'Input': Input, 'model1': model1, 'model2': model2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-model-input-switch'
        if Input == 1:
            return _output((model1, show_help))
        else:
            return _output((model2, show_help))


class CR_TextInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Input Switch', display_name='🔀 CR Text Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.String.Input('text1', optional=True, force_input=True), io.String.Input('text2', optional=True, force_input=True)], outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, text1=None, text2=None):
        _guard({'Input': Input, 'text1': text1, 'text2': text2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-text-input-switch'
        if Input == 1:
            return _output((text1, show_help))
        else:
            return _output((text2, show_help))


class CR_VAEInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR VAE Input Switch', display_name='🔀 CR VAE Input Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Vae.Input('VAE1', optional=True, extra_dict={'forceInput': True}), io.Vae.Input('VAE2', optional=True, extra_dict={'forceInput': True})], outputs=[io.Vae.Output(display_name='VAE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, VAE1=None, VAE2=None):
        _guard({'Input': Input, 'VAE1': VAE1, 'VAE2': VAE2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-vae-input-switch'
        if Input == 1:
            return _output((VAE1, show_help))
        else:
            return _output((VAE2, show_help))


class CR_ImageInputSwitch4way(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Input Switch (4 way)', display_name='🔀 CR Image Input Switch (4 way)', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=4), io.Image.Input('image1', optional=True), io.Image.Input('image2', optional=True), io.Image.Input('image3', optional=True), io.Image.Input('image4', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, image1=None, image2=None, image3=None, image4=None):
        _guard({'Input': Input, 'image1': image1, 'image2': image2, 'image3': image3, 'image4': image4})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-text-input-switch-4-way'
        if Input == 1:
            return _output((image1, show_help))
        elif Input == 2:
            return _output((image2, show_help))
        elif Input == 3:
            return _output((image3, show_help))
        else:
            return _output((image4, show_help))


class CR_TextInputSwitch4way(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Input Switch (4 way)', display_name='🔀 CR Text Input Switch (4 way)', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=4), io.String.Input('text1', optional=True, force_input=True), io.String.Input('text2', optional=True, force_input=True), io.String.Input('text3', optional=True, force_input=True), io.String.Input('text4', optional=True, force_input=True)], outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, text1=None, text2=None, text3=None, text4=None):
        _guard({'Input': Input, 'text1': text1, 'text2': text2, 'text3': text3, 'text4': text4})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-text-input-switch-4-way'
        if Input == 1:
            return _output((text1, show_help))
        elif Input == 2:
            return _output((text2, show_help))
        elif Input == 3:
            return _output((text3, show_help))
        else:
            return _output((text4, show_help))


class CR_ModelAndCLIPInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Switch Model and CLIP', display_name='🔀 CR Switch Model and CLIP', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Logic', is_output_node=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Model.Input('model1'), io.Clip.Input('clip1'), io.Model.Input('model2'), io.Clip.Input('clip2')], outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, clip1, clip2, model1, model2):
        _guard({'Input': Input, 'clip1': clip1, 'clip2': clip2, 'model1': model1, 'model2': model2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-switch-model-and-clip'
        if Input == 1:
            return _output((model1, clip1, show_help))
        else:
            return _output((model2, clip2, show_help))


class CR_Img2ImgProcessSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Img2Img Process Switch', display_name='🔂 CR Img2Img Process Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔂 Process', is_output_node=False, inputs=[io.Combo.Input('Input', options=['txt2img', 'img2img']), io.Latent.Input('txt2img', optional=True), io.Latent.Input('img2img', optional=True)], outputs=[io.Latent.Output(display_name='LATENT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, txt2img=None, img2img=None):
        _guard({'Input': Input, 'txt2img': txt2img, 'img2img': img2img})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Process-Nodes#cr-img2img-process-switch'
        if Input == 'txt2img':
            return _output((txt2img, show_help))
        else:
            return _output((img2img, show_help))


class CR_HiResFixProcessSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Hires Fix Process Switch', display_name='🔂 CR Hires Fix Process Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔂 Process', is_output_node=False, inputs=[io.Combo.Input('Input', options=['latent_upscale', 'image_upscale']), io.Latent.Input('latent_upscale', optional=True), io.Latent.Input('image_upscale', optional=True)], outputs=[io.Latent.Output(display_name='LATENT'), io.String.Output(display_name='STRING')])

    @classmethod
    def execute(cls, Input, latent_upscale=None, image_upscale=None):
        _guard({'Input': Input, 'latent_upscale': latent_upscale, 'image_upscale': image_upscale})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Process-Nodes#cr-hires-fix-process-switch'
        if Input == 'latent_upscale':
            return _output((latent_upscale, show_help))
        else:
            return _output((image_upscale, show_help))


class CR_BatchProcessSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Batch Process Switch', display_name='🔂 CR Batch Process Switch', category='🧩 Comfyroll Studio/🛠️ Utils/🔂 Process', is_output_node=False, inputs=[io.Combo.Input('Input', options=['image', 'image batch']), io.Image.Input('image', optional=True), io.Image.Input('image_batch', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, image=None, image_batch=None):
        _guard({'Input': Input, 'image': image, 'image_batch': image_batch})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Process-Nodes#cr-batch-process-switch'
        if Input == 'image':
            return _output((image, show_help))
        else:
            return _output((image_batch, show_help))


class CR_Trigger(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Trigger', display_name='🔢 CR Trigger', category='🧩 Comfyroll Studio/🛠️ Utils/🔢 Index', is_output_node=False, inputs=[io.Int.Input('index', default=0.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('trigger_value', default=1, min=0, max=10000)], outputs=[io.Int.Output(display_name='index'), io.Boolean.Output(display_name='trigger'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, index, trigger_value):
        _guard({'index': index, 'trigger_value': trigger_value})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Index-Nodes#cr-trigger'
        return _output((index, index == trigger_value, show_help))


class CR_Index(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Index', display_name='🔢 CR Index', category='🧩 Comfyroll Studio/🛠️ Utils/🔢 Index', is_output_node=False, inputs=[io.Int.Input('index', default=1, min=0, max=10000), io.Combo.Input('print_to_console', options=['Yes', 'No'])], outputs=[io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, index, print_to_console):
        _guard({'index': index, 'print_to_console': print_to_console})
        if print_to_console == 'Yes':
            print(f'[Info] CR Index:{index}')
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Index-Nodes#cr-index'
        return _output((index, show_help))


class CR_IncrementIndex(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Index Increment', display_name='🔢 CR Index Increment', category='🧩 Comfyroll Studio/🛠️ Utils/🔢 Index', is_output_node=False, inputs=[io.Int.Input('index', default=1, min=-10000, max=10000, force_input=True), io.Int.Input('interval', default=1, min=-10000, max=10000)], outputs=[io.Int.Output(display_name='index'), io.Int.Output(display_name='interval'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, index, interval):
        _guard({'index': index, 'interval': interval})
        index += interval
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Index-Nodes#cr-index-increment'
        return _output((index, interval, show_help))


class CR_MultiplyIndex(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Index Multiply', display_name='🔢 CR Index Multiply', category='🧩 Comfyroll Studio/🛠️ Utils/🔢 Index', is_output_node=False, inputs=[io.Int.Input('index', default=1, min=0, max=10000, force_input=True), io.Int.Input('factor', default=1, min=0, max=10000)], outputs=[io.Int.Output(display_name='index'), io.Int.Output(display_name='factor'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, index, factor):
        _guard({'index': index, 'factor': factor})
        index = index * factor
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Index-Nodes#cr-index-multiply'
        return _output((index, factor, show_help))


class CR_IndexReset(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Index Reset', display_name='🔢 CR Index Reset', category='🧩 Comfyroll Studio/🛠️ Utils/🔢 Index', is_output_node=False, inputs=[io.Int.Input('index', default=1, min=0, max=10000, force_input=True), io.Int.Input('reset_to', default=1, min=0, max=10000)], outputs=[io.Int.Output(display_name='index'), io.Int.Output(display_name='reset_to'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, index, reset_to):
        _guard({'index': index, 'reset_to': reset_to})
        index = reset_to
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Index-Nodes#cr-index-reset'
        return _output((index, reset_to, show_help))


class CR_ClampValue(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Clamp Value', display_name='⚙️ CR Clamp Value', category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other', is_output_node=False, inputs=[io.Float.Input('a', default=1, min=-18446744073709551615, max=18446744073709551615), io.Float.Input('range_min', default=1, min=-18446744073709551615, max=18446744073709551615), io.Float.Input('range_max', default=1, min=-18446744073709551615, max=18446744073709551615)], outputs=[io.Float.Output(display_name='a'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, a, range_min, range_max):
        _guard({'a': a, 'range_min': range_min, 'range_max': range_max})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-clamp-value'
        a = max(range_min, min(a, range_max))
        return _output((a, show_help))


class CR_IntegerMultipleOf(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Integer Multiple', display_name='⚙️ CR Integer Multiple', category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other', is_output_node=False, inputs=[io.Int.Input('integer', default=1, min=-18446744073709551615, max=18446744073709551615), io.Float.Input('multiple', default=8, min=1, max=18446744073709551615)], outputs=[io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, integer, multiple=8):
        _guard({'integer': integer, 'multiple': multiple})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-integer-multiple'
        if multiple == 0:
            return _output((int(integer), show_help))
        integer = integer * multiple
        return _output((int(integer), show_help))


class CR_Value(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Value', display_name='⚙️ CR Value', category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other', is_output_node=False, inputs=[io.Float.Input('value', default=1.0)], outputs=[io.Float.Output(display_name='FLOAT'), io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, value):
        _guard({'value': value})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-value'
        return _output((float(value), int(value), show_help))


class CR_MathOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Math Operation', display_name='⚙️ CR Math Operation', category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other', is_output_node=False, inputs=[io.Float.Input('a', default=1.0), io.Combo.Input('operation', options=['sin', 'cos', 'tan', 'sqrt', 'exp', 'log', 'neg', 'abs']), io.Int.Input('decimal_places', default=2, min=0, max=10)], outputs=[io.Float.Output(display_name='a'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, a, operation, decimal_places):
        _guard({'a': a, 'operation': operation, 'decimal_places': decimal_places})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-math-operation'
        if operation == 'sin':
            result = math.sin(a)
        elif operation == 'cos':
            result = math.cos(a)
        elif operation == 'tan':
            result = math.cos(a)
        elif operation == 'sqrt':
            result = math.sqrt(a)
        elif operation == 'exp':
            result = math.exp(a)
        elif operation == 'log':
            result = math.log(a)
        elif operation == 'neg':
            result = -a
        elif operation == 'abs':
            result = abs(a)
        else:
            raise ValueError('CR Math Operation: Unsupported operation.')
        result = round(result, decimal_places)
        return _output((result, show_help))


class CR_GetParameterFromPrompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Get Parameter From Prompt', display_name='⚙️ CR Get Parameter From Prompt', category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other', is_output_node=False, inputs=[io.String.Input('prompt', multiline=True, default='prompt', force_input=True), io.String.Input('search_string', multiline=False, default='!findme')], outputs=[io.String.Output(display_name='prompt'), io.AnyType.Output(display_name='text'), io.Float.Output(display_name='float'), io.Boolean.Output(display_name='boolean'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, prompt, search_string):
        _guard({'prompt': prompt, 'search_string': search_string})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-find-string-in-prompt'
        return_string = ''
        return_value = 0
        return_boolean = False
        return_prompt = prompt
        index = prompt.find(search_string)
        if index != -1:
            if prompt[index + len(search_string)] == '=':
                if prompt[index + len(search_string) + 1] == '"':
                    start_quote = index + len(search_string) + 2
                    end_quote = prompt.find('"', start_quote + 1)
                    if end_quote != -1:
                        return_string = prompt[start_quote:end_quote]
                        print(return_string)
                else:
                    space_index = prompt.find(' ', index + len(search_string))
                    if space_index != -1:
                        return_string = prompt[index + len(search_string):space_index]
                    else:
                        return_string = prompt[index + len(search_string):]
            else:
                return_string = search_string[1:]
        if return_string == '':
            return _output((return_prompt, return_string, return_value, return_boolean, show_help))
        if return_string.startswith('='):
            return_string = return_string[1:]
        return_boolean = return_string.lower() == 'true'
        try:
            return_value = int(return_string)
        except ValueError:
            try:
                return_value = float(return_string)
            except ValueError:
                return_value = 0
        remove_string = ' ' + search_string + '=' + return_string
        return_prompt = _bounded_replace(prompt, remove_string, '')
        return _output((return_prompt, return_string, return_value, return_boolean, show_help))


class CR_SelectResizeMethod(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Select Resize Method', display_name='⚙️ CR Select Resize Method', category='🧩 Comfyroll Studio/🛠️ Utils/⚙️ Other', is_output_node=False, inputs=[io.Combo.Input('method', options=['Fit', 'Crop'])], outputs=[io.AnyType.Output(display_name='method'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, method):
        _guard({'method': method})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-select-resize-method'
        return _output((method, show_help))


class CR_SetValueOnBinary(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Set Value On Binary', display_name='⚙️ CR Set Value On Binary', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Conditional', is_output_node=False, inputs=[io.Int.Input('binary', default=1, min=0, max=1, force_input=True), io.Float.Input('value_if_1', default=1, min=-18446744073709551615, max=18446744073709551615), io.Float.Input('value_if_0', default=0, min=-18446744073709551615, max=18446744073709551615)], outputs=[io.Int.Output(display_name='INT'), io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, binary, value_if_1, value_if_0):
        _guard({'binary': binary, 'value_if_1': value_if_1, 'value_if_0': value_if_0})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-set-value-on-boolean'
        if binary == 1:
            return _output((int(value_if_1), value_if_1, show_help))
        else:
            return _output((int(value_if_0), value_if_0, show_help))


class CR_SetValueOnBoolean(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Set Value On Boolean', display_name='⚙️ CR Set Value On Boolean', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Conditional', is_output_node=False, inputs=[io.Boolean.Input('boolean', default=True, force_input=True), io.Float.Input('value_if_true', default=1, min=-18446744073709551615, max=18446744073709551615), io.Float.Input('value_if_false', default=0, min=-18446744073709551615, max=18446744073709551615)], outputs=[io.Int.Output(display_name='INT'), io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, boolean, value_if_true, value_if_false):
        _guard({'boolean': boolean, 'value_if_true': value_if_true, 'value_if_false': value_if_false})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-set-value-on-boolean'
        if boolean == True:
            return _output((int(value_if_true), value_if_true, show_help))
        else:
            return _output((int(value_if_false), value_if_false, show_help))


class CR_SetValueOnString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Set Value on String', display_name='⚙️ CR Set Value on String', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Conditional', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='', force_input=True), io.String.Input('test_string', optional=True, multiline=False, default=''), io.String.Input('value_if_true', optional=True, multiline=False, default=''), io.String.Input('value_if_false', optional=True, multiline=False, default='')], outputs=[io.AnyType.Output(display_name='STRING'), io.Boolean.Output(display_name='BOOLEAN'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, test_string, value_if_true, value_if_false):
        _guard({'text': text, 'test_string': test_string, 'value_if_true': value_if_true, 'value_if_false': value_if_false})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-set-value-on-string'
        if test_string in text:
            text_out = value_if_true
            bool_out = True
        else:
            text_out = value_if_false
            bool_out = False
        return _output((text_out, bool_out, show_help))


class CR_SetSwitchFromString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Set Switch From String', display_name='⚙️ CR Set Switch From String', category='🧩 Comfyroll Studio/🛠️ Utils/🔀 Conditional', is_output_node=False, inputs=[io.String.Input('text', multiline=False, default='', force_input=True), io.String.Input('switch_1', optional=True, multiline=False, default=''), io.String.Input('switch_2', optional=True, multiline=False, default=''), io.String.Input('switch_3', optional=True, multiline=False, default=''), io.String.Input('switch_4', optional=True, multiline=False, default='')], outputs=[io.Int.Output(display_name='switch'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text, switch_1='', switch_2='', switch_3='', switch_4=''):
        _guard({'text': text, 'switch_1': switch_1, 'switch_2': switch_2, 'switch_3': switch_3, 'switch_4': switch_4})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-set-switch-from-string'
        if text == switch_1:
            switch = 1
        elif text == switch_2:
            switch = 2
        elif text == switch_3:
            switch = 3
        elif text == switch_4:
            switch = 4
        else:
            pass
        return _output((switch, show_help))


class CR_Seed(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Seed', display_name='🌱 CR Seed', category='🧩 Comfyroll Studio/✨ Essential/📦 Core', is_output_node=True, inputs=[io.Int.Input('seed', default=0, min=0, max=18446744073709551615)], outputs=[io.Int.Output(display_name='seed'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, seed):
        _guard({'seed': seed})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-seed'
        return _output((seed, show_help))


class CR_PromptText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Prompt Text', display_name='⚙️ CR Prompt Text', category='🧩 Comfyroll Studio/✨ Essential/📦 Core', is_output_node=False, inputs=[io.String.Input('prompt', default='prompt', multiline=True)], outputs=[io.String.Output(display_name='prompt'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, prompt):
        _guard({'prompt': prompt})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-prompt-text'
        return _output((prompt, show_help))


class CR_CombinePrompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Combine Prompt', display_name='⚙️ CR Combine Prompt', category='🧩 Comfyroll Studio/✨ Essential/📦 Core', is_output_node=False, inputs=[io.String.Input('part1', optional=True, default='', multiline=True), io.String.Input('part2', optional=True, default='', multiline=True), io.String.Input('part3', optional=True, default='', multiline=True), io.String.Input('part4', optional=True, default='', multiline=True), io.String.Input('separator', optional=True, default=',', multiline=False)], outputs=[io.String.Output(display_name='prompt'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, part1='', part2='', part3='', part4='', separator=''):
        _guard({'part1': part1, 'part2': part2, 'part3': part3, 'part4': part4, 'separator': separator})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-prompt-parts'
        prompt = part1 + separator + part2 + separator + part3 + separator + part4
        return _output((prompt, show_help))


NODE_CLASS_MAPPINGS = {
    'CR Split String': CR_SplitString,
    'CR Text': CR_Text,
    'CR Multiline Text': CR_MultilineText,
    'CR Text Concatenate': CR_TextConcatenate,
    'CR Text Replace': CR_TextReplace,
    'CR Text Blacklist': CR_TextBlacklist,
    'CR Text Operation': CR_TextOperation,
    'CR Text Length': CR_TextLength,
    'CR String To Number': CR_StringToNumber,
    'CR String To Combo': CR_StringToCombo,
    'CR String To Boolean': CR_StringToBoolean,
    'CR Integer To String': CR_IntegerToString,
    'CR Float To String': CR_FloatToString,
    'CR Float To Integer': CR_FloatToInteger,
    'CR Image Input Switch': CR_ImageInputSwitch,
    'CR Latent Input Switch': CR_LatentInputSwitch,
    'CR Conditioning Input Switch': CR_ConditioningInputSwitch,
    'CR Clip Input Switch': CR_ClipInputSwitch,
    'CR Model Input Switch': CR_ModelInputSwitch,
    'CR Text Input Switch': CR_TextInputSwitch,
    'CR VAE Input Switch': CR_VAEInputSwitch,
    'CR Image Input Switch (4 way)': CR_ImageInputSwitch4way,
    'CR Text Input Switch (4 way)': CR_TextInputSwitch4way,
    'CR Switch Model and CLIP': CR_ModelAndCLIPInputSwitch,
    'CR Img2Img Process Switch': CR_Img2ImgProcessSwitch,
    'CR Hires Fix Process Switch': CR_HiResFixProcessSwitch,
    'CR Batch Process Switch': CR_BatchProcessSwitch,
    'CR Trigger': CR_Trigger,
    'CR Index': CR_Index,
    'CR Index Increment': CR_IncrementIndex,
    'CR Index Multiply': CR_MultiplyIndex,
    'CR Index Reset': CR_IndexReset,
    'CR Clamp Value': CR_ClampValue,
    'CR Integer Multiple': CR_IntegerMultipleOf,
    'CR Value': CR_Value,
    'CR Math Operation': CR_MathOperation,
    'CR Get Parameter From Prompt': CR_GetParameterFromPrompt,
    'CR Select Resize Method': CR_SelectResizeMethod,
    'CR Set Value On Binary': CR_SetValueOnBinary,
    'CR Set Value On Boolean': CR_SetValueOnBoolean,
    'CR Set Value on String': CR_SetValueOnString,
    'CR Set Switch From String': CR_SetSwitchFromString,
    'CR Seed': CR_Seed,
    'CR Prompt Text': CR_PromptText,
    'CR Combine Prompt': CR_CombinePrompt,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Split String': '🔤 CR Split String', 'CR Text': '🔤 CR Text', 'CR Multiline Text': '🔤 CR Multiline Text', 'CR Text Concatenate': '🔤 CR Text Concatenate', 'CR Text Replace': '🔤 CR Text Replace', 'CR Text Blacklist': '🔤 Text Blacklist', 'CR Text Operation': '🔤 CR Text Operation', 'CR Text Length': '🔤 CR Text Length', 'CR String To Number': '🔧 CR String To Number', 'CR String To Combo': '🔧 CR String To Combo', 'CR String To Boolean': '🔧 CR String To Boolean', 'CR Integer To String': '🔧 CR Integer To String', 'CR Float To String': '🔧 CR Float To String', 'CR Float To Integer': '🔧 CR Float To Integer', 'CR Image Input Switch': '🔀 CR Image Input Switch', 'CR Latent Input Switch': '🔀 CR Latent Input Switch', 'CR Conditioning Input Switch': '🔀 CR Conditioning Input Switch', 'CR Clip Input Switch': '🔀 CR Clip Input Switch', 'CR Model Input Switch': '🔀 CR Model Input Switch', 'CR Text Input Switch': '🔀 CR Text Input Switch', 'CR VAE Input Switch': '🔀 CR VAE Input Switch', 'CR Image Input Switch (4 way)': '🔀 CR Image Input Switch (4 way)', 'CR Text Input Switch (4 way)': '🔀 CR Text Input Switch (4 way)', 'CR Switch Model and CLIP': '🔀 CR Switch Model and CLIP', 'CR Img2Img Process Switch': '🔂 CR Img2Img Process Switch', 'CR Hires Fix Process Switch': '🔂 CR Hires Fix Process Switch', 'CR Batch Process Switch': '🔂 CR Batch Process Switch', 'CR Trigger': '🔢 CR Trigger', 'CR Index': '🔢 CR Index', 'CR Index Increment': '🔢 CR Index Increment', 'CR Index Multiply': '🔢 CR Index Multiply', 'CR Index Reset': '🔢 CR Index Reset', 'CR Clamp Value': '⚙️ CR Clamp Value', 'CR Integer Multiple': '⚙️ CR Integer Multiple', 'CR Value': '⚙️ CR Value', 'CR Math Operation': '⚙️ CR Math Operation', 'CR Get Parameter From Prompt': '⚙️ CR Get Parameter From Prompt', 'CR Select Resize Method': '⚙️ CR Select Resize Method', 'CR Set Value On Binary': '⚙️ CR Set Value On Binary', 'CR Set Value On Boolean': '⚙️ CR Set Value On Boolean', 'CR Set Value on String': '⚙️ CR Set Value on String', 'CR Set Switch From String': '⚙️ CR Set Switch From String', 'CR Seed': '🌱 CR Seed', 'CR Prompt Text': '⚙️ CR Prompt Text', 'CR Combine Prompt': '⚙️ CR Combine Prompt'}
