"""Pack-owned schedule selection and public managed checkpoint/LoRA brokers."""
from comfy_api.latest import io,sdk
from .secure_schedules import _guard,_output,keyframe_scheduler
from .secure_lora import _name,_weight

def _preflight(values):
    _guard(values)
    for key in ('model_list','lora_list','schedule'):
        rows=values.get(key)
        if isinstance(rows,(list,tuple)) and len(rows)>256:
            raise ValueError('Scheduled loader rows exceed bound')

async def _load_checkpoint(name):
    return await sdk.ctx().models.load_checkpoint(_name(name))

async def _load_lora(model,clip,name,sm,sc):
    # Canonical LoraLoader checks both zero before touching name or files.
    if sm==0 and sc==0:return model,clip
    name=_name(name);_weight(sm);_weight(sc)
    asset=await sdk.ctx().assets.resolve('loras',name)
    return await model.apply_lora(asset,clip,sm,sc)

class CR_LoadScheduledModels(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load Scheduled Models',display_name='📑 CR Load Scheduled Models',category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers',inputs=[io.Combo.Input('mode',options=['Load default Model', 'Schedule']),io.Int.Input('current_frame',default=0.0,min=0.0,max=9999.0,step=1.0),io.String.Input('schedule_alias',default='',multiline=False),io.Combo.Input('default_model',options=[],remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True)),io.Combo.Input('schedule_format',options=['CR', 'Deforum']),io.Custom('MODEL_LIST').Input('model_list',optional=True),io.Custom('SCHEDULE').Input('schedule',optional=True)],outputs=[io.Model.Output(display_name='MODEL'),io.Clip.Output(display_name='CLIP'),io.Vae.Output(display_name='VAE'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, mode, current_frame, schedule_alias, default_model, schedule_format, model_list=None, schedule=None):
        _preflight({'mode': mode, 'current_frame': current_frame, 'schedule_alias': schedule_alias, 'default_model': default_model, 'schedule_format': schedule_format, 'model_list': model_list, 'schedule': schedule})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-load-scheduled-models'
        if mode == 'Load default Model':
            out = await _load_checkpoint(default_model)
            print(f'[Debug] CR Load Scheduled Models. Loading default model.')
            return io.NodeOutput(*out, show_help)
        params = keyframe_scheduler(schedule, schedule_alias, current_frame)
        if params == '':
            print(f'[Warning] CR Load Scheduled Models. No model specified in schedule for frame {current_frame}. Using default model.')
            out = await _load_checkpoint(default_model)
            return io.NodeOutput(*out, show_help)
        else:
            try:
                model_alias = str(params)
            except ValueError:
                print(f'[Warning] CR Load Scheduled Models. Invalid params: {params}')
                return _output(())
        for ckpt_alias, ckpt_name in model_list:
            if ckpt_alias == model_alias:
                model_name = ckpt_name
                break
        if model_name == '':
            print(f'[Info] CR Load Scheduled Models. No model alias match found for {model_alias}. Frame {current_frame} will produce an error.')
            return _output(())
        else:
            print(f'[Info] CR Load Scheduled Models. Model alias {model_alias} matched to {model_name}')
        out = await _load_checkpoint(model_name)
        print(f'[Info] CR Load Scheduled Models. Loading new checkpoint model {model_name}')
        return io.NodeOutput(*out, show_help)

class CR_LoadScheduledLoRAs(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('assets',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load Scheduled LoRAs',display_name='📑 CR Load Scheduled LoRAs',category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers',inputs=[io.Combo.Input('mode',options=['Off', 'Load default LoRA', 'Schedule']),io.Model.Input('model'),io.Clip.Input('clip'),io.Int.Input('current_frame',default=0.0,min=0.0,max=9999.0,step=1.0),io.String.Input('schedule_alias',default='',multiline=False),io.Combo.Input('default_lora',options=[],remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True)),io.Float.Input('strength_model',default=1.0,min=-10.0,max=10.0,step=0.01),io.Float.Input('strength_clip',default=1.0,min=-10.0,max=10.0,step=0.01),io.Combo.Input('schedule_format',options=['CR', 'Deforum']),io.Custom('LORA_LIST').Input('lora_list',optional=True),io.Custom('SCHEDULE').Input('schedule',optional=True)],outputs=[io.Model.Output(display_name='MODEL'),io.Clip.Output(display_name='CLIP'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, mode, model, clip, current_frame, schedule_alias, default_lora, strength_model, strength_clip, schedule_format, lora_list=None, schedule=None):
        _preflight({'mode': mode, 'model': model, 'clip': clip, 'current_frame': current_frame, 'schedule_alias': schedule_alias, 'default_lora': default_lora, 'strength_model': strength_model, 'strength_clip': strength_clip, 'schedule_format': schedule_format, 'lora_list': lora_list, 'schedule': schedule})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-load-scheduled-loras'
        if mode == 'Off':
            print(f'[Info] CR Load Scheduled LoRAs. Disabled.')
            return _output((model, clip, show_help))
        if mode == 'Load default LoRA':
            if default_lora == None:
                return _output((model, clip, show_help))
            if strength_model == 0 and strength_clip == 0:
                return _output((model, clip, show_help))
            model, clip = await _load_lora(model, clip, default_lora, strength_model, strength_clip)
            print(f'[Info] CR Load Scheduled LoRAs. Loading default LoRA {default_lora}.')
            return _output((model, clip, show_help))
        params = keyframe_scheduler(schedule, schedule_alias, current_frame)
        if params == '':
            print(f'[Warning] CR Load Scheduled LoRAs. No LoRA specified in schedule for frame {current_frame}. Using default lora.')
            if default_lora != None:
                model, clip = await _load_lora(model, clip, default_lora, strength_model, strength_clip)
            return _output((model, clip, show_help))
        else:
            parts = params.split(',')
            if len(parts) == 3:
                s_lora_alias = parts[0].strip()
                s_strength_model = float(parts[1].strip())
                s_strength_clip = float(parts[1].strip())
            else:
                print(f'[Warning] CR Simple Value Scheduler. Skipped invalid line: {line}')
                return _output(())
        for l_lora_alias, l_lora_name, l_strength_model, l_strength_clip in lora_list:
            print(l_lora_alias, l_lora_name, l_strength_model, l_strength_clip)
            if l_lora_alias == s_lora_alias:
                print(f'[Info] CR Load Scheduled LoRAs. LoRA alias match found for {s_lora_alias}')
                lora_name = l_lora_name
                break
        if lora_name == '':
            print(f'[Info] CR Load Scheduled LoRAs. No LoRA alias match found for {s_lora_alias}. Frame {current_frame}.')
            return _output(())
        else:
            print(f'[Info] CR Load Scheduled LoRAs. LoRA {lora_name}')
        model, clip = await _load_lora(model, clip, lora_name, s_strength_model, s_strength_clip)
        print(f'[Debug] CR Load Scheduled LoRAs. Loading new LoRA {lora_name}')
        return _output((model, clip, show_help))

NODE_CLASS_MAPPINGS={'CR Load Scheduled Models':CR_LoadScheduledModels,'CR Load Scheduled LoRAs':CR_LoadScheduledLoRAs}
NODE_DISPLAY_NAME_MAPPINGS={'CR Load Scheduled Models': '📑 CR Load Scheduled Models', 'CR Load Scheduled LoRAs': '📑 CR Load Scheduled LoRAs'}
