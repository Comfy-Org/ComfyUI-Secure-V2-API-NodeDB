import numpy as np,torch,cv2
import warnings
from PIL import Image
UPSCALE_METHODS = ["INTER_NEAREST", "INTER_LINEAR", "INTER_AREA", "INTER_CUBIC", "INTER_LANCZOS4"]
def HWC3(x):
    assert x.dtype == np.uint8
    if x.ndim == 2:
        x = x[:, :, None]
    assert x.ndim == 3
    H, W, C = x.shape
    assert C == 1 or C == 3 or C == 4
    if C == 3:
        return x
    if C == 1:
        return np.concatenate([x, x, x], axis=2)
    if C == 4:
        color = x[:, :, 0:3].astype(np.float32)
        alpha = x[:, :, 3:4].astype(np.float32) / 255.0
        y = color * alpha + 255.0 * (1.0 - alpha)
        y = y.clip(0, 255).astype(np.uint8)
        return y

def common_input_validate(input_image, output_type, **kwargs):
    if "img" in kwargs:
            warnings.warn("img is deprecated, please use `input_image=...` instead.", DeprecationWarning)
            input_image = kwargs.pop("img")
    
    if "return_pil" in kwargs:
            warnings.warn("return_pil is deprecated. Use output_type instead.", DeprecationWarning)
            output_type = "pil" if kwargs["return_pil"] else "np"
    
    if type(output_type) is bool:
        warnings.warn("Passing `True` or `False` to `output_type` is deprecated and will raise an error in future versions")
        if output_type:
            output_type = "pil"

    if input_image is None:
        raise ValueError("input_image must be defined.")

    if not isinstance(input_image, np.ndarray):
        input_image = np.array(input_image, dtype=np.uint8)
        output_type = output_type or "pil"
    else:
        output_type = output_type or "np"
    
    return (input_image, output_type)

def resize_image_with_pad(input_image, resolution, upscale_method = "", skip_hwc3=False, mode='edge'):
    if skip_hwc3:
        img = input_image
    else:
        img = HWC3(input_image)
    H_raw, W_raw, _ = img.shape
    if resolution == 0:
        return img, lambda x: x
    k = float(resolution) / float(min(H_raw, W_raw))
    H_target = int(np.round(float(H_raw) * k))
    W_target = int(np.round(float(W_raw) * k))
    img = cv2.resize(img, (W_target, H_target), interpolation=get_upscale_method(upscale_method) if k > 1 else cv2.INTER_AREA)
    H_pad, W_pad = pad64(H_target), pad64(W_target)
    img_padded = np.pad(img, [[0, H_pad], [0, W_pad], [0, 0]], mode=mode)

    def remove_pad(x):
        return safer_memory(x[:H_target, :W_target, ...])

    return safer_memory(img_padded), remove_pad

def get_upscale_method(method_str):
    assert method_str in UPSCALE_METHODS, f"Method {method_str} not found in {UPSCALE_METHODS}"
    return getattr(cv2, method_str)

def pad64(x):
    return int(np.ceil(float(x) / 64.0) * 64 - x)

def safer_memory(x):
    # Fix many MAC/AMD problems
    return np.ascontiguousarray(x.copy()).copy()

class MidasDetector:
    def __init__(self,model,processor):
        from transformers import DPTForDepthEstimation,DPTImageProcessor
        assert type(model) is DPTForDepthEstimation and type(processor) is DPTImageProcessor and not model.training
        self.model=model;self.processor=processor;self.device='cpu'
    def to(self, device):
            self.model = self.model.to(device) 
            self.device = device
            return self
    def __call__(self, input_image, a=np.pi * 2.0, bg_th=0.1, depth_and_normal=False, detect_resolution=512, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
            input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
            detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
            
            # Convert to PIL for processor
            pil_image = Image.fromarray(detected_map.astype(np.uint8))
            
            # Process with HuggingFace pipeline
            with torch.no_grad():
                inputs = self.processor(images=pil_image, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                outputs = self.model(**inputs)
                depth = outputs.predicted_depth
                
                # Normalize depth
                depth = torch.nn.functional.interpolate(
                    depth.unsqueeze(1),
                    size=(detected_map.shape[0], detected_map.shape[1]),
                    mode="bicubic",
                    align_corners=False,
                ).squeeze()
                
                depth_pt = depth.clone()
                depth_pt -= torch.min(depth_pt)
                depth_pt /= torch.max(depth_pt)
                depth_pt = depth_pt.cpu().numpy()
                depth_image = (depth_pt * 255.0).clip(0, 255).astype(np.uint8)
    
                if depth_and_normal:
                    depth_np = depth.cpu().numpy()
                    x = cv2.Sobel(depth_np, cv2.CV_32F, 1, 0, ksize=3)
                    y = cv2.Sobel(depth_np, cv2.CV_32F, 0, 1, ksize=3)
                    z = np.ones_like(x) * a
                    x[depth_pt < bg_th] = 0
                    y[depth_pt < bg_th] = 0
                    normal = np.stack([x, y, z], axis=2)
                    normal /= np.sum(normal ** 2.0, axis=2, keepdims=True) ** 0.5
                    normal_image = (normal * 127.5 + 127.5).clip(0, 255).astype(np.uint8)[:, :, ::-1]
            
            depth_image = HWC3(depth_image)
            if depth_and_normal:
                normal_image = HWC3(normal_image)
    
            depth_image = remove_pad(depth_image)
            if depth_and_normal:
                normal_image = remove_pad(normal_image)
            
            if output_type == "pil":
                depth_image = Image.fromarray(depth_image)
                if depth_and_normal:
                    normal_image = Image.fromarray(normal_image)
            
            if depth_and_normal:
                return depth_image, normal_image
            else:
                return depth_image
