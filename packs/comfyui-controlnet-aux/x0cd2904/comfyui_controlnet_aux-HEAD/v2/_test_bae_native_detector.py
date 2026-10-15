import numpy as np,torch
import torchvision.transforms as transforms
from PIL import Image
from einops import rearrange
from ._test_bae_native_batch import HWC3,common_input_validate,resize_image_with_pad
class NativeNormalBaeDetector:

    def __init__(self, model):
        self.model = model
        self.norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        self.device = 'cpu'

    def to(self, device):
        self.model.to(device)
        self.device = device
        return self

    def __call__(self, input_image, detect_resolution=512, output_type='pil', upscale_method='INTER_CUBIC', **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        image_normal = detected_map
        with torch.no_grad():
            image_normal = torch.from_numpy(image_normal).float().to(self.device)
            image_normal = image_normal / 255.0
            image_normal = rearrange(image_normal, 'h w c -> 1 c h w')
            image_normal = self.norm(image_normal)
            normal = self.model(image_normal)
            normal = normal[0][-1][:, :3]
            normal = ((normal + 1) * 0.5).clip(0, 1)
            normal = rearrange(normal[0], 'c h w -> h w c').cpu().numpy()
            normal_image = (normal * 255.0).clip(0, 255).astype(np.uint8)
        detected_map = remove_pad(HWC3(normal_image))
        if output_type == 'pil':
            detected_map = Image.fromarray(detected_map)
        return detected_map
