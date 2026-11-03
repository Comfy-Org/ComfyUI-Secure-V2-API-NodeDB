"""ComfyUI_Mira wai_illustrious_character_select.py, the English character selector, copied verbatim (pin dfb1c847).

The module imports requests and Util (cv2, comfy) at module level. At import its main() (L453-481)
reads json/settings.json (the LLM nodes' settings) and json/waiIllustriousSDXL_v160_characters.csv, downloading either
from GitHub when it is missing; the pinned pack ships both. _load_characters() below is main()'s character branch for
the shipped file, line for line, without the download (a guest has no network) and without the LLM settings (those
nodes are refused). It fills character_list_en, the module global the selector reads.
Copied:
#   cat: ComfyUI_Mira/wai_illustrious_character_select.py L19-19
#   illustrious_character_select_en: ComfyUI_Mira/wai_illustrious_character_select.py L361-433
"""
import math
import os

from .v3schema import node
from comfy_api.latest import IO

current_dir = os.path.dirname(os.path.abspath(__file__))
json_folder = os.path.join(current_dir, "json")
character_list_cn = ''
character_list_en = ''
character_dict = {}


def _load_characters():
    # main(): for the 'wai_character' item, with file_path = json/waiIllustriousSDXL_v160_characters.csv
    global character_list_cn
    global character_list_en
    file_path = os.path.join(json_folder, 'waiIllustriousSDXL_v160_characters.csv')
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in lines:
            key, value = line.split(',')
            character_dict[key.strip()]=value.strip()

    character_list_cn = list(character_dict.keys())
    character_list_cn.insert(0, "random")

    character_list_en = list(character_dict.values())
    character_list_en.insert(0, "random")


_load_characters()


# ComfyUI_Mira/wai_illustrious_character_select.py L19-19 (sha256 8006f9acaf2f3ff60c944fcd3b93cfe4f0dd9dd3c457070f066d8ca9d36e9e2b)
cat = "Mira/WAI_Character_Select"


# ComfyUI_Mira/wai_illustrious_character_select.py L361-433 (sha256 8006f9acaf2f3ff60c944fcd3b93cfe4f0dd9dd3c457070f066d8ca9d36e9e2b)
class illustrious_character_select_en(IO.ComfyNode):
    '''
    Same as illustrious_character_select
    But list in English tags
    '''                       
    @classmethod
    def define_schema(cls):
        return node(
            "illustrious_character_select_en",
            cat,
            cls._v1_inputs(),
            ("STRING","STRING",),
            ("prompt", "info",),
        )


    @classmethod
    def _v1_inputs(s):
        
        return {
            "optional": {
                "custom_prompt": ("STRING", {
                    "display": "input" ,
                    "multiline": True
                }),                      
            },
            "required": {
                "character": (character_list_en, ),
                "random_action_seed": ("INT", {
                    "default": 1024, 
                    "min": 0, 
                    "max": 0xffffffffffffffff,
                    "display": "input"
                }),
                "character_weight": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 2.0, "step": 0.05}),
                "insert_before_character" : ("BOOLEAN", {"default": False}),
            },
        }
                        
    
    @classmethod
    def execute(cls, character, random_action_seed, character_weight, insert_before_character, custom_prompt = ''):
        chara = ''
        rnd_character = ''
        
        if 'random' == character:
            index = random_action_seed % len(character_list_en)
            rnd_character = character_list_en[index]
            if 'random' == rnd_character:
                rnd_character = character_list_en[index+2]
            elif 'none' == rnd_character:
                rnd_character = character_list_en[index+1]
        else:
            rnd_character = character
            
        chara = rnd_character                                                      
        opt_chara = chara.replace('(', '\\(').replace(')', '\\)')          
        
        if not math.isclose(character_weight, 1.0):
            opt_chara = '({}:{:0.2f})'.format(opt_chara, character_weight)

        if not opt_chara.endswith(','):
            opt_chara = f'{opt_chara},'   
            
        if '' != custom_prompt and not custom_prompt.endswith(','):
            custom_prompt = f'{custom_prompt},'
                    
        prompt = f'{opt_chara} {custom_prompt}'
        if insert_before_character:            
            prompt = f'{custom_prompt} {opt_chara}'
        info = f'Character:{rnd_character}[{opt_chara}]\nCustom Promot:{custom_prompt}'
                
        return (prompt, info, )

