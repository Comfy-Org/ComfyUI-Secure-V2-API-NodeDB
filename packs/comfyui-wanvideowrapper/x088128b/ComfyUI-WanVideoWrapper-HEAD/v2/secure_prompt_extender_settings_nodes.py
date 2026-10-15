"""Immutable prompt/name settings only; never loads or runs Qwen models."""
from ._wan_catalogue import valid_catalogue_name
from comfy_api.latest import io
from .qwen.system_prompt import SYSTEM_PROMPT_MAP
from .secure_tensor_nodes import _bound_payload

SYSTEM_PROMPT_KEYS = [item['label'] for item in SYSTEM_PROMPT_MAP]


class WanVideoPromptExtenderSelect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoPromptExtenderSelect',
            display_name='Wan Video Prompt Extender Select', category='WanVideoWrapper', inputs=[
                io.Combo.Input('model', options=[],
                    remote=io.RemoteOptions(route='/models/text_encoders', refresh_button=True)),
                io.Int.Input('max_new_tokens', default=512, min=1, max=2048, step=1,
                    tooltip='Maximum number of new tokens to generate.'),
                io.Combo.Input('system_prompt', options=SYSTEM_PROMPT_KEYS,
                    tooltip='System prompt to use for the model.'),
                io.String.Input('custom_system_prompt', default='', force_input=True, optional=True,
                    tooltip='Custom system prompt to use instead of the predefined ones.'),
                io.Int.Input('seed', default=0, min=0, max=0xffffffffffffffff, optional=True),
            ], outputs=[io.Custom('WANVIDEOPROMPTEXTENDER_ARGS').Output(display_name='extender_args')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        if "model" in kwargs and not valid_catalogue_name(kwargs["model"]):
            return "Prompt extender requires a confined logical model name"
        if "system_prompt" in kwargs and kwargs["system_prompt"] not in SYSTEM_PROMPT_KEYS:
            return "Unknown Wan prompt extender system prompt"
        for name, lower, upper in (("max_new_tokens", 1, 2048), ("seed", 0, 0xffffffffffffffff)):
            if name in kwargs and (type(kwargs[name]) is not int or not lower <= kwargs[name] <= upper):
                return "Wan prompt extender integer settings exceed their declared bounds"
        custom = kwargs.get("custom_system_prompt")
        if custom is not None and (not isinstance(custom, str) or len(custom.encode("utf-8")) > 65536):
            return "Wan custom system prompt exceeds64KiB"
        return True

    @classmethod
    def execute(cls, model, system_prompt, max_new_tokens, custom_system_prompt=None, seed=0):
        validation = cls.validate_inputs(model=model, system_prompt=system_prompt, max_new_tokens=max_new_tokens, custom_system_prompt=custom_system_prompt, seed=seed)
        if validation is not True:
            raise ValueError(validation)
        _bound_payload((model, system_prompt, max_new_tokens, custom_system_prompt, seed))
        if custom_system_prompt is None:
            sys_prompt = next((item['prompt'] for item in SYSTEM_PROMPT_MAP if item['label'] == system_prompt), '')
        else:
            sys_prompt = custom_system_prompt
        # Literal 'gpu' is the pinned settings marker, not a device allocation
        # or policy grant. Its separate model-loading/generation consumer is pending.
        settings = {'model': model, 'system_prompt': sys_prompt, 'max_new_tokens': max_new_tokens,
                    'device': 'gpu', 'force_offload': True, 'seed': seed}
        _bound_payload(settings)
        return io.NodeOutput(settings)


NODE_CLASS_MAPPINGS = {'WanVideoPromptExtenderSelect': WanVideoPromptExtenderSelect}
