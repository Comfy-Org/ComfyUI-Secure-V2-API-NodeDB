import torch
import numpy as np
from PIL import Image

def tensor2pil(image):
    """
    Tensor to PIL
    """
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image):
    """
    PIL to Tensor
    """
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)
