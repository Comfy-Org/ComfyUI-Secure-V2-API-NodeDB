"""Gate before scientific imports, startup mutation, asset RPC and engines."""
from .selection import selected_family


async def execute(node_id, **values):
    selection = selected_family(node_id)
    # These imports retain native ordering: detector captures ONNX_PROVIDERS
    # before wrapper startup checks/mutates AUX_ORT_PROVIDERS. Native empty
    # cache constructors run only after the held authenticated generation gate.
    from .wrappers import DWPose_Preprocessor, AnimalPose_Preprocessor
    cls = {'DWPreprocessor': DWPose_Preprocessor,
           'AnimalPosePreprocessor': AnimalPose_Preprocessor}[node_id]
    return await cls().estimate_pose(selection=selection, **values)
