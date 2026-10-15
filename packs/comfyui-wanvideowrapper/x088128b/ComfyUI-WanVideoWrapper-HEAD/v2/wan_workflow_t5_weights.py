"""Complete original tensor-placement helpers; unchanged function AST."""
import torch

def check_device_same(first_device, second_device):
    if first_device.type != second_device.type:
        return False

    if first_device.type == "cuda" and first_device.index is None:
        first_device = torch.device("cuda", index=0)

    if second_device.type == "cuda" and second_device.index is None:
        second_device = torch.device("cuda", index=0)

    return first_device == second_device

def set_module_tensor_to_device(module, tensor_name, device, value=None, dtype=None):
    """
    A helper function to set a given tensor (parameter of buffer) of a module on a specific device (note that doing
    `param.to(device)` creates a new tensor not linked to the parameter, which is why we need this function).

    Args:
        module (`torch.nn.Module`):
            The module in which the tensor we want to move lives.
        tensor_name (`str`):
            The full name of the parameter/buffer.
        device (`int`, `str` or `torch.device`):
            The device on which to set the tensor.
        value (`torch.Tensor`, *optional*):
            The value of the tensor (useful when going from the meta device to any other device).
        dtype (`torch.dtype`, *optional*):
            If passed along the value of the parameter will be cast to this `dtype`. Otherwise, `value` will be cast to
            the dtype of the existing parameter in the model.
    """
    # Recurse if needed
    if "." in tensor_name:
        splits = tensor_name.split(".")
        for split in splits[:-1]:
            new_module = getattr(module, split)
            if new_module is None:
                raise ValueError(f"{module} has no attribute {split}.")
            module = new_module
        tensor_name = splits[-1]

    if tensor_name not in module._parameters and tensor_name not in module._buffers:
        raise ValueError(f"{module} does not have a parameter or a buffer named {tensor_name}.")
    is_buffer = tensor_name in module._buffers
    old_value = getattr(module, tensor_name)

    if old_value.device == torch.device("meta") and device not in ["meta", torch.device("meta")] and value is None:
        raise ValueError(f"{tensor_name} is on the meta device, we need a `value` to put in on {device}.")

    param = module._parameters[tensor_name] if tensor_name in module._parameters else None
    param_cls = type(param)

    if value is not None:
        if dtype is None:
            value = value.to(old_value.dtype)
        elif not str(value.dtype).startswith(("torch.uint", "torch.int", "torch.bool")):
            value = value.to(dtype)

    device_quantization = None
    with torch.no_grad():
        if value is None:
            new_value = old_value.to(device)
            if dtype is not None and device in ["meta", torch.device("meta")]:
                if not str(old_value.dtype).startswith(("torch.uint", "torch.int", "torch.bool")):
                    new_value = new_value.to(dtype)

                if not is_buffer:
                    module._parameters[tensor_name] = param_cls(new_value, requires_grad=old_value.requires_grad)
        elif isinstance(value, torch.Tensor):
            new_value = value.to(device)
        else:
            new_value = torch.tensor(value, device=device)
        if device_quantization is not None:
            device = device_quantization
        if is_buffer:
            module._buffers[tensor_name] = new_value
        elif value is not None or not check_device_same(device, module._parameters[tensor_name].device):
            param_cls = type(module._parameters[tensor_name])
            new_value = param_cls(new_value, requires_grad=False)
            module._parameters[tensor_name] = new_value
