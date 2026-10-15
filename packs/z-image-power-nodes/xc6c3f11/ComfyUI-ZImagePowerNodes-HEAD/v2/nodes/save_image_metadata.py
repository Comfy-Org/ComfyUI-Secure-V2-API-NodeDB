"""
File    : save_image.py
Purpose : Node for saving a generated images to disk injecting CivitAI compatible metadata.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jan 18, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

The V3 schema documentation can be found here:
 - https://docs.comfy.org/custom-nodes/v3_migration

Code for the metadata extraction process used by CivitAI:
 - https://github.com/civitai/civitai/blob/main/src/utils/metadata/comfy.metadata.ts

"""

import json
from typing import Any

def get_class_type(node: dict) -> str:
    """Returns the class name of a node."""
    class_type = node.get("class_type", "") if isinstance(node ,dict) else ""
    class_type = class_type.partition(" //")[0]  #< Z-Image Power Nodes has a special format for class names.
    return class_type


def get_input_value(node: dict, input_name: str, /, *, default: Any = None) -> Any:
    """Returns the value of a node's input."""
    inputs = node.get("inputs")     if isinstance(node  , dict) else None
    value  = inputs.get(input_name) if isinstance(inputs, dict) else None
    return value


def get_input_bool(node: dict, input_name: str, /, *, default: bool = False) -> bool:
    value = get_input_value(node, input_name, default=default)
    if isinstance(value, bool):
        return value
    elif isinstance(value, (int,float)):
        return bool(value)
    elif isinstance(value, str):
        return str(value).lower() in ['true', 'yes', '1', 'on']
    return bool(default) if isinstance(default, bool) else False


def get_input_int(node: dict, input_name: str, /, *, default: int = 0) -> int:
    """
    Retrieves the integer value of an input from a given node.

    If `input_name` does not exist in the node or is a connection to
    another node, this function returns the specified `default` value.

    Args:
        node        (dict): The node from which to retrieve the input value.
        input_name   (str): The name of the input to look up.
        default (optional): The default integer value to return if the input
                            is not found or is a connection. Defaults to 0.

    Returns:
        The integer representation of the input value
        or the provided default integer value if it cannot be converted.
    """
    value = get_input_value(node, input_name, default=default)
    if isinstance(value, (int,float)):
        return int(value)
    elif isinstance(value, str):
        try   : return int(value)
        except: pass
    return int(default) if isinstance(default,(int,float)) else 0


def get_input_float(node: dict, input_name: str, /, *, default: float = 0.0) -> float:
    """
    Retrieves the floating-point value of an input from a given node.

    If `input_name` does not exist in the node or is a connection to
    another node, this function returns the specified `default` value.

    Args:
        node        (dict): The node from which to retrieve the input value.
        input_name   (str): The name of the input to look up.
        default (optional): The default float value to return if the input
                            is not found or is a connection. Defaults to 0.0.

    Returns:
        The floating-point representation of the input value
        or the provided default float value if it cannot be converted.
    """
    value = get_input_value(node, input_name, default=default)
    if isinstance(value, (float, int)):
        return float(value)
    elif isinstance(value, str):
        try   : return float(value)
        except: pass
    return float(default) if isinstance(default,(float,int)) else 0.0


def get_input_string(node: dict, input_name: str, *, default: str = "") -> str:
    """
    Retrieves the string value of an input from a given node.

    If `input_name` does not exist in the node or is a connection to
    another node, this function returns the specified `default` value.

    Args:
        node        (dict): The node from which to retrieve the input value.
        input_name   (str): The name of the input to look up.
        default (optional): The default string value to return if the input is not found or is a connection.
                            Defaults to an empty string.

    Returns:
        The string representation of the input value or the provided default string value.
    """
    value = get_input_value(node, input_name, default=default)
    if isinstance(value, (float,int)):
        return str(value)
    if isinstance(value, str):
        return value
    return default


def get_input_node(node: dict, input_name: str | list[str] | tuple[str], *, nodes: dict) -> dict:
    """
    Returns the connected node for a given input connection identifier.

    Args:
        node       : The base node from which to retrieve the connected input node.
        input_name : Name or list of names of the input connections to look up.
        nodes      : Dictionary containing the entire 'prompt' structure (all nodes).

    Returns:
        A dictionary representing the connected node found,
        or an empty dictionary if no valid connection is found.
    """
    inputs = node.get("inputs") if isinstance(node, dict) else None
    if inputs:
        names_to_check = [input_name] if isinstance(input_name, str) else input_name
        for name in names_to_check:
            wire          = inputs.get(name)         if isinstance(inputs, dict)              else None
            input_node_id = wire[0]                  if isinstance(wire,list) and len(wire)>0 else None
            input_node    = nodes.get(input_node_id) if isinstance(input_node_id , str)       else None
            if isinstance(input_node,dict):
                # found it!
                return input_node

    return {}


def find_prompt(node: dict, type: str, *, nodes: dict, depth: int = 0) -> str:
    """
    Returns the text prompt from a given node searching through its inputs.
    Args:
        node (dict): The current node under consideration.
        type       : The specific type of prompt to retrieve ('positive' or 'negative').
        nodes      : A dictionary containing all nodes in the workflow.
        depth (optional): Internal parameter to track the recursion depth.
    """
    if not isinstance(node,dict) or not node or depth >= 8:
        return ""

    # in the first step of recursion, check if the `type` param is valid
    if depth==0 and type not in ["positive","negative"]:
        raise ValueError(f"Type must be 'positive' or 'negative', not '{type}'")

    # in the first step of recursion, node can be a sampler node with positive/negative inputs
    if depth==0:
        prompt_node = get_input_node(node, type, nodes=nodes)
        if prompt_node:
            return find_prompt(prompt_node, type, nodes=nodes, depth=depth+1)

    #--------------------------------------------
    # from this point, what we do is to traverse the connection chain until reaching a prompt

    class_type = node.get("class_type", "")

    if class_type == "ControlNetApply" or class_type == "FluxGuidance":
        conditioning_node = get_input_node( node,"conditioning", nodes=nodes )
        return find_prompt(conditioning_node, type, nodes=nodes, depth=depth+1)

    text_node = get_input_node( node,"text", nodes=nodes )
    if text_node:
        return find_prompt(text_node, type, nodes=nodes, depth=depth+1)

    # finally check if we are in a node that contains prompt
    TEXT_NAMES = ("prompt", "text", "text_g", f"text_{type}", "populated_text")
    for name in TEXT_NAMES:
        prompt: str = get_input_string(node, name)
        if prompt:
            return prompt

    return ""


LANDSCAPE_SIZES_BY_ASPECT_RATIO = {
    "1:1  (square)"      : (1024.0, 1024.0), # Social media posts and profile pictures
    "4:3  (retro tv)"    : (1182.4,  886.8), # Legacy television and older computer monitors
    "3:2  (photo)"       : (1252.8,  837.0), # DSLR cameras and standard 35mm film # (1254.1, 836.1)
    "16:10  (monitor)"   : (1295.3,  809.5), # Common in MacBooks and productivity laptops
    "16:9  (widescreen)" : (1365.3,  768.0), # Current universal standard for video and TV
    "2:1  (univisium)"   : (1448.2,  724.0), # Modern streaming series and smartphone screens
    "21:9  (ultrawide)"  : (1564.2,  670.4), # Wide cinema format and ultrawide monitors
    "12:5  (anamorphic)" : (1586.4,  661.0), # Standard theatrical widescreen cinema release
    "70:27  (cinerama)"  : (1648.8,  636.0), # Extreme panoramic cinema format
    "32:9  (super wide)" : (1930.9,  543.0), # Dual-monitor width for ultra-wide displays
    # "48:35  (35 mm)"     : (1199.2,  874.4),
    # "71:50  (~imax)"     : (1220.2,  859.3),
}


SCALES_BY_NAME = {
    "small"                : 1.0,
    "medium (recommended)" : 1.3,
    "large"                : 1.6,
}


class EmptyZImageLatentImage:
    @staticmethod
    def calculate_image_size(*, orientation: bool, ratio: str, size: str) -> tuple[int,int]:
        """
        Calculate the final image dimensions based on aspect ratio and scale.
        Args:
            orientation : If True, landscape orientation is used; if False, portrait.
            ratio       : A string specifying the aspect ratio to use; this should
                          correspond to a key defined in `LANDSCAPE_SIZES_BY_ASPECT_RATIO`.
            size        : A string specifying the scale factor to apply; this should
                          correspond to a key defined in `SCALES_BY_NAME`.
        Returns:
            A tuple of (width, height) integers, aligned to the 32-pixel grid.
        """
        GRID_SIZE = 32
        is_vertical                   = (orientation == False)
        scale                         = SCALES_BY_NAME.get(size, 1.0)
        desired_width, desired_height = LANDSCAPE_SIZES_BY_ASPECT_RATIO.get(ratio, (1024, 1024))
        desired_width, desired_height = desired_width * scale, desired_height * scale
        if is_vertical:
            desired_width, desired_height = desired_height, desired_width

        # fix image size to be divisible by the grid
        image_width  = int( (desired_width  // GRID_SIZE) * GRID_SIZE )
        image_height = int( (desired_height // GRID_SIZE) * GRID_SIZE )
        return  image_width, image_height


class SaveImageMetadata:
    CIVITAI_NODES="""{

  "$1": {
    "inputs": {
      "text": "",
      "clip": [ "$5", 1 ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": { "title": "CLIP Text Encode (Positive Prompt)" }
  },

  "$2": {
    "inputs": {
      "text": "",
      "clip": [ "$5", 1 ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": { "title": "CLIP Text Encode (Negative Prompt)" }
  },

  "$3": {
    "inputs": {
      "width": 1024,
      "height": 1024,
      "batch_size": 1
    },
    "class_type": "EmptySD3LatentImage",
    "_meta": { "title": "EmptySD3LatentImage" }
  },

  "$4": {
    "inputs": {
      "seed": 550110717236789,
      "steps": 20,
      "cfg": 1.0,
      "sampler_name": "euler",
      "scheduler": "simple",
      "denoise": 1.0,
      "model": [ "$5", 0 ],
      "positive": [ "$6", 0 ],
      "negative": [ "$2", 0 ],
      "latent_image": [ "$3", 0 ]
    },
    "class_type": "KSampler",
    "_meta": { "title": "KSampler"  }
  },


  "$5": {
    "inputs": {
      "ckpt_name": "z-image_turbo_.safetensors"
    },
    "class_type": "CheckpointLoaderSimple",
    "_meta": { "title": "Load Checkpoint"  }
  },

  "$6": {
    "inputs": {
      "guidance": 8.15,
      "conditioning": [ "$1", 0 ]
    },
    "class_type": "FluxGuidance",
    "_meta": { "title": "FluxGuidance" }
  }
}
"""


    @classmethod
    def find_civitai_nodes(cls,
                           nodes : dict[ str, dict ],
                           ) -> int:
        """
        Searches for existing CivitAI-injected nodes in the given node dictionary.

        This method looks through the provided nodes to check if it have been
        previously injected with a specific pattern of nodes required by CivitAI.
        It returns an index indicating where these nodes start, or 0 if no such
        injection is found.

        Args:
            nodes (dict): The dictionary containing existing nodes.

        Returns:
            int: The base index where the CivitAI-injected nodes start, or 0 if not found.
        """
        for id, node in nodes.items():

            # get the integer value of 'id' which should always be greater than 5
            if isinstance(id, str) and id.isdigit():
                id = int(id)
            if not isinstance(id, int):
                continue
            if id <= 5:
                continue

            # check only CheckpointLoaderSimple nodes
            if not isinstance(node,dict) or node.get('class_type', '') != 'CheckpointLoaderSimple':
                continue

            # verify that it is a CheckpointLoaderSimple node that was injected
            ckpt_name = node.get('inputs',{}).get('ckpt_name','')
            if ckpt_name != "z-image_turbo_.safetensors":
                continue

            # to be sure we have the right injected node,
            # the next one should be a FluxGuidance with a guidance value between 8.1 and 8.2
            next_node = nodes.get( str(id+1), {} )
            if not isinstance(next_node,dict) or next_node.get("class_type", "") != "FluxGuidance":
                continue
            guidance = next_node.get("inputs", {}).get("guidance", None)
            if not isinstance(guidance, (float,int)) or guidance <= 8.1 or guidance >= 8.2:
                continue

            base_index = (id - 5)
            first_node = nodes.get( str(base_index+1), None )
            if isinstance(first_node,dict) and first_node.get("class_type", "") == "CLIPTextEncode":
                return base_index

        return 0


    @classmethod
    def inject_civitai_nodes(cls,
                             nodes : dict[ str, dict ],
                             /,*,
                             positive     : str,
                             negative     : str   = "",
                             seed         : int   = 1,
                             steps        : int   = 8,
                             cfg          : float = 1.0,
                             sampler_name : str   = "euler",
                             scheduler    : str   = "simple",
                             width        : int   = 1024,
                             height       : int   = 1024,
                             ) -> dict:
        """
        Injects generation parameters into a node format that Civitai can read.

        This method takes an existing dictionary with nodes and injects additional
        nodes required by Civitai. The modified dictionary, now compatible with
        Civitai's expected structure, is returned.

        Args:
            nodes         (dict): Original dictionary containing existing nodes.
            positive       (str): Positive prompt text for generation.
            negative       (str): Negative prompt text for generation.
            seed           (int): Random seed value for reproducibility.
            steps          (int): Number of steps in the sampling process.
            cfg          (float): CFG scale, controlling how much the negative prompt affects the output.
            sampler_name   (str): Name of the sampler to be used in generation.
            scheduler (optional): Scheduler name. Defaults to "simple".
            width     (optional): Image width in pixels. Defaults to 1024.
            height    (optional): Image height in pixels. Defaults to 1024.

        Returns:
            Updated node dictionary with Civitai nodes included.
        """

        # check if `nodes` already has Civitai nodes injected
        base_index   = cls.find_civitai_nodes(nodes)
        not_injected = (base_index==0)

        # if there are no Civitai nodes injected,
        # get the maximum index of any node,
        # that will be the base for inject CivitAI nodes
        if not_injected:
            base_index = 0
            for node_id in nodes.keys():
                index = cls.max_index_from_node_identifier(node_id)
                base_index = max(base_index, index)
            base_index += 100

            # reenumerate the CivitAI nodes from `base_index`
            # this way they don't collide with the nodes in the actual workflow
            civitai_nodes = cls.CIVITAI_NODES
            for i in range(1, 9):
                civitai_nodes = civitai_nodes.replace(f'"${i}"', f'"{base_index+i}"')
            civitai_nodes = json.loads(civitai_nodes)

            # inject CivitAI nodes into `nodes`
            # these nodes are still "templates", they need to be configured with values
            nodes = {**nodes, **civitai_nodes}

        # modify the CivitAI nodes "1", "2" and "4" assigning them the parameters
        # prompt-positve, prompt-negative, seed, steps, etc...
        positive_node = nodes[ str(base_index+1) ]
        positive_node["inputs"]["text"] = str(positive) if positive is not None else ""

        negative_node = nodes[ str(base_index+2) ]
        negative_node["inputs"]["text"] = str(negative) if negative is not None else ""

        latent_image_node = nodes[ str(base_index+3) ]
        latent_image_node["inputs"]["width" ] = int(width ) if isinstance(width ,(int,float)) else 1024
        latent_image_node["inputs"]["height"] = int(height) if isinstance(height,(int,float)) else 1024

        ksampler_node = nodes[ str(base_index+4) ]
        ksampler_node["inputs"]["seed"]         = int(seed        ) if isinstance(seed ,(int,float)) else 1
        ksampler_node["inputs"]["steps"]        = int(steps       ) if isinstance(steps,(int,float)) else 25
        ksampler_node["inputs"]["cfg"]          = float(cfg       ) if isinstance(cfg  ,(int,float)) else 1.0
        ksampler_node["inputs"]["sampler_name"] = str(sampler_name) if sampler_name is not None else "euler"
        ksampler_node["inputs"]["scheduler"]    = str(scheduler   ) if scheduler    is not None else "simple"

        return nodes


    @classmethod
    def find_initial_sampler(cls, nodes: dict) -> tuple[dict, dict]:
        """
        Find the sampler node that seems to generate the initial image

        This function iterates through all nodes, searching for those with any
        class type related to sampling, and then checks if it is connected to
        a latent image creator. This indicates it might be the initial image
        generator.

        Args:
            nodes: Dictionary containing all nodes (prompt structure)

        Returns:
            A tuple containing the following elements:
                - The first element is a dict representing the found initial sampler node,
                  or empty dict if no suitable sampler is found.
                - The second element is a dict containing the parameters of the found sampler,
                  or empty dict if no parameters were found.
        """
        initial_sampler_node = {}
        params = {}

        # iterates through all nodes and analyzes those related to sampling
        for node in nodes.values():
            class_type: str = node.get("class_type","") if isinstance(node, dict) else ""
            if not class_type:
                continue

            if class_type == "KSampler":
                latent_node = get_input_node(node,"latent_image", nodes=nodes)
                if cls.is_empty_latent_node(latent_node):
                    initial_sampler_node = node
                    image_size             = cls.find_image_size(node, nodes=nodes)
                    params["positive"]     = find_prompt(node, type="positive", nodes=nodes)
                    params["negative"]     = find_prompt(node, type="negative", nodes=nodes)
                    params["seed"]         = get_input_int   (node, "seed"        , default=-1  )
                    params["steps"]        = get_input_int   (node, "steps"       , default=-1  )
                    params["cfg"]          = get_input_float (node, "cfg"         , default=-1.0)
                    params["sampler_name"] = get_input_string(node, "sampler_name", default=""  )
                    params["scheduler"]    = get_input_string(node, "scheduler"   , default=""  )
                    if image_size:
                        params["width" ] = image_size[0]
                        params["height"] = image_size[1]
                    break

            if class_type.startswith("ZSamplerTurbo"):
                latent_node = get_input_node(node,"latent_input", nodes=nodes)
                if cls.is_empty_latent_node(latent_node):
                    initial_sampler_node = node
                    image_size             = cls.find_image_size(node, nodes=nodes)
                    params["positive"]     = find_prompt(node, type="positive", nodes=nodes)
                    params["seed"]         = get_input_int(node, "seed" , default=-1)
                    params["steps"]        = get_input_int(node, "steps", default=-1)
                    params["cfg"]          = 1.0              # this node always uses cfg = 1.0
                    params["sampler_name"] = "zsampler_turbo" # internally, this node always uses "euler"
                    if image_size:
                        params["width" ] = image_size[0]
                        params["height"] = image_size[1]
                    # no scheduler, this node uses a fixed custom scheduler
                    break

        # remove any parameter that is out of range or empty
        if not params.get("positive"    ): params.pop("positive"    , None)
        if not params.get("negative"    ): params.pop("negative"    , None)
        if not params.get("sampler_name"): params.pop("sampler_name", None)
        if not params.get("scheduler"   ): params.pop("scheduler"   , None)
        if params.get("seed" ,-1) < 0    : params.pop("seed"        , None)
        if params.get("steps",-1) < 1    : params.pop("steps"       , None)
        if params.get("cfg"  ,-1) < 0    : params.pop("cfg"         , None)
        return initial_sampler_node, params


    @classmethod
    def find_image_size(cls, node: dict, *, nodes: dict, depth: int = 0) -> tuple[int, int] | None:
        """
        Recursively traverse the node graph to find the dimensions of the initial latent image.

        This function follows the input connections (latent images) backwards
        until it reaches a node capable of defining image dimensions, such as
        'EmptyLatentImage' or 'EmptyZImageLatentImage'.

        Args:
            node  : The current node dictionary being inspected.
            nodes : The full dictionary containing all nodes in the workflow.
            depth : Current recursion depth to prevent infinite loops or excessive
                    stack usage. Defaults to 0.

        Returns:
            A tuple of (width, height) integers if the image size is found,
            or `None` if no latent image node could be found.
        """
        if depth>5:
            return None

        # check if the node has an input connection that provides a
        # latent image and follow that path recursively.
        latent_node = get_input_node( node,["latent_image","latent_input"], nodes=nodes )
        if latent_node:
            return cls.find_image_size(latent_node, nodes=nodes, depth=depth+1)

        # identify the node class and extract information accordingly
        class_type = node.get("class_type", "")
        if not isinstance(class_type, str):
            return None

        # handle custom "Empty Z-Image Latent Image" node
        if class_type.startswith("EmptyZImageLatentImage"):
            orientation = get_input_bool(node, "orientation", default=False)
            ratio       = get_input_string(node, "ratio", default="")
            size        = get_input_string(node, "size" , default="")
            if not ratio or not size:
                return None
            return EmptyZImageLatentImage.calculate_image_size(
                                            orientation = orientation,
                                            ratio       = ratio,
                                            size        = size)

        # handle native comfyui "Empty Latent Image" node
        if class_type == "EmptyLatentImage":
            width  = get_input_int(node, "width" , default=0)
            height = get_input_int(node, "height", default=0)
            if not width or not height:
                return None
            return width, height

        return None


    @classmethod
    def find_user_params(cls, title_tag: str, nodes: dict) -> tuple[int, dict[str, Any]]:
        all_params = {}
        contrib_count = 0

        for node in nodes.values():
            if not isinstance(node,dict):
                continue

            # get "meta" and "class_type" from node
            # ensuring they are dictionary and string
            meta       = _ if isinstance(_ := node.get("_meta"     ), dict) else {}
            class_type = _ if isinstance(_ := node.get("class_type"), str ) else ""

            # verify that the node has a valid "title" and it is tagged
            title  = meta.get("title")
            if not isinstance(title,str)  or  (not title_tag in title):
                continue

            params = {}

            # assume that all tagged "String (Multiline)" nodes
            # contain prompts or negative prompts
            if class_type == "PrimitiveStringMultiline":
                prompt = get_input_string(node, "value", default="")
            else:
                prompt = get_input_string(node, "text", default="")

            if prompt:
                if "negative" in title.lower():  params["negative"] = prompt
                else:                            params["positive"] = prompt

            seed = get_input_int(node, "seed", default=-1)
            if seed>=0: params["seed"] = int(seed)

            steps = get_input_int(node, "steps", default=-1)
            if steps>0: params["steps"] = int(steps)

            cfg = get_input_float(node, "cfg", default=-1.0)
            if cfg>=0: params["cfg"] = float(cfg)

            sampler_name = get_input_string(node, "sampler_name", default="")
            if sampler_name: params["sampler_name"] = sampler_name

            scheduler = get_input_string(node, "scheduler", default="")
            if scheduler: params["scheduler"] = scheduler

            width = get_input_int(node, "width", default=-1)
            if width>0: params["width"] = int(width)

            height = get_input_int(node, "height", default=-1)
            if height>0: params["height"] = int(height)

            if params:
                contrib_count += 1

            all_params.update(params)

        return contrib_count, all_params


    @staticmethod
    def is_empty_latent_node(node: dict) -> bool:
        """
        Determines whether a given node represents an empty latent image generator.
        """
        class_type = node.get("class_type", "") if isinstance(node,dict) else ""
        if class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
            return True
        if class_type.startswith("EmptyZImageLatentImage"):
            return True
        return False


    @staticmethod
    def max_index_from_node_identifier(identifier: Any) -> int:
        """
        Converts a node identifier to integer, taking into account sub-graphs format ("sub-graph:node").

        Args:
            identifier: The node identifier to convert to integer.

        Returns:
            The maximum index extracted from the identifier.
            If the identifier cannot be processed, returns 0.
        """
        if isinstance(identifier, (int,float)):
            return int(identifier)
        if isinstance(identifier,str):
            max_index = 0
            # splitting the identifier by ':' to process sub-graph elements
            # (sub-graph and internal elements seem to form a single identifier delimited by ':')
            for index in identifier.split(":"):
                if not index.isdigit():
                    continue
                max_index = max(int(index), max_index)
            return max_index
        return 0

