"""Scalar and opaque-ref routing wrappers, no ambient imports or path authority."""
from comfy_api.latest import io
from .comfyui_jh_misc_nodes.jh_daisy_chainable_string_constant_node import JHDaisyChainableStringConstantNode as SourceString
from .comfyui_jh_misc_nodes.jh_n_way_switch_node import JHTwoWaySwitchNode as SourceTwo, JHThreeWaySwitchNode as SourceThree
from .comfyui_jh_misc_nodes.jh_preview_image import JHPreviewImage

class JHStringSecure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JHDaisyChainableStringConstantNode',display_name='Daisy-Chainable String Constant',category=SourceString.CATEGORY,is_experimental=True,
            inputs=[io.String.Input('text',multiline=True,dynamic_prompts=False,default='',optional=True),io.String.Input('input_text',multiline=True,dynamic_prompts=False,default='',force_input=True,optional=True)],outputs=[io.String.Output(display_name='text')])

    @classmethod
    def execute(cls,text,input_text=''):
        for value in (text,input_text):
            if value is not None and not isinstance(value,str):raise TypeError('STRING value required')
            if isinstance(value,str) and len(value.encode('utf-8'))>64*1024:raise ValueError('text byte budget exceeded')
        result=SourceString().execute(text,input_text)
        if len(result[0].encode('utf-8'))>64*1024:raise ValueError('text output byte budget exceeded')
        return io.NodeOutput(*result)

def switch(name,display,source):
    class JHSwitchSecure(io.ComfyNode):
        SDK_REFS=True
        SDK_PERMISSIONS=()
        FUNCTION='execute'

        @classmethod
        def define_schema(cls):
            return io.Schema(node_id=name,display_name=display,category=source.CATEGORY,is_experimental=True,
                inputs=[io.AnyType.Input(key,optional=True) for key in source.INPUT_TYPES()['optional']],outputs=[io.AnyType.Output()])

        @classmethod
        def execute(cls,**kwargs):
            return io.NodeOutput(*source().do_switch(**kwargs))
    JHSwitchSecure.__name__=source.__name__+'Secure'
    JHSwitchSecure.__qualname__=JHSwitchSecure.__name__
    return JHSwitchSecure

JHTwoWaySwitchNodeSecure=switch('JHTwoWaySwitchNode','Two-Way Switch',SourceTwo)
JHThreeWaySwitchNodeSecure=switch('JHThreeWaySwitchNode','Three-Way Switch',SourceThree)
NODE_CLASS_MAPPINGS={'JHDaisyChainableStringConstantNode':JHStringSecure,'JHTwoWaySwitchNode':JHTwoWaySwitchNodeSecure,'JHThreeWaySwitchNode':JHThreeWaySwitchNodeSecure,'JHPreviewImage':JHPreviewImage}
NODE_DISPLAY_NAME_MAPPINGS={'JHDaisyChainableStringConstantNode':'Daisy-Chainable String Constant','JHTwoWaySwitchNode':'Two-Way Switch','JHThreeWaySwitchNode':'Three-Way Switch','JHPreviewImage':'Preview Image'}
