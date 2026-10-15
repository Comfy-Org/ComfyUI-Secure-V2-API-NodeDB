"""Bounded pinned ArcFace debug raster; not face encoder inference."""
import math
import cv2
import numpy as np
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES

def _preflight(lynx_face_embeds,image):
    _bound_payload((lynx_face_embeds,image))
    if isinstance(image,torch.Tensor):
        if image.device.type!="cpu" or image.layout!=torch.strided:
            raise ValueError("Wan ArcFace raster requires dense CPU image values")
        if image.ndim==4:
            _,height,width,channels=image.shape
            if max(height,width)>2048:
                raise ValueError("Wan ArcFace raster dimension bounds")
            projected=image.numel()*image.element_size()+height*width*channels*40
            if projected>MAX_PAYLOAD_BYTES:
                raise ValueError("Wan ArcFace projected raster exceeds64MiB")
    points=lynx_face_embeds.get("landmarks") if isinstance(lynx_face_embeds,dict) else None
    if points is not None and not isinstance(points,(list,tuple,dict,str,np.ndarray,torch.Tensor)):
        raise TypeError("Wan ArcFace landmarks require bounded plain containers")
    if isinstance(points,(list,tuple,dict,str,np.ndarray,torch.Tensor)):
        if isinstance(points,torch.Tensor) and (points.device.type!="cpu" or points.layout!=torch.strided):
            raise ValueError("Wan ArcFace landmarks require dense CPU values")
        if len(points)>512:
            raise ValueError("Wan ArcFace landmarks exceeds512points")
        for point in points:
            if isinstance(point,(list,tuple,np.ndarray,torch.Tensor)):
                for coordinate in point:
                    if isinstance(coordinate,torch.Tensor) and coordinate.ndim==0:
                        coordinate=coordinate.item()
                    if isinstance(coordinate,(int,float,np.number)) and (not math.isfinite(coordinate) or abs(coordinate)>1000000):
                        raise ValueError("Wan ArcFace coordinates must be finite and bounded1000000")


class DrawArcFaceLandmarks(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):
        # Core required-first resolution makes the duplicate optional IMAGE
        # declaration inert; do not expose a second conflicting socket.
        return io.Schema(node_id="DrawArcFaceLandmarks",display_name="Draw ArcFace Landmarks",
            category="WanVideoWrapper",description="Draw face landmarks on an image for visualization/debugging",
            inputs=[io.Custom("LYNXIP").Input("lynx_face_embeds",tooltip="lynx resampler model"),
                io.Image.Input("image",tooltip="Input images for the model")],
            outputs=[io.Image.Output(display_name="landmarked_image")])
    @classmethod
    def execute(cls,lynx_face_embeds,image):
        _preflight(lynx_face_embeds,image)
        landmarks=lynx_face_embeds["landmarks"]
        image_np=image[0].numpy()*255
        for (x,y) in landmarks:
            cv2.circle(image_np,(int(x),int(y)),radius=3,color=(0,255,0),thickness=-1)
        image_out=torch.from_numpy(image_np/255).unsqueeze(0).float()
        return io.NodeOutput(image_out)


NODE_CLASS_MAPPINGS={"DrawArcFaceLandmarks":DrawArcFaceLandmarks}
