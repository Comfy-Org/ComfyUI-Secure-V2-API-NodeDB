"""V2 subset of upstream sigmas.py (057a913e): four sigma value nodes, copied verbatim in upstream order;
VENDOR.json records each one's source lines and sha256. They use only torch and math, so the upstream
module's other imports (scipy, ComfyUI core) are not needed (vendor_res4lyf.py proves that every global
name resolves as upstream)."""
import torch
import math


class sigmas_from_text:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True}),
            }
        }

    FUNCTION = "main"
    RETURN_TYPES = ("SIGMAS",)
    RETURN_NAMES = ("sigmas",)
    CATEGORY = "RES4LYF/sigmas"
    
    def main(self, text):
        text_list = [float(val) for val in text.replace(",", " ").split()]
        #text_list = [float(val.strip()) for val in text.split(",")]

        sigmas = torch.tensor(text_list) #.to('cuda').to(torch.float64)
        
        return (sigmas,)


class sigmas_rescale:
    def __init__(self):
        pass
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "start": ("FLOAT", {"default": 1.0, "min": -10000,"max": 10000,"step": 0.01}),
                "end": ("FLOAT", {"default": 0.0, "min": -10000,"max": 10000,"step": 0.01}),
                "sigmas": ("SIGMAS", ),
            },
            "optional": {
            }
        }
    FUNCTION = "main"
    RETURN_TYPES = ("SIGMAS",)
    RETURN_NAMES = ("sigmas_rescaled",)
    CATEGORY = "RES4LYF/sigmas"
    DESCRIPTION = ("Can be used to set denoise. Results are generally better than with the approach used by KSampler and most nodes with denoise values "
                   "(which slice the sigmas schedule according to step count, not the noise level). Will also flip the sigma schedule if the start and end values are reversed." 
                   )
      
    def main(self, start=0, end=-1, sigmas=None):

        s_out_1 = ((sigmas - sigmas.min()) * (start - end)) / (sigmas.max() - sigmas.min()) + end     
        
        return (s_out_1,)


class sigmas_easing:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "sigmas": ("SIGMAS", {"forceInput": True}),
                "easing_type": (["sine", "quad", "cubic", "quart", "quint", "expo", "circ", 
                                 "back", "elastic", "bounce"], {"default": "cubic"}),
                "easing_mode": (["in", "out", "in_out"], {"default": "in_out"}),
                "normalize_input": ("BOOLEAN", {"default": True}),
                "normalize_output": ("BOOLEAN", {"default": True}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 10.0, "step": 0.1})
            }
        }

    FUNCTION = "main"
    RETURN_TYPES = ("SIGMAS",)
    CATEGORY = "RES4LYF/sigmas"
    
    def main(self, sigmas, easing_type, easing_mode, normalize_input, normalize_output, strength):
        # Normalize input to [0, 1] if requested
        if normalize_input:
            t = (sigmas - sigmas.min()) / (sigmas.max() - sigmas.min())
        else:
            t = torch.clamp(sigmas, 0.0, 1.0)
        
        # Apply strength
        t_orig = t.clone()
        t = t ** strength
            
        # Apply easing function based on type and mode
        if easing_mode == "in":
            result = self._ease_in(t, easing_type)
        elif easing_mode == "out":
            result = self._ease_out(t, easing_type)
        else:  # in_out
            result = self._ease_in_out(t, easing_type)
            
        # Normalize output if requested
        if normalize_output:
            if normalize_input:
                result = ((result - result.min()) / (result.max() - result.min())) * (sigmas.max() - sigmas.min()) + sigmas.min()
            else:
                result = ((result - result.min()) / (result.max() - result.min()))
                
        return (result,)
    
    def _ease_in(self, t, easing_type):
        if easing_type == "sine":
            return 1 - torch.cos((t * math.pi) / 2)
        elif easing_type == "quad":
            return t * t
        elif easing_type == "cubic":
            return t * t * t
        elif easing_type == "quart":
            return t * t * t * t
        elif easing_type == "quint":
            return t * t * t * t * t
        elif easing_type == "expo":
            return torch.where(t == 0, torch.zeros_like(t), torch.pow(2, 10 * t - 10))
        elif easing_type == "circ":
            return 1 - torch.sqrt(1 - torch.pow(t, 2))
        elif easing_type == "back":
            c1 = 1.70158
            c3 = c1 + 1
            return c3 * t * t * t - c1 * t * t
        elif easing_type == "elastic":
            c4 = (2 * math.pi) / 3
            return torch.where(
                t == 0, 
                torch.zeros_like(t),
                torch.where(
                    t == 1,
                    torch.ones_like(t),
                    -torch.pow(2, 10 * t - 10) * torch.sin((t * 10 - 10.75) * c4)
                )
            )
        elif easing_type == "bounce":
            return 1 - self._ease_out_bounce(1 - t)
    
    def _ease_out(self, t, easing_type):
        if easing_type == "sine":
            return torch.sin((t * math.pi) / 2)
        elif easing_type == "quad":
            return 1 - (1 - t) * (1 - t)
        elif easing_type == "cubic":
            return 1 - torch.pow(1 - t, 3)
        elif easing_type == "quart":
            return 1 - torch.pow(1 - t, 4)
        elif easing_type == "quint":
            return 1 - torch.pow(1 - t, 5)
        elif easing_type == "expo":
            return torch.where(t == 1, torch.ones_like(t), 1 - torch.pow(2, -10 * t))
        elif easing_type == "circ":
            return torch.sqrt(1 - torch.pow(t - 1, 2))
        elif easing_type == "back":
            c1 = 1.70158
            c3 = c1 + 1
            return 1 + c3 * torch.pow(t - 1, 3) + c1 * torch.pow(t - 1, 2)
        elif easing_type == "elastic":
            c4 = (2 * math.pi) / 3
            return torch.where(
                t == 0, 
                torch.zeros_like(t),
                torch.where(
                    t == 1,
                    torch.ones_like(t),
                    torch.pow(2, -10 * t) * torch.sin((t * 10 - 0.75) * c4) + 1
                )
            )
        elif easing_type == "bounce":
            return self._ease_out_bounce(t)
    
    def _ease_in_out(self, t, easing_type):
        if easing_type == "sine":
            return -(torch.cos(math.pi * t) - 1) / 2
        elif easing_type == "quad":
            return torch.where(t < 0.5, 2 * t * t, 1 - torch.pow(-2 * t + 2, 2) / 2)
        elif easing_type == "cubic":
            return torch.where(t < 0.5, 4 * t * t * t, 1 - torch.pow(-2 * t + 2, 3) / 2)
        elif easing_type == "quart":
            return torch.where(t < 0.5, 8 * t * t * t * t, 1 - torch.pow(-2 * t + 2, 4) / 2)
        elif easing_type == "quint":
            return torch.where(t < 0.5, 16 * t * t * t * t * t, 1 - torch.pow(-2 * t + 2, 5) / 2)
        elif easing_type == "expo":
            return torch.where(
                t < 0.5, 
                torch.pow(2, 20 * t - 10) / 2,
                (2 - torch.pow(2, -20 * t + 10)) / 2
            )
        elif easing_type == "circ":
            return torch.where(
                t < 0.5,
                (1 - torch.sqrt(1 - torch.pow(2 * t, 2))) / 2,
                (torch.sqrt(1 - torch.pow(-2 * t + 2, 2)) + 1) / 2
            )
        elif easing_type == "back":
            c1 = 1.70158
            c2 = c1 * 1.525
            return torch.where(
                t < 0.5,
                (torch.pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2,
                (torch.pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2
            )
        elif easing_type == "elastic":
            c5 = (2 * math.pi) / 4.5
            return torch.where(
                t < 0.5,
                -(torch.pow(2, 20 * t - 10) * torch.sin((20 * t - 11.125) * c5)) / 2,
                (torch.pow(2, -20 * t + 10) * torch.sin((20 * t - 11.125) * c5)) / 2 + 1
            )
        elif easing_type == "bounce":
            return torch.where(
                t < 0.5,
                (1 - self._ease_out_bounce(1 - 2 * t)) / 2,
                (1 + self._ease_out_bounce(2 * t - 1)) / 2
            )
    
    def _ease_out_bounce(self, t):
        n1 = 7.5625
        d1 = 2.75
        
        mask1 = t < 1 / d1
        mask2 = t < 2 / d1
        mask3 = t < 2.5 / d1
        
        result = torch.zeros_like(t)
        result = torch.where(mask1, n1 * t * t, result)
        result = torch.where(mask2 & ~mask1, n1 * (t - 1.5 / d1) * (t - 1.5 / d1) + 0.75, result)
        result = torch.where(mask3 & ~mask2, n1 * (t - 2.25 / d1) * (t - 2.25 / d1) + 0.9375, result)
        result = torch.where(~mask3, n1 * (t - 2.625 / d1) * (t - 2.625 / d1) + 0.984375, result)
        
        return result


class sigmas_split_value:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "sigmas": ("SIGMAS",),
                "split_value": ("FLOAT", {"default": 0.875, "min": 0.0, "max": 80085.0, "step": 0.001}),
                "bias_split_up": ("BOOLEAN", {"default": False, "tooltip": "If True, split happens above the split value, so high_sigmas includes the split point."}),
            }
        }

    FUNCTION = "main"
    RETURN_TYPES = ("SIGMAS", "SIGMAS")
    RETURN_NAMES = ("high_sigmas", "low_sigmas")
    CATEGORY = "RES4LYF/sigmas"
    DESCRIPTION = ("Splits sigma schedule at a specific sigma value.")

    def main(self, sigmas, split_value, bias_split_up):
        if len(sigmas) == 0:
            return (sigmas, sigmas)
        
        # Find the split index
        if bias_split_up:
            # Find first sigma <= split_value
            split_idx = None
            for i, sigma in enumerate(sigmas):
                if sigma <= split_value:
                    split_idx = i
                    break
            
            if split_idx is None:
                # All sigmas are above split_value
                return (sigmas, torch.tensor([], device=sigmas.device, dtype=sigmas.dtype))
            
            # high_sigmas: from start to split_idx (inclusive)
            # low_sigmas: from split_idx to end
            high_sigmas = sigmas[:split_idx + 1]
            low_sigmas = sigmas[split_idx:]
            
        else:
            # Find first sigma < split_value
            split_idx = None
            for i, sigma in enumerate(sigmas):
                if sigma < split_value:
                    split_idx = i
                    break
            
            if split_idx is None:
                # All sigmas are >= split_value
                return (torch.tensor([], device=sigmas.device, dtype=sigmas.dtype), sigmas)
            
            # high_sigmas: from start to split_idx (exclusive)
            # low_sigmas: from split_idx-1 to end (includes the boundary point)
            high_sigmas = sigmas[:split_idx]
            low_sigmas = sigmas[split_idx - 1:]
        
        return (high_sigmas, low_sigmas)
