"""Bounded prompt composition over immutable pinned pack resources."""
from comfy_api.latest import io
from .HunyuanVideoStyler import HunyuanVideoStyler as Source, styler_data

MAX_TEXT=65536
def preflight(text_positive,text_negative,debug_prompt,styles):
    if not isinstance(text_positive,str) or not isinstance(text_negative,str):
        raise ValueError('STRING prompts required')
    if type(debug_prompt) is not bool:raise ValueError('Boolean debug control required')
    positive=len(text_positive.encode('utf-8'));negative=len(text_negative.encode('utf-8'))
    if positive+negative>MAX_TEXT:raise ValueError('prompt input byte bound exceeded')
    cumulative=positive+negative
    for group in Source.style_order:
        selected=styles.get(group)
        if selected and selected!='None':
            template=styler_data[group][selected]
            count=template.prompt.count('{prompt}')
            positive=len(template.prompt.encode('utf-8'))-count*len('{prompt}')+count*positive
            template_negative=len(template.negative_prompt.encode('utf-8'))
            negative=template_negative+negative+(2 if template_negative and negative else 0)
            cumulative+=positive+negative
            if positive+negative>MAX_TEXT or cumulative>512*1024:
                raise ValueError('projected prompt output/work bound exceeded')

class HunyuanVideoStylerSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=()
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        inputs=[]
        for name,spec in Source.INPUT_TYPES()['required'].items():
            if isinstance(spec[0],list):inputs.append(io.Combo.Input(name,options=spec[0]))
            elif spec[0]=='STRING':inputs.append(io.String.Input(name,**spec[1]))
            else:inputs.append(io.Boolean.Input(name,default=spec[1]['default'],extra_dict={'label':spec[1]['label']}))
        return io.Schema(node_id='HunyuanVideoStyler',display_name='Hunyuan Video Styler',category=Source.CATEGORY,inputs=inputs,outputs=[io.String.Output(display_name=name) for name in Source.RETURN_NAMES])

    @classmethod
    def execute(cls,text_positive,text_negative,debug_prompt,**styles):
        preflight(text_positive,text_negative,debug_prompt,styles)
        return io.NodeOutput(*Source().style_video_prompt(text_positive,text_negative,debug_prompt,**styles))

NODE_CLASS_MAPPINGS={'HunyuanVideoStyler':HunyuanVideoStylerSecure}
NODE_DISPLAY_NAME_MAPPINGS={'HunyuanVideoStyler':'Hunyuan Video Styler'}
