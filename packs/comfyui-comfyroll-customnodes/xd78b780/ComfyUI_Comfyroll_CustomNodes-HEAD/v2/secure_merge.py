"""Bounded public checkpoint loading/merge; stack policy remains pack-side."""
from comfy_api.latest import io, sdk
from .secure_lora import _name, _stack, _weight

class CR_ModelMergeStack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Model Merge Stack', display_name='⛏️ CR Model Merge Stack', category='🧩 Comfyroll Studio/✨ Essential/⛏️ Model Merge', inputs=[io.Combo.Input('switch_1', options=['Off', 'On']), io.Combo.Input('ckpt_name1', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.Float.Input('model_ratio1', default=1.0, min=-100.0, max=100.0, step=0.01), io.Float.Input('clip_ratio1', default=1.0, min=-100.0, max=100.0, step=0.01), io.Combo.Input('switch_2', options=['Off', 'On']), io.Combo.Input('ckpt_name2', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.Float.Input('model_ratio2', default=1.0, min=-100.0, max=100.0, step=0.01), io.Float.Input('clip_ratio2', default=1.0, min=-100.0, max=100.0, step=0.01), io.Combo.Input('switch_3', options=['Off', 'On']), io.Combo.Input('ckpt_name3', options=['None'], remote=io.RemoteOptions(route='/secure-nodes/models/checkpoints', refresh_button=True, static_options=['None'])), io.Float.Input('model_ratio3', default=1.0, min=-100.0, max=100.0, step=0.01), io.Float.Input('clip_ratio3', default=1.0, min=-100.0, max=100.0, step=0.01), io.Custom('MODEL_STACK').Input('model_stack', optional=True)], outputs=[io.Custom('MODEL_STACK').Output(display_name='MODEL_STACK'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, switch_1, ckpt_name1, model_ratio1, clip_ratio1, switch_2, ckpt_name2, model_ratio2, clip_ratio2, switch_3, ckpt_name3, model_ratio3, clip_ratio3, model_stack=None):
        model_stack = _stack(model_stack)
        for name, model_ratio, clip_ratio in ((ckpt_name1, model_ratio1, clip_ratio1), (ckpt_name2, model_ratio2, clip_ratio2), (ckpt_name3, model_ratio3, clip_ratio3)):
            _name(name)
            _weight(model_ratio)
            _weight(clip_ratio)
        model_list = list()
        if model_stack is not None:
            model_list.extend([l for l in model_stack if l[0] != 'None'])
        if ckpt_name1 != 'None' and switch_1 == 'On':
            (model_list.extend([(ckpt_name1, model_ratio1, clip_ratio1)]),)
        if ckpt_name2 != 'None' and switch_2 == 'On':
            (model_list.extend([(ckpt_name2, model_ratio2, clip_ratio2)]),)
        if ckpt_name3 != 'None' and switch_3 == 'On':
            (model_list.extend([(ckpt_name3, model_ratio3, clip_ratio3)]),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Model-Merge-Nodes#cr-model-stack'
        return io.NodeOutput(model_list, show_help)

class CR_ApplyModelMerge(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Apply Model Merge', display_name='⛏️ CR Apply Model Merge', category='🧩 Comfyroll Studio/✨ Essential/⛏️ Model Merge', inputs=[io.Custom('MODEL_STACK').Input('model_stack'), io.Combo.Input('merge_method', options=['Recursive', 'Weighted']), io.Combo.Input('normalise_ratios', options=['Yes', 'No']), io.Float.Input('weight_factor', default=1.0, min=0.0, max=1.0, step=0.01)], outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='model_mix_info'), io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, model_stack, merge_method, normalise_ratios, weight_factor):
        stack=_stack(model_stack)
        _weight(weight_factor)
        if not 0<=weight_factor<=1:
            raise ValueError('weight_factor must be in [0,1]')
        if not stack:
            # Explicit coordinator-approved repair of pinned malformed empty success.
            raise ValueError('No active checkpoints in model merge stack')
        if len(stack)==1:
            name=stack[0][0]
            model,clip,_=await sdk.ctx().models.load_checkpoint(name)
            # Explicit repair: preserve declared MODEL/CLIP/STRING/STRING, not loader extras.
            info='Merge Info:\nOnly one active checkpoint; no merge applied.\nBase Model Name: '+name
            help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Model-Merge-Nodes#cr-apply-model-merge'
            return io.NodeOutput(model,clip,info,help_url)
        sum_model_ratio=sum(row[1] for row in stack)
        sum_clip_ratio=sum(row[2] for row in stack)
        model_mix_info='Merge Info:\nRatios are applied using the Recursive method\n\n'
        for i,(name,model_ratio,clip_ratio) in enumerate(stack):
            merge_model,merge_clip,_=await sdk.ctx().models.load_checkpoint(name)
            # Deliberately retain pinned condition (MODEL sum gates BOTH normalizations).
            if sum_model_ratio!=1 and normalise_ratios=='Yes':
                model_ratio=round(model_ratio/sum_model_ratio,2)
                clip_ratio=round(clip_ratio/sum_clip_ratio,2)
            if merge_method=='Weighted' and i==1:
                model_ratio=1-weight_factor+weight_factor*model_ratio
                clip_ratio=1-weight_factor+weight_factor*clip_ratio
            if i==0:
                # Next public merge clones the receiver before adding donor patches.
                model1,clip1=merge_model,merge_clip
                model_mix_info+='Base Model Name: '+name
            else:
                model1=await model1.merge(merge_model,1-model_ratio)
                clip1=await clip1.merge(merge_clip,1-clip_ratio)
                model_mix_info+='\nModel Name: '+name+'\nModel Ratio: '+str(model_ratio)+'\nCLIP Ratio: '+str(clip_ratio)+'\n'
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Model-Merge-Nodes#cr-apply-model-merge'
        return io.NodeOutput(model1,clip1,model_mix_info,help_url)

NODE_CLASS_MAPPINGS = {
    'CR Model Merge Stack': CR_ModelMergeStack,
    'CR Apply Model Merge': CR_ApplyModelMerge,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Model Merge Stack': '⛏️ CR Model Merge Stack', 'CR Apply Model Merge': '⛏️ CR Apply Model Merge'}
