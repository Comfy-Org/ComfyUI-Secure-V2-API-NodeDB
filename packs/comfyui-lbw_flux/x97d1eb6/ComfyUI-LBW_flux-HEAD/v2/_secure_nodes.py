"""Bounded parser wrapper; original parser/math remains byte-exact."""
from comfy_api.latest import io
from .LBW_flux import LoraBlockWeight_Flux as Source

MAX_TEXT_BYTES=65536
MAX_INDICES=65536
def preflight(value):
 if type(value) is not str:raise TypeError('text string required')
 if len(value.encode('utf-8'))>MAX_TEXT_BYTES:raise ValueError('text byte budget exceeded')
 work=0
 for item in value.split(','):
  item=item.strip()
  if '-' in item:
   try:start,end=map(int,item.split('-'))
   except ValueError:continue
   work+=max(0,end-start+1)
  else:
   try:int(item)
   except ValueError:continue
   work+=1
  if work>MAX_INDICES:raise ValueError('expanded parser work budget exceeded')

class LoraBlockWeightFluxSecure(io.ComfyNode):
 SDK_REFS=False
 SDK_PERMISSIONS=()
 FUNCTION='execute'
 @classmethod
 def define_schema(cls):
  spec=Source.INPUT_TYPES()['required']['layer_or_multi_layer']
  return io.Schema(node_id='LoraBlockWeight_Flux',display_name='LoraBlockWeight_Flux',category=Source.CATEGORY,inputs=[io.String.Input('layer_or_multi_layer',**spec[1])],outputs=[io.String.Output(display_name='block_vector')])
 @classmethod
 def execute(cls,layer_or_multi_layer):
  preflight(layer_or_multi_layer)
  return io.NodeOutput(*Source().test(layer_or_multi_layer))
NODE_CLASS_MAPPINGS={'LoraBlockWeight_Flux':LoraBlockWeightFluxSecure}
NODE_DISPLAY_NAME_MAPPINGS={'LoraBlockWeight_Flux':'LoraBlockWeight_Flux'}
