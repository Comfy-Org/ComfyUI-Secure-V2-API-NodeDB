"""Real ordinary unmerged LoRA execution on pack-owned trained transformers.

No Core model/patcher/adapter is fabricated. Actual A/B tensors become explicit
owned weight data consumed by the unchanged original CustomLinear implementation.
Merged LoRA, GGUF, FP8, DoRA/mid/reshape and other adapters remain separate gates.
"""
import logging
import uuid

from .wan_workflow_lora_contract import OwnedPatchState, validate_lora_plan, read_lora_state
from .wan_workflow_lora_preprocess import prepare_set_lora_state
from .wan_workflow_owned_lora_weights import OwnedLoRAWeights

MAX_PLAIN_LORA_BYTES = 256 * 1024**2
MAX_PLAIN_LORA_TENSORS = 4096
MAX_PLAIN_LORA_RANK = 256
_PAIR_SUFFIXES = ('.lora_up.weight', '.lora_down.weight', '_lora.up.weight', '_lora.down.weight',
    '.lora_B.weight', '.lora_A.weight', '.lora.up.weight', '.lora.down.weight',
    '.lora_B', '.lora_A', '.lora_linear_layer.up.weight', '.lora_linear_layer.down.weight',
    '.lora_B.default.weight', '.lora_A.default.weight', '.alpha')


def owned_key_map(transformer):
    """Native Wan key aliases from actual parameter keys; native U-Net config={}."""
    result = {}
    for raw in transformer.state_dict().keys():
        key = ('diffusion_model.' + raw).replace('_orig_mod.', '')
        if key.endswith('.weight'):
            alias = key[len('diffusion_model.'):-len('.weight')].replace('.', '_')
            result['lora_unet_{}'.format(alias)] = key
            result['{}'.format(key[:-len('.weight')])] = key
        else:
            result['{}'.format(key)] = key
    return result


def load_plain_owned_patches(state, key_map):
    """Same key-map iteration and native LoRA loader precedence in finite domain."""
    if len(state) > MAX_PLAIN_LORA_TENSORS:
        raise NotImplementedError('Plain LoRA tensor count exceeds this source execution domain')
    if any(not isinstance(key, str) or not key.endswith(_PAIR_SUFFIXES) for key in state):
        raise NotImplementedError('Non-ordinary LoRA adapter family needs its own native execution slice')
    patches = {}
    loaded_keys = set()
    for alias in key_map:
        alpha_name = '{}.alpha'.format(alias)
        alpha = None
        if alpha_name in state.keys():
            alpha = state[alpha_name].item()
            loaded_keys.add(alpha_name)
        payload = OwnedLoRAWeights.load(alias, state, alpha, None, loaded_keys)
        if payload is not None:
            up, down, _, mid, dora, reshape = payload.weights
            if mid is not None or dora is not None or reshape is not None:
                raise NotImplementedError('DoRA/mid/reshape LoRA is outside the ordinary A/B domain')
            # Alpha deliberately stays under native .item() above, including
            # integer, boolean, float64 and nonscalar native failures. Check only
            # matrices actually consumed, after original preprocessing/parser.
            import torch
            if up.dtype not in (torch.float16, torch.bfloat16, torch.float32) or down.dtype not in (torch.float16, torch.bfloat16, torch.float32):
                raise NotImplementedError('Quantized/non-floating A/B weights need a separate domain')
            if up.ndim != 2 or down.ndim != 2 or not 1 <= down.shape[0] <= MAX_PLAIN_LORA_RANK or up.shape[1] != down.shape[0]:
                raise NotImplementedError('Only bounded positive-rank matrix A/B pairs are admitted here')
            if up.device.type != 'cpu' or down.device.type != 'cpu':
                raise NotImplementedError('Owned ordinary LoRA first execution domain is CPU')
            patches[key_map[alias]] = payload
            loaded_keys.update(payload.loaded_keys)
    for key in state.keys():
        if key not in loaded_keys:
            logging.warning('lora key not loaded: {}'.format(key))
    return patches


def append_owned_patches(owner, patches, strength_patch=1.0, strength_model=1.0):
    """Native match/._orig_mod/append order on the actual NN, no ejection shim."""
    model_sd = {'diffusion_model.' + key: value for key, value in owner.transformer.state_dict().items()}
    # Native load_lora_for_models_mod clones before add_patches. Copy lists,
    # retaining schedule and tensor payload identity and the existing backups.
    owner.patches = {key: value[:] for key, value in owner.patches.items()}
    matched = set()
    for patch_key in patches:
        offset = function = None
        if isinstance(patch_key, str):
            key = patch_key
        else:
            offset = patch_key[1]
            key = patch_key[0]
            if len(patch_key) > 2:
                function = patch_key[2]
        direct = key in model_sd
        alternate = None
        if not direct:
            parts = key.split('.')
            try:
                idx = parts.index('blocks')
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    alternate = '.'.join(parts[:idx + 2] + ['_orig_mod'] + parts[idx + 2:])
            except ValueError:
                pass
        if direct or alternate is not None and alternate in model_sd:
            actual = key if direct else alternate
            matched.add(patch_key)
            current = owner.patches.get(actual, [])
            current.append((strength_patch, patches[patch_key], strength_model, offset, function))
            owner.patches[actual] = current
    owner.generation = uuid.uuid4()
    return list(matched)


async def prepare_unmerged_owned_patches(transformer, state, selection, owner):
    """Actual local executor for apply_ordered_lora_plan's callback contract.

    Normalize/filter using the frozen original functions, derive native aliases
    from the real base, parse actual tensor weights, and append original patch
    rows. Native sampler set_lora_params performs the single original buffer
    installation at its original phase, after all descriptors have succeeded;
    its real CustomLinear.forward applies patches at each step.
    """
    import torch
    if not isinstance(owner, OwnedPatchState) or owner.transformer is not transformer:
        raise ValueError('LoRA patch ownership belongs to another actual transformer')
    if any(parameter.device.type != 'cpu' for parameter in transformer.parameters()):
        raise NotImplementedError('Ordinary unmerged first execution domain requires actual CPU parameters')
    # Preserve native preprocessing and its unsupported-control guard order.
    prepared = prepare_set_lora_state(state, selection, transformer.state_dict().keys())
    patches = load_plain_owned_patches(prepared, owned_key_map(transformer))
    loaded = set(append_owned_patches(owner, patches, selection['strength']))
    for key in patches:
        if key not in loaded:
            logging.warning('NOT LOADED {}'.format(key))


async def materialize_unmerged_lora_plan(context, transformer, plan, *, devices, prior=None):
    """Interleave each pinned read, original preprocessing and real patch append.

    Earlier prepared descriptors may already have broker lookup effects. This
    does not claim the original V1 SetLoRAs producer error phase is qualified.
    """
    devices.validate_cpu_scope()
    plan = validate_lora_plan(plan)
    owner = OwnedPatchState(transformer) if prior is None else prior.fork(transformer)
    for entry in plan['entries']:
        if entry['weights']['bytes'] > MAX_PLAIN_LORA_BYTES:
            raise NotImplementedError('Ordinary LoRA file exceeds the finite256MiB domain')
        async with read_lora_state(context, entry, devices=devices,
                max_bytes=MAX_PLAIN_LORA_BYTES, max_tensors=MAX_PLAIN_LORA_TENSORS) as state:
            await prepare_unmerged_owned_patches(transformer, state, entry['selection'], owner)
            owner.applied_resources.append(entry['weights'])
        del state
    return owner
