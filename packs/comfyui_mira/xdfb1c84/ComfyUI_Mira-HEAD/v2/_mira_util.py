"""ComfyUI_Mira Util.py, the helpers and classes the converted nodes run, copied verbatim (pin dfb1c847).

Util.py imports cv2, comfy, folder_paths and torchvision at module level, so a guest cannot import it. Names bound here
(not Mira code):
  - con: torchvision.transforms.functional's PIL path of adjust_contrast and adjust_sharpness, vendored verbatim in
    _vendor_torchvision.py (ImageContrast and ImageSharpness pass PIL images);
  - ColorTransfer: color_transfer.py's class, copied verbatim in _mira_color_transfer.py;
  - node: v3schema.py's, imported as it is (define_schema is not called in v2: the schemas are frozen).
Copied:
#   cat: ComfyUI_Mira/Util.py L32-32
#   cat_image: ComfyUI_Mira/Util.py L33-33
#   DecodeImage: ComfyUI_Mira/Util.py L35-38
#   EncodeImage: ComfyUI_Mira/Util.py L40-43
#   ConvertToNP: ComfyUI_Mira/Util.py L45-48
#   SafeCheck: ComfyUI_Mira/Util.py L50-63
#   Fixeight: ComfyUI_Mira/Util.py L65-73
#   CanvasCreatorSimple: ComfyUI_Mira/Util.py L135-190
#   CanvasCreatorAdvanced: ComfyUI_Mira/Util.py L193-275
#   SeedGenerator: ComfyUI_Mira/Util.py L543-572
#   ImageContrast: ComfyUI_Mira/Util.py L613-658
#   ImageSharpness: ComfyUI_Mira/Util.py L660-705
#   ImageColorTransfer: ComfyUI_Mira/Util.py L895-984
"""
import math

import numpy as np
import torch
from PIL import Image

from . import _vendor_torchvision as con
from ._mira_color_transfer import ColorTransfer
from .v3schema import node
from comfy_api.latest import IO


# ComfyUI_Mira/Util.py L32-32 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
cat = "Mira/Util"


# ComfyUI_Mira/Util.py L33-33 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
cat_image = "Mira/Util/Image"


# ComfyUI_Mira/Util.py L35-38 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
def DecodeImage(src_image):
    i = 255. * src_image[0].cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))    
    return img


# ComfyUI_Mira/Util.py L40-43 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
def EncodeImage(src_image):
    img = np.array(src_image).astype(np.float32) / 255.0
    img = torch.from_numpy(img)[None,]
    return img


# ComfyUI_Mira/Util.py L45-48 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
def ConvertToNP(src_image):            
    i = 255. * src_image[0].cpu().numpy()
    array_image = np.clip(i, 0, 255).astype(np.uint8)
    return array_image.astype(np.float32)           


# ComfyUI_Mira/Util.py L50-63 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
def SafeCheck(Width = 16, Height = 16, Batch = 1, HiResMultiplier = 1.0):
        if 16 > Width:
            Width = 16
            
        if 16 > Height:
            Height = 16
            
        if 1 > Batch:
            Batch = 1
            
        if 1.0 > HiResMultiplier:
            HiResMultiplier = 1.0
        
        return Width, Height, Batch, HiResMultiplier


# ComfyUI_Mira/Util.py L65-73 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
def Fixeight(num):
    new_num = int(num)
    if 0 != math.floor(num)%8:
        residue = math.floor(num)%8
        if 3 >= math.floor(num)%8:
            new_num = math.floor(num) - residue
        else:
            new_num = math.floor(num) + 8 - residue    
    return new_num


# ComfyUI_Mira/Util.py L135-190 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
class CanvasCreatorSimple(IO.ComfyNode):
    '''
    Create Canvas information Width and Height for Latent with Landscape switch.
    
    Inputs:
    Width       - Image Width
    Height      - Image Height
    Landscape   - When ENABLED, will swap Width and Height for output
        
    Outputs:
    Width       - Image Width
    Height      - Image Height
    '''
    @classmethod
    def define_schema(cls):
        return node(
            "CanvasCreatorSimple",
            cat,
            cls._v1_inputs(),
            ("INT","INT",),
            ("Width","Height",),
        )

    @classmethod
    def _v1_inputs(s):
        return {
            "required": {
                "Width": ("INT", {
                    "default": 576,
                    "min": 16,
                    "max": 4096,
                    "step": 8,
                    "display": "number" 
                }),
                "Height": ("INT", {
                    "default": 1024,
                    "min": 16,
                    "max": 4096,
                    "step": 8,
                    "display": "number" 
                }),
                "Landscape": ("BOOLEAN", {
                    "default": False
                }),
            },
        }
                
    
    @classmethod
    def execute(cls, Width, Height, Landscape):                         
        Width, Height, Batch, HiResMultiplier = SafeCheck(Width, Height)
        
        if(False == Landscape):
            return(Width, Height,)
        else:
            return(Height, Width,)


# ComfyUI_Mira/Util.py L193-275 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
class CanvasCreatorAdvanced(IO.ComfyNode):
    '''
    Create Canvas information Width and Height for Latent with Landscape switch, Batch and HiResMultiplier.
    
    Inputs:
    Width           - Image Width
    Height          - Image Height
    Landscape       - When ENABLED, will swap Width and Height for output
    Batch           - Batch size for Latent
    HiResMultiplier - Multiplier setting for high-resolution output 
        
    Outputs:
    Width           - Image Width for Latent
    Height          - Image Height for Latent
    Batch           - Batch size for Latent
    HiRes Width     - Width x HiResMultiplier. The result is not the product of the original data, but the nearest multiple of 8.
    HiRes Height    - Height x HiResMultiplier. 
    HiResMultiplier - Same as Input
    '''
    @classmethod
    def define_schema(cls):
        return node(
            "CanvasCreatorAdvanced",
            cat,
            cls._v1_inputs(),
            ("INT","INT","INT","INT","INT","FLOAT"),
            ("Width","Height","Batch","HiRes Width","HiRes Height","HiResMultiplier",),
        )

    @classmethod
    def _v1_inputs(s):
        return {
            "required": {
                "Width": ("INT", {
                    "default": 576,
                    "min": 16,
                    "max": 4096,
                    "step": 8,
                    "display": "number" 
                }),
                "Height": ("INT", {
                    "default": 1024,
                    "min": 16,
                    "max": 4096,
                    "step": 8,
                    "display": "number" 
                }),
                "Batch": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 16,
                    "step": 1,
                    "display": "number" 
                }),
                "Landscape": ("BOOLEAN", {
                    "default": False
                }),
                "HiResMultiplier": ("FLOAT", {
                    "default": 1.5,
                    "min": 0.1,
                    "max": 8,
                    "step": 0.1,
                    "display": "number" 
                }),
            },
        }

    
    @classmethod
    def execute(cls, Width, Height, Batch, Landscape, HiResMultiplier):              
        Width, Height, Batch, HiResMultiplier = SafeCheck(Width, Height, Batch, HiResMultiplier)
            
        HiResWidth = Fixeight(Width * HiResMultiplier)
        HiResHeight = Fixeight(Height * HiResMultiplier)
                
        if(False == Landscape):            
            intHiResHeight = math.floor(HiResHeight)
            intHiResWidth = math.floor(HiResWidth)
            return(Width, Height, Batch, intHiResWidth, intHiResHeight, HiResMultiplier, )
        else:            
            intHiResHeight = math.floor(HiResHeight)
            intHiResWidth = math.floor(HiResWidth)
            return(Height, Width, Batch, intHiResHeight, intHiResWidth, HiResMultiplier, )


# ComfyUI_Mira/Util.py L543-572 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
class SeedGenerator(IO.ComfyNode):
    '''
    SeedGenerator
    '''
    @classmethod
    def define_schema(cls):
        return node(
            "SeedGeneratorMira",
            cat,
            cls._v1_inputs(),
            ("INT",),
            ("seed",),
        )

    @classmethod
    def _v1_inputs(s):
        return {
            "required": {
                "seed": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 0xffffffffffffffff
                }),
            },            
        }
        
    
    @classmethod
    def execute(cls, seed):
        return(seed,)


# ComfyUI_Mira/Util.py L613-658 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
class ImageContrast(IO.ComfyNode):
    '''
    Adjust Image Contrast
    
    Inputs:
    src_image           - Source Image
    level               - Contrast Level, default is 1.0
            
    Outputs:
    image               - Torched Image                    
    '''
    @classmethod
    def define_schema(cls):
        return node(
            "ImageContrast",
            cat_image,
            cls._v1_inputs(),
            ("IMAGE",),
            ("image",),
        )

    
    @classmethod
    def _v1_inputs(s):
        return {
            "required": {
                "src_image": ("IMAGE", {
                    "default": None, 
                }),       
                "level": ("FLOAT", {
                    "default": 1.0, 
                    "step": 0.001,
                    "min": 0, 
                    "max": 10
                }),         
            },            
        }
        
    
    @classmethod
    def execute(cls, src_image, level):         
        img = DecodeImage(src_image)            
        img_adj = con.adjust_contrast(img, level)                     
        result = EncodeImage(img_adj)
        
        return(result,)


# ComfyUI_Mira/Util.py L660-705 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
class ImageSharpness(IO.ComfyNode):
    '''
    Adjust Image Sharpness
    
    Inputs:
    src_image           - Source Image
    level               - Sharpness Level, default is 1.0
            
    Outputs:
    image               - Torched Image                    
    '''
    @classmethod
    def define_schema(cls):
        return node(
            "ImageSharpness",
            cat_image,
            cls._v1_inputs(),
            ("IMAGE",),
            ("image",),
        )

    
    @classmethod
    def _v1_inputs(s):
        return {
            "required": {
                "src_image": ("IMAGE", {
                    "default": None, 
                }),       
                "level": ("FLOAT", {
                    "default": 1.0, 
                    "step": 0.1,
                    "min": 0, 
                    "max": 100
                }),       
            },            
        }
        
    
    @classmethod
    def execute(cls, src_image, level):         
        img = DecodeImage(src_image)            
        img_adj = con.adjust_sharpness(img, level)                     
        result = EncodeImage(img_adj)
        
        return(result,)


# ComfyUI_Mira/Util.py L895-984 (sha256 6d291059da957b23328a5097243561bbaa08117326f55c6ecf163ac44455e7f3)
class ImageColorTransfer(IO.ComfyNode):
    '''
    Refer to: https://en.wikipedia.org/wiki/Image_color_transfer
    
    Image Color Transfer
    
    Inputs:
    src_image           - Source Image
    ref_image           - Reference image. The colors of this Image will applied to the Source Image
            
    Outputs:
    image               - Output Image                    
    '''
    @classmethod
    def define_schema(cls):
        return node(
            "ImageColorTransferMira",
            cat_image,
            cls._v1_inputs(),
            ("IMAGE",),
            ("image",),
        )

    
    @classmethod
    def _v1_inputs(s):
        return {
            "required": {
                "src_image": ("IMAGE", {
                    "default": None, 
                }),       
                "ref_image": ("IMAGE", {
                    "default": None, 
                }),
                "method" : (['Mean', 'Lab', 'Pdf', 'Pdf+Regrain'], ),
            },            
        }
        
    
    @classmethod
    def execute(cls, src_image, ref_image, method):
        if not isinstance(src_image, torch.Tensor):
            raise ValueError("src_image must be a torch.Tensor")
        if not isinstance(ref_image, torch.Tensor):
            raise ValueError("ref_image must be a torch.Tensor")

        if src_image.ndim == 3:
            src_image = src_image.unsqueeze(0)
        if ref_image.ndim == 3:
            ref_image = ref_image.unsqueeze(0)

        batch_size = src_image.shape[0]
        ref_batch_size = ref_image.shape[0]

        # Ensure ref_image batch size is either 1 or equal to src_image batch size
        if ref_batch_size == 1:
            ref_images = [ref_image[0]] * batch_size
        elif ref_batch_size == batch_size:
            ref_images = [ref_image[i] for i in range(batch_size)]
        else:
            raise ValueError("ref_image batch size must be 1 or equal to src_image batch size")

        PT = ColorTransfer()
        out_imgs = []
        for i in range(batch_size):
            s = src_image[i].unsqueeze(0)
            r = ref_images[i].unsqueeze(0)
            if method == "Mean":
                s_np = ConvertToNP(s)
                r_np = ConvertToNP(r)
                new_img = PT.mean_std_transfer(img_arr_in=s_np, img_arr_ref=r_np)
            elif method == "Lab":
                s_pil = np.array(DecodeImage(s), dtype=np.uint8)
                r_pil = np.array(DecodeImage(r), dtype=np.uint8)
                new_img = PT.lab_transfer(img_arr_in=s_pil, img_arr_ref=r_pil)
            elif method == "Pdf":
                s_np = ConvertToNP(s)
                r_np = ConvertToNP(r)
                new_img = PT.pdf_transfer(img_arr_in=s_np, img_arr_ref=r_np, regrain=False)
            else:
                s_np = ConvertToNP(s)
                r_np = ConvertToNP(r)
                new_img = PT.pdf_transfer(img_arr_in=s_np, img_arr_ref=r_np, regrain=True)
            result = EncodeImage(new_img)
            out_imgs.append(result)

        out_imgs_tensor = torch.cat(out_imgs, dim=0)
        if out_imgs_tensor.ndim == 3:
            out_imgs_tensor = out_imgs_tensor.unsqueeze(0)
        return (out_imgs_tensor,)                                       

