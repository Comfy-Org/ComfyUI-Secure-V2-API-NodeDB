"""Exact retained detector math; no from_pretrained/download/path loader."""
import torch
import cv2
import numpy as np
from PIL import Image
from einops import rearrange
from ._image_math import HWC3, resize_image_with_pad, common_input_validate
from ._anime_face_palette import seg2img

class AnimeFaceSegmentor:
    def __init__(self, model, seg_model):
            self.model = model
            self.seg_model = seg_model
            self.device = "cpu"

    def to(self, device):
            self.model.to(device)
            self.seg_model.net.to(device)
            self.device = device
            return self

    def __call__(self, input_image, detect_resolution=512, output_type="pil", upscale_method="INTER_CUBIC", remove_background=True, **kwargs):
            input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
            input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
    
            with torch.no_grad():
                if remove_background:
                    print(input_image.shape)
                    mask, input_image = self.seg_model(input_image, 0) #Don't resize image as it is resized
                image_feed = torch.from_numpy(input_image).float().to(self.device)
                image_feed = rearrange(image_feed, 'h w c -> 1 c h w')
                image_feed = image_feed / 255
                seg = self.model(image_feed).squeeze(dim=0)
                result = seg2img(seg.cpu().detach().numpy())
            
            detected_map = HWC3(result)
            detected_map = remove_pad(detected_map)
            if remove_background:
                mask = remove_pad(mask)
                H, W, C = detected_map.shape
                tmp = np.zeros([H, W, C + 1])
                tmp[:,:,:C] = detected_map
                tmp[:,:,3:] = mask
                detected_map = tmp
            
            if output_type == "pil":
                detected_map = Image.fromarray(detected_map[..., :3])
            
            return detected_map
