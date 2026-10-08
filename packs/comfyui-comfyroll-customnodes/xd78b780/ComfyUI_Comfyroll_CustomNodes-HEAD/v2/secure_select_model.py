"""Bounded public checkpoint selection with explicit missing-selection failure."""
from comfy_api.latest import io,sdk
from .secure_schedules import _guard
from .secure_lora import _name
class CR_SelectModel(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Select Model',display_name='🔮 CR Select Model',category='🧩 Comfyroll Studio/✨ Essential/📦 Core',inputs=[io.Combo.Input('ckpt_name1',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints',refresh_button=True, static_options=['None'])), io.Combo.Input('ckpt_name2',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints',refresh_button=True, static_options=['None'])), io.Combo.Input('ckpt_name3',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints',refresh_button=True, static_options=['None'])), io.Combo.Input('ckpt_name4',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints',refresh_button=True, static_options=['None'])), io.Combo.Input('ckpt_name5',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints',refresh_button=True, static_options=['None'])), io.Int.Input('select_model',default=1,min=1,max=5)],outputs=[io.Model.Output(display_name='MODEL'),io.Clip.Output(display_name='CLIP'),io.Vae.Output(display_name='VAE'),io.String.Output(display_name='ckpt_name'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,ckpt_name1,ckpt_name2,ckpt_name3,ckpt_name4,ckpt_name5,select_model):
        _guard(dict(ckpt_name1=ckpt_name1,ckpt_name2=ckpt_name2,ckpt_name3=ckpt_name3,ckpt_name4=ckpt_name4,ckpt_name5=ckpt_name5,select_model=select_model))
        if select_model==1:name=ckpt_name1
        elif select_model==2:name=ckpt_name2
        elif select_model==3:name=ckpt_name3
        elif select_model==4:name=ckpt_name4
        elif select_model==5:name=ckpt_name5
        else:raise ValueError('Invalid checkpoint selection: choose one of 1..5')
        if name=='None':raise ValueError('No checkpoint selected')
        name=_name(name)
        model,clip,vae=await sdk.ctx().models.load_checkpoint(name)
        return io.NodeOutput(model,clip,vae,name,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-select-model')
NODE_CLASS_MAPPINGS={'CR Select Model':CR_SelectModel}
NODE_DISPLAY_NAME_MAPPINGS={'CR Select Model':'🔮 CR Select Model'}
