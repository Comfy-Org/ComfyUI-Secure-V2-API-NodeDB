"""Exact lifted pinned architecture selection and tensor encoding arithmetic."""
import torch
from tqdm import tqdm as loading
from .gguf_math.const import GGMLQuantizationType
from .gguf_math.quant5 import quantize, QuantError
QUANTIZATION_THRESHOLD = 1024
MAX_TENSOR_NAME_LENGTH = 127
class ModelTemplate:
    arch = 'invalid'
    keys_detect = []
    keys_banned = []
class ModelFlux(ModelTemplate):
    arch = 'flux'
    keys_detect = [('transformer_blocks.0.attn.norm_added_k.weight',), (
        'double_blocks.0.img_attn.proj.weight',)]
    keys_banned = ['transformer_blocks.0.attn.norm_added_k.weight']
class ModelSD3(ModelTemplate):
    arch = 'sd3'
    keys_detect = [('transformer_blocks.0.attn.add_q_proj.weight',), (
        'joint_blocks.0.x_block.attn.qkv.weight',)]
    keys_banned = ['transformer_blocks.0.attn.add_q_proj.weight']
class ModelSDXL(ModelTemplate):
    arch = 'sdxl'
    keys_detect = [('down_blocks.0.downsamplers.0.conv.weight',
        'add_embedding.linear_1.weight'), ('input_blocks.3.0.op.weight',
        'input_blocks.6.0.op.weight', 'output_blocks.2.2.conv.weight',
        'output_blocks.5.2.conv.weight'), ('label_emb.0.0.weight',)]
class ModelSD1(ModelTemplate):
    arch = 'sd1'
    keys_detect = [('down_blocks.0.downsamplers.0.conv.weight',), (
        'input_blocks.3.0.op.weight', 'input_blocks.6.0.op.weight',
        'input_blocks.9.0.op.weight', 'output_blocks.2.1.conv.weight',
        'output_blocks.5.2.conv.weight', 'output_blocks.8.2.conv.weight')]
arch_list = [ModelFlux, ModelSD3, ModelSDXL, ModelSD1]
def is_model_arch(model, state_dict):
    matched = False
    invalid = False
    for match_list in model.keys_detect:
        if all(key in state_dict for key in match_list):
            matched = True
            invalid = any(key in state_dict for key in model.keys_banned)
            break
    assert not invalid, 'Model architecture not supported for alpha (please opt to use zero)'
    return matched
def detect_arch(state_dict):
    model_arch = None
    for arch in arch_list:
        if is_model_arch(arch, state_dict):
            model_arch = arch
            break
    assert model_arch is not None, 'Unknown model architecture detected!'
    return model_arch
def handle_tensors(args, writer, state_dict, model_arch):
    name_lengths = tuple(sorted(((key, len(key)) for key in state_dict.keys
        ()), key=lambda item: item[1], reverse=True))
    if not name_lengths:
        return
    max_name_len = name_lengths[0][1]
    if max_name_len > MAX_TENSOR_NAME_LENGTH:
        bad_list = ', '.join(f'{key!r} ({namelen})' for key, namelen in
            name_lengths if namelen > MAX_TENSOR_NAME_LENGTH)
        raise ValueError(f'Can only handle tensor names up to {MAX_TENSOR_NAME_LENGTH} characters. Tensors exceeding the limit: {bad_list}')
    for key, data in loading(state_dict.items()):
        old_dtype = data.dtype
        if data.dtype == torch.bfloat16:
            data = data.to(torch.float32).numpy()
        elif data.dtype in [getattr(torch, 'float8_e4m3fn', '_invalid'),
            getattr(torch, 'float8_e5m2', '_invalid')]:
            data = data.to(torch.float16).numpy()
        else:
            data = data.numpy()
        n_dims = len(data.shape)
        data_shape = data.shape
        data_qtype = getattr(GGMLQuantizationType, 'BF16' if old_dtype ==
            torch.bfloat16 else 'F16')
        n_params = 1
        for dim_size in data_shape:
            n_params *= dim_size
        blacklist = {'time_embedding.', 'add_embedding.', 'time_in.',
            'txt_in.', 'vector_in.', 'img_in.', 'guidance_in.', 'final_layer.'}
        if old_dtype in (torch.float32, torch.bfloat16):
            if n_dims == 1:
                data_qtype = GGMLQuantizationType.F32
            elif n_params <= QUANTIZATION_THRESHOLD:
                data_qtype = GGMLQuantizationType.F32
            elif '.weight' in key and any(x in key for x in blacklist):
                data_qtype = GGMLQuantizationType.F32
        try:
            data = quantize(data, data_qtype)
        except (AttributeError, QuantError) as e:
            loading.write(f'falling back to F16: {e}')
            data_qtype = GGMLQuantizationType.F16
            data = quantize(data, data_qtype)
        new_name = key
        shape_str = f"{{{', '.join(str(n) for n in reversed(data.shape))}}}"
        loading.write(
            f"{f'%-{max_name_len + 4}s' % f'{new_name}'} {old_dtype} --> {data_qtype.name}, shape = {shape_str}"
            )
        writer.add_tensor(new_name, data, raw_dtype=data_qtype)
