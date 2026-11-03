"""mikey_nodes upstream code for Secure Nodes V2 (pin a5aa9cf637c4).

The functions and classes below are copied verbatim from the pristine mikey_nodes.py as AST source segments
(line ranges and the file's sha256 on each). The V2 node classes in _secure_used.py call them.
Boundary stand-ins (not upstream code):
  folder_paths  the user directory and Core's folder do not exist in the guest, so read_ratios uses the pack's own
                ratios.json only (the user_ratios.json extension is a known difference); the output directory is
                the engine's (the V2 save nodes write through the SDK)
  comfy.utils.common_upscale  Core's own function, copied verbatim in _core_upscale.py
  find_and_replace_wildcards  verbatim in _mikey_wildcards.py, reading the wildcard asset kind
  OobaPrompt    the original sends <llm:...> text to a text-generation server over the network; the guest has
                no network, so its api_request raises a named refusal
Copied:
#   mikey_nodes/mikey_nodes.py L175-194 find_latent_size
#   mikey_nodes/mikey_nodes.py L205-215 find_tile_dimensions
#   mikey_nodes/mikey_nodes.py L217-237 read_ratios
#   mikey_nodes/mikey_nodes.py L425-513 search_and_replace
#   mikey_nodes/mikey_nodes.py L413-423 process_wildcard_syntax
#   mikey_nodes/mikey_nodes.py L592-622 process_random_syntax
#   mikey_nodes/mikey_nodes.py L667-668 tensor2pil
#   mikey_nodes/mikey_nodes.py L671-672 pil2tensor
#   mikey_nodes/mikey_nodes.py L2821-2861 split_image
#   mikey_nodes/mikey_nodes.py L2863-2909 stitch_images
#   mikey_nodes/mikey_nodes.py L689-719 WildcardProcessor
#   mikey_nodes/mikey_nodes.py L752-767 EmptyLatentRatioSelector
#   mikey_nodes/mikey_nodes.py L1004-1018 INTtoSTRING
#   mikey_nodes/mikey_nodes.py L1058-1078 RangeInteger
#   mikey_nodes/mikey_nodes.py L1080-1103 ResizeImageSDXL
#   mikey_nodes/mikey_nodes.py L1446-1623 SaveImagesMikeyML
#   mikey_nodes/mikey_nodes.py L1747-1778 FileNamePrefix
#   mikey_nodes/mikey_nodes.py L1780-1811 FileNamePrefixDateDirFirst
#   mikey_nodes/mikey_nodes.py L3702-3730 UpscaleTileCalculator
#   mikey_nodes/mikey_nodes.py L3732-3744 IntegerAndString
#   mikey_nodes/mikey_nodes.py L4242-4275 TextConcat
#   mikey_nodes/mikey_nodes.py L4277-4300 RemoveTextBetween
#   mikey_nodes/mikey_nodes.py L4667-4712 WildcardOobaPrompt
"""
import datetime
import json
import os
import random
import re
import types
from fractions import Fraction
from math import ceil, pow, gcd

import numpy as np
import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from ._core_upscale import common_upscale as _common_upscale
from ._mikey_wildcards import find_and_replace_wildcards

# ---------------------------------------------------------------- boundary stand-ins
folder_paths = types.SimpleNamespace(
    __file__="/nonexistent/comfyui/folder_paths.py",
    get_user_directory=lambda: "/nonexistent/comfyui/user",
    get_output_directory=lambda: "",
)
comfy = types.SimpleNamespace(utils=types.SimpleNamespace(common_upscale=_common_upscale))


class LlmSyntaxRefused(RuntimeError):
    """<llm:...> needs a text-generation server over the network."""


class OobaPrompt:
    def api_request(self, prompt_text, seed, mode, custom_history=None):
        raise LlmSyntaxRefused(
            "mikey_nodes/WildcardOobaPrompt: <llm:...> is not yet converted to Secure Nodes V2: it sends the text to a "
            "text-generation server over the network, and a Secure Nodes V2 guest has no network")


# ---------------------------------------------------------------- upstream mikey_nodes.py
# mikey_nodes/mikey_nodes.py L175-194 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def find_latent_size(width: int, height: int, res: int = 1024) -> (int, int):
    best_w = 0
    best_h = 0
    target_ratio = Fraction(width, height)

    for i in range(1, 256):
        for j in range(1, 256):
            if Fraction(8 * i, 8 * j) > target_ratio * 0.98 and Fraction(8 * i, 8 * j) < target_ratio and 8 * i * 8 * j <= res * res:
                candidates = [
                    (ceil(8 * i / 64) * 64, ceil(8 * j / 64) * 64),
                    (8 * i // 64 * 64, ceil(8 * j / 64) * 64),
                    (ceil(8 * i / 64) * 64, 8 * j // 64 * 64),
                    (8 * i // 64 * 64, 8 * j // 64 * 64),
                ]
                for w, h in candidates:
                    if w * h > res * res:
                        continue
                    if w * h > best_w * best_h:
                        best_w, best_h = w, h
    return best_w, best_h


# mikey_nodes/mikey_nodes.py L205-215 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def find_tile_dimensions(width: int, height: int, multiplier: float, res: int) -> (int, int):
    new_width = int(width * multiplier) // 8 * 8
    new_height = int(height * multiplier) // 8 * 8

    width_multiples = max(1, new_width // res)
    height_multiples = max(1, new_height // res)

    tile_width = new_width // width_multiples
    tile_height = new_height // height_multiples

    return int(tile_width), int(tile_height)


# mikey_nodes/mikey_nodes.py L217-237 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def read_ratios():
    p = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(p, 'ratios.json')
    with open(file_path, 'r') as file:
        data = json.load(file)
    ratio_sizes = list(data['ratios'].keys())
    ratio_dict = data['ratios']
    # user_styles.json
    user_styles_path = os.path.join(folder_paths.get_user_directory(), 'user_ratios.json')
    # backwards compatibility with pre paths update to comfy
    if not os.path.isfile(user_styles_path):
        user_styles_path = os.path.join(os.path.dirname(folder_paths.__file__), 'user_ratios.json')
    # check if file exists
    if os.path.isfile(user_styles_path):
        # read json and update ratio_dict
        with open(user_styles_path, 'r') as file:
            user_data = json.load(file)
        for ratio in user_data['ratios']:
            ratio_dict[ratio] = user_data['ratios'][ratio]
            ratio_sizes.append(ratio)
    return ratio_sizes, ratio_dict


# mikey_nodes/mikey_nodes.py L425-513 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def search_and_replace(text, extra_pnginfo, prompt):
    if extra_pnginfo is None or prompt is None:
        return text
    # if %date: in text, then replace with date
    #print(text)
    if '%date:' in text:
        for match in re.finditer(r'%date:(.*?)%', text):
            date_match = match.group(1)
            cursor = 0
            date_pattern = ''
            now = datetime.datetime.now()

            pattern_map = {
                'yyyy': now.strftime('%Y'),
                'yy': now.strftime('%y'),
                'MM': now.strftime('%m'),
                'M': now.strftime('%m').lstrip('0'),
                'dd': now.strftime('%d'),
                'd': now.strftime('%d').lstrip('0'),
                'hh': now.strftime('%H'),
                'h': now.strftime('%H').lstrip('0'),
                'mm': now.strftime('%M'),
                'm': now.strftime('%M').lstrip('0'),
                'ss': now.strftime('%S'),
                's': now.strftime('%S').lstrip('0')
            }

            sorted_keys = sorted(pattern_map.keys(), key=len, reverse=True)

            while cursor < len(date_match):
                replaced = False
                for key in sorted_keys:
                    if date_match.startswith(key, cursor):
                        date_pattern += pattern_map[key]
                        cursor += len(key)
                        replaced = True
                        break
                if not replaced:
                    date_pattern += date_match[cursor]
                    cursor += 1

            text = text.replace('%date:' + match.group(1) + '%', date_pattern)
    # Parse JSON if they are strings
    if isinstance(extra_pnginfo, str):
        extra_pnginfo = json.loads(extra_pnginfo)
    if isinstance(prompt, str):
        prompt = json.loads(prompt)

    # Map from "Node name for S&R" to id in the workflow
    node_to_id_map = {}
    try:
        for node in extra_pnginfo['workflow']['nodes']:
            node_name = node['properties'].get('Node name for S&R')
            node_id = node['id']
            node_to_id_map[node_name] = node_id
    except:
        return text

    # Find all patterns in the text that need to be replaced
    patterns = re.findall(r"%([^%]+)%", text)
    for pattern in patterns:
        # Split the pattern to get the node name and widget name
        node_name, widget_name = pattern.split('.')

        # Find the id for this node name
        node_id = node_to_id_map.get(node_name)
        if node_id is None:
            print(f"No node with name {node_name} found.")
            # check if user entered id instead of node name
            if node_name in node_to_id_map.values():
                node_id = node_name
            else:
                continue

        # Find the value of the specified widget in prompt JSON
        prompt_node = prompt.get(str(node_id))
        if prompt_node is None:
            print(f"No prompt data for node with id {node_id}.")
            continue

        widget_value = prompt_node['inputs'].get(widget_name)
        if widget_value is None:
            print(f"No widget with name {widget_name} found for node {node_name}.")
            continue

        # Replace the pattern in the text
        text = text.replace(f"%{pattern}%", str(widget_value))

    return text


# mikey_nodes/mikey_nodes.py L413-423 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def process_wildcard_syntax(text, seed):
    # wildcard sytax is {like|this}
    # select a random word from the | separated list
    random.seed(seed)
    wc_re = re.compile(r'{([^{}]*)}')
    def repl(m):
        parts = m.group(1).split('|')
        return random.choice(parts)
    while wc_re.search(text):
        text = wc_re.sub(repl, text)
    return text


# mikey_nodes/mikey_nodes.py L592-622 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def process_random_syntax(text, seed):
    #print('checking for random syntax')
    random.seed(seed)
    random_re = r'<random:(-?\d*\.?\d+):(-?\d*\.?\d+)>'
    matches = re.finditer(random_re, text)

    # Create a list to hold the new segments of text
    new_text_list = []
    last_end = 0

    # Iterate through matches
    for match in matches:
        lower_bound, upper_bound = map(float, match.groups())
        random_value = random.uniform(lower_bound, upper_bound)
        random_value = round(random_value, 4)

        # Append text up to the match and the generated number
        new_text_list.append(text[last_end:match.start()])
        new_text_list.append(str(random_value))

        # Update the index of the last match end
        last_end = match.end()

    # Append remaining text after the last match
    new_text_list.append(text[last_end:])

    # Combine the list into a single string
    new_text = ''.join(new_text_list)

    #print(new_text)
    return new_text


# mikey_nodes/mikey_nodes.py L667-668 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))


# mikey_nodes/mikey_nodes.py L671-672 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


# mikey_nodes/mikey_nodes.py L2821-2861 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def split_image(img, tile_size=1024):
    """Generate tiles for a given image."""
    tile_width, tile_height = tile_size, tile_size
    width, height = img.width, img.height

    # Determine the number of tiles needed
    num_tiles_x = ceil(width / tile_width)
    num_tiles_y = ceil(height / tile_height)

    # If width or height is an exact multiple of the tile size, add an additional tile for overlap
    if width % tile_width == 0:
        num_tiles_x += 1
    if height % tile_height == 0:
        num_tiles_y += 1

    # Calculate the overlap
    overlap_x = (num_tiles_x * tile_width - width) / (num_tiles_x - 1)
    overlap_y = (num_tiles_y * tile_height - height) / (num_tiles_y - 1)
    if overlap_x < 256:
        num_tiles_x += 1
        overlap_x = (num_tiles_x * tile_width - width) / (num_tiles_x - 1)
    if overlap_y < 256:
        num_tiles_y += 1
        overlap_y = (num_tiles_y * tile_height - height) / (num_tiles_y - 1)

    tiles = []

    for i in range(num_tiles_y):
        for j in range(num_tiles_x):
            x_start = j * tile_width - j * overlap_x
            y_start = i * tile_height - i * overlap_y

            # Correct for potential float precision issues
            x_start = round(x_start)
            y_start = round(y_start)

            # Crop the tile from the image
            tile_img = img.crop((x_start, y_start, x_start + tile_width, y_start + tile_height))
            tiles.append(((x_start, y_start, x_start + tile_width, y_start + tile_height), tile_img))

    return tiles


# mikey_nodes/mikey_nodes.py L2863-2909 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def stitch_images(upscaled_size, tiles):
    """Stitch tiles together to create the final upscaled image with overlaps."""
    width, height = upscaled_size
    result = torch.zeros((3, height, width))

    # We assume tiles come in the format [(coordinates, tile), ...]
    sorted_tiles = sorted(tiles, key=lambda x: (x[0][1], x[0][0]))  # Sort by upper then left

    # Variables to keep track of the current row's starting point
    current_row_upper = None

    for (left, upper, right, lower), tile in sorted_tiles:

        # Check if we're starting a new row
        if current_row_upper != upper:
            current_row_upper = upper
            first_tile_in_row = True
        else:
            first_tile_in_row = False

        tile_width = right - left
        tile_height = lower - upper
        feather = tile_width // 8  # Assuming feather size is consistent with the example

        mask = torch.ones(tile.shape[0], tile.shape[1], tile.shape[2])

        if not first_tile_in_row:  # Left feathering for tiles other than the first in the row
            for t in range(feather):
                mask[:, :, t:t+1] *= (1.0 / feather) * (t + 1)

        if upper != 0:  # Top feathering for all tiles except the first row
            for t in range(feather):
                mask[:, t:t+1, :] *= (1.0 / feather) * (t + 1)

        # Apply the feathering mask
        tile = tile.squeeze(0).squeeze(0)  # Removes first two dimensions
        tile_to_add = tile.permute(2, 0, 1)
        # Use the mask to correctly feather the new tile on top of the existing image
        combined_area = tile_to_add * mask.unsqueeze(0) + result[:, upper:lower, left:right] * (1.0 - mask.unsqueeze(0))
        result[:, upper:lower, left:right] = combined_area

    # Expand dimensions to get (1, 3, height, width)
    tensor_expanded = result.unsqueeze(0)

    # Permute dimensions to get (1, height, width, 3)
    tensor_final = tensor_expanded.permute(0, 2, 3, 1)
    return tensor_final


# mikey_nodes/mikey_nodes.py L689-719 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class WildcardProcessor:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"prompt": ("STRING", {"multiline": True, "placeholder": "Prompt Text"}),
                             "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff})},
                "hidden": {"prompt_": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},}

    RETURN_TYPES = ('STRING',)
    FUNCTION = 'process'
    CATEGORY = 'Mikey/Text'

    def process(self, prompt, seed, prompt_=None, extra_pnginfo=None):
        if prompt_ is None:
            prompt_ = {}
        if extra_pnginfo is None:
            extra_pnginfo = {}
        prompt = search_and_replace(prompt, extra_pnginfo, prompt_)
        prompt = process_wildcard_syntax(prompt, seed)
        prompt = process_random_syntax(prompt, seed)
        new_prompt = find_and_replace_wildcards(prompt, seed)
        # loop to pick up wildcards that are in wildcard files
        if new_prompt != prompt:
            for i in range(10):
                prompt = new_prompt
                prompt = search_and_replace(prompt, extra_pnginfo, prompt_)
                prompt = process_wildcard_syntax(prompt, seed)
                prompt = process_random_syntax(prompt, seed)
                new_prompt = find_and_replace_wildcards(prompt, seed)
                if new_prompt == prompt:
                    break
        return (new_prompt, )


# mikey_nodes/mikey_nodes.py L752-767 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class EmptyLatentRatioSelector:
    @classmethod
    def INPUT_TYPES(s):
        s.ratio_sizes, s.ratio_dict = read_ratios()
        return {'required': {'ratio_selected': (s.ratio_sizes,),
                             "batch_size": ("INT", {"default": 1, "min": 1, "max": 64})}}

    RETURN_TYPES = ('LATENT',)
    FUNCTION = 'generate'
    CATEGORY = 'Mikey/Latent'

    def generate(self, ratio_selected, batch_size=1):
        width = self.ratio_dict[ratio_selected]["width"]
        height = self.ratio_dict[ratio_selected]["height"]
        latent = torch.zeros([batch_size, 4, height // 8, width // 8])
        return ({"samples":latent}, )


# mikey_nodes/mikey_nodes.py L1004-1018 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class INTtoSTRING:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"int_": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                             "use_commas": (['true','false'], {"default": 'false'})}}

    RETURN_TYPES = ('STRING',)
    FUNCTION = 'convert'
    CATEGORY = 'Mikey/Utils'

    def convert(self, int_, use_commas):
        if use_commas == 'true':
            return (f'{int_:,}', )
        else:
            return (f'{int_}', )


# mikey_nodes/mikey_nodes.py L1058-1078 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class RangeInteger:
    # using the seed value as the step in a range
    # generate a list of numbers from start to end with a step value
    # then select the number at the offset value
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"start": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                             "end": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                             "step": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                             "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff})}}

    RETURN_TYPES = ('INT','STRING',)
    FUNCTION = 'generate'
    CATEGORY = 'Mikey/Utils'

    def generate(self, start, end, step, seed):
        range_ = np.arange(start, end, step)
        list_of_numbers = list(range_)
        # offset
        offset = seed % len(list_of_numbers)
        return (list_of_numbers[offset], f'{list_of_numbers[offset]}',)


# mikey_nodes/mikey_nodes.py L1080-1103 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class ResizeImageSDXL:
    crop_methods = ["disabled", "center"]
    upscale_methods = ["nearest-exact", "bilinear", "area", "bicubic"]

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "image": ("IMAGE",), "upscale_method": (s.upscale_methods,),
                              "crop": (s.crop_methods,)}}

    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'resize'
    CATEGORY = 'Mikey/Image'

    def upscale(self, image, upscale_method, width, height, crop):
        samples = image.movedim(-1,1)
        s = comfy.utils.common_upscale(samples, width, height, upscale_method, crop)
        s = s.movedim(1,-1)
        return (s,)

    def resize(self, image, upscale_method, crop):
        w, h = find_latent_size(image.shape[2], image.shape[1])
        #print('Resizing image from {}x{} to {}x{}'.format(image.shape[2], image.shape[1], w, h))
        img = self.upscale(image, upscale_method, w, h, crop)[0]
        return (img, )


# mikey_nodes/mikey_nodes.py L1446-1623 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class SaveImagesMikeyML:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                    {"images": ("IMAGE", ),
                     'sub_directory': ("STRING", {'default': ''}),
                     "filename_text_1": ("STRING", {'default': 'Filename Text 1'}),
                     "filename_text_2": ("STRING", {'default': 'Filename Text 2'}),
                     "filename_text_3": ("STRING", {'default': 'Filename Text 3'}),
                     "filename_separator": ("STRING", {'default': '_'}),
                     "timestamp": (["true", "false"], {'default': 'true'}),
                     "counter_type": (["none", "folder", "filename"], {'default': 'folder'}),
                     "filename_text_1_pos": ("INT", {'default': 0}),
                     "filename_text_2_pos": ("INT", {'default': 2}),
                     "filename_text_3_pos": ("INT", {'default': 4}),
                     "timestamp_pos": ("INT", {'default': 1}),
                     "timestamp_type": (['job','save_time'], {'default': 'save_time'}),
                     "counter_pos": ("INT", {'default': 3}),
                     "extra_metadata": ("STRING", {'default': 'Extra Metadata'}),},
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Mikey/Image"

    def _prepare_filename_texts(self, filename_text_1, filename_text_2, filename_text_3, extra_pnginfo, prompt):
        # replace default values with empty strings
        filename_texts = [filename_text_1, filename_text_2, filename_text_3]
        default_texts = ['Filename Text 1', 'Filename Text 2', 'Filename Text 3']
        for i, text in enumerate(filename_texts):
            if text == default_texts[i]:
                filename_texts[i] = ''
            # use search and replace
            filename_texts[i] = search_and_replace(text, extra_pnginfo, prompt)
            # replace any special characters with nothing
            #filename_texts[i] = re.sub(r'[^a-zA-Z0-9 _-]', '', filename_texts[i])
            # replace only characters that are not allowed in filenames
            filename_texts[i] = re.sub(r'[<>:"/\\|?*]', '', filename_texts[i])
            # remove non ascii characters
            filename_texts[i] = filename_texts[i].encode('ascii', 'ignore').decode('ascii')

        # need to make sure the total filelength name is under 256 characters including the .png, separator, and counter
        # if the total length is over 256 characters, truncate the longest text to fit under 250 characters total length
        total_length = len(filename_texts[0]) + len(filename_texts[1]) + len(filename_texts[2]) + 5 + 5 + 12
        if total_length > 120:
            longest_text = max(filename_texts, key=len)
            longest_text_idx = filename_texts.index(longest_text)
            text_length_without_longest = total_length - len(longest_text)
            filename_texts[longest_text_idx] = longest_text[0:120 - text_length_without_longest]
        return filename_texts

    def _get_initial_counter(self, files, full_output_folder, counter_type, filename_separator, counter_pos, filename_texts):
        counter = 1
        if counter_type == "folder":
            if files:
                for f in files:
                    if filename_separator in f:
                        try:
                            counter = max(counter, int(f.split(filename_separator)[counter_pos]) + 1)
                        except:
                            counter = 1
                            break
            else:
                counter = 1
        elif counter_type == "filename":
            for f in files:
                f_split = f.split(filename_separator)
                # strip .png from strings
                f_split = [x.replace('.png', '') for x in f_split]
                matched_texts = all(
                    filename_texts[i] == f_split[i] for i in range(3) if filename_texts[i]
                )
                if matched_texts:
                    counter += 1
        return counter

    def _get_next_counter(self, full_output_folder, filename_base, counter):
        """Checks for the next available counter value."""
        while True:
            current_filename = filename_base.format(counter=f"{counter:05}")
            if not os.path.exists(os.path.join(full_output_folder, f"{current_filename}.png")):
                return counter
            counter += 1

    def save_images(self, images, sub_directory, filename_text_1, filename_text_2, filename_text_3,
                    filename_separator, timestamp, counter_type,
                    filename_text_1_pos, filename_text_2_pos, filename_text_3_pos,
                    timestamp_pos, timestamp_type, counter_pos, extra_metadata,
                    prompt=None, extra_pnginfo=None):
        positions = [filename_text_1_pos, filename_text_2_pos, filename_text_3_pos, timestamp_pos, counter_pos]
        if len(positions) != len(set(positions)):
            raise ValueError("Duplicate position numbers detected. Please ensure all position numbers are unique.")
        sub_directory = search_and_replace(sub_directory, extra_pnginfo, prompt)
        # strip special characters from sub_directory
        #sub_directory = re.sub(r'[^a-zA-Z0-9 _/\\]', '', sub_directory)
        # replace only characters that are not allowed in filenames
        sub_directory = re.sub(r'[<>:"|?*]', '', sub_directory)
        # remove non ascii characters
        sub_directory = sub_directory.encode('ascii', 'ignore').decode('ascii')
        full_output_folder = os.path.join(self.output_dir, sub_directory)
        os.makedirs(full_output_folder, exist_ok=True)

        filename_texts = self._prepare_filename_texts(filename_text_1, filename_text_2, filename_text_3, extra_pnginfo, prompt)

        if timestamp == 'true':
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        else:
            ts = ''

        elements = {
            filename_text_1_pos: filename_texts[0],
            filename_text_2_pos: filename_texts[1],
            filename_text_3_pos: filename_texts[2],
            timestamp_pos: ts,
            counter_pos: 'counter' if counter_type != 'none' else None
        }

        # Construct initial filename without the counter
        sorted_elements = [elem for _, elem in sorted(elements.items()) if elem]
        filename_base = filename_separator.join(sorted_elements).replace('counter', '{counter}')

        # Get initial counter value
        files = os.listdir(full_output_folder)
        if counter_type != 'none':
            counter = self._get_initial_counter(files, full_output_folder, counter_type, filename_separator, counter_pos, filename_texts)
        else:
            counter = 0

        results = list()
        for ix, image in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    if x == 'parameters':
                        # encode text as utf-8
                        text = extra_pnginfo[x].encode('utf-8').decode('utf-8')
                        metadata.add_text(x, text)
                    elif x == 'workflow':
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))
                    elif x == 'prompt':
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))
                    else:
                        metadata.add_text(x, json.dumps(extra_pnginfo[x], ensure_ascii=False))
            if extra_metadata:
                #metadata.add_text("extra_metadata", json.dumps(extra_metadata, ensure_ascii=False))
                metadata.add_text("extra_metadata", extra_metadata)
            # Check and get the next available counter
            if counter_type != 'none':
                counter = self._get_next_counter(full_output_folder, filename_base, counter)
                current_filename = filename_base.format(counter=f"{counter:05}")
            else:
                current_filename = filename_base
            if timestamp_type == 'save_time' and timestamp == 'true':
                current_timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
                current_filename = current_filename.replace(ts, current_timestamp)
                ts = current_timestamp
            if ix > 0 and counter_type == 'none':
                current_filename = current_filename.replace(ts, ts + f'_{ix:02}')
            img.save(os.path.join(full_output_folder, f"{current_filename}.png"), pnginfo=metadata, compress_level=4)
            results.append({
                "filename": f"{current_filename}.png",
                "subfolder": sub_directory,
                "type": self.type
            })
            if counter_type != 'none':
                counter += 1

        return {"ui": {"images": results}}


# mikey_nodes/mikey_nodes.py L1747-1778 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class FileNamePrefix:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {'date': (['true','false'], {'default':'true'}),
                             'date_directory': (['true','false'], {'default':'true'}),
                             'custom_directory': ('STRING', {'default': ''}),
                             'custom_text': ('STRING', {'default': ''})},
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},}

    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('filename_prefix',)
    FUNCTION = 'get_filename_prefix'
    CATEGORY = 'Mikey/Meta'

    def get_filename_prefix(self, date, date_directory, custom_directory, custom_text,
                            prompt=None, extra_pnginfo=None):
        filename_prefix = ''
        if custom_directory:
            custom_directory = search_and_replace(custom_directory, extra_pnginfo, prompt)
            filename_prefix += custom_directory + '/'
        if date_directory == 'true':
            ts_str = datetime.datetime.now().strftime("%y%m%d")
            filename_prefix += ts_str + '/'
        if date == 'true':
            ts_str = datetime.datetime.now().strftime("%y%m%d%H%M%S")
            filename_prefix += ts_str
        if custom_text != '':
            custom_text = search_and_replace(custom_text, extra_pnginfo, prompt)
            # remove invalid characters from filename
            custom_text = re.sub(r'[<>:"/\\|?*]', '', custom_text)
            filename_prefix += '_' + custom_text
        return (filename_prefix,)


# mikey_nodes/mikey_nodes.py L1780-1811 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class FileNamePrefixDateDirFirst:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {'date': (['true','false'], {'default':'true'}),
                             'date_directory': (['true','false'], {'default':'true'}),
                             'custom_directory': ('STRING', {'default': ''}),
                             'custom_text': ('STRING', {'default': ''})},
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},}

    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('filename_prefix',)
    FUNCTION = 'get_filename_prefix'
    CATEGORY = 'Mikey/Meta'

    def get_filename_prefix(self, date, date_directory, custom_directory, custom_text,
                            prompt=None, extra_pnginfo=None):
        filename_prefix = ''
        if date_directory == 'true':
            ts_str = datetime.datetime.now().strftime("%y%m%d")
            filename_prefix += ts_str + '/'
        if custom_directory:
            custom_directory = search_and_replace(custom_directory, extra_pnginfo, prompt)
            filename_prefix += custom_directory + '/'
        if date == 'true':
            ts_str = datetime.datetime.now().strftime("%y%m%d%H%M%S")
            filename_prefix += ts_str
        if custom_text != '':
            custom_text = search_and_replace(custom_text, extra_pnginfo, prompt)
            # remove invalid characters from filename
            custom_text = re.sub(r'[<>:"/\\|?*]', '', custom_text)
            filename_prefix += '_' + custom_text
        return (filename_prefix,)


# mikey_nodes/mikey_nodes.py L3702-3730 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class UpscaleTileCalculator:
    @classmethod
    def INPUT_TYPES(s):
        return {'required': {'image': ('IMAGE',),
                            # 'upscale_by': ('FLOAT', {'default': 1.0, 'min': 0.1, 'max': 10.0, 'step': 0.1}),
                             'tile_resolution': ('INT', {'default': 512, 'min': 1, 'max': 8192, 'step': 8})}}

    RETURN_TYPES = ('IMAGE', 'INT', 'INT')
    RETURN_NAMES = ('image', 'tile_width', 'tile_height')
    FUNCTION = 'calculate'
    CATEGORY = 'Mikey/Image'

    def upscale(self, image, upscale_method, width, height, crop):
        samples = image.movedim(-1,1)
        s = comfy.utils.common_upscale(samples, width, height, upscale_method, crop)
        s = s.movedim(1,-1)
        return (s,)

    def resize(self, image, width, height, upscale_method, crop):
        w, h = find_latent_size(image.shape[2], image.shape[1])
        #print('Resizing image from {}x{} to {}x{}'.format(image.shape[2], image.shape[1], w, h))
        img = self.upscale(image, upscale_method, w, h, crop)[0]
        return (img, )

    def calculate(self, image, tile_resolution):
        width, height = image.shape[2], image.shape[1]
        tile_width, tile_height = find_tile_dimensions(width, height, 1.0, tile_resolution)
        #print('Tile width: ' + str(tile_width), 'Tile height: ' + str(tile_height))
        return (image, tile_width, tile_height)


# mikey_nodes/mikey_nodes.py L3732-3744 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class IntegerAndString:
    @classmethod
    def INPUT_TYPES(s):
        return {'required': {'seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff})}}

    RETURN_TYPES = ('INT','STRING')
    RETURN_NAMES = ('seed','seed_string')
    FUNCTION = 'output'
    CATEGORY = 'Mikey/Utils'

    def output(self, seed):
        seed_string = str(seed)
        return (seed, seed_string,)


# mikey_nodes/mikey_nodes.py L4242-4275 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class TextConcat:
    # takes 5 text inputs and concatenates them into a single string
    # with an option for delimiter
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'delimiter': ('STRING', {'default': ' '})},
                'optional': {'text1': ('STRING', {'default': ''}),
                             'text2': ('STRING', {'default': ''}),
                             'text3': ('STRING', {'default': ''}),
                             'text4': ('STRING', {'default': ''}),
                             'text5': ('STRING', {'default': ''}),
                             }}

    RETURN_TYPES = ('STRING',)
    FUNCTION = 'concat'
    CATEGORY = 'Mikey/Text'

    def concat(self, delimiter, text1, text2, text3, text4, text5):
        # search and replace
        # concatenate the strings
        # text values might be none
        texts = []
        if text1:
            texts.append(text1)
        if text2:
            texts.append(text2)
        if text3:
            texts.append(text3)
        if text4:
            texts.append(text4)
        if text5:
            texts.append(text5)
        text = delimiter.join(texts)
        return (text,)


# mikey_nodes/mikey_nodes.py L4277-4300 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class RemoveTextBetween:
    # removes text between two strings
    # default start is <think> and end is </think>
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'text': ('STRING', {'multiline': True, 'default': 'Input Text Here', 'dynamicPrompts': False})},
                'optional': {'start': ('STRING', {'default': '<think>'}),
                             'end': ('STRING', {'default': '</think>'})}}
    
    RETURN_TYPES = ('STRING','STRING')
    RETURN_NAMES = ('text','removed_text')
    FUNCTION = 'remove'
    CATEGORY = 'Mikey/Text'

    def remove(self, text, start, end):
        # search and replace
        # remove text between start and end
        removed = re.findall(re.escape(start) + '(.*?)' + re.escape(end), text, flags=re.DOTALL)
        text = re.sub(re.escape(start) + '.*?' + re.escape(end), '', text, flags=re.DOTALL).lstrip().rstrip()
        if len(removed) == 1:
            removed_text = removed[0].lstrip().rstrip()
        else:
            removed_text = '\n'.join(removed)
        return (text, removed_text)


# mikey_nodes/mikey_nodes.py L4667-4712 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
class WildcardOobaPrompt:
    # processes wildcard syntax
    # and also processes a llm sytax using the oobaprompt class
    @classmethod
    def INPUT_TYPES(s):
        return {'required': {'input_prompt': ('STRING', {'multiline': True, 'default': 'Prompt Text Here', 'dynamicPrompts': False}),
                             #'mode': (['prompt', 'style', 'descriptor', 'custom'], {'default': 'prompt'}),
                             #'custom_history': ('STRING', {'multiline': False, 'default': 'path to history.json', 'dynamicPrompts': True}),
                             'seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff})},
                "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO", "prompt": "PROMPT"}}

    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('text',)
    FUNCTION = 'process'
    OUTPUT_NODE = True
    CATEGORY = 'Mikey/AI'

    def process(self, input_prompt, seed, prompt=None, unique_id=None, extra_pnginfo=None):
        # search and replace
        input_prompt = search_and_replace(input_prompt, extra_pnginfo, prompt)
        # wildcard sytax is {like|this}
        # select a random word from the | separated list
        wc_re = re.compile(r'{([^}]+)}')
        def repl(m):
            return random.choice(m.group(1).split('|'))
        for m in wc_re.finditer(input_prompt):
            input_prompt = input_prompt.replace(m.group(0), repl(m))
        # process wildcards
        input_prompt = find_and_replace_wildcards(input_prompt, seed, debug=True)
        # check if llm syntax is in the prompt
        # examples <llm:prompt:prompt text here>, <llm:style:prompt text here>, <llm:descriptor:prompt text here>
        # example for custom history file <llm:path/to/history.json:prompt text here>
        llm_re = re.compile(r'<llm:(.*?):(.*?)>')
        for m in llm_re.finditer(input_prompt):
            mode = m.group(1)
            if '.json' in mode:
                custom_history = mode
                mode = 'custom'
            else:
                custom_history = None
            prompt_text = m.group(2)
            ooba = OobaPrompt()
            result = ooba.api_request(prompt_text, seed, mode, custom_history)
            input_prompt = input_prompt.replace(m.group(0), result)
        prompt.get(str(unique_id))['inputs']['output_text'] = input_prompt
        return (input_prompt,)

