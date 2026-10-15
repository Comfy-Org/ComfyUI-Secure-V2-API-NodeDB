"""Real finite CPU merged A/B LoRA on explicitly owned trained NN state.

This is pack-owned tensor/parameter work. It does not create a Core model,
ModelPatcher, WeightAdapterBase or substitute import namespace. The native
leaf traversal, alpha calculation, exception boundary, deterministic cast,
backup/copy/replacement and patched-leaf flags are kept for the stated domain.
Quantized/scaled, custom setters and other patch families need
separate actual native domains; no caller silently receives an unpatched NN.
"""
from dataclasses import dataclass
import logging

from .wan_workflow_lora_contract import OwnedPatchState
from .wan_workflow_owned_lora_weights import OwnedLoRAWeights


@dataclass(frozen=True)
class OwnedBackup:
    weight: object
    inplace_update: bool


def _module_and_name(transformer, key):
    if not isinstance(key, str) or not key.startswith('diffusion_model.'):
        raise ValueError('Merged LoRA key must address the actual owned diffusion NN')
    names = key[len('diffusion_model.'):].split('.')
    module = transformer
    for name in names[:-1]:
        module = getattr(module, name)
    return module, names[-1]


def _set_parameter(module, name, value):
    import torch
    # Exact native inference-tensor ownership rule before Parameter creation.
    if not torch.is_inference_mode_enabled() and value.is_inference():
        value = value.clone()
    setattr(module, name, torch.nn.Parameter(value, requires_grad=False))


def _check_owned_plain_domain(owner, *, low_mem_load=False, scale_weights=None):
    import torch
    if not isinstance(owner, OwnedPatchState):
        raise TypeError('Actual OwnedPatchState is required for merged tensor execution')
    if scale_weights:
        raise NotImplementedError('Scaled LoRA needs its separate native domain')
    if getattr(owner.transformer, 'patched_linear', False):
        raise NotImplementedError('Merged first domain precedes unmerged linear conversion')
    if any(p.device.type not in (('cpu', 'meta') if low_mem_load else ('cpu',))
           or p.dtype not in (torch.float16, torch.bfloat16, torch.float32)
           for p in owner.transformer.parameters()):
        raise NotImplementedError('Merged CPU domain permits real meta construction only with low-memory placement')
    if type(owner.weight_inplace_update) is not bool:
        raise TypeError('Owned in-place weight policy must be explicit')
    for key, rows in owner.patches.items():
        module, name = _module_and_name(owner.transformer, key)
        if hasattr(module, 'set_'+name) or hasattr(module, 'convert_'+name):
            raise NotImplementedError('Custom parameter setters/converters need a separate native domain')
        for strength, payload, strength_model, offset, function in rows:
            if not isinstance(payload, OwnedLoRAWeights):
                raise NotImplementedError('Merged first domain requires actual ordinary A/B tensor data')
            if isinstance(strength, list):
                raise ValueError('LoRA strength should be a single value when merge_loras=True')
            if offset is not None or function is not None:
                raise NotImplementedError('Offset/function patch records need their own native slice')
            up, down, alpha, mid, dora, reshape = payload.weights
            if mid is not None or dora is not None or reshape is not None:
                raise NotImplementedError('Merged DoRA/mid/reshape needs a separate native domain')
            if (up.ndim != 2 or down.ndim != 2 or not 1 <= down.shape[0] <= 256
                or up.shape[1] != down.shape[0] or up.device.type != 'cpu' or down.device.type != 'cpu'
                or up.dtype not in (torch.float16, torch.bfloat16, torch.float32)
                or down.dtype not in (torch.float16, torch.bfloat16, torch.float32)):
                raise NotImplementedError('Merged first domain requires bounded floating CPU matrix A/B')


def _calculate_owned_weight(patches, weight, key):
    """Native ordinary LoRA merge branch, including its original try boundary.

    This deliberately differs from unmerged CustomLinear for explicit alpha=0:
    native merged alpha/rank is zero; native unmerged treats zero as scale1.
    Shape/mm/update errors are logged and return the current weight, as native.
    """
    import torch
    for strength, payload, strength_model, offset, function in patches:
        if function is None:
            function = lambda a: a
        # Offsets/functions were explicitly excluded before any NN mutation.
        if strength_model != 1.0:
            weight *= strength_model
        v = payload.weights
        mat1 = v[0].to(dtype=torch.float32)
        mat2 = v[1].to(dtype=torch.float32)
        if v[2] is not None:
            alpha = v[2] / mat2.shape[0]
        else:
            alpha = 1.0
        try:
            lora_diff = torch.mm(
                mat1.flatten(start_dim=1), mat2.flatten(start_dim=1)
            ).reshape(weight.shape)
            del mat1, mat2
            weight += function(((strength * alpha) * lora_diff).type(weight.dtype))
        except Exception as e:
            logging.error("ERROR {} {} {}".format('lora', key, e))
    return weight


def patch_owned_weight_to_device(owner, key, *, inplace_update=False, backup_keys=False):
    """Actual native CPU backup -> fp32 calculation -> cast -> parameter write."""
    import torch
    if key not in owner.patches:
        return
    module, name = _module_and_name(owner.transformer, key)
    weight = getattr(module, name)
    inplace_update = owner.weight_inplace_update or inplace_update
    if backup_keys and key not in owner.backups:
        owner.backups[key] = OwnedBackup(weight.to(device=torch.device('cpu'), copy=inplace_update), inplace_update)
    temp_weight = weight.to(dtype=torch.float32, copy=True)
    out_weight = _calculate_owned_weight(owner.patches[key], temp_weight, key)
    # Pinned native stochastic_rounding is exactly .to for these three dtypes;
    # it does not draw from any generator. FP8 is deliberately not admitted.
    out_weight = out_weight.to(dtype=weight.dtype)
    if inplace_update:
        weight.data.copy_(out_weight)
    else:
        _set_parameter(module, name, out_weight)


def merge_owned_patches(owner, device_to, transformer_load_device, params_to_keep=None,
                        dtype=None, base_dtype=None, state_dict=None,
                        low_mem_load=False, control_lora=False, scale_weights=None):
    """Native reverse leaf ordering and mutation on the actual owned NN.

    Preparation validates CPU/meta finite domain before mutation. Low-memory
    placement consumes actual caller-owned checkpoint tensors, using original
    pre-placement/patch/post-placement/final-leftovers order and catch phases.
    This source does not
    claim original resource acquisition/error phases, unsupported families or runtime
    qualification. All actual matrix multiplication and NN writes happen here.
    """
    import torch
    from tqdm import tqdm
    from ._wan_full_vae_runtime import ProgressBar
    from .wan_workflow_t5_weights import set_module_tensor_to_device
    if torch.device(device_to).type != 'cpu' or torch.device(transformer_load_device).type != 'cpu':
        raise NotImplementedError('Owned merged first domain is CPU-only')
    _check_owned_plain_domain(owner, low_mem_load=low_mem_load, scale_weights=scale_weights)
    to_load = []
    for raw_name, module in owner.transformer.named_modules():
        name = 'diffusion_model' + ('.'+raw_name if raw_name else '')
        params = []
        skip = False
        for param_name, param in module.named_parameters(recurse=False):
            params.append(param_name)
        for param_name, param in module.named_parameters(recurse=True):
            if param_name not in params:
                skip = True
                break
        if not skip and (hasattr(module, 'comfy_cast_weights') or len(params) > 0):
            to_load.append((name, module, params))
    to_load.sort(reverse=True)
    count = 0
    pbar = ProgressBar(len(to_load))
    for name, module, params in tqdm(to_load, desc='Loading model and applying LoRA weights:', leave=True):
        if hasattr(module, 'comfy_patched_weights'):
            if module.comfy_patched_weights == True:
                continue
        for param in params:
            name = name.replace('._orig_mod.', '.')
            if low_mem_load:
                dtype_to_use = base_dtype if any(keyword in name for keyword in params_to_keep) else dtype
                if 'patch_embedding' in name:
                    dtype_to_use = torch.float32
                key = f"{name.replace('diffusion_model.', '')}.{param}"
                try:
                    set_module_tensor_to_device(owner.transformer, key,
                        device=transformer_load_device, dtype=dtype_to_use, value=state_dict[key])
                except Exception:
                    continue
            key = f'{name}.{param}'
            patch_owned_weight_to_device(owner, key, inplace_update=low_mem_load, backup_keys=control_lora)
            if not low_mem_load and device_to != transformer_load_device:
                set_module_tensor_to_device(module, param, device=transformer_load_device)
            if low_mem_load:
                try:
                    # Keep the native full-prefix lookup and swallowed failure.
                    # It is not silently rewritten to an unprefixed lookup.
                    set_module_tensor_to_device(owner.transformer, key,
                        device=transformer_load_device, dtype=dtype_to_use,
                        value=owner.transformer.state_dict()[key])
                except Exception:
                    continue
        module.comfy_patched_weights = True
        count += 1
        if count % 100 == 0:
            pbar.update(100)
    owner.current_generation = owner.generation
    if low_mem_load:
        for name, param in owner.transformer.named_parameters():
            if param.device != transformer_load_device:
                dtype_to_use = base_dtype if any(keyword in name for keyword in params_to_keep) else dtype
                if 'patch_embedding' in name:
                    dtype_to_use = torch.float32
                try:
                    set_module_tensor_to_device(owner.transformer, name,
                        device=transformer_load_device, dtype=dtype_to_use, value=state_dict[name])
                except Exception:
                    continue
    return owner


def restore_owned_backups(owner, device_to=None):
    """Real native plain-NN backup restoration, preserving shared backup owner."""
    import torch
    if not isinstance(owner, OwnedPatchState):
        raise TypeError('Actual owned backup lifetime is required')
    if device_to is not None and torch.device(device_to).type != 'cpu':
        raise NotImplementedError('Owned restore first domain is CPU-only')
    for key in list(owner.backups.keys()):
        backup = owner.backups[key]
        module, name = _module_and_name(owner.transformer, key)
        if backup.inplace_update:
            getattr(module, name).data.copy_(backup.weight)
        else:
            _set_parameter(module, name, backup.weight)
    owner.current_generation = None
    owner.backups.clear()
    if device_to is not None:
        owner.transformer.to(device_to)
    for module in owner.transformer.modules():
        if hasattr(module, 'comfy_patched_weights'):
            del module.comfy_patched_weights


def apply_lora(execution, device_to, transformer_load_device, params_to_keep=None,
               dtype=None, base_dtype=None, state_dict=None, low_mem_load=False,
               control_lora=False, scale_weights=None):
    """Connect original sampler calls to actual owned merge state, never Core.

    The ordinary admitted sampler currently keeps control_lora=False. Actual
    Control-LoRA resources, architecture and live scheduling remain gated; this
    compatibility call is not counted as trained Control-LoRA qualification.
    """
    from .wan_workflow_sampler_runtime import ExecutionState
    if not isinstance(execution, ExecutionState):
        raise TypeError('Only the actual local owned ExecutionState may merge weights')
    owner = execution.patch_ownership
    if not isinstance(owner, OwnedPatchState) or owner.transformer is not execution.model.diffusion_model or owner.patches is not execution.patches:
        raise ValueError('Merged patches and backup ownership must belong to the same actual NN')
    merge_owned_patches(owner, device_to, transformer_load_device, params_to_keep,
                        dtype, base_dtype, state_dict, low_mem_load, control_lora, scale_weights)
    return execution
