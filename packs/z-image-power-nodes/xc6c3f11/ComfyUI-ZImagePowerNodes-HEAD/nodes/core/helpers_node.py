"""
File    : helpers_node.py
Purpose : Functions to help with ComfyUI nodes data extraction and node execution.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jan 24, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

There are two types of structures that store the nodes in ComfyUI:
  - "workflow" : This is a dictionary containing all nodes, groups, and
                 connections as they are presented visually in the editor.
  - "prompt"   : This is a dictionary with information for the backend and
                 contains a summary of the nodes with only selected values
                 and essential data.

In general, the functions in this file operate on the "prompt" structure.

"""
import nodes
from typing  import Any
from .system import logger


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


def execute_node(node_name: str,
                 *,
                 remove_none_args      : bool = False,
                 fallback_methods_names: list[str] | tuple[str] | None = None,
                 **kwargs
                 ):
    """Locate, instantiate, and execute any ComfyUI node dynamically.

    Use this function to execute specific node logic by node name (like model loaders,
    image processors, or samplers), providing node parameters as keyword arguments.
    Ensure that all required inputs for the node are correctly passed via `**kwargs`.

    Args:
        node_name             : The exact key name of the node as registered in NODE_CLASS_MAPPINGS.
        remove_none_args      : If True, removes arguments with `None` values before execution.
        fallback_methods_names: A list of candidate method names to attempt if the standard
                                execution entry points are not found or accessible.
        **kwargs              : Arbitrary keyword arguments required by the node.

    Returns:
        Any value returned by the executed node method.
    """
    # dynamically retrieve the node class
    node_class = nodes.NODE_CLASS_MAPPINGS.get(node_name)
    if node_class is None:
        raise RuntimeError(
            f"The node '{node_name}' is not available. "
            f"Please ensure the required custom nodes are installed."
        )

    # optional cleaning of arguments with `None` values
    node_kwargs = {k: v for k, v in kwargs.items() if v is not None} if remove_none_args else kwargs

    # attempt modern node execution: direct call to class method 'execute'
    if hasattr(node_class, "execute") and callable(getattr(node_class, "execute")):
        try:
            return node_class.execute(**node_kwargs)
        except Exception as e:
            logger.warning(f"Failed modern 'execute' method on \"{node_name}\" node: {e}")

    # safe node instance creation
    try:
        node_instance = node_class()
    except Exception as e:
        logger.warning(f"Could not instantiate \"{node_name}\" node: {e}")
        node_instance = None

    # attempt legacy node execution: use the 'FUNCTION' property defined in the node
    legacy_func_name = getattr(node_class, "FUNCTION", None)
    if legacy_func_name and node_instance and hasattr(node_instance, legacy_func_name):
        method = getattr(node_instance, legacy_func_name)
        return method(**node_kwargs)

    # brute force attempt to find the legacy method in the instance or class
    if isinstance(fallback_methods_names,list) or isinstance(fallback_methods_names,tuple):
        for method_name in fallback_methods_names:
            if node_instance and hasattr(node_instance, method_name):
                emergency_method = getattr(node_instance, method_name)
                return emergency_method(**node_kwargs)
            elif hasattr(node_class, method_name):
                emergency_method = getattr(node_class, method_name)
                return emergency_method(**node_kwargs)

    raise AttributeError(f"Node \"{node_name}\" found, but no compatible execution method was identified.")
