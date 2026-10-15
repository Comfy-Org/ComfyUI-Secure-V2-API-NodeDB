"""Private durable full-library Prompt; native class/schema preserved.
No typed-library fallback, provider expansion or profile grant.
"""
from comfy_api.latest import io
from .secure_durable_text_node import fingerprint, _text_input, _seed_input
from .secure_services.durable_wildcard_prompt import encode_saved_prompt

class Prompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Prompt (LoraManager)', category='Lora Manager/conditioning',
            description='Encodes a text prompt using a CLIP model into an embedding that can be used to guide the diffusion model towards generating specific images. Supports dynamic trigger words inputs and runtime wildcard expansion.',
            inputs=[_text_input('Enter prompt... /character, /artist, /wildcard for quick search',
                'The text to be encoded. Wildcard references inserted with /wildcard are expanded at runtime.'),
                io.Clip.Input('clip',tooltip='The CLIP model used for encoding the text.'), _seed_input(),
                io.String.Input('trigger_words1', optional=True, force_input=True,
                    tooltip='Trigger words to prepend. Connect to add more inputs.')],
            hidden=[io.Hidden.prompt, io.Hidden.unique_id],
            outputs=[io.Conditioning.Output(display_name='CONDITIONING', tooltip='A conditioning containing the embedded text used to guide the diffusion model.'),io.String.Output(display_name='PROMPT')],
            accept_all_inputs=True)

    @classmethod
    async def execute(cls, text, clip, seed=None, prompt=None, unique_id=None, **kwargs):
        return io.NodeOutput(*await encode_saved_prompt(clip, text, seed, **kwargs))

    @classmethod
    def fingerprint_inputs(cls, text=None, seed=None, **kwargs):
        hidden = cls.hidden
        return fingerprint(text, seed, kwargs.get('prompt', getattr(hidden,'prompt',None)),
            kwargs.get('unique_id', getattr(hidden,'unique_id',None)))
