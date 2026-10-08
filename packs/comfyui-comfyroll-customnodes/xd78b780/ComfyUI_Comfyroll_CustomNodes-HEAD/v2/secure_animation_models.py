"""Plain animation catalogue lists and public scoped LoRA application; no legacy host access."""
from comfy_api.latest import io,sdk
from .secure_schedules import _guard,_output
from .secure_lora import _name,_weight

def _preflight(values):
    _guard(values)
    loops=values.get('loops',1)
    for key in ('model_list','lora_list'):
        rows=values.get(key)
        if rows is not None and (not isinstance(rows,(list,tuple)) or len(rows)>256):
            raise ValueError('Animation model/LoRA rows exceed bound')
        if isinstance(loops,int) and (abs(loops)>1000 or max(0,loops)*len(rows or [])>16384):
            raise ValueError('Animation LoRA projected loop workload exceeds bound')
    for key,value in values.items():
        if key.startswith(('ckpt_name','lora_name')):_name(value)
        if key.startswith(('model_strength','clip_strength')):_weight(value)
    projected=sum(len(repr(v).encode('utf-8')) for v in values.values() if isinstance(v,(str,list,tuple)))
    if projected>262144:raise ValueError('Animation model/LoRA text projection exceeds bound')

class CR_ModelList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Model List',display_name='CR Model List (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',inputs=[io.Combo.Input('ckpt_name1', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.String.Input('alias1', multiline=False, default=''), io.Combo.Input('ckpt_name2', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.String.Input('alias2', multiline=False, default=''), io.Combo.Input('ckpt_name3', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.String.Input('alias3', multiline=False, default=''), io.Combo.Input('ckpt_name4', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.String.Input('alias4', multiline=False, default=''), io.Combo.Input('ckpt_name5', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.String.Input('alias5', multiline=False, default=''), io.Custom('MODEL_LIST').Input('model_list', optional=True)],outputs=[io.Custom('MODEL_LIST').Output(display_name='MODEL_LIST'), io.String.Output(display_name='show_text')])

    @classmethod
    def execute(cls, ckpt_name1, alias1, ckpt_name2, alias2, ckpt_name3, alias3, ckpt_name4, alias4, ckpt_name5, alias5, model_list=None):
        _preflight({'ckpt_name1': ckpt_name1, 'alias1': alias1, 'ckpt_name2': ckpt_name2, 'alias2': alias2, 'ckpt_name3': ckpt_name3, 'alias3': alias3, 'ckpt_name4': ckpt_name4, 'alias4': alias4, 'ckpt_name5': ckpt_name5, 'alias5': alias5, 'model_list': model_list})
        models = list()
        model_text = list()
        if model_list is not None:
            models.extend([l for l in model_list if l[0] != None])
            model_text += '\n'.join(map(str, model_list)) + '\n'
        if ckpt_name1 != 'None':
            model1_tup = [(alias1, ckpt_name1)]
            (models.extend(model1_tup),)
            model_text += '\n'.join(map(str, model1_tup)) + '\n'
        if ckpt_name2 != 'None':
            model2_tup = [(alias2, ckpt_name2)]
            (models.extend(model2_tup),)
            model_text += '\n'.join(map(str, model2_tup)) + '\n'
        if ckpt_name3 != 'None':
            model3_tup = [(alias3, ckpt_name3)]
            (models.extend(model3_tup),)
            model_text += '\n'.join(map(str, model3_tup)) + '\n'
        if ckpt_name4 != 'None':
            model4_tup = [(alias4, ckpt_name4)]
            (models.extend(model4_tup),)
            model_text += '\n'.join(map(str, model4_tup)) + '\n'
        if ckpt_name5 != 'None':
            model5_tup = [(alias5, ckpt_name5)]
            (models.extend(model5_tup),)
            model_text += '\n'.join(map(str, model5_tup)) + '\n'
        show_text = ''.join(model_text)
        return _output((models, show_text))


class CR_LoRAList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR LoRA List',display_name='CR LoRA List (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',inputs=[io.Combo.Input('lora_name1', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.String.Input('alias1', multiline=False, default=''), io.Float.Input('model_strength_1', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_strength_1', default=1.0, min=-10.0, max=10.0, step=0.01), io.Combo.Input('lora_name2', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.String.Input('alias2', multiline=False, default=''), io.Float.Input('model_strength_2', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_strength_2', default=1.0, min=-10.0, max=10.0, step=0.01), io.Combo.Input('lora_name3', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.String.Input('alias3', multiline=False, default=''), io.Float.Input('model_strength_3', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_strength_3', default=1.0, min=-10.0, max=10.0, step=0.01), io.Custom('LORA_LIST').Input('lora_list', optional=True)],outputs=[io.Custom('LORA_LIST').Output(display_name='LORA_LIST'), io.String.Output(display_name='show_text')])

    @classmethod
    def execute(cls, lora_name1, model_strength_1, clip_strength_1, alias1, lora_name2, model_strength_2, clip_strength_2, alias2, lora_name3, model_strength_3, clip_strength_3, alias3, lora_list=None):
        _preflight({'lora_name1': lora_name1, 'model_strength_1': model_strength_1, 'clip_strength_1': clip_strength_1, 'alias1': alias1, 'lora_name2': lora_name2, 'model_strength_2': model_strength_2, 'clip_strength_2': clip_strength_2, 'alias2': alias2, 'lora_name3': lora_name3, 'model_strength_3': model_strength_3, 'clip_strength_3': clip_strength_3, 'alias3': alias3, 'lora_list': lora_list})
        loras = list()
        lora_text = list()
        if lora_list is not None:
            loras.extend([l for l in lora_list if l[0] != None])
            lora_text += '\n'.join(map(str, lora_list)) + '\n'
        if lora_name1 != 'None':
            lora1_tup = [(alias1, lora_name1, model_strength_1, clip_strength_1)]
            (loras.extend(lora1_tup),)
            lora_text += '\n'.join(map(str, lora1_tup)) + '\n'
        if lora_name2 != 'None':
            lora2_tup = [(alias2, lora_name2, model_strength_2, clip_strength_2)]
            (loras.extend(lora2_tup),)
            lora_text += '\n'.join(map(str, lora2_tup)) + '\n'
        if lora_name3 != 'None':
            lora3_tup = [(alias3, lora_name3, model_strength_3, clip_strength_3)]
            (loras.extend(lora3_tup),)
            lora_text += '\n'.join(map(str, lora3_tup)) + '\n'
        show_text = ''.join(lora_text)
        return _output((loras, show_text))


class CR_CycleLoRAs(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('assets',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Cycle LoRAs',display_name='CR Cycle LoRAs (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',inputs=[io.Combo.Input('mode', options=['Off', 'Sequential']), io.Model.Input('model'), io.Clip.Input('clip'), io.Custom('LORA_LIST').Input('lora_list'), io.Int.Input('frame_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)],outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls,mode,model,clip,lora_list,frame_interval,loops,current_frame):
        _preflight(dict(mode=mode,model=model,clip=clip,lora_list=lora_list,frame_interval=frame_interval,loops=loops,current_frame=current_frame))
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Cycler-Nodes#cr-cycle-loras'
        rows=[]
        if lora_list:
            for _ in range(loops):rows.extend(lora_list)
        else:return io.NodeOutput(model,clip,help_url)
        if mode=='Sequential':
            index=(current_frame//frame_interval)%len(rows)
            alias,name,model_strength,clip_strength=rows[index]
            _name(name);_weight(model_strength);_weight(clip_strength)
            asset=await sdk.ctx().assets.resolve('loras',name)
            model,clip=await model.apply_lora(asset,clip,model_strength,clip_strength,skip_zero=False)
            return io.NodeOutput(model,clip,help_url)
        return io.NodeOutput(model,clip,help_url)

NODE_CLASS_MAPPINGS={
    'CR Model List':CR_ModelList,
    'CR LoRA List':CR_LoRAList,
    'CR Cycle LoRAs':CR_CycleLoRAs,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Model List': 'CR Model List (Legacy)', 'CR LoRA List': 'CR LoRA List (Legacy)', 'CR Cycle LoRAs': 'CR Cycle LoRAs (Legacy)'}
