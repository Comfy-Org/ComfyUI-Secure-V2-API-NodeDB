"""Test-only, unregistered fixture: zero-capability service denial."""
from comfy_api.latest import io,sdk
class AssetDenialProbe(io.ComfyNode):
 SDK_REFS=False
 SDK_PERMISSIONS=()
 @classmethod
 def define_schema(cls):
  return io.Schema(node_id='AssetDenialProbe',inputs=[],outputs=[])
 @classmethod
 async def execute(cls):
  await sdk.ctx().assets.list('input')
  raise AssertionError('asset enumeration escaped zero-permission scope')
