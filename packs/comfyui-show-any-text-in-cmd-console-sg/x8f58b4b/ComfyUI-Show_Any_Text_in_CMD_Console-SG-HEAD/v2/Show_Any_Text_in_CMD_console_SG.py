from comfy_api.latest import io
from ._algorithm import ShowAnyTextInCMDconsoleSG as Original

class ShowAnyTextInCMDconsoleSG(io.ComfyNode):
    
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        options = Original.INPUT_TYPES()['required']
        return io.Schema(node_id='ShowAnyTextInCMDconsoleSG',display_name='Show Any Text In CMD console-SG',category='utils',is_output_node=True,
            inputs=[io.String.Input('text',force_input=True),
                io.Boolean.Input('show_any_text_in_console',default=True,tooltip=options['show_any_text_in_console'][1]['tooltip']),
                io.Combo.Input('color_preset',options=options['color_preset'][0],tooltip=options['color_preset'][1]['tooltip']),
                io.String.Input('hex_color',default='',multiline=False,tooltip=options['hex_color'][1]['tooltip'])],outputs=[io.String.Output()])

    @classmethod
    async def execute(cls,text,show_any_text_in_console,color_preset='white',hex_color=''):
        for name,value,bound in [('text',text,65280),('color_preset',color_preset,64),('hex_color',hex_color,256)]:
            if type(value) is not str or len(value.encode('utf-8'))>bound:
                raise ValueError(f'{name} exceeds bounded plain UTF-8 string profile')
        if type(show_any_text_in_console) is not bool:
            raise ValueError('plain Boolean console switch required')
        return io.NodeOutput.from_dict(Original().display_text(text,show_any_text_in_console,color_preset,hex_color))

# Node registration
NODE_CLASS_MAPPINGS = {
    "ShowAnyTextInCMDconsoleSG": ShowAnyTextInCMDconsoleSG,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ShowAnyTextInCMDconsoleSG": "Show Any Text In CMD console-SG",
}
