import torch
import math

class HunyuanImageLatentToVideoLatent:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "length": ("INT", {"default": 49, "min": 1, "max": 40000, "step": 4, "tooltip": "The number of frames desired"}),
                "latent": ("LATENT", {"tooltip": "The Hunyuan image latent to convert into a Hunyuan video latent"}),
                "use_noise_mask": ("BOOLEAN", {"default": True, "tooltip": "Whether to include a noise mask"}),
                "noise_s": ("FLOAT", {"default": 20, "min": 0.0, "max": 100.0, "tooltip": "The s (scale) parameter in the noise intensity function (see https://www.desmos.com/calculator/vhw74mr1vh)"}),
                "noise_o": ("FLOAT", {"default": 0.25, "min": -2.0, "max": 2.0, "step": 0.01, "tooltip": "The o parameter (offset) in the noise intensity function (see https://www.desmos.com/calculator/vhw74mr1vh)"}),
                "noise_w": ("FLOAT", {"default": 0.05, "min": 0, "max": 2.0, "step": 0.01, "tooltip": "The w parameter (width) in the noise intensity function (see https://www.desmos.com/calculator/vhw74mr1vh)"}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "run_node"

    OUTPUT_NODE = False

    CATEGORY = "latent"
    DESCRIPTION = "Copies the given latent's samples tensor along the time axis ((length - 1) // 4) + 1 times to form a longer latent (see EmptyHunyuanLatentVideo's implementation for why this specific number of copies is used). Then, prepares a noise_mask tensor of the same shape such that the value of the mask for a given time step is given by the function shown at https://www.desmos.com/calculator/vhw74mr1vh."

    def get_noise_intensity(self, x, s, o, w):
        return 1 - math.exp(s*(x-o+w/2))/(1+math.exp(s*(x-o+w/2))) + math.exp(s*(x-o-w/2))/(1+math.exp(s*(x-o-w/2)))

    def run_node(self, length, latent, use_noise_mask, noise_s, noise_o, noise_w):
        duplication_amt = ((length - 1) // 4) + 1
        
        samples_tensor = latent['samples']
        samples_tensor = torch.concat([samples_tensor for i in range(duplication_amt)], dim=2)

        result_dict = {"samples": samples_tensor}

        if use_noise_mask:
            noise_mask_tensor = torch.ones(size=latent['samples'].shape)
            noise_mask_tensor = torch.concat([self.get_noise_intensity(i/duplication_amt, noise_s, noise_o, noise_w)*noise_mask_tensor for i in range(duplication_amt)], dim=2)
            print(f"Using noise mask with intensities {[self.get_noise_intensity(i/duplication_amt, noise_s, noise_o, noise_w) for i in range(duplication_amt)]}")
            result_dict["noise_mask"] = noise_mask_tensor
        
        return (result_dict,)

NODE_CLASS_MAPPINGS = {
    "HunyuanImageLatentToVideoLatent": HunyuanImageLatentToVideoLatent
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HunyuanImageLatentToVideoLatent": "Hunyuan Image Latent To Video Latent"
}
