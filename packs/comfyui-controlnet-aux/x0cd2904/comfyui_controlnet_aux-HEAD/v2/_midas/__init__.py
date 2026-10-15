"""Real depth/normal wrapper composition; resource seam explicitly held."""
import numpy as np
from .._annotator import common_annotator_call
from .original_transformers_math import MidasDetector

async def managed_detector():
    from .managed_components import construct_components
    processor,model=await construct_components()
    return MidasDetector(model,processor)

async def _normal( image, a=np.pi * 2.0, bg_threshold=0.1, resolution=512, **kwargs):

    model = (await managed_detector()).to('cpu')
    #Dirty hack :))
    cb = lambda image, **kargs: model(image, **kargs)[1]
    out = common_annotator_call(cb, image, resolution=resolution, a=a, bg_th=bg_threshold, depth_and_normal=True)
    del model
    return (out, )


async def _depth( image, a=np.pi * 2.0, bg_threshold=0.1, resolution=512, **kwargs):

    # Ref: https://github.com/lllyasviel/ControlNet/blob/main/gradio_depth2image.py
    model = (await managed_detector()).to('cpu')
    out = common_annotator_call(model, image, resolution=resolution, a=a, bg_th=bg_threshold)
    del model
    return (out, )

async def execute(node_id, **values):
    method={'MiDaS-DepthMapPreprocessor':_depth,
            'MiDaS-NormalMapPreprocessor':_normal}[node_id]
    return await method(**values)
