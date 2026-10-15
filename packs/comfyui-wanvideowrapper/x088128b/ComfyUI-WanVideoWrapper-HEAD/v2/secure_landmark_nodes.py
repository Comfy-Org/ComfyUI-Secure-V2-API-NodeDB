"""Pack-owned FantasyPortrait landmark rasterization, not detector inference."""
import math
import cv2
import numpy as np
import torch
from comfy_api.latest import io, sdk
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS

def _preflight(landmarks,width,height,image):
    _bound_payload([landmarks,image])
    if isinstance(landmarks,(list,tuple,np.ndarray,torch.Tensor)) and len(landmarks)>512:
        raise ValueError('Wan landmarks exceeds512 frames')
    for size in (width,height):
        if isinstance(size,(int,float)) and (not math.isfinite(size) or abs(size)>2048):
            raise ValueError('Wan landmark canvas exceeds bounded dimensions')
    if isinstance(image,torch.Tensor):
        if image.device.type!='cpu' or image.layout!=torch.strided:
            raise ValueError('Wan landmark raster requires dense CPU image values')
    if isinstance(landmarks,(list,tuple,np.ndarray,torch.Tensor)):
        for frame in landmarks:
            if isinstance(frame,(list,tuple,np.ndarray,torch.Tensor)) and len(frame)>512:
                raise ValueError('Wan landmarks exceeds512 points/frame')
            for point in frame if isinstance(frame,(list,tuple,np.ndarray,torch.Tensor)) else ():
                for value in point if isinstance(point,(list,tuple,np.ndarray,torch.Tensor)) else ():
                    if isinstance(value,(int,float,np.number)) and math.isfinite(value) and abs(value)>1000000:
                        raise ValueError('Wan landmark coordinate exceeds bounded raster input')
    if isinstance(landmarks,(list,tuple,np.ndarray,torch.Tensor)) and isinstance(width,int) and isinstance(height,int):
        count=len(landmarks)
        blank=max(0,width)*max(0,height)*3
        supplied=int(np.prod(image.shape[1:])) if isinstance(image,torch.Tensor) and image.ndim>=2 else 0
        elements=count*max(blank,supplied)
        # Reserve NumPy canvases, tensor stack, division and float32 conversion;
        # source image*255 buffer overlaps these. Conservative float64 reserve.
        projected=elements*32+(image.numel()*image.element_size()*2 if isinstance(image,torch.Tensor) else 0)
        if elements>MAX_TENSOR_ELEMENTS or projected>MAX_PAYLOAD_BYTES:
            raise ValueError('Wan landmark projected raster exceeds tensor/64MiB bounds')

class LandmarksToImage(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LandmarksToImage',display_name='Landmarks to Image',category='LivePortrait',
            inputs=[io.Custom('LANDMARKS').Input('landmarks',extra_dict={'default':[]}),
                io.Int.Input('width',default=512,min=1,max=2048,step=1,tooltip='Width of the output image'),
                io.Int.Input('height',default=512,min=1,max=2048,step=1,tooltip='Height of the output image'),
                io.Image.Input('image',optional=True)],
            outputs=[io.Image.Output(display_name='keypoints_image')])
    @classmethod
    async def execute(cls,landmarks,width=512,height=512,image=None):
        _preflight(landmarks,width,height,image)
        if image is not None:
            image = image.detach().cpu().numpy() * 255
        keypoints_img_list = []
        for i, lmk in enumerate(landmarks):
            if len(lmk) > 0:
                if image is None:
                    keypoints_image = np.zeros((height, width, 3), dtype=np.uint8) * 255
                else:
                    keypoints_image = image[i].copy()
                for (x, y) in lmk:
                    cv2.circle(keypoints_image, (int(x), int(y)), radius=2, thickness=-1, color=(255,255,255))
            else:
                keypoints_image = np.zeros((height, width, 3), dtype=np.uint8) * 255
            keypoints_img_list.append(keypoints_image)
            await sdk.ctx().progress.update(i+1,len(landmarks))
        keypoints_img_tensor = (
            torch.stack([torch.from_numpy(np_array) for np_array in keypoints_img_list]) / 255).float()
        return io.NodeOutput(keypoints_img_tensor)

NODE_CLASS_MAPPINGS={'LandmarksToImage':LandmarksToImage}
