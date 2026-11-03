"""Functions and node classes copied verbatim from WAS_Node_Suite.py at 44de705818d4663fefefde57ffe0ea5a9ea39df4.

The build extracts each block by name from the pinned file (the line ranges are noted above each block) and checks
it byte for byte. The module-level names they use are bound here: TEXT_TYPE and is_force_input with the original's
default configuration (WAS_Node_Suite.py:309-319), TextTokens from tokens.py (the original's class, for a guest).
"""
import random
import re

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageFilter

from .tokens import TextTokens

TEXT_TYPE = "STRING"


# --- WAS_Node_Suite.py:72-143
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

# --- WAS_Node_Suite.py:146-148
cstr.color.add_code("msg", f"{cstr.color.BLUE}WAS Node Suite: {cstr.color.END}")
cstr.color.add_code("warning", f"{cstr.color.BLUE}WAS Node Suite {cstr.color.LIGHTYELLOW}Warning: {cstr.color.END}")
cstr.color.add_code("error", f"{cstr.color.RED}WAS Node Suite {cstr.color.END}Error: {cstr.color.END}")


# --- WAS_Node_Suite.py:318-319
def is_force_input():
    return True if TEXT_TYPE == 'STRING' else False


# --- WAS_Node_Suite.py:405-406
def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))


# --- WAS_Node_Suite.py:409-410
def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


# --- WAS_Node_Suite.py:11366-11384
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


# --- WAS_Node_Suite.py:11386-11408
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


# --- WAS_Node_Suite.py:11411-11429
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


# --- WAS_Node_Suite.py:12758-12776
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


# --- WAS_Node_Suite.py:10508-10559
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


# --- WAS_Node_Suite.py:10597-10623
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


# --- WAS_Node_Suite.py:9903-9930
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


# --- WAS_Node_Suite.py:2792-2951
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


# --- WAS_Node_Suite.py:8890-8912
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


# --- WAS_Node_Suite.py:9750-9765
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


# --- WAS_Node_Suite.py:12629-12670
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


# --- WAS_Node_Suite.py:13061-13125
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


# --- WAS_Node_Suite.py:13271-13295
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


# --- WAS_Node_Suite.py:13916-13940
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


# --- WAS_Node_Suite.py:13559-13583
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


# --- WAS_Node_Suite.py:13700-13724
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


# --- WAS_Node_Suite.py:13531-13555
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


# --- WAS_Node_Suite.py:13503-13527
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


# --- WAS_Node_Suite.py:9996-10031
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


# --- WAS_Node_Suite.py:10036-10061
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


# --- WAS_Node_Suite.py:9958-9991
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


# --- WAS_Node_Suite.py:10266-10297
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


# --- WAS_Node_Suite.py:9933-9953
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


# --- WAS_Node_Suite.py:11008-11032
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


# --- WAS_Node_Suite.py:12853-12871
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


# --- WAS_Node_Suite.py:12782-12800
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


# --- WAS_Node_Suite.py:12875-12893
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


# --- WAS_Node_Suite.py:12918-12938
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


# --- WAS_Node_Suite.py:10357-10476
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


# --- WAS_Node_Suite.py:10302-10350
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


# --- WAS_Node_Suite.py:10481-10503
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
