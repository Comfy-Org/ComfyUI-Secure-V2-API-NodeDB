"""Selection before NEW vendor/scientific imports, environment or config eval."""
from .selection import selected_checkpoint


async def execute(**values):
    selection = selected_checkpoint()
    from .wrapper import Uniformer_SemSegPreprocessor
    return await Uniformer_SemSegPreprocessor().semantic_segmentate(selection=selection, **values)
