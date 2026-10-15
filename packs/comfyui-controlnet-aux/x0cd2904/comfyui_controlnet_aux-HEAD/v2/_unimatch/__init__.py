"""Native frame-count assertion before selection, NEW imports or asset RPC."""
from .selection import selected_checkpoint


async def execute(image, ckpt_name, backward_flow=False, bidirectional_flow=False):
    assert len(image) > 1, "[Unimatch] Requiring as least two frames as an optical flow estimator. Only use this node on video input."
    selection = selected_checkpoint(ckpt_name)
    from .wrapper import Unimatch_OptFlowPreprocessor
    return await Unimatch_OptFlowPreprocessor().estimate(image, ckpt_name, backward_flow, bidirectional_flow, selection=selection)
