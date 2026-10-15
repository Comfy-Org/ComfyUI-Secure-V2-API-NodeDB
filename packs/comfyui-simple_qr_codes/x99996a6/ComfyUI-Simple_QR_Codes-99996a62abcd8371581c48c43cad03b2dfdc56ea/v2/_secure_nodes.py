"""Complete twelve-node V3 conversion; source math remains pack-side."""
from comfy_api.latest import io
from . import _bounds
from .nodes.qr_codes import QRCodesLogo,QRCodesSimple,QRCodesSimpleBW
from .nodes.qr_codes_style_color import QRCodesStyle
from .nodes.qr_codes_segno import QRCodesSegnoFull
from .nodes.qr_codes_segno_simple import QRCodesSegnoSimple
from .nodes.qr_codes_segno_logo import QRCodesSegnoLogo
from .nodes.qr_codes_reader import QRCodeReader
from .nodes.create_frame_01 import CreateCornerFrame,CreateSolidFrame,CreateTextFrame
from .nodes.show_data import ShowData
SOURCES={
 '🛸 QRCodes (Segno Full Version)':QRCodesSegnoFull,
 '🛸 QRCodes (Segno Simple Version)':QRCodesSegnoSimple,
 '🛸 QRCodes (Segno Simple Logo)':QRCodesSegnoLogo,
 '🛰️ QRCodes (Simple Color)':QRCodesSimple,
 '🛰️ QRCodes (Simple Logo)':QRCodesLogo,
 '🛰️ QRCodes (Simple Style)':QRCodesStyle,
 '🛰️ QRCodes (Simple B&W)':QRCodesSimpleBW,
 '🎭 QRCodeReader':QRCodeReader,'🎭 ShowData':ShowData,
 '🚢 CreateCornerFrame':CreateCornerFrame,
 '🚢 CreateSolidFrame':CreateSolidFrame,'🚢 CreateTextFrame':CreateTextFrame}
KINDS={'IMAGE':io.Image,'MASK':io.Mask,'STRING':io.String,'INT':io.Int,'*':io.AnyType}
def schema(node_id,source):
 fields=source.INPUT_TYPES(); inputs=[]
 for group in ('required','optional'):
  for name,spec in fields.get(group,{}).items():
   kind=spec[0]; options=dict(spec[1]) if len(spec)>1 else {}
   if 'forceInput' in options:
    flag=options.pop('forceInput')
    if str(kind)=='*':options['extra_dict']={'forceInput':flag}
    else:options['force_input']=flag
   if group=='optional': options['optional']=True
   if isinstance(kind,list):inputs.append(io.Combo.Input(name,options=kind,**options))
   else:inputs.append(KINDS[str(kind)].Input(name,**options))
 names=getattr(source,'RETURN_NAMES',source.RETURN_TYPES)
 listed=getattr(source,'OUTPUT_IS_LIST',())
 outputs=[KINDS[kind].Output(display_name=names[i],is_output_list=listed[i] if i<len(listed) else False)
          for i,kind in enumerate(source.RETURN_TYPES)]
 return io.Schema(node_id=node_id,category=source.CATEGORY,inputs=inputs,outputs=outputs,
  hidden=[io.Hidden.unique_id] if source is ShowData else [],
  is_input_list=bool(getattr(source,'INPUT_IS_LIST',False)),
  is_output_node=bool(getattr(source,'OUTPUT_NODE',False)))
def create(node_id,source):
 class Converted(io.ComfyNode):
  SDK_REFS=False
  SDK_PERMISSIONS=('raw',)
  FUNCTION='execute'
  @classmethod
  def define_schema(cls):return schema(node_id,source)
  @classmethod
  def execute(cls,**values):
   if source is ShowData:
    _bounds.value_work(values['input'])
    text=source().render_data(values['input'])
    if len(text.encode('utf8'))>65536:raise ValueError('display result text workload exceeded')
    return io.NodeOutput(ui={'data':text})
   _bounds.preflight(source,values)
   return io.NodeOutput(*getattr(source(),source.FUNCTION)(**values))
 Converted.__name__=source.__name__+'Secure'; Converted.__qualname__=Converted.__name__
 Converted.__module__=__name__
 return Converted
NODE_CLASS_MAPPINGS={node_id:create(node_id,source) for node_id,source in SOURCES.items()}
globals().update({cls.__name__:cls for cls in NODE_CLASS_MAPPINGS.values()})
