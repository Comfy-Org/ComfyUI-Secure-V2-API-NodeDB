"""Functions and node classes copied verbatim from WAS_Node_Suite.py at ea935d1044ae5a26efa54ebeb18fe9020af49a45.

The build extracts each block by name from the pinned file (the line ranges are noted above each block) and checks
it byte for byte against the file read as text (the pinned file has CRLF line endings; this module uses LF).
WAS_Tools_Class keeps only the members the converted nodes call. The module-level names they use are bound here:
TEXT_TYPE and is_force_input with the original's default configuration (WAS_Node_Suite.py:277-287), TextTokens from
tokens.py (the original's class, for a guest).
"""
import hashlib
import math
import random
import re

import numpy as np
import torch
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .tokens import TextTokens

TEXT_TYPE = "STRING"


# --- WAS_Node_Suite.py:65-136
class cstr(str):
    class color:
        END = '\33[0m'
        BOLD = '\33[1m'
        ITALIC = '\33[3m'
        UNDERLINE = '\33[4m'
        BLINK = '\33[5m'
        BLINK2 = '\33[6m'
        SELECTED = '\33[7m'

        BLACK = '\33[30m'
        RED = '\33[31m'
        GREEN = '\33[32m'
        YELLOW = '\33[33m'
        BLUE = '\33[34m'
        VIOLET = '\33[35m'
        BEIGE = '\33[36m'
        WHITE = '\33[37m'

        BLACKBG = '\33[40m'
        REDBG = '\33[41m'
        GREENBG = '\33[42m'
        YELLOWBG = '\33[43m'
        BLUEBG = '\33[44m'
        VIOLETBG = '\33[45m'
        BEIGEBG = '\33[46m'
        WHITEBG = '\33[47m'

        GREY = '\33[90m'
        LIGHTRED = '\33[91m'
        LIGHTGREEN = '\33[92m'
        LIGHTYELLOW = '\33[93m'
        LIGHTBLUE = '\33[94m'
        LIGHTVIOLET = '\33[95m'
        LIGHTBEIGE = '\33[96m'
        LIGHTWHITE = '\33[97m'

        GREYBG = '\33[100m'
        LIGHTREDBG = '\33[101m'
        LIGHTGREENBG = '\33[102m'
        LIGHTYELLOWBG = '\33[103m'
        LIGHTBLUEBG = '\33[104m'
        LIGHTVIOLETBG = '\33[105m'
        LIGHTBEIGEBG = '\33[106m'
        LIGHTWHITEBG = '\33[107m'

        @staticmethod
        def add_code(name, code):
            if not hasattr(cstr.color, name.upper()):
                setattr(cstr.color, name.upper(), code)
            else:
                raise ValueError(f"'cstr' object already contains a code with the name '{name}'.")

    def __new__(cls, text):
        return super().__new__(cls, text)

    def __getattr__(self, attr):
        if attr.lower().startswith("_cstr"):
            code = getattr(self.color, attr.upper().lstrip("_cstr"))
            modified_text = self.replace(f"__{attr[1:]}__", f"{code}")
            return cstr(modified_text)
        elif attr.upper() in dir(self.color):
            code = getattr(self.color, attr.upper())
            modified_text = f"{code}{self}{self.color.END}"
            return cstr(modified_text)
        elif attr.lower() in dir(cstr):
            return getattr(cstr, attr.lower())
        else:
            raise AttributeError(f"'cstr' object has no attribute '{attr}'")

    def print(self, **kwargs):
        print(self, **kwargs)

# --- WAS_Node_Suite.py:139-141
cstr.color.add_code("msg", f"{cstr.color.BLUE}WAS Node Suite: {cstr.color.END}")
cstr.color.add_code("warning", f"{cstr.color.BLUE}WAS Node Suite {cstr.color.LIGHTYELLOW}Warning: {cstr.color.END}")
cstr.color.add_code("error", f"{cstr.color.RED}WAS Node Suite {cstr.color.END}Error: {cstr.color.END}")


# --- WAS_Node_Suite.py:286-287
def is_force_input():
    return True if TEXT_TYPE == 'STRING' else False


# --- WAS_Node_Suite.py:361-362
def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))


# --- WAS_Node_Suite.py:365-366
def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


# --- WAS_Node_Suite.py:11315-11333
class WAS_Text_To_String:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (TEXT_TYPE, {"forceInput": is_force_input()}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "text_to_string"

    CATEGORY = "WAS Suite/Text/Operations"

    def text_to_string(self, text):
        return (text, )


# --- WAS_Node_Suite.py:11335-11357
class WAS_Text_To_Number:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (TEXT_TYPE, {"forceInput": is_force_input()}),
            }
        }

    RETURN_TYPES = ("NUMBER",)
    FUNCTION = "text_to_number"

    CATEGORY = "WAS Suite/Text/Operations"

    def text_to_number(self, text):
        if "." in text:
            number = float(text)
        else:
            number = int(text)
        return (number, )


# --- WAS_Node_Suite.py:11360-11378
class WAS_String_To_Text:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "string": ("STRING", {}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "string_to_text"

    CATEGORY = "WAS Suite/Text/Operations"

    def string_to_text(self, string):
        return (string, )


# --- WAS_Node_Suite.py:12707-12725
class WAS_Number_To_Int:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number": ("NUMBER",),
            }
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "number_to_int"

    CATEGORY = "WAS Suite/Number/Operations"

    def number_to_int(self, number):
        return (int(number), )


# --- WAS_Node_Suite.py:10462-10513
class WAS_Text_Concatenate:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "delimiter": ("STRING", {"default": ", "}),
                "clean_whitespace": (["true", "false"],),
            },
            "optional": {
                "text_a": ("STRING", {"forceInput": True}),
                "text_b": ("STRING", {"forceInput": True}),
                "text_c": ("STRING", {"forceInput": True}),
                "text_d": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "text_concatenate"

    CATEGORY = "WAS Suite/Text"

    def text_concatenate(self, delimiter, clean_whitespace, **kwargs):
        text_inputs = []

        # Handle special case where delimiter is "\n" (literal newline).
        if delimiter in ("\n", "\\n"):
            delimiter = "\n"

        # Iterate over the received inputs in sorted order.
        for k in sorted(kwargs.keys()):
            v = kwargs[k]

            # Only process string input ports.
            if isinstance(v, str):
                if clean_whitespace == "true":
                    # Remove leading and trailing whitespace around this input.
                    v = v.strip()

                # Only use this input if it's a non-empty string, since it
                # never makes sense to concatenate totally empty inputs.
                # NOTE: If whitespace cleanup is disabled, inputs containing
                # 100% whitespace will be treated as if it's a non-empty input.
                if v != "":
                    text_inputs.append(v)

        # Merge the inputs. Will always generate an output, even if empty.
        merged_text = delimiter.join(text_inputs)

        return (merged_text,)


# --- WAS_Node_Suite.py:10551-10577
class WAS_Search_and_Replace:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "find": ("STRING", {"default": '', "multiline": False}),
                "replace": ("STRING", {"default": '', "multiline": False}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE, "NUMBER", "FLOAT", "INT")
    RETURN_NAMES = ("result_text", "replacement_count_number", "replacement_count_float", "replacement_count_int")
    FUNCTION = "text_search_and_replace"

    CATEGORY = "WAS Suite/Text/Search"

    def text_search_and_replace(self, text, find, replace):
        modified_text, count = self.replace_substring(text, find, replace)
        return (modified_text, count, float(count), int(count))

    def replace_substring(self, text, find, replace):
        modified_text, count = re.subn(find, replace, text)
        return (modified_text, count)


# --- WAS_Node_Suite.py:9857-9884
class WAS_Text_Multiline:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": '', "multiline": True, "dynamicPrompts": True}),
            }
        }
    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "text_multiline"

    CATEGORY = "WAS Suite/Text"

    def text_multiline(self, text):
        import io
        new_text = []
        for line in io.StringIO(text):
            if not line.strip().startswith('#'):
                new_text.append(line.replace("\n", ''))
        new_text = "\n".join(new_text)

        tokens = TextTokens()
        new_text = tokens.parseTokens(new_text)

        return (new_text, )


# --- WAS_Node_Suite.py:2748-2907
class WAS_Image_Filters:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "brightness": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.01}),
                "contrast": ("FLOAT", {"default": 1.0, "min": -1.0, "max": 2.0, "step": 0.01}),
                "saturation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.01}),
                "sharpness": ("FLOAT", {"default": 1.0, "min": -5.0, "max": 5.0, "step": 0.01}),
                "blur": ("INT", {"default": 0, "min": 0, "max": 16, "step": 1}),
                "gaussian_blur": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1024.0, "step": 0.1}),
                "edge_enhance": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "detail_enhance": (["false", "true"],),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_filters"

    CATEGORY = "WAS Suite/Image/Filter"

    def image_filters(self, image, brightness, contrast, saturation, sharpness, blur, gaussian_blur, edge_enhance, detail_enhance):


        tensors = []
        if len(image) > 1:
            for img in image:

                pil_image = None

                # Apply NP Adjustments
                if brightness > 0.0 or brightness < 0.0:
                    # Apply brightness
                    img = np.clip(img + brightness, 0.0, 1.0)

                if contrast > 1.0 or contrast < 1.0:
                    # Apply contrast
                    img = np.clip(img * contrast, 0.0, 1.0)

                # Apply PIL Adjustments
                if saturation > 1.0 or saturation < 1.0:
                    # PIL Image
                    pil_image = tensor2pil(img)
                    # Apply saturation
                    pil_image = ImageEnhance.Color(pil_image).enhance(saturation)

                if sharpness > 1.0 or sharpness < 1.0:
                    # Assign or create PIL Image
                    pil_image = pil_image if pil_image else tensor2pil(img)
                    # Apply sharpness
                    pil_image = ImageEnhance.Sharpness(pil_image).enhance(sharpness)

                if blur > 0:
                    # Assign or create PIL Image
                    pil_image = pil_image if pil_image else tensor2pil(img)
                    # Apply blur
                    for _ in range(blur):
                        pil_image = pil_image.filter(ImageFilter.BLUR)

                if gaussian_blur > 0.0:
                    # Assign or create PIL Image
                    pil_image = pil_image if pil_image else tensor2pil(img)
                    # Apply Gaussian blur
                    pil_image = pil_image.filter(
                        ImageFilter.GaussianBlur(radius=gaussian_blur))

                if edge_enhance > 0.0:
                    # Assign or create PIL Image
                    pil_image = pil_image if pil_image else tensor2pil(img)
                    # Edge Enhancement
                    edge_enhanced_img = pil_image.filter(ImageFilter.EDGE_ENHANCE_MORE)
                    # Blend Mask
                    blend_mask = Image.new(
                        mode="L", size=pil_image.size, color=(round(edge_enhance * 255)))
                    # Composite Original and Enhanced Version
                    pil_image = Image.composite(
                        edge_enhanced_img, pil_image, blend_mask)
                    # Clean-up
                    del blend_mask, edge_enhanced_img

                if detail_enhance == "true":
                    pil_image = pil_image if pil_image else tensor2pil(img)
                    pil_image = pil_image.filter(ImageFilter.DETAIL)

                # Output image
                out_image = (pil2tensor(pil_image) if pil_image else img.unsqueeze(0))

                tensors.append(out_image)

            tensors = torch.cat(tensors, dim=0)

        else:

            pil_image = None
            img = image

            # Apply NP Adjustments
            if brightness > 0.0 or brightness < 0.0:
                # Apply brightness
                img = np.clip(img + brightness, 0.0, 1.0)

            if contrast > 1.0 or contrast < 1.0:
                # Apply contrast
                img = np.clip(img * contrast, 0.0, 1.0)

            # Apply PIL Adjustments
            if saturation > 1.0 or saturation < 1.0:
                # PIL Image
                pil_image = tensor2pil(img)
                # Apply saturation
                pil_image = ImageEnhance.Color(pil_image).enhance(saturation)

            if sharpness > 1.0 or sharpness < 1.0:
                # Assign or create PIL Image
                pil_image = pil_image if pil_image else tensor2pil(img)
                # Apply sharpness
                pil_image = ImageEnhance.Sharpness(pil_image).enhance(sharpness)

            if blur > 0:
                # Assign or create PIL Image
                pil_image = pil_image if pil_image else tensor2pil(img)
                # Apply blur
                for _ in range(blur):
                    pil_image = pil_image.filter(ImageFilter.BLUR)

            if gaussian_blur > 0.0:
                # Assign or create PIL Image
                pil_image = pil_image if pil_image else tensor2pil(img)
                # Apply Gaussian blur
                pil_image = pil_image.filter(
                    ImageFilter.GaussianBlur(radius=gaussian_blur))

            if edge_enhance > 0.0:
                # Assign or create PIL Image
                pil_image = pil_image if pil_image else tensor2pil(img)
                # Edge Enhancement
                edge_enhanced_img = pil_image.filter(ImageFilter.EDGE_ENHANCE_MORE)
                # Blend Mask
                blend_mask = Image.new(
                    mode="L", size=pil_image.size, color=(round(edge_enhance * 255)))
                # Composite Original and Enhanced Version
                pil_image = Image.composite(
                    edge_enhanced_img, pil_image, blend_mask)
                # Clean-up
                del blend_mask, edge_enhanced_img

            if detail_enhance == "true":
                pil_image = pil_image if pil_image else tensor2pil(img)
                pil_image = pil_image.filter(ImageFilter.DETAIL)

            # Output image
            out_image = (pil2tensor(pil_image) if pil_image else img)

            tensors = out_image

        return (tensors, )


# --- WAS_Node_Suite.py:8844-8866
class WAS_Latent_Noise:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "noise_std": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "inject_noise"

    CATEGORY = "WAS Suite/Latent/Generate"

    def inject_noise(self, samples, noise_std):
        s = samples.copy()
        noise = torch.randn_like(s["samples"]) * noise_std
        s["samples"] = s["samples"] + noise
        return (s,)


# --- WAS_Node_Suite.py:9704-9719
class WAS_Seed:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":
                {"seed": ("INT", {"default": 0, "min": 0,
                          "max": 0xffffffffffffffff})}
                }

    RETURN_TYPES = ("SEED", "NUMBER", "FLOAT", "INT")
    RETURN_NAMES = ("seed", "number", "float", "int")
    FUNCTION = "seed"

    CATEGORY = "WAS Suite/Number"

    def seed(self, seed):
        return ({"seed": seed, }, seed, float(seed), int(seed) )


# --- WAS_Node_Suite.py:12578-12619
class WAS_Constant_Number:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number_type": (["integer", "float", "bool"],),
                "number": ("FLOAT", {"default": 0, "min": -18446744073709551615, "max": 18446744073709551615, "step": 0.01}),
            },
            "optional": {
                "number_as_text": (TEXT_TYPE, {"forceInput": is_force_input()}),
            }
        }

    RETURN_TYPES = ("NUMBER", "FLOAT", "INT")
    FUNCTION = "return_constant_number"

    CATEGORY = "WAS Suite/Number"

    def return_constant_number(self, number_type, number, number_as_text=None):

        if number_as_text:
            if number_type == "integer":
                number = int(number_as_text)
            elif number_type == "float":
                number = float(number_as_text)
            else:
                number = bool(number_as_text)

        # Return number
        if number_type:
            if number_type == 'integer':
                return (int(number), float(number), int(number) )
            elif number_type == 'float':
                return (float(number), float(number), int(number) )
            elif number_type == 'bool':
                boolean = (1 if float(number) > 0.5 else 0)
                return (int(boolean), float(boolean), int(boolean) )
            else:
                return (number, float(number), int(number) )


# --- WAS_Node_Suite.py:13010-13074
class WAS_Number_Operation:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number_a": ("NUMBER",),
                "number_b": ("NUMBER",),
                "operation": (["addition", "subtraction", "division", "floor division", "multiplication", "exponentiation", "modulus", "greater-than", "greater-than or equals", "less-than", "less-than or equals", "equals", "does not equal"],),
            }
        }

    RETURN_TYPES = ("NUMBER", "FLOAT", "INT")
    FUNCTION = "math_operations"

    CATEGORY = "WAS Suite/Number/Operations"

    def math_operations(self, number_a, number_b, operation="addition"):

        # Return random number
        if operation:
            if operation == 'addition':
                result = (number_a + number_b)
                return result, result, int(result)
            elif operation == 'subtraction':
                result = (number_a - number_b)
                return result, result, int(result)
            elif operation == 'division':
                result = (number_a / number_b)
                return result, result, int(result)
            elif operation == 'floor division':
                result = (number_a // number_b)
                return result, result, int(result)
            elif operation == 'multiplication':
                result = (number_a * number_b)
                return result, result, int(result)
            elif operation == 'exponentiation':
                result = (number_a ** number_b)
                return result, result, int(result)
            elif operation == 'modulus':
                result = (number_a % number_b)
                return result, result, int(result)
            elif operation == 'greater-than':
                result = +(number_a > number_b)
                return result, result, int(result)
            elif operation == 'greater-than or equals':
                result = +(number_a >= number_b)
                return result, result, int(result)
            elif operation == 'less-than':
                result = +(number_a < number_b)
                return result, result, int(result)
            elif operation == 'less-than or equals':
                result = +(number_a <= number_b)
                return result, result, int(result)
            elif operation == 'equals':
                result = +(number_a == number_b)
                return result, result, int(result)
            elif operation == 'does not equal':
                result = +(number_a != number_b)
                return result, result, int(result)
            else:
                cstr("Invalid number operation selected.").error.print()
                return (number_a, number_a, int(number_a))


# --- WAS_Node_Suite.py:13220-13244
class WAS_Latent_Input_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent_a": ("LATENT",),
                "latent_b": ("LATENT",),
                "boolean": ("BOOLEAN", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "latent_input_switch"

    CATEGORY = "WAS Suite/Logic"

    def latent_input_switch(self, latent_a, latent_b, boolean=True):

        if boolean:
            return (latent_a, )
        else:
            return (latent_b, )


# --- WAS_Node_Suite.py:13865-13889
class WAS_Lora_Input_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_a": ("MODEL",),
                "clip_a": ("CLIP",),
                "model_b": ("MODEL",),
                "clip_b": ("CLIP",),
                "boolean": ("BOOLEAN", {"forceInput": True}),
            }
        }
    RETURN_TYPES = ("MODEL", "CLIP")
    FUNCTION = "lora_input_switch"

    CATEGORY = "WAS Suite/Logic"

    def lora_input_switch(self, model_a, clip_a, model_b, clip_b, boolean=True):
        if boolean:
            return (model_a, clip_a)
        else:
            return (model_b, clip_b)


# --- WAS_Node_Suite.py:13508-13532
class WAS_VAE_Input_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "vae_a": ("VAE",),
                "vae_b": ("VAE",),
                "boolean": ("BOOLEAN", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("VAE",)
    FUNCTION = "vae_switch"

    CATEGORY = "WAS Suite/Logic"

    def vae_switch(self, vae_a, vae_b, boolean=True):

        if boolean:
            return (vae_a, )
        else:
            return (vae_b, )


# --- WAS_Node_Suite.py:13649-13673
class WAS_Text_Input_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_a": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "text_b": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "boolean": ("BOOLEAN", {"forceInput": True}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "text_input_switch"

    CATEGORY = "WAS Suite/Logic"

    def text_input_switch(self, text_a, text_b, boolean=True):

        if boolean:
            return (text_a, )
        else:
            return (text_b, )


# --- WAS_Node_Suite.py:13480-13504
class WAS_Model_Input_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_a": ("MODEL",),
                "model_b": ("MODEL",),
                "boolean": ("BOOLEAN", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "model_switch"

    CATEGORY = "WAS Suite/Logic"

    def model_switch(self, model_a, model_b, boolean=True):

        if boolean:
            return (model_a, )
        else:
            return (model_b, )


# --- WAS_Node_Suite.py:13452-13476
class WAS_Conditioning_Input_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "conditioning_a": ("CONDITIONING",),
                "conditioning_b": ("CONDITIONING",),
                "boolean": ("BOOLEAN", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "conditioning_input_switch"

    CATEGORY = "WAS Suite/Logic"

    def conditioning_input_switch(self, conditioning_a, conditioning_b, boolean=True):

        if boolean:
            return (conditioning_a, )
        else:
            return (conditioning_b, )


# --- WAS_Node_Suite.py:9950-9985
class WAS_Text_List:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
            },
            "optional": {
                "text_a": ("STRING", {"forceInput": True}),
                "text_b": ("STRING", {"forceInput": True}),
                "text_c": ("STRING", {"forceInput": True}),
                "text_d": ("STRING", {"forceInput": True}),
                "text_e": ("STRING", {"forceInput": True}),
                "text_f": ("STRING", {"forceInput": True}),
                "text_g": ("STRING", {"forceInput": True}),
            }
        }
    RETURN_TYPES = ("LIST",)
    FUNCTION = "text_as_list"

    CATEGORY = "WAS Suite/Text"

    def text_as_list(self, **kwargs):
        text_list: list[str] = []

        # Iterate over the received inputs in sorted order.
        for k in sorted(kwargs.keys()):
            v = kwargs[k]

            # Only process string input ports.
            if isinstance(v, str):
                text_list.append(v)

        return (text_list,)


# --- WAS_Node_Suite.py:9990-10015
class WAS_Text_List_to_Text:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "delimiter": ("STRING", {"default": ", "}),
                "text_list": ("LIST", {"forceInput": True}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "text_list_to_text"

    CATEGORY = "WAS Suite/Text"

    def text_list_to_text(self, delimiter, text_list):
        # Handle special case where delimiter is "\n" (literal newline).
        if delimiter == "\\n":
            delimiter = "\n"

        merged_text = delimiter.join(text_list)

        return (merged_text,)


# --- WAS_Node_Suite.py:9912-9945
class WAS_Text_List_Concatenate:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
            },
            "optional": {
                "list_a": ("LIST", {"forceInput": True}),
                "list_b": ("LIST", {"forceInput": True}),
                "list_c": ("LIST", {"forceInput": True}),
                "list_d": ("LIST", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("LIST",)
    FUNCTION = "text_concatenate_list"

    CATEGORY = "WAS Suite/Text"

    def text_concatenate_list(self, **kwargs):
        merged_list: list[str] = []

        # Iterate over the received inputs in sorted order.
        for k in sorted(kwargs.keys()):
            v = kwargs[k]

            # Only process "list" input ports.
            if isinstance(v, list):
                merged_list += v

        return (merged_list,)


# --- WAS_Node_Suite.py:10220-10251
class WAS_Text_String:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": '', "multiline": False}),
            },
            "optional": {
                "text_b": ("STRING", {"default": '', "multiline": False}),
                "text_c": ("STRING", {"default": '', "multiline": False}),
                "text_d": ("STRING", {"default": '', "multiline": False}),
            }
        }
    RETURN_TYPES = (TEXT_TYPE,TEXT_TYPE,TEXT_TYPE,TEXT_TYPE)
    RETURN_NAMES = ("TEXT", "TEXT_B", "TEXT_C", "TEXT_D")
    FUNCTION = "text_string"

    CATEGORY = "WAS Suite/Text"

    def text_string(self, text='', text_b='', text_c='', text_d=''):

        tokens = TextTokens()

        text = tokens.parseTokens(text)
        text_b = tokens.parseTokens(text_b)
        text_c = tokens.parseTokens(text_c)
        text_d = tokens.parseTokens(text_d)

        return (text, text_b, text_c, text_d)


# --- WAS_Node_Suite.py:9887-9907
class WAS_Text_Multiline_Raw:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": '', "multiline": True, "dynamicPrompts": False}),
            }
        }
    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "text_multiline"

    CATEGORY = "WAS Suite/Text"

    def text_multiline(self, text):
        tokens = TextTokens()
        new_text = tokens.parseTokens(text)

        return (new_text, )


# --- WAS_Node_Suite.py:10957-10981
class WAS_Text_Parse_Tokens:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (TEXT_TYPE, {"forceInput": is_force_input()}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "text_parse_tokens"

    CATEGORY = "WAS Suite/Text/Tokens"

    def text_parse_tokens(self, text):
        # Token Parser
        tokens = TextTokens()
        return (tokens.parseTokens(text), )

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")


# --- WAS_Node_Suite.py:12802-12820
class WAS_Number_To_String:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number": ("NUMBER",),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "number_to_string"

    CATEGORY = "WAS Suite/Number/Operations"

    def number_to_string(self, number):
        return ( str(number), )


# --- WAS_Node_Suite.py:12731-12749
class WAS_Number_To_Float:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number": ("NUMBER",),
            }
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "number_to_float"

    CATEGORY = "WAS Suite/Number/Operations"

    def number_to_float(self, number):
        return (float(number), )


# --- WAS_Node_Suite.py:12824-12842
class WAS_Number_To_Text:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number": ("NUMBER",),
            }
        }

    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "number_to_text"

    CATEGORY = "WAS Suite/Number/Operations"

    def number_to_text(self, number):
        return ( str(number), )


# --- WAS_Node_Suite.py:12867-12887
class WAS_Boolean:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "boolean": ("FLOAT", {"default": 1, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("BOOLEAN", "NUMBER", "INT", "FLOAT")
    FUNCTION = "return_boolean"

    CATEGORY = "WAS Suite/Logic"

    def return_boolean(self, boolean=1.0):
        boolean_bool = bool(int(round(boolean)))
        int_bool = int(round(boolean))
        return (boolean_bool, int_bool, int_bool, boolean)


# --- WAS_Node_Suite.py:10311-10430
class WAS_Text_Compare:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_a": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "text_b": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "mode": (["similarity","difference"],),
                "tolerance": ("FLOAT", {"default":0.0,"min":0.0,"max":1.0,"step":0.01}),
            }
        }
    RETURN_TYPES = (TEXT_TYPE,TEXT_TYPE,"BOOLEAN","NUMBER",TEXT_TYPE)
    RETURN_NAMES = ("TEXT_A_PASS","TEXT_B_PASS","BOOLEAN","SCORE_NUMBER","COMPARISON_TEXT")
    FUNCTION = "text_compare"

    CATEGORY = "WAS Suite/Text/Search"

    def text_compare(self, text_a='', text_b='', mode='similarity', tolerance=0.0):

        boolean = ( 1 if text_a == text_b else 0 )
        sim = self.string_compare(text_a, text_b, tolerance, ( True if mode == 'difference' else False ))
        score = float(sim[0])
        sim_result = ' '.join(sim[1][::-1])
        sim_result = ' '.join(sim_result.split())

        return (text_a, text_b, bool(boolean), score, sim_result)

    def string_compare(self, str1, str2, threshold=1.0, difference_mode=False):
        m = len(str1)
        n = len(str2)
        if difference_mode:
            dp = [[0 for x in range(n+1)] for x in range(m+1)]
            for i in range(m+1):
                for j in range(n+1):
                    if i == 0:
                        dp[i][j] = j
                    elif j == 0:
                        dp[i][j] = i
                    elif str1[i-1] == str2[j-1]:
                        dp[i][j] = dp[i-1][j-1]
                    else:
                        dp[i][j] = 1 + min(dp[i][j-1],      # Insert
                                           dp[i-1][j],      # Remove
                                           dp[i-1][j-1])    # Replace
            diff_indices = []
            i, j = m, n
            while i > 0 and j > 0:
                if str1[i-1] == str2[j-1]:
                    i -= 1
                    j -= 1
                else:
                    diff_indices.append(i-1)
                    i, j = min((i, j-1), (i-1, j))
            diff_indices.reverse()
            words = []
            start_idx = 0
            for i in diff_indices:
                if str1[i] == " ":
                    words.append(str1[start_idx:i])
                    start_idx = i+1
            words.append(str1[start_idx:m])
            difference_score = 1 - ((dp[m][n] - len(words)) / max(m, n))
            return (difference_score, words[::-1])
        else:
            dp = [[0 for x in range(n+1)] for x in range(m+1)]
            similar_words = set()
            for i in range(m+1):
                for j in range(n+1):
                    if i == 0:
                        dp[i][j] = j
                    elif j == 0:
                        dp[i][j] = i
                    elif str1[i-1] == str2[j-1]:
                        dp[i][j] = dp[i-1][j-1]
                        if i > 1 and j > 1 and str1[i-2] == ' ' and str2[j-2] == ' ':
                            word1_start = i-2
                            word2_start = j-2
                            while word1_start > 0 and str1[word1_start-1] != " ":
                                word1_start -= 1
                            while word2_start > 0 and str2[word2_start-1] != " ":
                                word2_start -= 1
                            word1 = str1[word1_start:i-1]
                            word2 = str2[word2_start:j-1]
                            if word1 in str2 or word2 in str1:
                                if word1 not in similar_words:
                                    similar_words.add(word1)
                                if word2 not in similar_words:
                                    similar_words.add(word2)
                    else:
                        dp[i][j] = 1 + min(dp[i][j-1],      # Insert
                                           dp[i-1][j],      # Remove
                                           dp[i-1][j-1])    # Replace
                    if dp[i][j] <= threshold and i > 0 and j > 0:
                        word1_start = max(0, i-dp[i][j])
                        word2_start = max(0, j-dp[i][j])
                        word1_end = i
                        word2_end = j
                        while word1_start > 0 and str1[word1_start-1] != " ":
                            word1_start -= 1
                        while word2_start > 0 and str2[word2_start-1] != " ":
                            word2_start -= 1
                        while word1_end < m and str1[word1_end] != " ":
                            word1_end += 1
                        while word2_end < n and str2[word2_end] != " ":
                            word2_end += 1
                        word1 = str1[word1_start:word1_end]
                        word2 = str2[word2_start:word2_end]
                        if word1 in str2 or word2 in str1:
                            if word1 not in similar_words:
                                similar_words.add(word1)
                            if word2 not in similar_words:
                                similar_words.add(word2)
            if(max(m,n) == 0):
                similarity_score = 1
            else:
                similarity_score = 1 - (dp[m][n]/max(m,n))
            return (similarity_score, list(similar_words))


# --- WAS_Node_Suite.py:10256-10304
class WAS_Text_String_Truncate:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "truncate_by": (["characters", "words"],),
                "truncate_from": (["end", "beginning"],),
                "truncate_to": ("INT", {"default": 10, "min": -99999999, "max": 99999999, "step": 1}),
            },
            "optional": {
                "text_b": ("STRING", {"forceInput": True}),
                "text_c": ("STRING", {"forceInput": True}),
                "text_d": ("STRING", {"forceInput": True}),
            }
        }
    RETURN_TYPES = (TEXT_TYPE,TEXT_TYPE,TEXT_TYPE,TEXT_TYPE)
    RETURN_NAMES = ("TEXT", "TEXT_B", "TEXT_C", "TEXT_D")
    FUNCTION = "truncate_string"

    CATEGORY = "WAS Suite/Text/Operations"

    def truncate_string(self, text, truncate_by, truncate_from, truncate_to, text_b='', text_c='', text_d=''):
        return (
            self.truncate(text, truncate_to, truncate_from, truncate_by),
            self.truncate(text_b, truncate_to, truncate_from, truncate_by),
            self.truncate(text_c, truncate_to, truncate_from, truncate_by),
            self.truncate(text_d, truncate_to, truncate_from, truncate_by),
        )

    def truncate(self, string, max_length, mode='end', truncate_by='characters'):
        if mode not in ['beginning', 'end']:
            cstr("Invalid mode. 'mode' must be either 'beginning' or 'end'.").error.print()
            mode = "end"
        if truncate_by not in ['characters', 'words']:
            cstr("Invalid truncate_by. 'truncate_by' must be either 'characters' or 'words'.").error.print()
        if truncate_by == 'characters':
            if mode == 'beginning':
                return string[:max_length] if max_length >= 0 else string[max_length:]
            else:
                return string[-max_length:] if max_length >= 0 else string[:max_length]
        words = string.split()
        if mode == 'beginning':
            return ' '.join(words[:max_length]) if max_length >= 0 else ' '.join(words[max_length:])
        else:
            return ' '.join(words[-max_length:]) if max_length >= 0 else ' '.join(words[:max_length])


# --- WAS_Node_Suite.py:10435-10457
class WAS_Text_Random_Line:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE,)
    FUNCTION = "text_random_line"

    CATEGORY = "WAS Suite/Text"

    def text_random_line(self, text, seed):
        lines = text.split("\n")
        random.seed(seed)
        choice = random.choice(lines)
        return (choice, )


# --- WAS_Node_Suite.py:432-437
def image2seed(image):
    image_data = image.tobytes()
    hash_object = hashlib.sha256(image_data)
    hash_digest = hash_object.digest()
    seed = int.from_bytes(hash_digest[:4], byteorder='big')
    return seed


# --- WAS_Node_Suite.py:13160-13182
class WAS_Image_Size_To_Number:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("NUMBER", "NUMBER", "FLOAT", "FLOAT", "INT", "INT")
    RETURN_NAMES = ("width_num", "height_num", "width_float", "height_float", "width_int", "height_int")
    FUNCTION = "image_width_height"

    CATEGORY = "WAS Suite/Number/Operations"

    def image_width_height(self, image):
        image = tensor2pil(image)
        if image.size:
            return( image.size[0], image.size[1], float(image.size[0]), float(image.size[1]), image.size[0], image.size[1] )
        return ( 0, 0, 0, 0, 0, 0)


# --- WAS_Node_Suite.py:13187-13215
class WAS_Latent_Size_To_Number:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
            }
        }

    RETURN_TYPES = ("NUMBER", "NUMBER", "FLOAT", "FLOAT", "INT", "INT")
    RETURN_NAMES = ("tensor_w_num","tensor_h_num","tensor_w_float","tensor_h_float","tensor_w_int","tensor_h_int")
    FUNCTION = "latent_width_height"

    CATEGORY = "WAS Suite/Number/Operations"

    def latent_width_height(self, samples):
        size_dict = {}
        i = 0
        for tensor in samples['samples'][0]:
            if not isinstance(tensor, torch.Tensor):
                cstr(f'Input should be a torch.Tensor').error.print()
            shape = tensor.shape
            tensor_height = shape[-2]
            tensor_width = shape[-1]
            size_dict.update({i:[tensor_width, tensor_height]})
        return ( size_dict[0][0], size_dict[0][1], float(size_dict[0][0]), float(size_dict[0][1]), size_dict[0][0], size_dict[0][1] )


# --- WAS_Node_Suite.py:3674-3747
class WAS_Image_Grid_Image_Batch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "border_width": ("INT", {"default":3, "min": 0, "max": 100, "step":1}),
                "number_of_columns": ("INT", {"default":6, "min": 1, "max": 24, "step":1}),
                "max_cell_size": ("INT", {"default":256, "min":32, "max":2048, "step":1}),
                "border_red": ("INT", {"default":0, "min": 0, "max": 255, "step":1}),
                "border_green": ("INT", {"default":0, "min": 0, "max": 255, "step":1}),
                "border_blue": ("INT", {"default":0, "min": 0, "max": 255, "step":1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "smart_grid_image"

    CATEGORY = "WAS Suite/Image/Process"

    def smart_grid_image(self, images, number_of_columns=6, max_cell_size=256, add_border=False, border_red=255, border_green=255, border_blue=255, border_width=3):

        cols = number_of_columns
        border_color = (border_red, border_green, border_blue)

        images_resized = []
        max_row_height = 0

        for tensor_img in images:
            img = tensor2pil(tensor_img)
            img_w, img_h = img.size
            aspect_ratio = img_w / img_h

            if img_w > img_h:
                cell_w = min(img_w, max_cell_size)
                cell_h = int(cell_w / aspect_ratio)
            else:
                cell_h = min(img_h, max_cell_size)
                cell_w = int(cell_h * aspect_ratio)

            img_resized = img.resize((cell_w, cell_h))

            if add_border:
                img_resized = ImageOps.expand(img_resized, border=border_width // 2, fill=border_color)

            images_resized.append(img_resized)
            max_row_height = max(max_row_height, cell_h)

        max_row_height = int(max_row_height)
        total_images = len(images_resized)
        rows = math.ceil(total_images / cols)

        grid_width = cols * max_cell_size + (cols - 1) * border_width
        grid_height = rows * max_row_height + (rows - 1) * border_width

        new_image = Image.new('RGB', (grid_width, grid_height), border_color)

        for i, img in enumerate(images_resized):
            x = (i % cols) * (max_cell_size + border_width)
            y = (i // cols) * (max_row_height + border_width)

            img_w, img_h = img.size
            paste_x = x + (max_cell_size - img_w) // 2
            paste_y = y + (max_row_height - img_h) // 2

            new_image.paste(img, (paste_x, paste_y, paste_x + img_w, paste_y + img_h))

        if add_border:
            new_image = ImageOps.expand(new_image, border=border_width, fill=border_color)

        return (pil2tensor(new_image), )


# --- WAS_Node_Suite.py:4712-4753
class WAS_Image_Batch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
            },
            "optional": {
                "images_a": ("IMAGE",),
                "images_b": ("IMAGE",),
                "images_c": ("IMAGE",),
                "images_d": ("IMAGE",),
                # "images_e": ("IMAGE",),
                # "images_f": ("IMAGE",),
                # Theoretically, an infinite number of image input parameters can be added.
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "image_batch"
    CATEGORY = "WAS Suite/Image"

    def _check_image_dimensions(self, tensors, names):
        reference_dimensions = tensors[0].shape[1:]  # Ignore batch dimension
        mismatched_images = [names[i] for i, tensor in enumerate(tensors) if tensor.shape[1:] != reference_dimensions]

        if mismatched_images:
            raise ValueError(f"WAS Image Batch Warning: Input image dimensions do not match for images: {mismatched_images}")

    def image_batch(self, **kwargs):
        batched_tensors = [kwargs[key] for key in kwargs if kwargs[key] is not None]
        image_names = [key for key in kwargs if kwargs[key] is not None]

        if not batched_tensors:
            raise ValueError("At least one input image must be provided.")

        self._check_image_dimensions(batched_tensors, image_names)
        batched_tensors = torch.cat(batched_tensors, dim=0)
        return (batched_tensors,)


# --- WAS_Node_Suite.py:6859-6885
class WAS_Images_To_RGB:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_to_rgb"

    CATEGORY = "WAS Suite/Image"

    def image_to_rgb(self, images):

        if len(images) > 1:
            tensors = []
            for image in images:
                tensors.append(pil2tensor(tensor2pil(image).convert('RGB')))
            tensors = torch.cat(tensors, dim=0)
            return (tensors, )
        else:
            return (pil2tensor(tensor2pil(images).convert("RGB")), )


# --- WAS_Node_Suite.py:7710-7737
class WAS_Tensor_Batch_to_Image:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images_batch": ("IMAGE",),
                "batch_image_number": ("INT", {"default": 0, "min": 0, "max": 64, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "tensor_batch_to_image"

    CATEGORY = "WAS Suite/Latent/Transform"

    def tensor_batch_to_image(self, images_batch=[], batch_image_number=0):

        count = 0
        for _ in images_batch:
            if batch_image_number == count:
                return (images_batch[batch_image_number].unsqueeze(0), )
            count = count+1

        cstr(f"Batch number `{batch_image_number}` is not defined, returning last image").error.print()
        return (images_batch[-1].unsqueeze(0), )


# --- WAS_Node_Suite.py:7788-7826
class WAS_Mask_To_Image:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "masks": ("MASK",),
                    }
                }

    CATEGORY = "WAS Suite/Image/Masking"

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("IMAGES",)

    FUNCTION = "mask_to_image"

    def mask_to_image(self, masks):
        if masks.ndim == 4:
            # If input has shape [N, C, H, W]
            tensor = masks.permute(0, 2, 3, 1)
            tensor_rgb = torch.cat([tensor] * 3, dim=-1)
            return (tensor_rgb,)
        elif masks.ndim == 3:
            # If Input has shape [N, H, W]
            tensor = masks.unsqueeze(-1)
            tensor_rgb = torch.cat([tensor] * 3, dim=-1)
            return (tensor_rgb, )
        elif masks.ndim == 2:
            # If input has shape [H, W]
            tensor = masks.unsqueeze(0).unsqueeze(-1)
            tensor_rgb = torch.cat([tensor] * 3, dim=-1)
            return (tensor_rgb,)
        else:
            cstr("Invalid input shape. Expected [N, C, H, W] or [H, W].").error.print()
            return masks


# --- WAS_Node_Suite.py:8782-8804
class WAS_Mask_Combine_Batch:

    def __init__(self):
        self.WT = WAS_Tools_Class()

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "masks": ("MASK",),
                    },
                }

    CATEGORY = "WAS Suite/Image/Masking"

    RETURN_TYPES = ("MASK",)

    FUNCTION = "combine_masks"

    def combine_masks(self, masks):
        combined_mask = torch.sum(torch.stack([mask.unsqueeze(0) for mask in masks], dim=0), dim=0)
        combined_mask = torch.clamp(combined_mask, 0, 1)  # Ensure values are between 0 and 1
        return (combined_mask, )


# --- WAS_Node_Suite.py:9724-9745
class WAS_Image_To_Seed:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
                    "images": ("IMAGE",),
                }
            }

    RETURN_TYPES = ("INT",)
    OUTPUT_IS_LIST = (True,)

    FUNCTION = "image_to_seed"
    CATEGORY = "WAS Suite/Image/Analyze"

    def image_to_seed(self, images):

        seeds = []
        for image in images:
            image = tensor2pil(image)
            seeds.append(image2seed(image))

        return (seeds, )


# --- WAS_Node_Suite.py:6099-6129
class WAS_Image_Blank:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 1}),
                "height": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 1}),
                "red": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
                "green": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
                "blue": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "blank_image"

    CATEGORY = "WAS Suite/Image"

    def blank_image(self, width, height, red, green, blue):

        # Ensure multiples
        width = (width // 8) * 8
        height = (height // 8) * 8

        # Blend image
        blank = Image.new(mode="RGB", size=(width, height),
                          color=(red, green, blue))

        return (pil2tensor(blank), )


# --- WAS_Node_Suite.py:4182-4216
class WAS_Image_Blend:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
                "blend_percentage": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "image_blend"

    CATEGORY = "WAS Suite/Image"

    def image_blend(self, image_a, image_b, blend_percentage):

        # Convert images to PIL
        img_a = tensor2pil(image_a)
        img_b = tensor2pil(image_b)

        # Blend image
        blend_mask = Image.new(mode="L", size=img_a.size,
                               color=(round(blend_percentage * 255)))
        blend_mask = ImageOps.invert(blend_mask)
        img_result = Image.composite(img_a, img_b, blend_mask)

        del img_a, img_b, blend_mask

        return (pil2tensor(img_result), )


# --- WAS_Node_Suite.py:5725-5769
class WAS_Image_Bloom_Filter:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "radius": ("FLOAT", {"default": 10, "min": 0.0, "max": 1024, "step": 0.1}),
                "intensity": ("FLOAT", {"default": 1, "min": 0.0, "max": 1.0, "step": 0.1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_bloom"

    CATEGORY = "WAS Suite/Image/Filter"

    def image_bloom(self, image, radius=0.5, intensity=1.0):
        return (pil2tensor(self.apply_bloom_filter(tensor2pil(image), radius, intensity)), )

    def apply_bloom_filter(self, input_image, radius, bloom_factor):
        # Apply a blur filter to the input image
        blurred_image = input_image.filter(
            ImageFilter.GaussianBlur(radius=radius))

        # Subtract the blurred image from the input image to create a high-pass filter
        high_pass_filter = ImageChops.subtract(input_image, blurred_image)

        # Create a blurred version of the bloom filter
        bloom_filter = high_pass_filter.filter(
            ImageFilter.GaussianBlur(radius=radius*2))

        # Adjust brightness and levels of bloom filter
        bloom_filter = ImageEnhance.Brightness(bloom_filter).enhance(2.0)

        # Multiply the bloom image with the bloom factor
        bloom_filter = ImageChops.multiply(bloom_filter, Image.new('RGB', input_image.size, (int(
            255 * bloom_factor), int(255 * bloom_factor), int(255 * bloom_factor))))

        # Multiply the bloom filter with the original image using the bloom factor
        blended_image = ImageChops.screen(input_image, bloom_filter)

        return blended_image


# --- WAS_Node_Suite.py:12060-12081
class WAS_Image_Bounds:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(self):
        return {
            "required": {
                "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE_BOUNDS",)
    FUNCTION = "image_bounds"

    CATEGORY = "WAS Suite/Image/Bound"

    def image_bounds(self, image):
        # Ensure we are working with batches
        image = image.unsqueeze(0) if image.dim() == 3 else image

        return([(0, img.shape[0]-1 , 0, img.shape[1]-1) for img in image],)


# --- WAS_Node_Suite.py:5626-5720
class WAS_Image_Chromatic_Aberration:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "red_offset": ("INT", {"default": 2, "min": -255, "max": 255, "step": 1}),
                "green_offset": ("INT", {"default": -1, "min": -255, "max": 255, "step": 1}),
                "blue_offset": ("INT", {"default": 1, "min": -255, "max": 255, "step": 1}),
                "intensity": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "fade_radius": ("INT", {"default": 12, "min": 0, "max": 1024, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_chromatic_aberration"

    CATEGORY = "WAS Suite/Image/Filter"

    def image_chromatic_aberration(self, image, red_offset=4, green_offset=2, blue_offset=0, intensity=1, fade_radius=12):
        return (pil2tensor(self.apply_chromatic_aberration(tensor2pil(image), red_offset, green_offset, blue_offset, intensity, fade_radius)), )

    def apply_chromatic_aberration(self, img, r_offset, g_offset, b_offset, intensity, fade_radius):

        def lingrad(size, direction, white_ratio):
            image = Image.new('RGB', size)
            draw = ImageDraw.Draw(image)
            if direction == 'vertical':
                black_end = size[1] - white_ratio
                range_start = 0
                range_end = size[1]
                range_step = 1
                for y in range(range_start, range_end, range_step):
                    color_ratio = y / size[1]
                    if y <= black_end:
                        color = (0, 0, 0)
                    else:
                        color_value = int(((y - black_end) / (size[1] - black_end)) * 255)
                        color = (color_value, color_value, color_value)
                    draw.line([(0, y), (size[0], y)], fill=color)
            elif direction == 'horizontal':
                black_end = size[0] - white_ratio
                range_start = 0
                range_end = size[0]
                range_step = 1
                for x in range(range_start, range_end, range_step):
                    color_ratio = x / size[0]
                    if x <= black_end:
                        color = (0, 0, 0)
                    else:
                        color_value = int(((x - black_end) / (size[0] - black_end)) * 255)
                        color = (color_value, color_value, color_value)
                    draw.line([(x, 0), (x, size[1])], fill=color)

            return image.convert("L")

        def create_fade_mask(size, fade_radius):
            mask = Image.new("L", size, 255)

            left = ImageOps.invert(lingrad(size, 'horizontal', int(fade_radius * 2)))
            right = left.copy().transpose(Image.FLIP_LEFT_RIGHT)
            top = ImageOps.invert(lingrad(size, 'vertical', int(fade_radius *2)))
            bottom = top.copy().transpose(Image.FLIP_TOP_BOTTOM)

            # Multiply masks with the original mask image
            mask = ImageChops.multiply(mask, left)
            mask = ImageChops.multiply(mask, right)
            mask = ImageChops.multiply(mask, top)
            mask = ImageChops.multiply(mask, bottom)
            mask = ImageChops.multiply(mask, mask)

            return mask

        # split the channels of the image
        r, g, b = img.split()

        # apply the offset to each channel
        r_offset_img = ImageChops.offset(r, r_offset, 0)
        g_offset_img = ImageChops.offset(g, 0, g_offset)
        b_offset_img = ImageChops.offset(b, 0, b_offset)

        # merge the channels with the offsets
        merged = Image.merge("RGB", (r_offset_img, g_offset_img, b_offset_img))

        # create fade masks for blending
        fade_mask = create_fade_mask(img.size, fade_radius)

        # merge the blended channels back into an RGB image
        result = Image.composite(merged, img, fade_mask).convert("RGB")

        return result


# --- WAS_Node_Suite.py:3342-3384
class WAS_Image_Crop_Location:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "top": ("INT", {"default":0, "max": 10000000, "min":0, "step":1}),
                "left": ("INT", {"default":0, "max": 10000000, "min":0, "step":1}),
                "right": ("INT", {"default":256, "max": 10000000, "min":0, "step":1}),
                "bottom": ("INT", {"default":256, "max": 10000000, "min":0, "step":1}),
            }
        }

    RETURN_TYPES = ("IMAGE", "CROP_DATA")
    FUNCTION = "image_crop_location"

    CATEGORY = "WAS Suite/Image/Process"

    def image_crop_location(self, image, top=0, left=0, right=256, bottom=256):
        image = tensor2pil(image)
        img_width, img_height = image.size

        # Calculate the final coordinates for cropping
        crop_top = max(top, 0)
        crop_left = max(left, 0)
        crop_bottom = min(bottom, img_height)
        crop_right = min(right, img_width)

        # Ensure that the cropping region has non-zero width and height
        crop_width = crop_right - crop_left
        crop_height = crop_bottom - crop_top
        if crop_width <= 0 or crop_height <= 0:
            raise ValueError("Invalid crop dimensions. Please check the values for top, left, right, and bottom.")

        # Crop the image and resize
        crop = image.crop((crop_left, crop_top, crop_right, crop_bottom))
        crop_data = (crop.size, (crop_left, crop_top, crop_right, crop_bottom))
        crop = crop.resize((((crop.size[0] // 8) * 8), ((crop.size[1] // 8) * 8)))

        return (pil2tensor(crop), crop_data)


# --- WAS_Node_Suite.py:6185-6243
class WAS_Image_Levels:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "black_level": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 255.0, "step": 0.1}),
                "mid_level": ("FLOAT", {"default": 127.5, "min": 0.0, "max": 255.0, "step": 0.1}),
                "white_level": ("FLOAT", {"default": 255, "min": 0.0, "max": 255.0, "step": 0.1}),
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_image_levels"

    CATEGORY = "WAS Suite/Image/Adjustment"

    def apply_image_levels(self, image, black_level, mid_level, white_level):

        # Convert image to PIL
        tensor_images = []
        for img in image:
            img = tensor2pil(img)
            levels = self.AdjustLevels(black_level, mid_level, white_level)
            tensor_images.append(pil2tensor(levels.adjust(img)))
        tensor_images = torch.cat(tensor_images, dim=0)

        # Return adjust image tensor
        return (tensor_images, )


    class AdjustLevels:
        def __init__(self, min_level, mid_level, max_level):
            self.min_level = min_level
            self.mid_level = mid_level
            self.max_level = max_level

        def adjust(self, im):

            im_arr = np.array(im).astype(np.float32)
            im_arr[im_arr < self.min_level] = self.min_level
            im_arr = (im_arr - self.min_level) * \
                (255 / (self.max_level - self.min_level))
            im_arr = np.clip(im_arr, 0, 255)

            # mid-level adjustment
            if self.mid_level <= self.min_level:  
                gamma = 1.0
            else:
                gamma = math.log(0.5) / math.log((self.mid_level - self.min_level) / (self.max_level - self.min_level))
            im_arr = np.power(im_arr / 255, gamma) * 255

            im_arr = im_arr.astype(np.uint8)

            im = Image.fromarray(im_arr)

            return im


# --- WAS_Node_Suite.py:3484-3585
class WAS_Image_Paste_Crop:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                "required": {
                    "image": ("IMAGE",),
                    "crop_image": ("IMAGE",),
                    "crop_data": ("CROP_DATA",),
                    "crop_blending": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.01}),
                    "crop_sharpening": ("INT", {"default": 0, "min": 0, "max": 3, "step": 1}),
                }
            }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("IMAGE", "MASK")
    FUNCTION = "image_paste_crop"

    CATEGORY = "WAS Suite/Image/Process"

    def image_paste_crop(self, image, crop_image, crop_data=None, crop_blending=0.25, crop_sharpening=0):

        if crop_data == False:
            cstr("No valid crop data found!").error.print()
            return (image, pil2tensor(Image.new("RGB", tensor2pil(image).size, (0,0,0))))

        result_image, result_mask = self.paste_image(tensor2pil(image), tensor2pil(crop_image), crop_data, crop_blending, crop_sharpening)

        return (result_image, result_mask)

    def paste_image(self, image, crop_image, crop_data, blend_amount=0.25, sharpen_amount=1):

        def lingrad(size, direction, white_ratio):
            image = Image.new('RGB', size)
            draw = ImageDraw.Draw(image)
            if direction == 'vertical':
                black_end = int(size[1] * (1 - white_ratio))
                range_start = 0
                range_end = size[1]
                range_step = 1
                for y in range(range_start, range_end, range_step):
                    color_ratio = y / size[1]
                    if y <= black_end:
                        color = (0, 0, 0)
                    else:
                        color_value = int(((y - black_end) / (size[1] - black_end)) * 255)
                        color = (color_value, color_value, color_value)
                    draw.line([(0, y), (size[0], y)], fill=color)
            elif direction == 'horizontal':
                black_end = int(size[0] * (1 - white_ratio))
                range_start = 0
                range_end = size[0]
                range_step = 1
                for x in range(range_start, range_end, range_step):
                    color_ratio = x / size[0]
                    if x <= black_end:
                        color = (0, 0, 0)
                    else:
                        color_value = int(((x - black_end) / (size[0] - black_end)) * 255)
                        color = (color_value, color_value, color_value)
                    draw.line([(x, 0), (x, size[1])], fill=color)

            return image.convert("L")

        crop_size, (left, top, right, bottom) = crop_data
        crop_image = crop_image.resize(crop_size)

        if sharpen_amount > 0:
            for _ in range(int(sharpen_amount)):
                crop_image = crop_image.filter(ImageFilter.SHARPEN)

        blended_image = Image.new('RGBA', image.size, (0, 0, 0, 255))
        blended_mask = Image.new('L', image.size, 0)
        crop_padded = Image.new('RGBA', image.size, (0, 0, 0, 0))
        blended_image.paste(image, (0, 0))
        crop_padded.paste(crop_image, (left, top))
        crop_mask = Image.new('L', crop_image.size, 0)

        if top > 0:
            gradient_image = ImageOps.flip(lingrad(crop_image.size, 'vertical', blend_amount))
            crop_mask = ImageChops.screen(crop_mask, gradient_image)

        if left > 0:
            gradient_image = ImageOps.mirror(lingrad(crop_image.size, 'horizontal', blend_amount))
            crop_mask = ImageChops.screen(crop_mask, gradient_image)

        if right < image.width:
            gradient_image = lingrad(crop_image.size, 'horizontal', blend_amount)
            crop_mask = ImageChops.screen(crop_mask, gradient_image)

        if bottom < image.height:
            gradient_image = lingrad(crop_image.size, 'vertical', blend_amount)
            crop_mask = ImageChops.screen(crop_mask, gradient_image)

        crop_mask = ImageOps.invert(crop_mask)
        blended_mask.paste(crop_mask, (left, top))
        blended_mask = blended_mask.convert("L")
        blended_image.paste(crop_padded, (0, 0), blended_mask)

        return (pil2tensor(blended_image.convert("RGB")), pil2tensor(blended_mask.convert("RGB")))


# --- WAS_Node_Suite.py:5204-5264
class WAS_Image_Rescale:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mode": (["rescale", "resize"],),
                "supersample": (["true", "false"],),
                "resampling": (["lanczos", "nearest", "bilinear", "bicubic"],),
                "rescale_factor": ("FLOAT", {"default": 2, "min": 0.01, "max": 16.0, "step": 0.01}),
                "resize_width": ("INT", {"default": 1024, "min": 1, "max": 48000, "step": 1}),
                "resize_height": ("INT", {"default": 1536, "min": 1, "max": 48000, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_rescale"

    CATEGORY = "WAS Suite/Image/Transform"

    def image_rescale(self, image, mode="rescale", supersample='true', resampling="lanczos", rescale_factor=2, resize_width=1024, resize_height=1024):
        scaled_images = []
        for img in image:
            scaled_images.append(pil2tensor(self.apply_resize_image(tensor2pil(img), mode, supersample, rescale_factor, resize_width, resize_height, resampling)))
        scaled_images = torch.cat(scaled_images, dim=0)

        return (scaled_images, )

    def apply_resize_image(self, image: Image.Image, mode='scale', supersample='true', factor: int = 2, width: int = 1024, height: int = 1024, resample='bicubic'):

        # Get the current width and height of the image
        current_width, current_height = image.size

        # Calculate the new width and height based on the given mode and parameters
        if mode == 'rescale':
            new_width, new_height = int(
                current_width * factor), int(current_height * factor)
        else:
            new_width = width if width % 8 == 0 else width + (8 - width % 8)
            new_height = height if height % 8 == 0 else height + \
                (8 - height % 8)

        # Define a dictionary of resampling filters
        resample_filters = {
            'nearest': 0,
            'bilinear': 2,
            'bicubic': 3,
            'lanczos': 1
        }

        # Apply supersample
        if supersample == 'true':
            image = image.resize((new_width * 8, new_height * 8), resample=Image.Resampling(resample_filters[resample]))

        # Resize the image using the given resampling filter
        resized_image = image.resize((new_width, new_height), resample=Image.Resampling(resample_filters[resample]))

        return resized_image


# --- WAS_Node_Suite.py:6339-6396
class WAS_Image_Rotate:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "mode": (["transpose", "internal",],),
                "rotation": ("INT", {"default": 0, "min": 0, "max": 360, "step": 90}),
                "sampler": (["nearest", "bilinear", "bicubic"],),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "image_rotate"

    CATEGORY = "WAS Suite/Image/Transform"

    def image_rotate(self, images, mode, rotation, sampler):

        batch_tensor = []
        for image in images:
            # PIL Image
            image = tensor2pil(image)

            # Check rotation
            if rotation > 360:
                rotation = int(360)
            if (rotation % 90 != 0):
                rotation = int((rotation//90)*90)

            # Set Sampler
            if sampler:
                if sampler == 'nearest':
                    sampler = Image.NEAREST
                elif sampler == 'bicubic':
                    sampler = Image.BICUBIC
                elif sampler == 'bilinear':
                    sampler = Image.BILINEAR
                else:
                    sampler == Image.BILINEAR

            # Rotate Image
            if mode == 'internal':
                image = image.rotate(rotation, sampler)
            else:
                rot = int(rotation / 90)
                for _ in range(rot):
                    image = image.transpose(2)

            batch_tensor.append(pil2tensor(image))

        batch_tensor = torch.cat(batch_tensor, dim=0)

        return (batch_tensor, )


# --- WAS_Node_Suite.py:6754-6806
class WAS_Image_Select_Color:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "red": ("INT", {"default": 255.0, "min": 0.0, "max": 255.0, "step": 0.1}),
                "green": ("INT", {"default": 255.0, "min": 0.0, "max": 255.0, "step": 0.1}),
                "blue": ("INT", {"default": 255.0, "min": 0.0, "max": 255.0, "step": 0.1}),
                "variance": ("INT", {"default": 10, "min": 0, "max": 255, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "select_color"

    CATEGORY = "WAS Suite/Image/Process"

    def select_color(self, image, red=255, green=255, blue=255, variance=10):

        image = self.color_pick(tensor2pil(image), red, green, blue, variance)

        return (pil2tensor(image), )

    def color_pick(self, image, red=255, green=255, blue=255, variance=10):
        # Convert image to RGB mode
        image = image.convert('RGB')

        # Create a new black image of the same size as the input image
        selected_color = Image.new('RGB', image.size, (0, 0, 0))

        # Get the width and height of the image
        width, height = image.size

        # Loop through every pixel in the image
        for x in range(width):
            for y in range(height):
                # Get the color of the pixel
                pixel = image.getpixel((x, y))
                r, g, b = pixel

                # Check if the pixel is within the specified color range
                if ((r >= red-variance) and (r <= red+variance) and
                    (g >= green-variance) and (g <= green+variance) and
                        (b >= blue-variance) and (b <= blue+variance)):
                    # Set the pixel in the selected_color image to the RGB value of the pixel
                    selected_color.putpixel((x, y), (r, g, b))

        # Return the selected color image
        return selected_color


# --- WAS_Node_Suite.py:12255-12359
class WAS_Bounded_Image_Blend_With_Mask:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(self):
        return {
            "required": {
                "target": ("IMAGE",),
                "target_mask": ("MASK",),
                "target_bounds": ("IMAGE_BOUNDS",),
                "source": ("IMAGE",),
                "blend_factor": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
                "feathering": ("INT", {"default": 16, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "bounded_image_blend_with_mask"

    CATEGORY = "WAS Suite/Image/Bound"

    def bounded_image_blend_with_mask(self, target, target_mask, target_bounds, source, blend_factor, feathering):
        # Ensure we are working with batches
        target = target.unsqueeze(0) if target.dim() == 3 else target
        source = source.unsqueeze(0) if source.dim() == 3 else source
        target_mask = target_mask.unsqueeze(0) if target_mask.dim() == 2 else target_mask

        # If number of target masks and source images don't match, then only the first mask will be used on
        # the source images, otherwise, each mask will be used for each source image 1 to 1
        # Simarly, if the number of target images and source images don't match then
        # all source images will be applied only to the first target, otherwise they will be applied
        # 1 to 1
        tgt_mask_len = 1 if len(target_mask) != len(source) else len(source)
        tgt_len = 1 if len(target) != len(source) else len(source)
        bounds_len = 1 if len(target_bounds) != len(source) else len(source)

        tgt_arr = [tensor2pil(tgt) for tgt in target[:tgt_len]]
        src_arr = [tensor2pil(src) for src in source]
        tgt_mask_arr=[]

        # Convert Target Mask(s) to grayscale image format
        for m_idx in range(tgt_mask_len):
            np_array = np.clip((target_mask[m_idx].cpu().numpy().squeeze() * 255.0), 0, 255)
            tgt_mask_arr.append(Image.fromarray((np_array).astype(np.uint8), mode='L'))

        result_tensors = []
        for idx in range(len(src_arr)):
            src = src_arr[idx]
            # If only one target image, then ensure it is the only one used
            if (tgt_len == 1 and idx == 0) or tgt_len > 1:
                tgt = tgt_arr[idx]

            # If only one bounds, no need to extract and calculate more than once
            if (bounds_len == 1 and idx == 0) or bounds_len > 1:
                # Extract the target bounds
                rmin, rmax, cmin, cmax = target_bounds[idx]

                # Calculate the dimensions of the target bounds
                height, width = (rmax - rmin + 1, cmax - cmin + 1)

            # If only one mask, then ensure that is the only the first is used
            if (tgt_mask_len == 1 and idx == 0) or tgt_mask_len > 1:
                tgt_mask = tgt_mask_arr[idx]

            # If only one mask and one bounds, then mask only needs to
            #   be extended once because all targets will be the same size
            if (tgt_mask_len == 1 and bounds_len == 1 and idx == 0) or \
                (tgt_mask_len > 1 or bounds_len > 1):

                # This is an imperfect, but easy way to determine if  the mask based on the
                #   target image or source image. If not target, assume source. If neither,
                #   then it's not going to look right regardless
                if (tgt_mask.size != tgt.size):
                    # Create the blend mask with the same size as the target image
                    mask_extended_canvas = Image.new('L', tgt.size, 0)

                    # Paste the mask portion into the extended mask at the target bounds position
                    mask_extended_canvas.paste(tgt_mask, (cmin, rmin))

                    tgt_mask = mask_extended_canvas

                # Apply feathering (Gaussian blur) to the blend mask if feather_amount is greater than 0
                if feathering > 0:
                    tgt_mask = tgt_mask.filter(ImageFilter.GaussianBlur(radius=feathering))

                # Apply blending factor to the tgt mask now that it has been extended
                tgt_mask = tgt_mask.point(lambda p: p * blend_factor)

            # Resize the source image to match the dimensions of the target bounds
            src_resized = src.resize((width, height), Image.Resampling.LANCZOS)

            # Create a blank image with the same size and mode as the target
            src_positioned = Image.new(tgt.mode, tgt.size)

            # Paste the source image onto the blank image using the target
            src_positioned.paste(src_resized, (cmin, rmin))

            # Blend the source and target images using the blend mask
            result = Image.composite(src_positioned, tgt, tgt_mask)

            # Convert the result back to a PyTorch tensor
            result_tensors.append(pil2tensor(result))

        return (torch.cat(result_tensors, dim=0),)


# --- WAS_Node_Suite.py:12363-12418
class WAS_Bounded_Image_Crop_With_Mask:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(self):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "padding_left": ("INT", {"default": 64, "min": 0, "max": 0xffffffffffffffff}),
                "padding_right": ("INT", {"default": 64, "min": 0, "max": 0xffffffffffffffff}),
                "padding_top": ("INT", {"default": 64, "min": 0, "max": 0xffffffffffffffff}),
                "padding_bottom": ("INT", {"default": 64, "min": 0, "max": 0xffffffffffffffff}),
                
            },
            "optional":{
                "return_list": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE_BOUNDS",)
    FUNCTION = "bounded_image_crop_with_mask"

    CATEGORY = "WAS Suite/Image/Bound"

    def bounded_image_crop_with_mask(self, image, mask, padding_left, padding_right, padding_top, padding_bottom,return_list=False):
        # Ensure we are working with batches
        image = image.unsqueeze(0) if image.dim() == 3 else image
        mask = mask.unsqueeze(0) if mask.dim() == 2 else mask

        # If number of masks and images don't match, then only the first mask will be used on
        # the images, otherwise, each mask will be used for each image 1 to 1
        mask_len = 1 if len(image) != len(mask) else len(image)

        cropped_images = []
        all_bounds = []
        for i in range(len(image)):
            # Single mask or multiple?
            if (mask_len == 1 and i == 0) or mask_len > 0:
                rows = torch.any(mask[i], dim=1)
                cols = torch.any(mask[i], dim=0)
                rmin, rmax = torch.where(rows)[0][[0, -1]]
                cmin, cmax = torch.where(cols)[0][[0, -1]]

                rmin = max(rmin - padding_top, 0)
                rmax = min(rmax + padding_bottom, mask[i].shape[0] - 1)
                cmin = max(cmin - padding_left, 0)
                cmax = min(cmax + padding_right, mask[i].shape[1] - 1)

            # Even if only a single mask, create a bounds for each cropped image
            all_bounds.append([rmin, rmax, cmin, cmax])
            cropped_images.append(image[i][rmin:rmax+1, cmin:cmax+1, :])
        if return_list:
            return cropped_images, all_bounds
        return torch.stack(cropped_images), all_bounds


# --- WAS_Node_Suite.py:8398-8421
class WAS_Mask_Subtract:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "masks_a": ("MASK",),
                        "masks_b": ("MASK",),
                    }
                }

    CATEGORY = "WAS Suite/Image/Masking"

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("MASKS",)

    FUNCTION = "subtract_masks"

    def subtract_masks(self, masks_a, masks_b):
        subtracted_masks = torch.clamp(masks_a - masks_b, 0, 255)
        return (subtracted_masks,)


# --- WAS_Node_Suite.py:10661-10691
class WAS_Search_and_Replace_Input:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "find": (TEXT_TYPE, {"forceInput": is_force_input()}),
                "replace": (TEXT_TYPE, {"forceInput": is_force_input()}),
            }
        }

    RETURN_TYPES = (TEXT_TYPE, "NUMBER", "FLOAT", "INT")
    RETURN_NAMES = ("result_text", "replacement_count_number", "replacement_count_float", "replacement_count_int")
    FUNCTION = "text_search_and_replace"

    CATEGORY = "WAS Suite/Text/Search"

    def text_search_and_replace(self, text, find, replace):
        count = 0
        new_text = text
        while find in new_text:
            new_text = new_text.replace(find, replace, 1)
            count += 1
        return (new_text, count, float(count), int(count))

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")


# --- WAS_Node_Suite.py:13110-13155
class WAS_Bus:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required":{},
            "optional": {
                "bus" : ("BUS",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
            }
        }
    RETURN_TYPES = ("BUS", "MODEL", "CLIP", "VAE", "CONDITIONING", "CONDITIONING",)
    RETURN_NAMES = ("bus", "model", "clip", "vae", "positive",     "negative")
    FUNCTION = "bus_fn"
    CATEGORY = "WAS Suite/Utilities"

    def bus_fn(self, bus=(None,None,None,None,None), model=None, clip=None, vae=None, positive=None, negative=None):

        # Unpack the 5 constituents of the bus from the bus tuple.
        (bus_model, bus_clip, bus_vae, bus_positive, bus_negative) = bus

        # If you pass in specific inputs, they override what comes from the bus.
        out_model       = model     or bus_model
        out_clip        = clip      or bus_clip
        out_vae         = vae       or bus_vae
        out_positive    = positive  or bus_positive
        out_negative    = negative  or bus_negative

        # Squash all 5 inputs into the output bus tuple.
        out_bus = (out_model, out_clip, out_vae, out_positive, out_negative)

        if not out_model:
            raise ValueError('Either model or bus containing a model should be supplied')
        if not out_clip:
            raise ValueError('Either clip or bus containing a clip should be supplied')
        if not out_vae:
            raise ValueError('Either vae or bus containing a vae should be supplied')
        # We don't insist that a bus contains conditioning.

        return (out_bus, out_model, out_clip, out_vae, out_positive, out_negative)


# --- WAS_Node_Suite.py:9599-9698
class WAS_Blend_Latents:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent_a": ("LATENT",),
                "latent_b": ("LATENT",),
                "operation": (["add", "multiply", "divide", "subtract", "overlay", "hard_light", "soft_light", "screen", "linear_dodge", "difference", "exclusion", "random"],),
                "blend": ("FLOAT", {"default": 0.5, "min": 0.01, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "latent_blend"

    CATEGORY = "WAS Suite/Latent"

    def latent_blend(self, latent_a, latent_b, operation, blend):
        return ( {"samples": self.blend_latents(latent_a['samples'], latent_b['samples'], operation, blend)}, )

    def blend_latents(self, latent1, latent2, mode='add', blend_percentage=0.5):

        def overlay_blend(latent1, latent2, blend_factor):
            low = 2 * latent1 * latent2
            high = 1 - 2 * (1 - latent1) * (1 - latent2)
            blended_latent = (latent1 * blend_factor) * low + (latent2 * blend_factor) * high
            return blended_latent

        def screen_blend(latent1, latent2, blend_factor):
            inverted_latent1 = 1 - latent1
            inverted_latent2 = 1 - latent2
            blended_latent = 1 - (inverted_latent1 * inverted_latent2 * (1 - blend_factor))
            return blended_latent

        def difference_blend(latent1, latent2, blend_factor):
            blended_latent = abs(latent1 - latent2) * blend_factor
            return blended_latent

        def exclusion_blend(latent1, latent2, blend_factor):
            blended_latent = (latent1 + latent2 - 2 * latent1 * latent2) * blend_factor
            return blended_latent

        def hard_light_blend(latent1, latent2, blend_factor):
            blended_latent = torch.where(latent2 < 0.5, 2 * latent1 * latent2, 1 - 2 * (1 - latent1) * (1 - latent2)) * blend_factor
            return blended_latent

        def linear_dodge_blend(latent1, latent2, blend_factor):
            blended_latent = torch.clamp(latent1 + latent2, 0, 1) * blend_factor
            return blended_latent

        def soft_light_blend(latent1, latent2, blend_factor):
            low = 2 * latent1 * latent2 + latent1 ** 2 - 2 * latent1 * latent2 * latent1
            high = 2 * latent1 * (1 - latent2) + torch.sqrt(latent1) * (2 * latent2 - 1)
            blended_latent = (latent1 * blend_factor) * low + (latent2 * blend_factor) * high
            return blended_latent

        def random_noise(latent1, latent2, blend_factor):
            noise1 = torch.randn_like(latent1)
            noise2 = torch.randn_like(latent2)
            noise1 = (noise1 - noise1.min()) / (noise1.max() - noise1.min())
            noise2 = (noise2 - noise2.min()) / (noise2.max() - noise2.min())
            blended_noise = (latent1 * blend_factor) * noise1 + (latent2 * blend_factor) * noise2
            blended_noise = torch.clamp(blended_noise, 0, 1)
            return blended_noise

        blend_factor1 = blend_percentage
        blend_factor2 = 1 - blend_percentage

        if mode == 'add':
            blended_latent = (latent1 * blend_factor1) + (latent2 * blend_factor2)
        elif mode == 'multiply':
            blended_latent = (latent1 * blend_factor1) * (latent2 * blend_factor2)
        elif mode == 'divide':
            blended_latent = (latent1 * blend_factor1) / (latent2 * blend_factor2)
        elif mode == 'subtract':
            blended_latent = (latent1 * blend_factor1) - (latent2 * blend_factor2)
        elif mode == 'overlay':
            blended_latent = overlay_blend(latent1, latent2, blend_factor1)
        elif mode == 'screen':
            blended_latent = screen_blend(latent1, latent2, blend_factor1)
        elif mode == 'difference':
            blended_latent = difference_blend(latent1, latent2, blend_factor1)
        elif mode == 'exclusion':
            blended_latent = exclusion_blend(latent1, latent2, blend_factor1)
        elif mode == 'hard_light':
            blended_latent = hard_light_blend(latent1, latent2, blend_factor1)
        elif mode == 'linear_dodge':
            blended_latent = linear_dodge_blend(latent1, latent2, blend_factor1)
        elif mode == 'soft_light':
            blended_latent = soft_light_blend(latent1, latent2, blend_factor1)
        elif mode == 'random':
            blended_latent = random_noise(latent1, latent2, blend_factor1)
        else:
            raise ValueError("Unsupported blending mode. Please choose from 'add', 'multiply', 'divide', 'subtract', 'overlay', 'screen', 'difference', 'exclusion', 'hard_light', 'linear_dodge', 'soft_light', 'custom_noise'.")

        blended_latent = self.normalize(blended_latent)
        return blended_latent

    def normalize(self, latent):
        return (latent - latent.min()) / (latent.max() - latent.min())


# --- WAS_Node_Suite.py:6248-6300
class WAS_Film_Grain:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "density": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
                "highlights": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 255.0, "step": 0.01}),
                "supersample_factor": ("INT", {"default": 4, "min": 1, "max": 8, "step": 1})
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "film_grain"

    CATEGORY = "WAS Suite/Image/Filter"

    def film_grain(self, image, density, intensity, highlights, supersample_factor):
        return (pil2tensor(self.apply_film_grain(tensor2pil(image), density, intensity, highlights, supersample_factor)), )

    def apply_film_grain(self, img, density=0.1, intensity=1.0, highlights=1.0, supersample_factor=4):
        """
        Apply grayscale noise with specified density, intensity, and highlights to a PIL image.
        """
        img_gray = img.convert('L')
        original_size = img.size
        img_gray = img_gray.resize(
            ((img.size[0] * supersample_factor), (img.size[1] * supersample_factor)), Image.Resampling(2))
        num_pixels = int(density * img_gray.size[0] * img_gray.size[1])

        noise_pixels = []
        for i in range(num_pixels):
            x = random.randint(0, img_gray.size[0]-1)
            y = random.randint(0, img_gray.size[1]-1)
            noise_pixels.append((x, y))

        for x, y in noise_pixels:
            value = random.randint(0, 255)
            img_gray.putpixel((x, y), value)

        img_noise = img_gray.convert('RGB')
        img_noise = img_noise.filter(ImageFilter.GaussianBlur(radius=0.125))
        img_noise = img_noise.resize(original_size, Image.Resampling(1))
        img_noise = img_noise.filter(ImageFilter.EDGE_ENHANCE_MORE)
        img_final = Image.blend(img, img_noise, intensity)
        enhancer = ImageEnhance.Brightness(img_final)
        img_highlights = enhancer.enhance(highlights)

        # Return the final image
        return img_highlights


# --- WAS_Node_Suite.py:12462-12505
class WAS_Random_Number:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number_type": (["integer", "float", "bool"],),
                "minimum": ("FLOAT", {"default": 0, "min": -18446744073709551615, "max": 18446744073709551615}),
                "maximum": ("FLOAT", {"default": 0, "min": -18446744073709551615, "max": 18446744073709551615}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("NUMBER", "FLOAT", "INT")
    FUNCTION = "return_randm_number"

    CATEGORY = "WAS Suite/Number"

    def return_randm_number(self, minimum, maximum, seed, number_type='integer'):

        # Set Generator Seed
        random.seed(seed)

        # Return random number
        if number_type:
            if number_type == 'integer':
                number = random.randint(minimum, maximum)
            elif number_type == 'float':
                number = random.uniform(minimum, maximum)
            elif number_type == 'bool':
                number = random.random()
            else:
                return

        # Return number
        return (number, float(number), round(number))

    @classmethod
    def IS_CHANGED(cls, seed, **kwargs):
        m = hashlib.sha256()
        m.update(seed)
        return m.digest().hex()


# --- WAS_Node_Suite.py:373-376
def pil2mask(image):
    image_np = np.array(image.convert("L")).astype(np.float32) / 255.0
    mask = torch.from_numpy(image_np)
    return 1.0 - mask


# --- WAS_Node_Suite.py:5447-5479
class WAS_Image_Stitch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
                "stitch": (["top", "left", "bottom", "right"],),
                "feathering": ("INT", {"default": 50, "min": 0, "max": 2048, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_stitching"

    CATEGORY = "WAS Suite/Image/Transform"

    def image_stitching(self, image_a, image_b, stitch="right", feathering=50):

        valid_stitches = ["top", "left", "bottom", "right"]
        if stitch not in valid_stitches:
            cstr(f"The stitch mode `{stitch}` is not valid. Valid sitch modes are {', '.join(valid_stitches)}").error.print()
        if feathering > 2048:
            cstr(f"The stitch feathering of `{feathering}` is too high. Please choose a value between `0` and `2048`").error.print()

        WTools = WAS_Tools_Class();

        stitched_image = WTools.stitch_image(tensor2pil(image_a), tensor2pil(image_b), stitch, feathering)

        return (pil2tensor(stitched_image), )


# --- WAS_Node_Suite.py:8689-8726
class WAS_Mask_Gaussian_Region:

    def __init__(self):
        self.WT = WAS_Tools_Class()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "masks": ("MASK",),
                "radius": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 1024, "step": 0.1}),
            }
        }

    CATEGORY = "WAS Suite/Image/Masking"

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("MASKS",)

    FUNCTION = "gaussian_region"

    def gaussian_region(self, masks, radius=5.0):
        if masks.ndim > 3:
            regions = []
            for mask in masks:
                mask_np = np.clip(255. * mask.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)
                pil_image = Image.fromarray(mask_np, mode="L")
                region_mask = self.WT.Masking.gaussian_region(pil_image, radius)
                region_tensor = pil2mask(region_mask).unsqueeze(0).unsqueeze(1)
                regions.append(region_tensor)
            regions_tensor = torch.cat(regions, dim=0)
            return (regions_tensor,)
        else:
            mask_np = np.clip(255. * masks.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)
            pil_image = Image.fromarray(mask_np, mode="L")
            region_mask = self.WT.Masking.gaussian_region(pil_image, radius)
            region_tensor = pil2mask(region_mask).unsqueeze(0).unsqueeze(1)
            return (region_tensor,)


# --- WAS_Node_Suite.py:5147-5198
class WAS_Image_Transpose:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "image_overlay": ("IMAGE",),
                "width": ("INT", {"default": 512, "min": -48000, "max": 48000, "step": 1}),
                "height": ("INT", {"default": 512, "min": -48000, "max": 48000, "step": 1}),
                "X": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
                "Y": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
                "rotation": ("INT", {"default": 0, "min": -360, "max": 360, "step": 1}),
                "feathering": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_transpose"

    CATEGORY = "WAS Suite/Image/Transform"

    def image_transpose(self, image: torch.Tensor, image_overlay: torch.Tensor, width: int, height: int, X: int, Y: int, rotation: int, feathering: int = 0):
        return (pil2tensor(self.apply_transpose_image(tensor2pil(image), tensor2pil(image_overlay), (width, height), (X, Y), rotation, feathering)), )

    def apply_transpose_image(self, image_bg, image_element, size, loc, rotate=0, feathering=0):

        # Apply transformations to the element image
        image_element = image_element.rotate(rotate, expand=True)
        image_element = image_element.resize(size)

        # Create a mask for the image with the faded border
        if feathering > 0:
            mask = Image.new('L', image_element.size, 255)  # Initialize with 255 instead of 0
            draw = ImageDraw.Draw(mask)
            for i in range(feathering):
                alpha_value = int(255 * (i + 1) / feathering)  # Invert the calculation for alpha value
                draw.rectangle((i, i, image_element.size[0] - i, image_element.size[1] - i), fill=alpha_value)
            alpha_mask = Image.merge('RGBA', (mask, mask, mask, mask))
            image_element = Image.composite(image_element, Image.new('RGBA', image_element.size, (0, 0, 0, 0)), alpha_mask)

        # Create a new image of the same size as the base image with an alpha channel
        new_image = Image.new('RGBA', image_bg.size, (0, 0, 0, 0))
        new_image.paste(image_element, loc)

        # Paste the new image onto the base image
        image_bg = image_bg.convert('RGBA')
        image_bg.paste(new_image, (0, 0), new_image)

        return image_bg


# --- WAS_Node_Suite.py:8456-8477
class WAS_Mask_Invert:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "masks": ("MASK",),
                    }
                }

    CATEGORY = "WAS Suite/Image/Masking"

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("MASKS",)

    FUNCTION = "add_masks"

    def add_masks(self, masks):
        return (1. - masks,)


# --- WAS_Node_Suite.py:6305-6336
class WAS_Image_Flip:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "mode": (["horizontal", "vertical",],),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "image_flip"

    CATEGORY = "WAS Suite/Image/Transform"

    def image_flip(self, images, mode):

        batch_tensor = []
        for image in images:
            image = tensor2pil(image)
            if mode == 'horizontal':
                image = image.transpose(0)
            if mode == 'vertical':
                image = image.transpose(1)
            batch_tensor.append(pil2tensor(image))
        batch_tensor = torch.cat(batch_tensor, dim=0)

        return (batch_tensor, )


# --- WAS_Node_Suite.py:4222-4262
class WAS_Image_Monitor_Distortion_Filter:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mode": (["Digital Distortion", "Signal Distortion", "TV Distortion"],),
                "amplitude": ("INT", {"default": 5, "min": 1, "max": 255, "step": 1}),
                "offset": ("INT", {"default": 10, "min": 1, "max": 255, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "image_monitor_filters"

    CATEGORY = "WAS Suite/Image/Filter"

    def image_monitor_filters(self, image, mode="Digital Distortion", amplitude=5, offset=5):

        # Convert images to PIL
        image = tensor2pil(image)

        # WAS Filters
        WTools = WAS_Tools_Class()

        # Apply image effect
        if mode:
            if mode == 'Digital Distortion':
                image = WTools.digital_distortion(image, amplitude, offset)
            elif mode == 'Signal Distortion':
                image = WTools.signal_distortion(image, amplitude)
            elif mode == 'TV Distortion':
                image = WTools.tv_vhs_distortion(image, amplitude)
            else:
                image = image

        return (pil2tensor(image), )


# --- WAS_Node_Suite.py:12623-12679
class WAS_Number_Counter:
    def __init__(self):
        self.counters = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number_type": (["integer", "float"],),
                "mode": (["increment", "decrement", "increment_to_stop", "decrement_to_stop", "reset_after_stop"],),
                "start": ("FLOAT", {"default": 0, "min": -18446744073709551615, "max": 18446744073709551615, "step": 0.01}),
                "stop": ("FLOAT", {"default": 0, "min": -18446744073709551615, "max": 18446744073709551615, "step": 0.01}),
                "step": ("FLOAT", {"default": 1, "min": 0, "max": 99999, "step": 0.01}),
            },
            "optional": {
                "reset_bool": ("NUMBER",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    RETURN_TYPES = ("NUMBER", "FLOAT", "INT")
    RETURN_NAMES = ("number", "float", "int")
    FUNCTION = "increment_number"

    CATEGORY = "WAS Suite/Number"

    def increment_number(self, number_type, mode, start, stop, step, unique_id, reset_bool=0):

        counter = int(start) if mode == 'integer' else start
        if self.counters.__contains__(unique_id):
            counter = self.counters[unique_id]

        if round(reset_bool) >= 1:
            counter = start

        if mode == 'increment':
            counter += step
        elif mode == 'deccrement':
            counter -= step
        elif mode == 'increment_to_stop':
            counter = counter + step if counter < stop else counter
        elif mode == 'decrement_to_stop':
            counter = counter - step if counter > stop else counter
        elif mode == 'reset_after_stop':
            counter = counter + step if counter < stop else start + step

        self.counters[unique_id] = counter

        result = int(counter) if number_type == 'integer' else float(counter)

        return ( result, float(counter), int(counter) )


# --- WAS_Node_Suite.py:978-981 (class line and docstring; selected members follow)
class WAS_Tools_Class():
    """
    Contains various tools and filters for WAS Node Suite
    """

    # --- WAS_Node_Suite.py:992-1073
    def stitch_image(self, image_a, image_b, mode='right', fuzzy_zone=50):

        def linear_gradient(start_color, end_color, size, start, end, mode='horizontal'):
            width, height = size
            gradient = Image.new('RGB', (width, height), end_color)
            draw = ImageDraw.Draw(gradient)

            for i in range(0, start):
                if mode == "horizontal":
                    draw.line((i, 0, i, height-1), start_color)
                elif mode == "vertical":
                    draw.line((0, i, width-1, i), start_color)

            for i in range(start, end):
                if mode == "horizontal":
                    curr_color = (
                        int(start_color[0] + (float(i - start) / (end - start)) * (end_color[0] - start_color[0])),
                        int(start_color[1] + (float(i - start) / (end - start)) * (end_color[1] - start_color[1])),
                        int(start_color[2] + (float(i - start) / (end - start)) * (end_color[2] - start_color[2]))
                    )
                    draw.line((i, 0, i, height-1), curr_color)
                elif mode == "vertical":
                    curr_color = (
                        int(start_color[0] + (float(i - start) / (end - start)) * (end_color[0] - start_color[0])),
                        int(start_color[1] + (float(i - start) / (end - start)) * (end_color[1] - start_color[1])),
                        int(start_color[2] + (float(i - start) / (end - start)) * (end_color[2] - start_color[2]))
                    )
                    draw.line((0, i, width-1, i), curr_color)

            for i in range(end, width if mode == 'horizontal' else height):
                if mode == "horizontal":
                    draw.line((i, 0, i, height-1), end_color)
                elif mode == "vertical":
                    draw.line((0, i, width-1, i), end_color)

            return gradient

        image_a = image_a.convert('RGB')
        image_b = image_b.convert('RGB')

        offset = int(fuzzy_zone / 2)
        canvas_width = int(image_a.size[0] + image_b.size[0] - fuzzy_zone) if mode == 'right' or mode == 'left' else image_a.size[0]
        canvas_height = int(image_a.size[1] + image_b.size[1] - fuzzy_zone) if mode == 'top' or mode == 'bottom' else image_a.size[1]
        canvas = Image.new('RGB', (canvas_width, canvas_height), (0,0,0))

        im_ax = 0
        im_ay = 0
        im_bx = 0
        im_by = 0

        image_a_mask = None
        image_b_mask = None

        if mode == 'top':

            image_a_mask = linear_gradient((0,0,0), (255,255,255), image_a.size, 0, fuzzy_zone, 'vertical')
            image_b_mask = linear_gradient((255,255,255), (0,0,0), image_b.size, int(image_b.size[1] - fuzzy_zone), image_b.size[1], 'vertical')
            im_ay = image_b.size[1] - fuzzy_zone

        elif mode == 'bottom':

            image_a_mask = linear_gradient((255,255,255), (0,0,0), image_a.size, int(image_a.size[1] - fuzzy_zone), image_a.size[1], 'vertical')
            image_b_mask = linear_gradient((0,0,0), (255,255,255), image_b.size, 0, fuzzy_zone, 'vertical').convert('L')
            im_by = image_a.size[1] - fuzzy_zone

        elif mode == 'left':

            image_a_mask = linear_gradient((0,0,0), (255,255,255), image_a.size, 0, fuzzy_zone, 'horizontal')
            image_b_mask = linear_gradient((255,255,255), (0,0,0), image_b.size, int(image_b.size[0] - fuzzy_zone), image_b.size[0], 'horizontal')
            im_ax = image_b.size[0] - fuzzy_zone

        elif mode == 'right':

            image_a_mask = linear_gradient((255,255,255), (0,0,0), image_a.size, int(image_a.size[0] - fuzzy_zone), image_a.size[0], 'horizontal')
            image_b_mask = linear_gradient((0,0,0), (255,255,255), image_b.size, 0, fuzzy_zone, 'horizontal')
            im_bx = image_a.size[0] - fuzzy_zone

        Image.Image.paste(canvas, image_a, (im_ax, im_ay), image_a_mask.convert('L'))
        Image.Image.paste(canvas, image_b, (im_bx, im_by), image_b_mask.convert('L'))


        return canvas

    # --- WAS_Node_Suite.py:1434 (class line; selected members follow)
    class Masking:

        # --- WAS_Node_Suite.py:1648-1652
        @staticmethod
        def gaussian_region(image, radius=5.0):
            image = ImageOps.invert(image.convert("L"))
            image = image.filter(ImageFilter.GaussianBlur(radius=int(radius)))
            return image.convert("RGB")

    # --- WAS_Node_Suite.py:1801-1825
    def digital_distortion(self, image, amplitude=5, line_width=2):

        im = np.array(image)

        x, y, z = im.shape
        sine_wave = amplitude * np.sin(np.linspace(-np.pi, np.pi, y))
        sine_wave = sine_wave.astype(int)

        left_distortion = np.zeros((x, y, z), dtype=np.uint8)
        right_distortion = np.zeros((x, y, z), dtype=np.uint8)
        for i in range(y):
            left_distortion[:, i, :] = np.roll(im[:, i, :], -sine_wave[i], axis=0)
            right_distortion[:, i, :] = np.roll(im[:, i, :], sine_wave[i], axis=0)

        distorted_image = np.maximum(left_distortion, right_distortion)
        scan_lines = np.zeros((x, y), dtype=np.float32)
        scan_lines[::line_width, :] = 1
        scan_lines = np.minimum(scan_lines * amplitude*50.0, 1)  # Scale scan line values
        scan_lines = np.tile(scan_lines[:, :, np.newaxis], (1, 1, z))  # Add channel dimension
        distorted_image = np.where(scan_lines > 0, np.random.permutation(im), distorted_image)
        distorted_image = np.roll(distorted_image, np.random.randint(0, y), axis=1)

        distorted_image = Image.fromarray(distorted_image)

        return distorted_image

    # --- WAS_Node_Suite.py:1827-1840
    def signal_distortion(self, image, amplitude):

        img_array = np.array(image)
        row_shifts = np.random.randint(-amplitude, amplitude + 1, size=img_array.shape[0])
        distorted_array = np.zeros_like(img_array)

        for y in range(img_array.shape[0]):
            x_shift = row_shifts[y]
            x_shift = x_shift + y % (amplitude * 2) - amplitude
            distorted_array[y,:] = np.roll(img_array[y,:], x_shift, axis=0)

        distorted_image = Image.fromarray(distorted_array)

        return distorted_image

    # --- WAS_Node_Suite.py:1842-1872
    def tv_vhs_distortion(self, image, amplitude=10):
        np_image = np.array(image)
        offset_variance = int(image.height / amplitude)
        row_shifts = np.random.randint(-offset_variance, offset_variance + 1, size=image.height)
        distorted_array = np.zeros_like(np_image)

        for y in range(np_image.shape[0]):
            x_shift = row_shifts[y]
            x_shift = x_shift + y % (offset_variance * 2) - offset_variance
            distorted_array[y,:] = np.roll(np_image[y,:], x_shift, axis=0)

        h, w, c = distorted_array.shape
        x_scale = np.linspace(0, 1, w)
        y_scale = np.linspace(0, 1, h)
        x_idx = np.broadcast_to(x_scale, (h, w))
        y_idx = np.broadcast_to(y_scale.reshape(h, 1), (h, w))
        noise = np.random.rand(h, w, c) * 0.1
        distortion = np.sin(x_idx * 50) * 0.5 + np.sin(y_idx * 50) * 0.5
        distorted_array = distorted_array + distortion[:, :, np.newaxis] + noise

        distorted_image = Image.fromarray(np.uint8(distorted_array))
        distorted_image = distorted_image.resize((image.width, image.height))

        image_enhance = ImageEnhance.Color(image)
        image = image_enhance.enhance(0.5)

        effect_image = ImageChops.overlay(image, distorted_image)
        result_image = ImageChops.overlay(image, effect_image)
        result_image = ImageChops.blend(image, result_image, 0.25)

        return result_image
