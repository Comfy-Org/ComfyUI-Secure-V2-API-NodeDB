import csv
import os

import numpy as np
import torch

import folder_paths

import comfy.model_management

custom_nodes_dir = folder_paths.get_folder_paths("custom_nodes")[0]
presets_dir = os.path.join(custom_nodes_dir, "ComfyUI-SizeFromArray", "presets")
    
class SizeFromArray:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sizes": ("STRING", {"default": "512,512\n512,768\n768,512\n", "multiline": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
        }

    RETURN_TYPES = ("INT","INT")
    RETURN_NAMES = ("width","height")
    FUNCTION = "get_size"
    CATEGORY = "SizeFromArray"
    DESCRIPTION = """
Return random pair of width&height from given array  

For example the default values:  
512,512
512,768
768,512
  
Would return random pair from 512x512, 512x768 or 768x512
"""

    def get_size(self, sizes, seed):
        random_gen = np.random.default_rng(seed)
        
        lines = [line for line in sizes.split('\n') if line] # Split the string into lines (except empty ones)
        tuples_array = [ tuple(map(int, line.strip().split(','))) for line in lines] 
        
        preset = random_gen.choice(tuples_array)
                
        return (preset[0], preset[1])