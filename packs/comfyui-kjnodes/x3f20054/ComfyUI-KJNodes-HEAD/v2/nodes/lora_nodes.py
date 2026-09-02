from __future__ import annotations
import ast as _remaining_u_ast
import logging as _remaining_u_logging
import os as _remaining_u_os
import pathlib as _remaining_u_pathlib
import types as _remaining_u_types
import numpy as _remaining_u_np
import torch as _remaining_u_torch
from tqdm import tqdm as _remaining_u_tqdm
from comfy_api.latest import io as _remaining_u_io, sdk as _remaining_u_sdk
from . import _packload as _remaining_u_packload
_remaining_u_RESIZE_LORA = None

class _remaining_u_ProgressBar:

    def __init__(self, total):
        self.total = total
        self.value = 0

    def update(self, value):
        self.value += value

def _remaining_u_resize_lora():
    global _remaining_u_RESIZE_LORA
    if _remaining_u_RESIZE_LORA is not None:
        return _remaining_u_RESIZE_LORA
    path = _remaining_u_pathlib.Path(_remaining_u_packload.ROOT) / 'nodes' / 'lora_nodes.py'
    source = path.read_text(encoding='utf-8')
    tree = _remaining_u_ast.parse(source, filename=str(path))
    function_names = {'_svd_extract', 'extract_conv', 'extract_conv3d', 'extract_linear', 'extract_linear_factored', 'index_sv_cumulative', 'index_sv_fro', 'index_sv_knee', 'index_sv_ratio', 'merge_conv', 'merge_conv3d', 'merge_linear', 'rank_resize', 'resize_lora_model'}
    constant_names = {'MIN_SV', 'LORA_DOWN_UP_FORMATS'}
    functions = [node for node in tree.body if isinstance(node, _remaining_u_ast.FunctionDef) and node.name in function_names]
    constants = [node for node in tree.body if isinstance(node, _remaining_u_ast.Assign) and any((isinstance(target, _remaining_u_ast.Name) and target.id in constant_names for target in node.targets))]
    found_constants = {target.id for node in constants for target in node.targets if isinstance(target, _remaining_u_ast.Name)}
    if {node.name for node in functions} != function_names or found_constants != constant_names:
        raise RuntimeError(f'LoRA resize helpers changed in {path}; found functions {sorted((node.name for node in functions))} and constants {sorted(found_constants)}')
    comfy = _remaining_u_types.SimpleNamespace(utils=_remaining_u_types.SimpleNamespace(ProgressBar=_remaining_u_ProgressBar))
    namespace = {'comfy': comfy, 'logging': _remaining_u_logging, 'np': _remaining_u_np, 'torch': _remaining_u_torch, 'tqdm': _remaining_u_tqdm}
    module = _remaining_u_ast.fix_missing_locations(_remaining_u_ast.Module(body=[*constants, *functions], type_ignores=[]))
    exec(compile(module, f'<secure-lora-resize:{path}>', 'exec'), namespace)
    _remaining_u_RESIZE_LORA = namespace['resize_lora_model']
    return _remaining_u_RESIZE_LORA

def _remaining_u_output_prefix(lora_name, old_dim, rank_str, output_dtype):
    directory, filename = _remaining_u_os.path.split(_remaining_u_os.path.normpath(lora_name))
    filename = filename.replace('.safetensors', '')
    dtype_suffix = f'_{output_dtype}' if output_dtype != 'match_original' else ''
    resized = f'{filename}_resized_from_{old_dim}_to_{rank_str}{dtype_suffix}'
    return _remaining_u_os.path.join('loras', directory, resized)

class LoraReduceRankKJSecure(_remaining_u_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'output', 'raw')

    @classmethod
    def define_schema(cls):
        return _remaining_u_io.Schema(node_id='LoraReduceRankKJSecure', display_name='🔒 LoraReduceRank (secure)', category='KJNodes/lora', description='Resize a LoRA model by reducing its rank while keeping file access brokered by the host.', is_output_node=True, is_experimental=True, inputs=[_remaining_u_io.Combo.Input('lora_name', options=[], remote=_remaining_u_io.RemoteOptions(route='/models/loras', refresh_button=True), tooltip='The name of the LoRA.'), _remaining_u_io.Int.Input('new_rank', default=8, min=1, max=4096, step=1, tooltip='The new rank, or maximum rank for a dynamic method.'), _remaining_u_io.Combo.Input('dynamic_method', options=['disabled', 'sv_ratio', 'sv_cumulative', 'sv_fro', 'sv_knee'], default='disabled'), _remaining_u_io.Float.Input('dynamic_param', default=0.2, min=0.0, max=2.0, step=0.01), _remaining_u_io.Combo.Input('output_dtype', options=['match_original', 'fp16', 'bf16', 'fp32'], default='match_original'), _remaining_u_io.Boolean.Input('verbose', default=True)])

    @classmethod
    def validate_inputs(cls, lora_name):
        if not isinstance(lora_name, str) or not lora_name:
            return 'lora_name must be a non-empty asset name'
        return True

    @classmethod
    async def execute(cls, lora_name, new_rank, dynamic_method, dynamic_param, output_dtype, verbose):
        ctx = _remaining_u_sdk.ctx()
        asset = await ctx.assets.resolve('loras', lora_name)
        lora_sd, metadata = await ctx.assets.load_state_dict(asset, return_metadata=True)
        await ctx.progress.update(0.0, 1.0)
        dtypes = {'bf16': _remaining_u_torch.bfloat16, 'fp16': _remaining_u_torch.float16, 'fp32': _remaining_u_torch.float32}
        if output_dtype == 'match_original':
            first_weight_key = next((key for key in lora_sd if key.endswith('.weight') and isinstance(lora_sd[key], _remaining_u_torch.Tensor)))
            save_dtype = lora_sd[first_weight_key].dtype
        else:
            save_dtype = dtypes[output_dtype]
        normalized = {key.replace('.default', ''): value for key, value in lora_sd.items()}
        first_tensor = next((value for value in normalized.values() if isinstance(value, _remaining_u_torch.Tensor)))
        output_sd, old_dim, new_alpha, rank_list = _remaining_u_resize_lora()(normalized, new_rank, save_dtype, first_tensor.device, dynamic_method, dynamic_param, verbose)
        metadata = {} if metadata is None else dict(metadata)
        comment = metadata.get('ss_training_comment', '')
        if dynamic_method == 'disabled':
            metadata['ss_training_comment'] = f'dimension is resized from {old_dim} to {new_rank}; {comment}'
            metadata['ss_network_dim'] = str(new_rank)
            metadata['ss_network_alpha'] = str(new_alpha)
            rank_str = new_rank
        else:
            metadata['ss_training_comment'] = f'Dynamic resize with {dynamic_method}: {dynamic_param} from {old_dim}; {comment}'
            metadata['ss_network_dim'] = 'Dynamic'
            metadata['ss_network_alpha'] = 'Dynamic'
            rank_str = f'dynamic_{int(_remaining_u_np.mean(rank_list))}'
        for key, value in list(output_sd.items()):
            if type(value) is _remaining_u_torch.Tensor and value.dtype.is_floating_point and (value.dtype != save_dtype):
                output_sd[key] = value.to(save_dtype)
        state_ref = await _remaining_u_sdk.ValueRef.from_value(output_sd)
        await ctx.output.save_state_dict(state_ref, _remaining_u_output_prefix(lora_name, old_dim, rank_str, output_dtype), metadata=metadata)
        await ctx.progress.update(1.0, 1.0)
        return _remaining_u_io.NodeOutput()
import ast as _remaining_z_ast
import logging as _remaining_z_logging
import pathlib as _remaining_z_pathlib
import torch as _remaining_z_torch
from comfy_api.latest import io as _remaining_z_io, sdk as _remaining_z_sdk
from . import _packload as _remaining_z_packload
_remaining_z_EXTRACT_LORA = None

def _remaining_z_extract_lora():
    global _remaining_z_EXTRACT_LORA
    if _remaining_z_EXTRACT_LORA is not None:
        return _remaining_z_EXTRACT_LORA
    path = _remaining_z_pathlib.Path(_remaining_z_packload.ROOT) / 'nodes' / 'lora_nodes.py'
    source = path.read_text(encoding='utf-8')
    tree = _remaining_z_ast.parse(source, filename=str(path))
    functions = [node for node in tree.body if isinstance(node, _remaining_z_ast.FunctionDef) and node.name == 'extract_lora']
    constants = [node for node in tree.body if isinstance(node, _remaining_z_ast.Assign) and any((isinstance(target, _remaining_z_ast.Name) and target.id == 'CLAMP_QUANTILE' for target in node.targets))]
    if len(functions) != 1 or len(constants) != 1:
        raise RuntimeError(f'LoRA extraction helpers changed in {path}')
    namespace = {'logging': _remaining_z_logging, 'torch': _remaining_z_torch}
    module = _remaining_z_ast.fix_missing_locations(_remaining_z_ast.Module(body=[*constants, *functions], type_ignores=[]))
    exec(compile(module, f'<secure-lora-extract:{path}>', 'exec'), namespace)
    _remaining_z_EXTRACT_LORA = namespace['extract_lora']
    return _remaining_z_EXTRACT_LORA

class LoraExtractKJSecure(_remaining_z_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output', 'raw')

    @classmethod
    def define_schema(cls):
        return _remaining_z_io.Schema(node_id='LoraExtractKJSecure', display_name='🔒 LoraExtractKJ (secure)', category='KJNodes/lora', is_output_node=True, inputs=[_remaining_z_io.MultiType.Input('finetuned', [_remaining_z_io.Model, _remaining_z_io.Clip], tooltip='The finetuned model or clip to extract LoRA from.'), _remaining_z_io.MultiType.Input('original', [_remaining_z_io.Model, _remaining_z_io.Clip], tooltip='The original base model or clip to diff against.'), _remaining_z_io.String.Input('filename_prefix', default='loras/ComfyUI_extracted_lora'), _remaining_z_io.Int.Input('rank', default=64, min=1, max=4096, step=1, tooltip='The rank for standard LoRA, or the maximum rank for adaptive methods.'), _remaining_z_io.Combo.Input('lora_type', options=['standard', 'full', 'adaptive_ratio', 'adaptive_quantile', 'adaptive_energy', 'adaptive_fro']), _remaining_z_io.Combo.Input('algorithm', options=['svd_linalg', 'svd_lowrank'], default='svd_lowrank', tooltip='SVD algorithm; svd_lowrank is faster but less accurate.'), _remaining_z_io.Int.Input('lowrank_iters', default=7, min=1, max=100, step=1, tooltip='Subspace iterations for low-rank SVD.'), _remaining_z_io.Combo.Input('output_dtype', options=['fp16', 'bf16', 'fp32'], default='fp16'), _remaining_z_io.Boolean.Input('bias_diff', default=True), _remaining_z_io.Float.Input('adaptive_param', default=0.15, min=0.0, max=1.0, step=0.01, tooltip='Ratio, quantile, energy, or Frobenius parameter for the selected adaptive method.'), _remaining_z_io.Boolean.Input('clamp_quantile', default=False)])

    @classmethod
    async def execute(cls, finetuned, original, filename_prefix, rank, lora_type, algorithm, lowrank_iters, output_dtype, bias_diff, adaptive_param, clamp_quantile):
        if algorithm == 'svd_lowrank' and lora_type != 'standard':
            raise ValueError('svd_lowrank algorithm is only supported for standard LoRA extraction.')
        dtype = {'bf16': _remaining_z_torch.bfloat16, 'fp16': _remaining_z_torch.float16, 'fp32': _remaining_z_torch.float32}[output_dtype]
        cursor = await finetuned.lora_weight_differences(original, include_bias=bias_diff)
        output_sd = {}
        extract_lora = _remaining_z_extract_lora()
        ctx = _remaining_z_sdk.ctx()
        async for item in cursor:
            tensor_ref = item['tensor']
            if tensor_ref is None:
                await ctx.progress.update(item['position'], item['total'])
                continue
            try:
                weight_diff = await tensor_ref.raw()
                output_key = item['output_key']
                if item['kind'] == 'bias':
                    output_sd[f'{output_key}.diff_b'] = weight_diff.contiguous().to(dtype).cpu()
                elif lora_type != 'full':
                    if weight_diff.ndim < 2:
                        if bias_diff:
                            output_sd[f'{output_key}.diff'] = weight_diff.contiguous().to(dtype).cpu()
                    else:
                        try:
                            up, down = extract_lora(weight_diff, output_key, rank, algorithm, lora_type, lowrank_iters=lowrank_iters, adaptive_param=adaptive_param, clamp_quantile=clamp_quantile)
                            output_sd[f'{output_key}.lora_up.weight'] = up.contiguous().to(dtype).cpu()
                            output_sd[f'{output_key}.lora_down.weight'] = down.contiguous().to(dtype).cpu()
                        except Exception as error:
                            _remaining_z_logging.warning('Could not generate lora weights for key %s, error %s', output_key, error)
                else:
                    output_sd[f'{output_key}.diff'] = weight_diff.contiguous().to(dtype).cpu()
                del weight_diff
            finally:
                await tensor_ref.release()
            await ctx.progress.update(item['position'], item['total'])
        rank_label = f'{lora_type}_{adaptive_param:.2f}' if 'adaptive' in lora_type else rank
        state_ref = await _remaining_z_sdk.ValueRef.from_value(output_sd)
        await ctx.output.save_state_dict(state_ref, f'{filename_prefix}_rank_{rank_label}_{output_dtype}', metadata=None)
        return _remaining_z_io.NodeOutput()

NODE_CLASS_MAPPINGS = {
    'LoraReduceRankKJSecure': LoraReduceRankKJSecure,
    'LoraExtractKJSecure': LoraExtractKJSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'LoraReduceRankKJSecure': '🔒 LoraReduceRank (secure)',
    'LoraExtractKJSecure': '🔒 LoraExtractKJ (secure)',
}
