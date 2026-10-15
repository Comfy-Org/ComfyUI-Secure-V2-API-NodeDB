"""Fail closed before NEW DensePose scientific imports or executable archive RPC."""
from .selection import selected_checkpoint


async def execute(**values):
    selection = selected_checkpoint(values.get('model', 'densepose_r50_fpn_dl.torchscript'))
    from .wrapper import DensePose_Preprocessor
    return await DensePose_Preprocessor().execute(selection=selection, **values)
