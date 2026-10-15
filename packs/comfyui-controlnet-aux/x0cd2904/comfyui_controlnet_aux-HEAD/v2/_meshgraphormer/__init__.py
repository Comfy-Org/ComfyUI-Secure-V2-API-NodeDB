"""Unsupported setup/raw geometry refuses before NEW imports or asset RPC."""
from .selection import selected_construction


async def execute(**values):
    selection = selected_construction()
    from .selection import prepare_construction
    construction = await prepare_construction(selection)
    from .wrapper import Mesh_Graphormer_Depth_Map_Preprocessor
    return await Mesh_Graphormer_Depth_Map_Preprocessor().execute(selection=selection, construction=construction, **values)


async def execute_impact(**values):
    # Retain the same hard MANO/vendor refusal before scientific imports,
    # asset RPC, custom detector calls, or any model construction.
    selection = selected_construction()
    from .selection import prepare_construction
    construction = await prepare_construction(selection)
    from .impact_wrapper import Mesh_Graphormer_With_ImpactDetector_Depth_Map_Preprocessor
    return await Mesh_Graphormer_With_ImpactDetector_Depth_Map_Preprocessor().execute(selection=selection, construction=construction, **values)
