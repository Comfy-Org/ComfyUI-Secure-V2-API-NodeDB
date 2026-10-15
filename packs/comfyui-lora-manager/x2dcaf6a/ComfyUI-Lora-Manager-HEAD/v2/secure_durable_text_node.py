"""Original Text adapter; authored-library backing and lifecycle qualification remain pending."""
import re

from comfy_api.latest import io
from .secure_algorithms.bounds import bounded_json
from .secure_services.durable_wildcard_library import expand_saved_text

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
    SDK_PERMISSIONS = ('storage',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Text (LoraManager)', category='Lora Manager/utils',
            description='A simple text input node with autocomplete support for tags, styles, and wildcard expansion.',
            inputs=[_text_input('Enter text... /character, /artist, /wildcard for quick search',
                'The text output. Wildcard references inserted with /wildcard are expanded at runtime.'), _seed_input()],
            hidden=[io.Hidden.prompt, io.Hidden.unique_id], outputs=[io.String.Output(display_name='STRING', tooltip='The text output.')])

    @classmethod
    async def execute(cls, text, seed=None, prompt=None, unique_id=None):
        return io.NodeOutput(await expand_saved_text(text, seed))

    @classmethod
    def fingerprint_inputs(cls, text=None, seed=None, **kwargs):
        hidden = cls.hidden
        return fingerprint(text, seed, kwargs.get('prompt', getattr(hidden,'prompt',None)),
            kwargs.get('unique_id', getattr(hidden,'unique_id',None)))
