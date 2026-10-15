"""Pinned batch/quantization behavior without host progress/global mutation."""
import numpy as np
import torch


def common_annotator_call(model, tensor_image, input_batch=False, show_pbar=True, **kwargs):
    kwargs.pop('detect_resolution', None)
    resolution = kwargs.pop('resolution', 512)
    detect_resolution = resolution if type(resolution) is int and resolution >= 64 else 512
    if input_batch:
        images = np.asarray(tensor_image * 255., dtype=np.uint8)
        result = model(images, output_type='np', detect_resolution=detect_resolution, **kwargs)
        return torch.from_numpy(result.astype(np.float32) / 255.0)
    output = None
    for i, image in enumerate(tensor_image):
        pixels = np.asarray(image.cpu() * 255., dtype=np.uint8)
        result = model(pixels, output_type='np', detect_resolution=detect_resolution, **kwargs)
        value = torch.from_numpy(result.astype(np.float32) / 255.0)
        if output is None:
            output = torch.zeros(tensor_image.shape[0], *value.shape, dtype=torch.float32)
        output[i] = value
    return output
