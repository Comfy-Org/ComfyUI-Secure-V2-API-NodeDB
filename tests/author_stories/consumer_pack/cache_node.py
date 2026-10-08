"""Acceptance-only opt-in DATA cache around actual converted My-Mask nodes.

Normal converted node execution has no automatic cache behavior. This pipeline
consumer publishes only numerical tensor DATA, never models or Python objects.
"""
import hashlib,os
from comfy_api.latest import io,sdk
from .converted import NODE_CLASS_MAPPINGS
from .converted.admission import geometry

PIN='1fdd5c50bfe2e00164f2026871715e201a2eb684'
class CachedMaskAlgorithm(io.ComfyNode):
 SDK_REFS=True
 SDK_PERMISSIONS=('inspect','raw','storage')
 @classmethod
 def define_schema(cls):
  return io.Schema(node_id='ManyAuthorStoryCachedMask',inputs=[io.Mask.Input('mask'),io.Combo.Input('algorithm',options=list(NODE_CLASS_MAPPINGS)),io.String.Input('name'),io.Int.Input('ttl_seconds',default=5,min=1,max=3600)],outputs=[io.Mask.Output(),io.Boolean.Output(),io.Int.Output(),io.String.Output()])
 @classmethod
 async def execute(cls,mask,algorithm,name,ttl_seconds):
  if type(name)is not str or not 1<=len(name.encode('utf-8'))<=32:raise ValueError('cache name bound')
  if algorithm not in NODE_CLASS_MAPPINGS:raise ValueError('unknown algorithm')
  if type(ttl_seconds)is not int or not 1<=ttl_seconds<=3600:raise ValueError('cache request TTL bound')
  geometry(await mask.describe());source=await mask.raw()
  # Public buffer bits plus full source pin/type/shape distinguish artifacts.
  content=source.contiguous().reshape(-1).view(__import__('torch').uint8).numpy().tobytes()
  header=repr((PIN,algorithm,str(source.dtype),list(source.shape),name)).encode()
  key='mask-cache.v1.'+hashlib.sha256(header+b'\0'+content).hexdigest()
  record=await sdk.ctx().storage.read_value(key)
  hit=record['value']is not None
  if hit:
   geometry(await record['value'].describe())
   result=await record['value'].value()
  else:
   computed=await NODE_CLASS_MAPPINGS[algorithm].execute(mask)
   result=await computed.result[0].raw()
   geometry({'shape':list(result.shape)})
   data=await sdk.ValueRef.from_value(result)
   committed=await sdk.ctx().storage.compare_and_set_value(key,record['revision'],data,ttl_seconds=ttl_seconds)
   # A competing writer never changes this call's correctly computed result.
   if not committed['updated']:raise RuntimeError('cache CAS conflict; no stale replacement')
  return io.NodeOutput(await sdk.MaskRef.from_value(result),hit,os.getpid(),key)
