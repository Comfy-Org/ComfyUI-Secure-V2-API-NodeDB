"""Public opaque ControlNet operations; no tensor raw or model-object recovery."""
from comfy_api.latest import io
from .categories import icons

HELP_APPLY='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/ControlNet-Nodes#cr-apply-controlnet'
HELP_SWITCH='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Logic-Nodes#cr-controlnet-input-switch'

class CR_ApplyControlNet(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Apply ControlNet',display_name='🕹️ CR Apply ControlNet',category=icons['Comfyroll/ControlNet'],
            inputs=[io.Conditioning.Input('conditioning'),io.ControlNet.Input('control_net'),io.Image.Input('image'),
                    io.Combo.Input('switch',options=['On','Off']),io.Float.Input('strength',default=1.0,min=0.0,max=10.0,step=0.01)],
            outputs=[io.Conditioning.Output(display_name='CONDITIONING'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,conditioning,control_net,image,switch,strength):
        if strength==0 or switch=='Off':
            return io.NodeOutput(conditioning,HELP_APPLY)
        # Empty plain containers are not admitted as CondRef by the public input wrapper.
        # Approved normal-BHWC adaptation; no raw access or manufactured opaque ref.
        # Unlike the source, this cannot validate malformed image.movedim on this branch.
        if isinstance(conditioning,(list,tuple)) and len(conditioning)==0:
            return io.NodeOutput([],HELP_APPLY)
        result=await control_net.apply_single(conditioning,image,strength,apply_to_uncond=None)
        return io.NodeOutput(result,HELP_APPLY)

class CR_ControlNetInputSwitch(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        # Canonical get_input_info gives required sockets precedence over duplicate optional entries.
        return io.Schema(node_id='CR ControlNet Input Switch',display_name='🔀 CR ControlNet Input Switch',category=icons['Comfyroll/Utils/Logic'],
            inputs=[io.Int.Input('Input',default=1,min=1,max=2),io.ControlNet.Input('control_net1'),io.ControlNet.Input('control_net2')],
            outputs=[io.ControlNet.Output(display_name='CONTROL_NET'),io.String.Output(display_name='show_help')])
    @classmethod
    def execute(cls,Input,control_net1=None,control_net2=None):
        return io.NodeOutput(control_net1 if Input==1 else control_net2,HELP_SWITCH)

NODE_CLASS_MAPPINGS={'CR Apply ControlNet':CR_ApplyControlNet,'CR ControlNet Input Switch':CR_ControlNetInputSwitch}
NODE_DISPLAY_NAME_MAPPINGS={'CR Apply ControlNet':'🕹️ CR Apply ControlNet','CR ControlNet Input Switch':'🔀 CR ControlNet Input Switch'}
