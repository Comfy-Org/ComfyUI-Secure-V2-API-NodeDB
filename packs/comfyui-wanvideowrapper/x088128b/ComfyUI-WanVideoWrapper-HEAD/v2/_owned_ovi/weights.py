"""Public, digest-bound Ovi checkpoint reads at original constructor positions."""
import re
from comfy_api.latest import sdk
from .._wan_catalogue import valid_catalogue_name

MAX_FILE_BYTES = 2 * 1024**3
KEYS = {'folder', 'name', 'bytes', 'sha256'}


def validate_resource(value):
    if type(value) is not dict or set(value) != KEYS:
        raise ValueError('Invalid owned Ovi checkpoint descriptor')
    if value['folder'] not in ('vae', 'mmaudio') or not valid_catalogue_name(value['name']):
        raise ValueError('Ovi checkpoint requires its original confined model catalogue')
    if type(value['bytes']) is not int or not 0 < value['bytes'] <= MAX_FILE_BYTES:
        raise ValueError('Ovi checkpoint exceeds the bounded 2 GiB file domain')
    if type(value['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', value['sha256']) is None:
        raise ValueError('Ovi checkpoint requires an exact SHA256')
    return value


async def describe_resource(folder, name):
    if folder not in ('vae', 'mmaudio') or not valid_catalogue_name(name):
        raise ValueError('Ovi checkpoint requires its original confined model catalogue')
    assets = sdk.current_context().assets
    ref = await assets.resolve(folder, name)
    return validate_resource({'folder': folder, 'name': name,
        'bytes': await assets.size(ref), 'sha256': await assets.digest(ref)})


async def load_bound_state_dict(resource):
    """Core's real weights-only loader and native member-unwrapping policy.

Called exactly where the original constructor called load_torch_file, after
the preceding original module construction and RNG effects. No decoder,
pickle policy, cache or direct host path is reimplemented here.
"""
    validate_resource(resource)
    assets = sdk.current_context().assets
    ref = await assets.resolve(resource['folder'], resource['name'])
    if await assets.size(ref) != resource['bytes'] or await assets.digest(ref) != resource['sha256']:
        raise ValueError('Ovi checkpoint changed since loader execution')
    state = await assets.load_state_dict(ref)
    if await assets.size(ref) != resource['bytes'] or await assets.digest(ref) != resource['sha256']:
        raise ValueError('Ovi checkpoint changed while loading')
    return state
