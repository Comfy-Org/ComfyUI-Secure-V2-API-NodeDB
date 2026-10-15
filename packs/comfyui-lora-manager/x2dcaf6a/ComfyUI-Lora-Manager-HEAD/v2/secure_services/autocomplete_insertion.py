"""Native tip correspondence for exact current managed LoRA logical names.

No scanner paths or substring-alias ownership are fabricated. Other native
path queries require a selected ordered scanner namespace and visibly refuse.
Authored data remains separate from weight headers. All reads use sdk.ctx().
"""
from comfy_api.latest import sdk
from .managed_library import _logical, _syntax_format
from .durable_model_records import read_record

MAX_NAMES = 2048


def require_current_name(relative_path, names):
    # This profile is selected by the actual logical catalogue caller, not a
    # fabricated host path or a scanner substring match that cannot be proved.
    relative_path = _logical(relative_path)
    if type(names) is not list or len(names) > MAX_NAMES:
        raise ValueError('Autocomplete catalogue exceeds entry bounds')
    for name in names:
        _logical(name)
    if len(set(names)) != len(names):
        raise ValueError('Duplicate autocomplete catalogue name')
    if relative_path not in names:
        raise ValueError('Autocomplete scanner alias ownership is not selected')
    return relative_path


def usage_payload(metadata):
    # Native service returns lora.get(usage_tips, '') unchanged. Its handler
    # then applies `usage_tips or ""`: do not borrow pool's str normalization.
    tips = '' if metadata is None else metadata.get('usage_tips', '')
    return {'success': True, 'usage_tips': tips or ''}


async def read_usage_tips(relative_path):
    names = await sdk.ctx().assets.list('loras')
    name = require_current_name(relative_path, names)
    # Resolve/digest once through the existing unchanged durable adapter;
    # permission/corruption/refusal propagates. Missing authored record alone
    # is the real new-record/no-tip case, never missing producer authority.
    current = await read_record(name)
    return usage_payload(current['metadata'])


async def read_insertion_inputs(relative_path):
    # Available to a genuine registered pack consumer through the real SDK.
    # No new frontend endpoint is invented for this internal composition.
    payload = await read_usage_tips(relative_path)
    syntax_format = await _syntax_format()
    return {'syntax_format': syntax_format, 'usage_response': payload}
