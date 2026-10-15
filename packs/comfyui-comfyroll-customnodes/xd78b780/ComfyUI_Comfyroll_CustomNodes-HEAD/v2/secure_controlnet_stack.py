"""Pack-owned ControlNet stacks; typed models/hints/schedules, no raw host access."""
from comfy_api.latest import io,sdk
from .secure_schedules import _guard,_output
from .secure_lora import _name
def _preflight(values):
    _guard(values)
    rows=values.get('controlnet_stack')
    if isinstance(rows,(list,tuple)) and len(rows)>256:raise ValueError('ControlNet stack exceeds bound')
async def _load(name):return await sdk.ctx().models.load_controlnet(_name(name))

class CR_ControlNetStack(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Multi-ControlNet Stack',display_name='🕹️ CR Multi-ControlNet Stack',category='🧩 Comfyroll Studio/✨ Essential/🕹️ ControlNet',inputs=[io.Combo.Input('switch_1',optional=True,options=['Off', 'On']),io.Combo.Input('controlnet_1',optional=True,options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/controlnet', refresh_button=True, static_options=['None'])),io.Float.Input('controlnet_strength_1',default=1.0,min=-10.0,max=10.0,step=0.01,optional=True),io.Float.Input('start_percent_1',default=0.0,min=0.0,max=1.0,step=0.001,optional=True),io.Float.Input('end_percent_1',default=1.0,min=0.0,max=1.0,step=0.001,optional=True),io.Combo.Input('switch_2',optional=True,options=['Off', 'On']),io.Combo.Input('controlnet_2',optional=True,options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/controlnet', refresh_button=True, static_options=['None'])),io.Float.Input('controlnet_strength_2',default=1.0,min=-10.0,max=10.0,step=0.01,optional=True),io.Float.Input('start_percent_2',default=0.0,min=0.0,max=1.0,step=0.001,optional=True),io.Float.Input('end_percent_2',default=1.0,min=0.0,max=1.0,step=0.001,optional=True),io.Combo.Input('switch_3',optional=True,options=['Off', 'On']),io.Combo.Input('controlnet_3',optional=True,options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/controlnet', refresh_button=True, static_options=['None'])),io.Float.Input('controlnet_strength_3',default=1.0,min=-10.0,max=10.0,step=0.01,optional=True),io.Float.Input('start_percent_3',default=0.0,min=0.0,max=1.0,step=0.001,optional=True),io.Float.Input('end_percent_3',default=1.0,min=0.0,max=1.0,step=0.001,optional=True),io.Image.Input('image_1',optional=True),io.Image.Input('image_2',optional=True),io.Image.Input('image_3',optional=True),io.Custom('CONTROL_NET_STACK').Input('controlnet_stack',optional=True)],outputs=[io.Custom('CONTROL_NET_STACK').Output(display_name='CONTROLNET_STACK'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, switch_1, controlnet_1, controlnet_strength_1, start_percent_1, end_percent_1, switch_2, controlnet_2, controlnet_strength_2, start_percent_2, end_percent_2, switch_3, controlnet_3, controlnet_strength_3, start_percent_3, end_percent_3, image_1=None, image_2=None, image_3=None, controlnet_stack=None):
        _preflight({'switch_1': switch_1, 'controlnet_1': controlnet_1, 'controlnet_strength_1': controlnet_strength_1, 'start_percent_1': start_percent_1, 'end_percent_1': end_percent_1, 'switch_2': switch_2, 'controlnet_2': controlnet_2, 'controlnet_strength_2': controlnet_strength_2, 'start_percent_2': start_percent_2, 'end_percent_2': end_percent_2, 'switch_3': switch_3, 'controlnet_3': controlnet_3, 'controlnet_strength_3': controlnet_strength_3, 'start_percent_3': start_percent_3, 'end_percent_3': end_percent_3, 'image_1': image_1, 'image_2': image_2, 'image_3': image_3, 'controlnet_stack': controlnet_stack})
        controlnet_list = []
        if controlnet_stack is not None:
            controlnet_list.extend([l for l in controlnet_stack if l[0] != 'None'])
        if controlnet_1 != 'None' and switch_1 == 'On' and (image_1 is not None):
            controlnet_1 = await _load(controlnet_1)
            (controlnet_list.extend([(controlnet_1, image_1, controlnet_strength_1, start_percent_1, end_percent_1)]),)
        if controlnet_2 != 'None' and switch_2 == 'On' and (image_2 is not None):
            controlnet_2 = await _load(controlnet_2)
            (controlnet_list.extend([(controlnet_2, image_2, controlnet_strength_2, start_percent_2, end_percent_2)]),)
        if controlnet_3 != 'None' and switch_3 == 'On' and (image_3 is not None):
            controlnet_3 = await _load(controlnet_3)
            (controlnet_list.extend([(controlnet_3, image_3, controlnet_strength_3, start_percent_3, end_percent_3)]),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/ControlNet-Nodes#cr-multi-controlnet-stack'
        return _output((controlnet_list, show_help))

class CR_ApplyControlNetStack(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Apply Multi-ControlNet',display_name='🕹️ CR Apply Multi-ControlNet',category='🧩 Comfyroll Studio/✨ Essential/🕹️ ControlNet',inputs=[io.Conditioning.Input('base_positive'),io.Conditioning.Input('base_negative'),io.Combo.Input('switch',options=['Off', 'On']),io.Custom('CONTROL_NET_STACK').Input('controlnet_stack')],outputs=[io.Conditioning.Output(display_name='base_pos'),io.Conditioning.Output(display_name='base_neg'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, base_positive, base_negative, switch, controlnet_stack=None):
        _preflight({'base_positive': base_positive, 'base_negative': base_negative, 'switch': switch, 'controlnet_stack': controlnet_stack})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/ControlNet-Nodes#cr-apply-multi-controlnet-stack'
        if switch == 'Off':
            return _output((base_positive, base_negative, show_help))
        if controlnet_stack is not None:
            for controlnet_tuple in controlnet_stack:
                controlnet_name, image, strength, start_percent, end_percent = controlnet_tuple
                if type(controlnet_name) == str:
                    controlnet = await _load(controlnet_name)
                else:
                    controlnet = controlnet_name
                if strength == 0:
                    continue
                controlnet_conditioning = await controlnet.apply(base_positive, base_negative, image, strength, start_percent, end_percent)
                base_positive, base_negative = (controlnet_conditioning[0], controlnet_conditioning[1])
        return _output((base_positive, base_negative, show_help))

NODE_CLASS_MAPPINGS={'CR Multi-ControlNet Stack':CR_ControlNetStack,'CR Apply Multi-ControlNet':CR_ApplyControlNetStack}
NODE_DISPLAY_NAME_MAPPINGS={'CR Multi-ControlNet Stack': '🕹️ CR Multi-ControlNet Stack', 'CR Apply Multi-ControlNet': '🕹️ CR Apply Multi-ControlNet'}
