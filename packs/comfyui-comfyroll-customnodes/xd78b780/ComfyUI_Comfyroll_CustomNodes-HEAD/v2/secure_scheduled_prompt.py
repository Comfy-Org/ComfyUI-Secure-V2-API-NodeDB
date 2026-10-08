"""Scheduled prompt tensor math stays pack-side under explicit raw authority."""
from comfy_api.latest import io,sdk
from .categories import icons
from .secure_schedules import _guard
from .secure_sdxl import _bounded
from .secure_tensors import CR_ConditioningMixer

class CR_EncodeScheduledPrompts(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Encode Scheduled Prompts',display_name='📝 CR Encode Scheduled Prompts',category=icons['Comfyroll/Animation/Prompt'],
            inputs=[io.Clip.Input('clip'),io.String.Input('current_prompt',multiline=True),io.String.Input('next_prompt',multiline=True),
                    io.Float.Input('weight',default=0.0,min=-9999.0,max=9999.0,step=0.01)],
            outputs=[io.Conditioning.Output(display_name='CONDITIONING'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,clip,current_prompt,next_prompt,weight):
        _guard(dict(current_prompt=current_prompt,next_prompt=next_prompt,weight=weight))
        # Preserve next-before-current encode order, even at weight 0 or 1.
        tokens=await clip.tokenize(str(next_prompt));_bounded(tokens)
        conditioning_from=await (await clip.encode_from_tokens(tokens)).value()
        tokens=await clip.tokenize(str(current_prompt));_bounded(tokens)
        conditioning_to=await (await clip.encode_from_tokens(tokens)).value()
        print(weight)
        # Pinned CR Conditioning Mixer Average is the identical pack-side tensor algorithm.
        # Its preflight bounds shapes/input bytes/projected broadcast and pooled temporaries.
        mixed=CR_ConditioningMixer.execute('Average',conditioning_from,conditioning_to,weight).result[0]
        result=await sdk.CondRef.from_value(mixed)
        return io.NodeOutput(result,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Prompt-Nodes#cr-encode-scheduled-prompts')
NODE_CLASS_MAPPINGS={'CR Encode Scheduled Prompts':CR_EncodeScheduledPrompts}
NODE_DISPLAY_NAME_MAPPINGS={'CR Encode Scheduled Prompts':'📝 CR Encode Scheduled Prompts'}

