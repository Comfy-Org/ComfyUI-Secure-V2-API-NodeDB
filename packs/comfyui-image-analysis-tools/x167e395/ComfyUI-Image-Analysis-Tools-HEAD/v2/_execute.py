"""Pack-owned admission, raw numerical computation and public publication."""
from importlib import import_module
from comfy_api.latest import io, sdk
from ._admission import admit, admit_outputs

def execution_rng(np):
    # Native RandomState draws within one execution; fresh local entropy
    # normalizes ambient continuation without mutating shared NumPy RNG state.
    return np.random.RandomState()

async def execute(algorithm_name,fields):
    await admit(algorithm_name,fields)
    image=await fields['image'].raw()
    algorithm=import_module('.algorithms.'+algorithm_name,__package__)
    fields=dict(fields,image=image)
    if algorithm_name=='color_harmony_analyzer':fields['rng']=execution_rng(algorithm.np)
    from . import _render
    with _render.scope():
        result=algorithm.compute(**fields)
        admit_outputs(result)
        import torch
        published=[]
        for value in result:
            published.append(await sdk.ImageRef.from_value(value) if isinstance(value,torch.Tensor) else value)
        return io.NodeOutput(*published)
