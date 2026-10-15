"""Structural checks; host grants govern model storage and memory capacity."""
import torch

def logical_name(value):
    if not isinstance(value, str):
        raise ValueError("logical catalogue name required")
    logical = value.replace("\\", "/")
    # Match published asset confinement. Individual models/output domains
    # enforce their own additional contracts and filesystem limits.
    if "\x00" in logical or logical.startswith("/") or any(part==".." for part in logical.split("/")):
        raise ValueError("catalogue name cannot be an arbitrary path")
    return value


def state_bounds(state, *, output_itemsize=None):
    if not isinstance(state, dict):
        raise ValueError("tensor dictionary required")
    if output_itemsize is not None and (type(output_itemsize) is not int or output_itemsize < 1):
        raise ValueError("positive projected output item size required")
    for key, tensor in state.items():
        if not isinstance(key, str):
            raise ValueError("string tensor key required")
        if not isinstance(tensor, torch.Tensor) or tensor.layout != torch.strided:
            raise ValueError("dense tensor state required")
    return state


def output_prefix(name, suffix):
    name = logical_name(name)
    stem = name.rsplit(".", 1)[0]
    # Managed counter-suffixed names replace legacy overwrite/input() semantics.
    return "calcuis-gguf/" + stem + suffix
