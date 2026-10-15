"""Actual Text/Prompt IDs over the saved public-library consumer.

Direct-dispatch checkpoint only. Dynamic slot frontend, authenticated library,
cache-fingerprint host binding and full extension registration remain pending.
"""
import re

from comfy_api.latest import io
from .secure_algorithms.bounds import bounded_json
from .secure_services.managed_wildcards import expand_saved_text, encode_saved_prompt

_WILDCARD = re.compile(r'__([\w\s.\-+/*\\]+?)__')
_OPTION = re.compile(r'{([^{}]*?)}')


def _dynamic(text):
    return isinstance(text, str) and bool(_WILDCARD.search(text) or _OPTION.search(text))


def _link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], (int, float))


def _linked_rerun(prompt, unique_id):
    if not isinstance(prompt, dict) or unique_id is None:
        return True
    node = prompt.get(str(unique_id))
    if not isinstance(node, dict) or not isinstance(node.get('inputs'), dict):
        return True
    value = node['inputs'].get('text')
    if not _link(value):
        return _dynamic(value)
    upstream = prompt.get(value[0])
    if not isinstance(upstream, dict) or not isinstance(upstream.get('inputs'), dict):
        return True
    return any(_link(item) or _dynamic(item) for item in upstream['inputs'].values())


def fingerprint(text, seed=None, prompt=None, unique_id=None):
    bounded_json([text, seed, prompt, unique_id])
    if seed is not None:
        return False
    if _dynamic(text) or (text is None and _linked_rerun(prompt, unique_id)):
        return float('nan')
    return False


def _text_input(placeholder, tooltip):
    return io.MultiType.Input('text', types=[io.Custom('AUTOCOMPLETE_TEXT_PROMPT'), io.String],
        tooltip=tooltip, extra_dict={'widgetType':'AUTOCOMPLETE_TEXT_PROMPT', 'placeholder':placeholder})


def _seed_input():
    return io.Int.Input('seed', optional=True, force_input=True,
        tooltip='Optional seed for wildcard generation. Leave unconnected for non-deterministic wildcard expansion.')


class Text(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Text (LoraManager)', category='Lora Manager/utils',
            inputs=[_text_input('Enter text... /character, /artist, /wildcard for quick search',
                'The text output. Wildcard references inserted with /wildcard are expanded at runtime.'), _seed_input()],
            hidden=[io.Hidden.prompt, io.Hidden.unique_id], outputs=[io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, text, seed=None, prompt=None, unique_id=None):
        return io.NodeOutput(await expand_saved_text(text, seed))

    @classmethod
    def fingerprint_inputs(cls, text=None, seed=None, **kwargs):
        hidden = cls.hidden
        return fingerprint(text, seed, kwargs.get('prompt', getattr(hidden,'prompt',None)),
            kwargs.get('unique_id', getattr(hidden,'unique_id',None)))


class Prompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Prompt (LoraManager)', category='Lora Manager/conditioning',
            inputs=[_text_input('Enter prompt... /character, /artist, /wildcard for quick search',
                'The text to be encoded. Wildcard references inserted with /wildcard are expanded at runtime.'),
                io.Clip.Input('clip',tooltip='The CLIP model used for encoding the text.'), _seed_input(),
                io.String.Input('trigger_words1', optional=True, force_input=True,
                    tooltip='Trigger words to prepend. Connect to add more inputs.')],
            hidden=[io.Hidden.prompt, io.Hidden.unique_id],
            outputs=[io.Conditioning.Output(display_name='CONDITIONING'),io.String.Output(display_name='PROMPT')],
            accept_all_inputs=True)

    @classmethod
    async def execute(cls, text, clip, seed=None, prompt=None, unique_id=None, **kwargs):
        return io.NodeOutput(*await encode_saved_prompt(clip, text, seed, **kwargs))

    @classmethod
    def fingerprint_inputs(cls, text=None, seed=None, **kwargs):
        hidden = cls.hidden
        return fingerprint(text, seed, kwargs.get('prompt', getattr(hidden,'prompt',None)),
            kwargs.get('unique_id', getattr(hidden,'unique_id',None)))
