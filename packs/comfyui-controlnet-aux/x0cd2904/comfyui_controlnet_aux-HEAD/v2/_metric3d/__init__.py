"""Approved selection before new imports, config eval or shared state use."""
from .selection import selected_checkpoint


async def execute(node_id, **values):
    selection = selected_checkpoint(values.get('backbone', 'vit-small'))
    from .wrapper import Metric3D_Depth_Map_Preprocessor, Metric3D_Normal_Map_Preprocessor
    wrapper = Metric3D_Depth_Map_Preprocessor if node_id == 'Metric3D-DepthMapPreprocessor' else Metric3D_Normal_Map_Preprocessor
    return await wrapper().execute(selection=selection, **values)
