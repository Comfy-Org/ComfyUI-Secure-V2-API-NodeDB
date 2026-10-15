"""Pinned Single/Cached orchestration around JACK's one T5 implementation.

Cache, context and model math are shared with the main encoder. No alternate
T5 or Qwen model exists here. Learned encoding and extender paths require the
respective owner's complete runtime and remain explicit qualification gates.
"""
import gc
from comfy_api.latest import io, sdk
from .wan_workflow_context import encode_literal, get_extended_prompt, remember_extended_prompt
from .wan_workflow_text_cache import TextEmbeddingCache
from .wan_workflow_resources import logical_name
from .secure_tensor_nodes import _bound_strings


class WanVideoTextEncodeSingle(io.ComfyNode):
    # This node consumes owned JSON recipes and emits raw embedding tensors.
    # The public values adapter performs their reference publication.
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'storage')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoTextEncodeSingle', display_name='WanVideo TextEncodeSingle',
            category='WanVideoWrapper', description='Encodes text prompt into text embedding.',
            inputs=[io.String.Input('prompt',default='',multiline=True),
                io.Custom('WANTEXTENCODER').Input('t5',optional=True),
                io.Boolean.Input('force_offload',optional=True,default=True),
                io.Custom('WANVIDEOMODEL').Input('model_to_offload',optional=True,
                    tooltip='Model to move to offload_device before encoding'),
                io.Boolean.Input('use_disk_cache',optional=True,default=False,
                    tooltip='Cache text embeddings in persistent user and pack storage for faster reuse'),
                io.Combo.Input('device',options=['gpu','cpu'],optional=True,default='gpu',
                    tooltip='Device to run the text encoding on.')],
            outputs=[io.Custom('WANVIDEOTEXTEMBEDS').Output(display_name='text_embeds')])

    @classmethod
    async def execute(cls,prompt,t5=None,force_offload=True,model_to_offload=None,use_disk_cache=False,device='gpu'):
        _bound_strings([prompt])
        context=sdk.current_context()
        encoded=None
        echoshot='[1]' in prompt
        cache=TextEmbeddingCache(context.storage) if use_disk_cache else None
        if cache is not None:
            encoded=await cache.get(prompt)
        if t5 is None and encoded is None:
            raise ValueError('No cached text embeds found for prompts, please provide a T5 encoder.')
        if encoded is None:
            # Unlike the main encoder, Single forwards [prompt] literally:
            # pipes, weights, whitespace and [#] tokens are not parsed here.
            encoded=await encode_literal(t5,prompt,context,force_offload=force_offload,
                                         device=device,model_to_offload=model_to_offload)
            if cache is not None:
                await cache.store_if_absent(prompt,encoded)
        return io.NodeOutput({'prompt_embeds':encoded,'negative_prompt_embeds':None,'echoshot':echoshot})


class WanVideoTextEncodeCached(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'storage')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoTextEncodeCached',display_name='WanVideo TextEncode Cached',
            category='WanVideoWrapper',
            description=('Encodes text prompts into text embeddings. This node loads and completely unloads the T5 after done,  \n'
                'leaving no VRAM or RAM imprint. If prompts have been cached before T5 is not loaded at all.  \n'
                'negative output is meant to be used with NAG, it contains only negative prompt embeddings.  \n\n'
                'Additionally you can provide a Qwen LLM model to extend the positive prompt with either one  \n'
                'of the original Wan templates or a custom system prompt.  \n'),
            inputs=[io.Combo.Input('model_name',options=[],
                    tooltip="These models are loaded from 'ComfyUI/models/text_encoders'",
                    remote=io.RemoteOptions(route='/models/text_encoders',refresh_button=True,control_after_refresh='first')),
                io.Combo.Input('precision',options=['fp32','bf16'],default='bf16'),
                io.String.Input('positive_prompt',default='',multiline=True),
                io.String.Input('negative_prompt',default='',multiline=True),
                io.Combo.Input('quantization',options=['disabled','fp8_e4m3fn'],default='disabled',tooltip='optional quantization method'),
                io.Boolean.Input('use_disk_cache',default=True,
                    tooltip='Cache text embeddings in persistent user and pack storage for faster reuse'),
                io.Combo.Input('device',options=['gpu','cpu'],default='gpu',tooltip='Device to run the text encoding on.'),
                io.Custom('WANVIDEOPROMPTEXTENDER_ARGS').Input('extender_args',optional=True,
                    tooltip='Use this node to extend the prompt with additional text.')],
            outputs=[io.Custom('WANVIDEOTEXTEMBEDS').Output(display_name='text_embeds',tooltip='The text embeddings for both prompts'),
                io.Custom('WANVIDEOTEXTEMBEDS').Output(display_name='negative_text_embeds',tooltip='The text embeddings for the negative prompt only (for NAG)'),
                io.String.Output(display_name='positive_prompt',tooltip='Positive prompt to display prompt extender results')])

    @classmethod
    def validate_inputs(cls,input_types=None,**kwargs):
        name=kwargs.get('model_name')
        return True if name is None or logical_name(name) else 'Wan T5 requires a logical catalogue name'

    @classmethod
    async def execute(cls,model_name,precision,positive_prompt,negative_prompt,quantization='disabled',
                      use_disk_cache=True,device='gpu',extender_args=None):
        _bound_strings([positive_prompt,negative_prompt])
        context=sdk.current_context()
        echoshot='[1]' in positive_prompt
        original_prompt=positive_prompt
        if extender_args is not None:
            remembered=get_extended_prompt(original_prompt,extender_args)
            if remembered is not None:
                positive_prompt=remembered
            else:
                # Stable owner-agreed visual-lane interface. Module is imported
                # only for a real cache miss; no substitute model is installed.
                from .secure_qwen_runtime import load_qwen_resource, extend_qwen_prompt
                qwen=await load_qwen_resource(extender_args['model'],
                    load_device='main_device' if device=='gpu' else 'cpu',precision=precision)
                positive_prompt=await extend_qwen_prompt(qwen=qwen,max_new_tokens=extender_args['max_new_tokens'],
                    prompt=original_prompt,device=device,force_offload=False,
                    custom_system_prompt=extender_args['system_prompt'],seed=extender_args['seed'])
                remember_extended_prompt(original_prompt,extender_args,positive_prompt)
                del qwen
            await context.progress.update(1,3)
        if use_disk_cache:
            positive,negative=await TextEmbeddingCache(context.storage).get_pair(positive_prompt,negative_prompt)
            if positive is not None and negative is not None:
                # The original cache-hit flag is computed before extension;
                # cache-miss main encoding computes its own flag afterward.
                return io.NodeOutput({'prompt_embeds':positive,'negative_prompt_embeds':negative,'echoshot':echoshot},
                                     {'prompt_embeds':negative},positive_prompt)
        from .wan_workflow_text_nodes import LoadWanVideoT5TextEncoder, WanVideoTextEncode
        t5=(await LoadWanVideoT5TextEncoder.execute(model_name,precision,'main_device',quantization))[0]
        await context.progress.update(2 if extender_args is not None else 1,3)
        encoded=(await WanVideoTextEncode.execute(positive_prompt=positive_prompt,negative_prompt=negative_prompt,
            t5=t5,force_offload=False,model_to_offload=None,use_disk_cache=use_disk_cache,device=device))[0]
        await context.progress.update(3 if extender_args is not None else 2,3)
        del t5
        gc.collect()
        return io.NodeOutput(encoded,{'prompt_embeds':encoded['negative_prompt_embeds']},positive_prompt)


NODE_CLASS_MAPPINGS={'WanVideoTextEncodeSingle':WanVideoTextEncodeSingle,'WanVideoTextEncodeCached':WanVideoTextEncodeCached}
