"""Selection precedes native scientific imports, KMP context and models."""
from .selection import selected_checkpoint


async def execute(**values):
    selection = selected_checkpoint()
    from .wrapper import OpenPose_Preprocessor
    return await OpenPose_Preprocessor().estimate_pose(selection=selection, **values)
