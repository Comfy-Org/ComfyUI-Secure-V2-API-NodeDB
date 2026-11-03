"""ComfyUI_JPS-Nodes upstream code for Secure Nodes V2 (pin 0e2a9aca02b1).

The classes below are copied verbatim from the pristine jps_nodes.py as AST source segments (line ranges and the
file's sha256 on each). The V2 node classes in _secure_used.py call their methods.
Boundary stand-in (not upstream code): `comfy.samplers.KSampler.SAMPLERS / SCHEDULERS` are empty lists here. Only
Sampler_Scheduler_Settings' class attributes (RETURN_TYPES, INPUT_TYPES) read them; the V2 schema comes from the
frozen original schema, and get_samsched does not use them.
Copied:
#   ComfyUI_JPS-Nodes/jps_nodes.py L245-297 SDXL_Resolutions
#   ComfyUI_JPS-Nodes/jps_nodes.py L551-571 Text_Prompt
#   ComfyUI_JPS-Nodes/jps_nodes.py L575-597 Text_Prompt_Combo
#   ComfyUI_JPS-Nodes/jps_nodes.py L601-645 SDXL_Prompt_Handling
#   ComfyUI_JPS-Nodes/jps_nodes.py L649-675 Math_Resolution_Multiply
#   ComfyUI_JPS-Nodes/jps_nodes.py L679-708 Math_Largest_Integer
#   ComfyUI_JPS-Nodes/jps_nodes.py L740-764 Math_Multiply_INT_FLOAT
#   ComfyUI_JPS-Nodes/jps_nodes.py L824-883 Text_Concatenate
#   ComfyUI_JPS-Nodes/jps_nodes.py L887-916 Get_Date_Time_String
#   ComfyUI_JPS-Nodes/jps_nodes.py L2049-2060 Sampler_Scheduler_Settings
#   ComfyUI_JPS-Nodes/jps_nodes.py L2147-2185 Model_Switch
#   ComfyUI_JPS-Nodes/jps_nodes.py L2231-2269 Latent_Switch
#   ComfyUI_JPS-Nodes/jps_nodes.py L2315-2353 Integer_Switch
#   ComfyUI_JPS-Nodes/jps_nodes.py L2622-2645 Get_Image_Size
"""
import types
from datetime import datetime

comfy = types.SimpleNamespace(samplers=types.SimpleNamespace(KSampler=types.SimpleNamespace(SAMPLERS=[], SCHEDULERS=[])))


# ---------------------------------------------------------------- upstream jps_nodes.py
# ComfyUI_JPS-Nodes/jps_nodes.py L245-297 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class SDXL_Resolutions:
    resolution = ["square - 1024x1024 (1:1)","landscape - 1152x896 (4:3)","landscape - 1216x832 (3:2)","landscape - 1344x768 (16:9)","landscape - 1536x640 (21:9)", "portrait - 896x1152 (3:4)","portrait - 832x1216 (2:3)","portrait - 768x1344 (9:16)","portrait - 640x1536 (9:21)"]
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "resolution": (s.resolution,),
            }
        }
    RETURN_TYPES = ("INT","INT",)
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_resolutions"

    CATEGORY="JPS Nodes/Settings"

    def get_resolutions(self,resolution):
        width = 1024
        height = 1024
        width = int(width)
        height = int(height)
        if(resolution == "square - 1024x1024 (1:1)"):
            width = 1024
            height = 1024
        if(resolution == "landscape - 1152x896 (4:3)"):
            width = 1152
            height = 896
        if(resolution == "landscape - 1216x832 (3:2)"):
            width = 1216
            height = 832
        if(resolution == "landscape - 1344x768 (16:9)"):
            width = 1344
            height = 768
        if(resolution == "landscape - 1536x640 (21:9)"):
            width = 1536
            height = 640
        if(resolution == "portrait - 896x1152 (3:4)"):
            width = 896
            height = 1152
        if(resolution == "portrait - 832x1216 (2:3)"):
            width = 832
            height = 1216
        if(resolution == "portrait - 768x1344 (9:16)"):
            width = 768
            height = 1344
        if(resolution == "portrait - 640x1536 (9:21)"):
            width = 640
            height = 1536
            
        return(int(width),int(height))


# ComfyUI_JPS-Nodes/jps_nodes.py L551-571 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Text_Prompt:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "placeholder": "Prompt Text", "dynamicPrompts": True}),
            },
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "text_prompt"

    CATEGORY="JPS Nodes/Text"

    def text_prompt(self,text):

        return(text,)


# ComfyUI_JPS-Nodes/jps_nodes.py L575-597 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Text_Prompt_Combo:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "pos": ("STRING", {"multiline": True, "placeholder": "Prompt Text Positive", "dynamicPrompts": True}),
                "neg": ("STRING", {"multiline": True, "placeholder": "Prompt Text Negative", "dynamicPrompts": True}),
            },
        }
    
    RETURN_TYPES = ("STRING","STRING",)
    RETURN_NAMES = ("pos","neg",)
    FUNCTION = "give_values"

    CATEGORY="JPS Nodes/Text"

    def give_values(self,pos,neg):
        
        return(pos,neg,)


# ComfyUI_JPS-Nodes/jps_nodes.py L601-645 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class SDXL_Prompt_Handling:
    handling = ["Copy to Both if Empty","Use Positive_G + Positive_L","Copy Positive_G to Both","Copy Positive_L to Both","Ignore Positive_G Input", "Ignore Positive_L Input", "Combine Positive_G + Positive_L", "Combine Positive_L + Positive_G",]
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "handling": (s.handling,),
                "pos_g": ("STRING", {"default": ""}),
                "pos_l": ("STRING", {"default": ""}),
            },
        }
    RETURN_TYPES = ("STRING","STRING",)
    RETURN_NAMES = ("pos_g","pos_l",)
    FUNCTION = "pick_handling"

    CATEGORY="JPS Nodes/Text"

    def pick_handling(self,handling,pos_g,pos_l,):
        
        if(handling == "Copy Positive_G to Both"):
            pos_l = pos_g
        elif(handling == "Copy Positive_L to Both"):
            pos_g = pos_l
        elif(handling == "Ignore Positive_G Input"):
            pos_g = ''
        elif(handling == "Ignore Positive_L Input"):
            pos_l = ''
        elif(handling == "Combine Positive_G + Positive_L"):
            combine = pos_g + ' . ' + pos_l
            pos_g = combine
            pos_l = combine
        elif(handling == "Combine Positive_L + Positive_G"):
            combine = pos_l + ' . ' + pos_g
            pos_g = combine
            pos_l = combine
        elif(handling == "Copy to Both if Empty" and pos_l == ''):
            pos_l = pos_g
        elif(handling == "Copy to Both if Empty" and pos_g == ''):
            pos_g = pos_l

        return(pos_g,pos_l,)


# ComfyUI_JPS-Nodes/jps_nodes.py L649-675 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Math_Resolution_Multiply:
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 256, "max": 8192, "step": 16}),
                "height": ("INT", {"default": 1024, "min": 256, "max": 8192, "step": 16}),
                "factor": ("INT", {"default": 2, "min": 1, "max": 8, "step": 1}),
        }}
    RETURN_TYPES = ("INT","INT")
    RETURN_NAMES = ("width_resized", "height_resized")
    FUNCTION = "get_newres"

    CATEGORY="JPS Nodes/Math"

    def get_newres(self,width,height,factor):
        factor = int(factor)
        width = int(width)
        width_resized = int(width) * int(factor)
        height = int(height)
        height_resized = int (height) * int(factor)
            
        return(int(width_resized),int(height_resized))


# ComfyUI_JPS-Nodes/jps_nodes.py L679-708 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Math_Largest_Integer:

    def init(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "int_a": ("INT", {"default": 1,}),
                "int_b": ("INT", {"default": 1,}),
            }
        }

    RETURN_TYPES = ("INT","INT","INT")
    RETURN_NAMES = ("larger_int","smaller_int","is_a_larger")
    FUNCTION = "get_lrg"

    CATEGORY="JPS Nodes/Math"

    def get_lrg(self,int_a,int_b):
        larger_int = int(int_b)
        smaller_int = int(int_a)
        is_a_larger = int(0)
        if int_a > int_b:
            larger_int = int(int_a)
            smaller_int = int(int_b)
            is_a_larger = int(1)

        return(int(larger_int),int(smaller_int),int(is_a_larger))


# ComfyUI_JPS-Nodes/jps_nodes.py L740-764 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Math_Multiply_INT_FLOAT:

    def init(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "int_a": ("INT", {"default": 1,}),
                "float_b": ("FLOAT", {"default": 1,}),
            }
        }

    RETURN_TYPES = ("INT","FLOAT")
    RETURN_NAMES = ("int_multiply","float_multiply")
    FUNCTION = "get_multiply_int_float"

    CATEGORY="JPS Nodes/Math"

    def get_multiply_int_float(self,int_a,float_b):
        int_multiply = int(int_a) * float(float_b)
        float_multiply = int(int_a) * float(float_b)

        return(int(int_multiply),float(float_multiply))


# ComfyUI_JPS-Nodes/jps_nodes.py L824-883 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Text_Concatenate:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "delimiter": (["none", "space", "comma"],),
            },
            "optional": {
                "text1": ("STRING", {"forceInput": True}),
                "text2": ("STRING", {"forceInput": True}),      
                "text3": ("STRING", {"forceInput": True}),      
                "text4": ("STRING", {"forceInput": True}),      
                "text5": ("STRING", {"forceInput": True}),       
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "get_contxt"
    CATEGORY = "JPS Nodes/Text"

    def get_contxt(self, delimiter, text1=None, text2=None, text3=None, text4=None, text5=None):
        needdelim = False
        delim = ""
        if delimiter == "space":
            delim = " "
        if delimiter == "comma":
            delim = ", "

        concatenated = ""

        if text1:
            concatenated = text1
            needdelim = True
        
        if text2:
            if needdelim:
                concatenated += delim
            concatenated += text2
            needdelim = True
        
        if text3:
            if needdelim:
                concatenated += delim
            concatenated += text3
            needdelim = True

        if text4:
            if needdelim:
                concatenated += delim
            concatenated += text4
            needdelim = True

        if text5:
            if needdelim:
                concatenated += delim
            concatenated += text5
            needdelim = True

        return (concatenated,)


# ComfyUI_JPS-Nodes/jps_nodes.py L887-916 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Get_Date_Time_String:
    time_format = ["%Y%m%d%H%M%S","%Y%m%d%H%M","%Y%m%d","%Y-%m-%d-%H_%M_%S","%Y-%m-%d-%H_%M","%Y-%m-%d","%Y-%m-%d %H_%M_%S","%Y-%m-%d %H_%M","%Y-%m-%d","%H%M","%H%M%S","%H_%M","%H_%M_%S"]
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "style": (s.time_format,),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("time_format",)
    FUNCTION = "get_time"

    CATEGORY = "JPS Nodes/Text"

    def get_time(self, style):
        now = datetime.now()
        timestamp = now.strftime(style)

        return (timestamp,)

    @classmethod
    def IS_CHANGED(s, style):
        now = datetime.now()
        timestamp = now.strftime(style)
        return (timestamp,)


# ComfyUI_JPS-Nodes/jps_nodes.py L2049-2060 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Sampler_Scheduler_Settings:
    CATEGORY = 'JPS Nodes/Settings'
    RETURN_TYPES = (comfy.samplers.KSampler.SAMPLERS,comfy.samplers.KSampler.SCHEDULERS,)
    RETURN_NAMES = ("sampler_name","scheduler",)
    FUNCTION = "get_samsched"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"sampler_name": (comfy.samplers.KSampler.SAMPLERS,),"scheduler": (comfy.samplers.KSampler.SCHEDULERS,)}}

    def get_samsched(self, sampler_name, scheduler):
        return (sampler_name, scheduler, )


# ComfyUI_JPS-Nodes/jps_nodes.py L2147-2185 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Model_Switch:

    CATEGORY = 'JPS Nodes/Switches'
    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model_out",)
    FUNCTION = "get_model"

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "select": ("INT", {}),
            },
            "optional": {
                "model_1": ("MODEL",),
                "model_2": ("MODEL",),
                "model_3": ("MODEL",),
                "model_4": ("MODEL",),
                "model_5": ("MODEL",),
            }
        }

    def get_model(self,select,model_1,model_2=None,model_3=None,model_4=None,model_5=None,):
        
        model_out = model_1

        if (select == 2):
            model_out = model_2
        elif (select == 3):
            model_out  = model_3
        elif (select == 4):
            model_out = model_4
        elif (select == 5):
            model_out = model_5

        return (model_out,)


# ComfyUI_JPS-Nodes/jps_nodes.py L2231-2269 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Latent_Switch:

    CATEGORY = 'JPS Nodes/Switches'
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent_out",)
    FUNCTION = "get_latent"

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "select": ("INT", {}),
            },
            "optional": {
                "latent_1": ("LATENT",),
                "latent_2": ("LATENT",),
                "latent_3": ("LATENT",),
                "latent_4": ("LATENT",),
                "latent_5": ("LATENT",),
            }
        }

    def get_latent(self,select,latent_1=None,latent_2=None,latent_3=None,latent_4=None,latent_5=None,):
        
        latent_out = latent_1

        if (select == 2):
            latent_out = latent_2
        elif (select == 3):
            latent_out = latent_3
        elif (select == 4):
            latent_out = latent_4
        elif (select == 5):
            latent_out = latent_5

        return (latent_out,)


# ComfyUI_JPS-Nodes/jps_nodes.py L2315-2353 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Integer_Switch:

    CATEGORY = 'JPS Nodes/Switches'
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("int_out",)
    FUNCTION = "get_int"

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "select": ("INT", {}),
            },
            "optional": {
                "int_1": ("INT", {}),
                "int_2": ("INT", {}),
                "int_3": ("INT", {}),
                "int_4": ("INT", {}),
                "int_5": ("INT", {}),
            }
        }

    def get_int(self,select,int_1=None,int_2=None,int_3=None,int_4=None,int_5=None,):
        
        int_out = int_1

        if (select == 2):
            int_out = int_2
        elif (select == 3):
            int_out = int_3
        elif (select == 4):
            int_out = int_4
        elif (select == 5):
            int_out = int_5

        return (int_out,)


# ComfyUI_JPS-Nodes/jps_nodes.py L2622-2645 (pristine sha256 ed7fcd08d8b931f3592a35ae8a38ef0dc44f8430ffc36003768f1826d655547e)
class Get_Image_Size:
    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("INT", "INT",)
    RETURN_NAMES = ("width", "height",)
    CATEGORY = "JPS Nodes/Image"

    FUNCTION = 'get_imagesize'

    def get_imagesize(self, image):
        samples = image.movedim(-1,1)
        size_w = samples.shape[3]
        size_h = samples.shape[2]

        return (size_w, size_h, )

