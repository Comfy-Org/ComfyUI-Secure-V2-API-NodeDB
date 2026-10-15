import cv2,numpy as np,torch,functools
import torch.nn as nn
from einops import rearrange
from PIL import Image
from ._native_batch_reference import HWC3,resize_image_with_pad,common_input_validate,common_annotator_call
HF_MODEL_NAME='lllyasviel/Annotators'
BDS_MODEL_NAME='bdsqlsz/qinglong_controlnet-lllite'
STATES={}
from ._native_teed_model.ted import TED
from ._native_teed_util_reference import safe_step
class TEDDetector:

    def __init__(self, model):
        self.model = model
        self.device = 'cpu'

    @classmethod
    def from_pretrained(cls, pretrained_model_or_path=BDS_MODEL_NAME, filename='7_model.pth', subfolder='Annotators'):
        model = TED()
        model.load_state_dict(dict(STATES[filename]))
        model.eval()
        return cls(model)

    def to(self, device):
        self.model.to(device)
        self.device = device
        return self

    def __call__(self, input_image, detect_resolution=512, safe_steps=2, upscale_method='INTER_CUBIC', output_type='pil', **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        H, W, _ = input_image.shape
        with torch.no_grad():
            image_teed = torch.from_numpy(input_image.copy()).float().to(self.device)
            image_teed = rearrange(image_teed, 'h w c -> 1 c h w')
            edges = self.model(image_teed)
            edges = [e.detach().cpu().numpy().astype(np.float32)[0, 0] for e in edges]
            edges = [cv2.resize(e, (W, H), interpolation=cv2.INTER_LINEAR) for e in edges]
            edges = np.stack(edges, axis=2)
            edge = 1 / (1 + np.exp(-np.mean(edges, axis=2).astype(np.float64)))
            if safe_steps != 0:
                edge = safe_step(edge, safe_steps)
            edge = (edge * 255.0).clip(0, 255).astype(np.uint8)
        detected_map = remove_pad(HWC3(edge))
        if output_type == 'pil':
            detected_map = Image.fromarray(detected_map[..., :3])
        return detected_map
