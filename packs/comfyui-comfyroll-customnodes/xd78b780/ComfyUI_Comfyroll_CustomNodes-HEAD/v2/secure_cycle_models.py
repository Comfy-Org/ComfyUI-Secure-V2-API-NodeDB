"""Pinned model-selection math plus explicit coordinator-approved output-position repair."""
from comfy_api.latest import io, sdk
from .secure_schedules import _guard
from .secure_lora import _name

def _preflight(values):
    _guard(values)
    rows=values['model_list'];loops=values['loops']
    if rows is not None and (not isinstance(rows,(list,tuple)) or len(rows)>256):
        raise ValueError('Model cycler list exceeds bound')
    if isinstance(loops,int) and (abs(loops)>1000 or max(0,loops)*len(rows or [])>16384):
        raise ValueError('Model cycler projected loop workload exceeds bound')

class CR_CycleModels(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Cycle Models',display_name='CR Cycle Models (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',inputs=[io.Combo.Input('mode', options=['Off', 'Sequential']), io.Model.Input('model'), io.Clip.Input('clip'), io.Custom('MODEL_LIST').Input('model_list'), io.Int.Input('frame_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)],outputs=[io.Model.Output(display_name='MODEL'),io.Clip.Output(display_name='CLIP'),io.Vae.Output(display_name='VAE'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls,mode,model,clip,model_list,frame_interval,loops,current_frame):
        _preflight(dict(mode=mode,model=model,clip=clip,model_list=model_list,frame_interval=frame_interval,loops=loops,current_frame=current_frame))
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Cycler-Nodes#cr-cycle-models'
        model_params=[]
        if model_list:
            for _ in range(loops):model_params.extend(model_list)
        if mode=='Off':
            # Approved repair: no inactive VAE can be fabricated from absent input.
            return io.NodeOutput(model,clip,None,help_url)
        elif mode=='Sequential':
            if current_frame==0:return io.NodeOutput(model,clip,None,help_url)
            index=(current_frame//frame_interval)%len(model_params)
            alias,name=model_params[index]
            name=_name(name)
            selected_model,selected_clip,selected_vae=await sdk.ctx().models.load_checkpoint(name)
            return io.NodeOutput(selected_model,selected_clip,selected_vae,help_url)

NODE_CLASS_MAPPINGS={'CR Cycle Models':CR_CycleModels}
NODE_DISPLAY_NAME_MAPPINGS={'CR Cycle Models':'CR Cycle Models (Legacy)'}

