"""Unmodified source algorithms behind bounded typed Secure Nodes inputs."""
from comfy_api.latest import io, sdk
from .src.immac_tools import nodes as source
from .src.immac_tools import forwarding_nodes as forwarding
from ._bounded import description,raw,sigma_plan,image_plan,publish,check,MAX_SEQUENCE

class ConcatenateSigmasNode(source.ConcatenateSigmasNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    async def execute(cls,sigmas_1,sigmas_2):
        if sigmas_1 is None: return io.NodeOutput(sigmas_2)
        if sigmas_2 is None: return io.NodeOutput(sigmas_1)
        sigma_plan('concat',[await description(sigmas_1),await description(sigmas_2)])
        result=source.ConcatenateSigmasNode.execute(await raw(sigmas_1),await raw(sigmas_2))
        return io.NodeOutput(*await publish(result,['SIGMAS']))

class SpliceSigmasAtNode(source.SpliceSigmasAtNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    async def execute(cls,sigmas_a,sigmas_b,boundary,include_boundary):
        if sigmas_a is None: return io.NodeOutput(sigmas_b,None,sigmas_b)
        if sigmas_b is None: return io.NodeOutput(sigmas_a,sigmas_a,None)
        sigma_plan('splice',[await description(sigmas_a),await description(sigmas_b)])
        result=source.SpliceSigmasAtNode.execute(await raw(sigmas_a),await raw(sigmas_b),boundary,include_boundary)
        return io.NodeOutput(*await publish(result,['SIGMAS']*3))

class ResampleSigmas(source.ResampleSigmas):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    async def execute(cls,sigmas,steps):
        if sigmas is None: return io.NodeOutput(None)
        sigma_plan('resample',[await description(sigmas)],steps)
        return io.NodeOutput(*await publish(source.ResampleSigmas.execute(await raw(sigmas),steps),['SIGMAS']))

class SkipEveryNthImages(source.SkipEveryNthImages):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    async def execute(cls,images,n):
        if isinstance(images,sdk.Ref) and images.kind in ('SIGMAS','TENSOR','IMAGE','MASK'):
            (shape,count,size),_=await description(images)
            batch=shape[0] if shape else 0
            check(size,6*size+batch*64+1_048_576,count)
            images=await raw(images)
        elif type(images) in (list,tuple) and len(images)>MAX_SEQUENCE:
            raise ValueError('ImmacTools sequence work budget exceeded')
        return io.NodeOutput(*await publish(source.SkipEveryNthImages.execute(images,n),['TENSOR','ANY']))

class MatchContrastNode(source.MatchContrastNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    async def execute(cls,image,reference,channel_mode,strength):
        image_plan([await description(image),await description(reference)])
        result=source.MatchContrastNode.execute(await raw(image),await raw(reference),channel_mode,strength)
        return io.NodeOutput(*await publish(result,['IMAGE']))

class SwitchNode(source.SwitchNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
class ForwardAnyNode(forwarding.ForwardAnyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
class ForwardConditioningNode(forwarding.ForwardConditioningNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
class ForwardModelNode(forwarding.ForwardModelNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
