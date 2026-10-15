"""Real published asset composition into the unchanged private V2 graph."""
from ._depth_v2_selection import selected_asset

def validate_materialized_state(state, contract):
    # Called only AFTER the approved resource read. The real Torch tensor
    # class is used, never a parser/fake tensor/SDK facade.
    from collections.abc import Mapping
    import torch
    if not isinstance(state, Mapping) or not state:
        raise TypeError('DepthAnythingV2 requires genuine nonempty tensor state')
    if hasattr(state, '_metadata'):
        raise ValueError('DepthAnythingV2 native metadata correspondence unsupported')
    specs = contract['ordered_tensors']
    if list(state) != [spec['key'] for spec in specs]:
        raise ValueError('DepthAnythingV2 managed state key/order differs from selected native root')
    total = 0
    for spec in specs:
        value = state[spec['key']]
        if not isinstance(value, torch.Tensor):
            raise TypeError('DepthAnythingV2 managed state must be string-to-Tensor')
        if value.device.type != 'cpu' or value.layout != torch.strided:
            raise ValueError('DepthAnythingV2 selected CPU strided state required')
        if str(value.dtype) != spec['dtype'] or list(value.shape) != spec['shape']:
            raise ValueError('DepthAnythingV2 managed state dtype/shape differs from selection')
        total += value.numel() * value.element_size()
    if total != contract['materialized_bytes']:
        raise ValueError('DepthAnythingV2 managed state byte count differs from selection')
    return state

async def execute(image, ckpt_name='depth_anything_v2_vitl.pth', resolution=512):
    selection, row = selected_asset(ckpt_name)
    # Missing selection refuses before these NEW SDK/graph/scientific imports
    # and before any asset RPC/model allocation.
    from comfy_api.latest import sdk
    assets = sdk.ctx().assets
    ref = await assets.resolve(row['catalogue_folder'], row['catalogue_name'])
    if await assets.size(ref) != row['verified_bytes']:
        raise ValueError('DepthAnythingV2 sealed asset size differs from selection')
    if await assets.digest(ref, algorithm='sha256') != row['verified_sha256']:
        raise ValueError('DepthAnythingV2 sealed asset digest differs from selection')
    state = await assets.load_state_dict(ref)
    # A post-read identity check observes changes; actual immutable catalogue
    # authority and cache scope/storage equivalence require the owner's proof.
    if await assets.size(ref) != row['verified_bytes'] or await assets.digest(ref, algorithm='sha256') != row['verified_sha256']:
        raise ValueError('DepthAnythingV2 sealed asset identity changed during read')
    validate_materialized_state(state, row['state_contract'])
    from ._depth_anything_v2_entry import execute as execute_graph
    return execute_graph(image, ckpt_name=ckpt_name, resolution=resolution,
                         state=state, device=selection['torch_device'])
