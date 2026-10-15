"""Authored workflow metadata; no execution authority or side effects."""
from comfy_api.latest import io
from .nodes.aivapp import AivParamNode as Source

class AivParamSecure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        inputs=[]
        for name,spec in Source.INPUT_TYPES()['required'].items():
            options=dict(spec[1]);options['dynamic_prompts']=options.pop('dynamicPrompts')
            inputs.append(io.String.Input(name,**options))
        return io.Schema(node_id='AivParam',display_name='Aiv Param',category=Source.CATEGORY,inputs=inputs,outputs=[])

    @classmethod
    def execute(cls,text_param,text_note):
        # Explicit coordinator-approved source-callability repair only.
        for name,value,limit in (('text_param',text_param,128*1024),('text_note',text_note,64*1024)):
            if not isinstance(value,str):raise TypeError(name+' STRING required')
            if len(value.encode('utf-8'))>limit:raise ValueError(name+' metadata byte budget exceeded')
        return io.NodeOutput()
