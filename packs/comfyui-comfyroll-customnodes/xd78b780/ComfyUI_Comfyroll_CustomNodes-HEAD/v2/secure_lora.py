"""Public model/assets LoRA orchestration. Full Comfyroll release remains pending."""
import math
from comfy_api.latest import io, sdk

def _name(name):
    if not isinstance(name,str) or not name or len(name.encode('utf-8'))>2048 or '\x00' in name or '\\' in name or name.startswith('/') or ':' in name or any(p in ('','.', '..') for p in name.split('/')):
        raise ValueError('LoRA name must be a bounded registered logical name')
    return name

def _weight(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not -100<=value<=100:
        raise ValueError('LoRA weight must be finite in [-100,100]')
    return value

def _stack(stack):
    if stack is None: return []
    if not isinstance(stack,(list,tuple)) or len(stack)>256:
        raise ValueError('LoRA stack exceeds 256 entries')
    result=[]
    for row in stack:
        if not isinstance(row,(list,tuple)) or len(row)!=3:
            raise ValueError('LoRA stack requires (logical name, model weight, clip weight) entries')
        result.append((_name(row[0]),_weight(row[1]),_weight(row[2])))
    return result

class CR_LoraLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load LoRA', display_name='💊 CR Load LoRA', category='🧩 Comfyroll Studio/✨ Essential/💊 LoRA', inputs=[io.Model.Input('model'), io.Clip.Input('clip'), io.Combo.Input('switch', options=['On', 'Off']), io.Combo.Input('lora_name', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Float.Input('strength_model', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('strength_clip', default=1.0, min=-10.0, max=10.0, step=0.01)], outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, model, clip, switch, lora_name, strength_model, strength_clip):
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/LoRA-Nodes#cr-load-lora'
        if strength_model==0 and strength_clip==0 or switch=='Off' or lora_name=='None':
            return io.NodeOutput(model,clip,help_url)
        name=_name(lora_name);_weight(strength_model);_weight(strength_clip)
        asset=await sdk.ctx().assets.resolve('loras',name)
        result_model,result_clip=await model.apply_lora(asset,clip,strength_model,strength_clip)
        return io.NodeOutput(result_model,result_clip,help_url)

class CR_LoRAStack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR LoRA Stack', display_name='💊 CR LoRA Stack', category='🧩 Comfyroll Studio/✨ Essential/💊 LoRA', inputs=[io.Combo.Input('switch_1', options=['Off', 'On']), io.Combo.Input('lora_name_1', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Float.Input('model_weight_1', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight_1', default=1.0, min=-10.0, max=10.0, step=0.01), io.Combo.Input('switch_2', options=['Off', 'On']), io.Combo.Input('lora_name_2', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Float.Input('model_weight_2', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight_2', default=1.0, min=-10.0, max=10.0, step=0.01), io.Combo.Input('switch_3', options=['Off', 'On']), io.Combo.Input('lora_name_3', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Float.Input('model_weight_3', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight_3', default=1.0, min=-10.0, max=10.0, step=0.01), io.Custom('LORA_STACK').Input('lora_stack', optional=True)], outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, lora_name_1, model_weight_1, clip_weight_1, switch_1, lora_name_2, model_weight_2, clip_weight_2, switch_2, lora_name_3, model_weight_3, clip_weight_3, switch_3, lora_stack=None):
        for weight in (model_weight_1, clip_weight_1, model_weight_2, clip_weight_2, model_weight_3, clip_weight_3):
            _weight(weight)
        lora_stack = _stack(lora_stack)
        _name(lora_name_1)
        _name(lora_name_2)
        _name(lora_name_3)
        lora_list = list()
        if lora_stack is not None:
            lora_list.extend([l for l in lora_stack if l[0] != 'None'])
        if lora_name_1 != 'None' and switch_1 == 'On':
            (lora_list.extend([(lora_name_1, model_weight_1, clip_weight_1)]),)
        if lora_name_2 != 'None' and switch_2 == 'On':
            (lora_list.extend([(lora_name_2, model_weight_2, clip_weight_2)]),)
        if lora_name_3 != 'None' and switch_3 == 'On':
            (lora_list.extend([(lora_name_3, model_weight_3, clip_weight_3)]),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/LoRA-Nodes#cr-lora-stack'
        return io.NodeOutput(_stack(lora_list), show_help)

class CR_ApplyLoRAStack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Apply LoRA Stack', display_name='💊 CR Apply LoRA Stack', category='🧩 Comfyroll Studio/✨ Essential/💊 LoRA', inputs=[io.Model.Input('model'), io.Clip.Input('clip'), io.Custom('LORA_STACK').Input('lora_stack')], outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, model, clip, lora_stack=None):
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/LoRA-Nodes#cr-apply-lora-stack'
        for name,strength_model,strength_clip in _stack(lora_stack):
            asset=await sdk.ctx().assets.resolve('loras',name)
            model,clip=await model.apply_lora(asset,clip,strength_model,strength_clip)
        return io.NodeOutput(model,clip,help_url)

NODE_CLASS_MAPPINGS = {
    'CR Load LoRA': CR_LoraLoader,
    'CR LoRA Stack': CR_LoRAStack,
    'CR Apply LoRA Stack': CR_ApplyLoRAStack,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Load LoRA': '💊 CR Load LoRA', 'CR LoRA Stack': '💊 CR LoRA Stack', 'CR Apply LoRA Stack': '💊 CR Apply LoRA Stack'}
