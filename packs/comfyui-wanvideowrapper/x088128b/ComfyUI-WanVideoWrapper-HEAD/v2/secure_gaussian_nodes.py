"""Exact source CPU Gaussian fill; source GPU choice remains explicitly pending."""
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_noise_algorithms import draw_gaussian_noise_cpu
MAX_WORK_BYTES=64*1024*1024

def _preflight(image,mask,B,H,W,C,BM,HM,WM):
    _bound_payload([image,mask])
    if not isinstance(image,torch.Tensor) or not isinstance(mask,torch.Tensor):
        raise TypeError("Wan Gaussian requires admitted tensor values")
    if image.device.type!="cpu" or mask.device.type!="cpu":
        raise ValueError("Wan Gaussian CPU path requires CPU tensor values")
    if image.layout!=torch.strided or mask.layout!=torch.strided:
        raise ValueError("Wan Gaussian requires dense tensor values")
    # Input clones, resized mask (BM, not B), repeat intermediate, per-image
    # expanded masks/noise/products, list storage and final stack coexist.
    # Reserve float64 intermediates for mixed scalar/dtype promotion.
    matched=max(B,BM)+BM
    projected=8*(8*B*H*W*max(C,3)+6*matched*H*W)+image.numel()*image.element_size()+mask.numel()*mask.element_size()
    if projected>MAX_WORK_BYTES:
        raise ValueError("Wan Gaussian projected work exceeds 64 MiB")

class DrawGaussianNoiseOnImage(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="DrawGaussianNoiseOnImage",display_name="Draw Gaussian Noise On Image",
            category="KJNodes/masking",description="Fills the background (masked area) with Gaussian noise sampled using the mean and variance of the subject (unmasked) region.",
            inputs=[io.Image.Input("image"),io.Mask.Input("mask"),
                io.Combo.Input("device",options=["cpu","gpu"],default="cpu",optional=True,tooltip="Device to use for processing"),
                io.Int.Input("seed",default=0,min=0,max=0xffffffffffffffff,optional=True)],
            outputs=[io.Image.Output(display_name="images")])
    @classmethod
    def execute(cls,image,mask,device="cpu",seed=0):
        B, H, W, C = image.shape
        BM, HM, WM = mask.shape

        _preflight(image,mask,B,H,W,C,BM,HM,WM)
        if device == "gpu":
            raise RuntimeError("Wan Gaussian GPU path pending host-admitted compute-device policy")
        return io.NodeOutput(*draw_gaussian_noise_cpu(image,mask,seed))

NODE_CLASS_MAPPINGS={"DrawGaussianNoiseOnImage":DrawGaussianNoiseOnImage}
