"""Acceptance-only wheel execution and default-network authority control."""
import errno,json,socket
from comfy_api.latest import io
class RuntimeAuthorityProbe(io.ComfyNode):
 SDK_REFS=True
 SDK_PERMISSIONS=()
 @classmethod
 def define_schema(cls):
  return io.Schema(node_id='ManyRuntimeAuthorityProbe',inputs=[io.Int.Input('port',min=1,max=65535)],outputs=[io.String.Output()])
 @classmethod
 async def execute(cls,port):
  import cv2,numpy as np,torch
  mask=np.zeros((4,4),dtype=np.uint8);mask[1:3,1:3]=1
  contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  assert len(contours)==1 and torch.from_numpy(mask).sum().item()==4
  try:
   connection=socket.create_connection(('127.0.0.1',port),timeout=.5)
  except OSError as error:
   if error.errno not in (errno.EPERM,errno.EACCES):raise
   denied=True;denial_errno=error.errno
  else:
   connection.close();raise AssertionError('default guest unexpectedly acquired network authority')
  return io.NodeOutput(json.dumps({'numpy':np.__version__,'opencv':cv2.__version__,'torch':torch.__version__,'denied':denied,'denial_errno':denial_errno,'origins':[np.__file__,cv2.__file__,torch.__file__]},sort_keys=True))
