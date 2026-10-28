"""Complete public V2 boundary. Original implementation modules unchanged."""
from comfy_api.latest import io

def _output(value):
    if type(value) is dict:
        return io.NodeOutput(*value['result'],ui=value.get('ui'),expand=value.get('expand'),block_execution=value.get('block_execution'))
    return io.NodeOutput(*value)

class ETSplitTextNode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETSplitTextNode',display_name='Split Text',category='exectails/Strings',
            inputs=[io.String.Input('text',default='',multiline=False,force_input=True,tooltip='The text to split.'),io.String.Input('split_by',default=',',multiline=False,tooltip='The string to split the text on.')],outputs=[io.String.Output(display_name='text',is_output_list=True)],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,text,split_by):
        from .nodes.combiner import ETSplitTextNode as Original
        return _output(Original().process(text=text,split_by=split_by))

class ETJoinTextNode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETJoinTextNode',display_name='Join Text',category='exectails/Strings',
            inputs=[io.String.Input('text',default='',multiline=False,force_input=True,tooltip='The text to replace in.'),io.String.Input('join_with',default=', ',multiline=False,tooltip='The string to join the elements with.'),io.String.Input('prefix',default='',multiline=False,tooltip='A string to place before the text.'),io.String.Input('suffix',default='',multiline=False,tooltip='A string to place after the text.')],outputs=[io.String.Output(display_name='text')],
            is_input_list=True,is_output_node=False)
    @classmethod
    async def execute(cls,text,join_with,prefix,suffix):
        from .nodes.combiner import ETJoinTextNode as Original
        return _output(Original().process(text=text,join_with=join_with,prefix=prefix,suffix=suffix))

class ETSwitchTextNode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETSwitchTextNode',display_name='Switch Text',category='exectails/Strings',
            inputs=[io.String.Input('option1',default='',multiline=False,tooltip='The option that will returned if the switch is off/false.'),io.String.Input('option2',default='',multiline=False,tooltip='The option that will returned if the switch is on/true.'),io.Boolean.Input('switch',default=False,label_off='option1',label_on='option2',tooltip='The switch that determines which option to return. Option 1 if off, option 2 if on.')],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,option1='',option2='',switch=False):
        from .nodes.combiner import ETSwitchTextNode as Original
        return _output(Original().process(option1=option1,option2=option2,switch=switch))

class ETATOI(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETATOI',display_name='ATOI',category='exectails/Strings',
            inputs=[io.String.Input('text',default='',multiline=False)],outputs=[io.Int.Output(display_name='integer')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,text):
        from .nodes.converter import ETATOI as Original
        return _output(Original().process(text=text))

class ETITOA(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETITOA',display_name='ITOA',category='exectails/Strings',
            inputs=[io.Int.Input('integer',default=0,min=-2000000000,max=2000000000)],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,integer):
        from .nodes.converter import ETITOA as Original
        return _output(Original().process(integer=integer))

class ETFTOA(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETFTOA',display_name='FTOA',category='exectails/Strings',
            inputs=[io.Float.Input('value',default=0.0,min=-2000000000,max=2000000000),io.Int.Input('decimals',default=3,min=0,max=8)],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,value,decimals):
        from .nodes.converter import ETFTOA as Original
        return _output(Original().process(value=value,decimals=decimals))

class ETTextFormatter2Node(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETTextFormatter2Node',display_name='Text Formatter (2 Arguments)',category='exectails/Strings',
            inputs=[io.String.Input('format',multiline=True),io.String.Input('arg0',optional=True,force_input=True),io.String.Input('arg1',optional=True,force_input=True)],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,format,arg0='',arg1=''):
        from .nodes.formatter import ETTextFormatter2Node as Original
        return _output(Original().process(format=format,arg0=arg0,arg1=arg1))

class ETTextFormatter5Node(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETTextFormatter5Node',display_name='Text Formatter (5 Arguments)',category='exectails/Strings',
            inputs=[io.String.Input('format',multiline=True),io.String.Input('arg0',optional=True,force_input=True),io.String.Input('arg1',optional=True,force_input=True),io.String.Input('arg2',optional=True,force_input=True),io.String.Input('arg3',optional=True,force_input=True),io.String.Input('arg4',optional=True,force_input=True)],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,format,arg0='',arg1='',arg2='',arg3='',arg4=''):
        from .nodes.formatter import ETTextFormatter5Node as Original
        return _output(Original().process(format=format,arg0=arg0,arg1=arg1,arg2=arg2,arg3=arg3,arg4=arg4))

class ETTextFormatter10Node(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETTextFormatter10Node',display_name='Text Formatter (10 Arguments)',category='exectails/Strings',
            inputs=[io.String.Input('format',multiline=True),io.String.Input('arg0',optional=True,force_input=True),io.String.Input('arg1',optional=True,force_input=True),io.String.Input('arg2',optional=True,force_input=True),io.String.Input('arg3',optional=True,force_input=True),io.String.Input('arg4',optional=True,force_input=True),io.String.Input('arg5',optional=True,force_input=True),io.String.Input('arg6',optional=True,force_input=True),io.String.Input('arg7',optional=True,force_input=True),io.String.Input('arg8',optional=True,force_input=True),io.String.Input('arg9',optional=True,force_input=True)],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,format,arg0='',arg1='',arg2='',arg3='',arg4='',arg5='',arg6='',arg7='',arg8='',arg9=''):
        from .nodes.formatter import ETTextFormatter10Node as Original
        return _output(Original().process(format=format,arg0=arg0,arg1=arg1,arg2=arg2,arg3=arg3,arg4=arg4,arg5=arg5,arg6=arg6,arg7=arg7,arg8=arg8,arg9=arg9))

class ETReplaceTextNode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ETReplaceTextNode',display_name='Text Replacer',category='exectails/Strings',
            inputs=[io.String.Input('text',default='',multiline=False,tooltip='The text to replace in.'),io.String.Input('replace',default='',multiline=False,tooltip='The text to replace.'),io.String.Input('replacement',default='',multiline=False,tooltip='The text to replace with.'),io.Combo.Input('mode',options=['normal', 'regex'],default='normal',tooltip='The mode to use for replacing.')],outputs=[io.String.Output(display_name='text')],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,text,replace,replacement,mode):
        from .nodes.replacer import ETReplaceTextNode as Original
        return _output(Original().process(text=text,replace=replace,replacement=replacement,mode=mode))

