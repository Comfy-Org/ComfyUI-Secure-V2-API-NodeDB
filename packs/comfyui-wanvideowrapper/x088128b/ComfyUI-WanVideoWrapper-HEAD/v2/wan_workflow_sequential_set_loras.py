"""Sequential original SetLoRAs phases using actual pinned files and owned NN.

Never prefetch/describe later descriptors before an earlier file has completed
its native normalization/unsupported guards and actual key-map patch parsing.
The real base is reconstructed lazily only when native image-key/key-map phases
need its state. This additional owned reconstruction boundary is explicit;
resource failures there are not claimed identical to a preexisting V1 model.
"""
from contextlib import AsyncExitStack
import gc
import logging

from .wan_lora_resource_preparation import PreparedLoRAResources
from .wan_workflow_context import clone_model, model_options, transformer_options
from .wan_workflow_resources import describe_asset
from .wan_workflow_lora_contract import (LORA_PLAN_KEY, OwnedPatchState,
    adopt_prepared_lora_resources, read_lora_state, validate_lora_plan)
from .wan_workflow_lora_preprocess import (compensate_rs_lora_format,
    standardize_lora_key_format, filter_state_dict_by_blocks)
from .wan_workflow_lora_unmerged import (MAX_PLAIN_LORA_BYTES,
    MAX_PLAIN_LORA_TENSORS, materialize_unmerged_lora_plan,
    owned_key_map, load_plain_owned_patches, append_owned_patches)
from .wan_workflow_model_runtime import materialize_model

log = logging.getLogger(__name__)


def normalize_before_model(lora_sd, descriptor):
    """Exact original pre-image-policy phase, once, before base reconstruction."""
    if 'dwpose_embedding.0.weight' in lora_sd:
        raise NotImplementedError('Unianimate LoRA patching is not implemented in this node.')
    if 'base_model.model.blocks.0.cross_attn.k.lora_A.weight' in lora_sd:
        lora_sd = compensate_rs_lora_format(lora_sd)
    lora_sd = standardize_lora_key_format(lora_sd)
    if descriptor['blocks']:
        lora_sd = filter_state_dict_by_blocks(lora_sd, descriptor['blocks'], descriptor.get('layer_filter', []))
    return lora_sd


async def prepare_set_loras_sequential(context, model, lora=None, *, devices):
    """Original descriptor loop interleaved with real file validation/patches.

    Native does not mutate base NN values in SetLoRAs. The producer parses real
    patches against its own real materialized base only for validation; public
    model context still carries exact pinned resources for consumer rebuilding.
    Tensor/storage publication and repeated consumer I/O remain explicit gates.
    """
    if lora is None:
        return model
    result = clone_model(model)
    merge_loras = False
    for descriptor in lora:
        merge_loras = descriptor.get('merge_loras', True)
    if merge_loras is True:
        raise ValueError("Set LoRA node does not use low_mem_load and can't merge LoRAs, disable 'merge_loras' in the LoRA select node.")
    options = transformer_options(result)
    options['lora_scheduling_enabled'] = False
    ordered = []
    transformer = owner = state = prepared = patches = None
    async with AsyncExitStack() as lifetime:
        async def actual_base_owner():
            nonlocal transformer, owner
            if transformer is None:
                # No base I/O happens until an earlier real LoRA file has
                # passed its original unsupported/RS/key/block phases.
                base = clone_model(result)
                previous = model_options(base).pop(LORA_PLAN_KEY, None)
                transformer, _ = await lifetime.enter_async_context(materialize_model(base, context))
                if previous is None:
                    owner = OwnedPatchState(transformer)
                else:
                    # A prior plan is not silently discarded or replaced by an
                    # unrelated NN's backup mapping. Its pinned real weights
                    # are reconstructed only into this NN's own patch owner.
                    owner = await materialize_unmerged_lora_plan(context, transformer,
                        validate_lora_plan(previous), devices=devices)
            return owner
        try:
            for descriptor in lora:
                log.info(f"Loading LoRA: {descriptor['name']} with strength: {descriptor['strength']}")
                name = descriptor['path']
                strength = descriptor['strength']
                if isinstance(strength, list):
                    if merge_loras:
                        raise ValueError('LoRA strength should be a single value when merge_loras=True')
                    options['lora_scheduling_enabled'] = True
                if strength == 0:
                    log.warning(f'LoRA {name} has strength 0, skipping...')
                    continue
                # Crucial: no list comprehension/bulk preparation precedes
                # this actual file read and completed descriptor validation.
                weights = await describe_asset(context.assets, 'loras', name)
                entry = {'weights': weights, 'selection': descriptor}
                async with read_lora_state(context, entry, devices=devices,
                        max_bytes=MAX_PLAIN_LORA_BYTES,
                        max_tensors=MAX_PLAIN_LORA_TENSORS) as state:
                    prepared = normalize_before_model(state, descriptor)
                    owner = await actual_base_owner()
                    if not any('img' in key for key in transformer.state_dict().keys()):
                        prepared = {key:value for key,value in prepared.items() if 'img' not in key}
                    if 'diffusion_model.patch_embedding.lora_A.weight' in prepared:
                        raise NotImplementedError('Control LoRA patching is not implemented in this node.')
                    patches = load_plain_owned_patches(prepared, owned_key_map(transformer))
                    loaded = set(append_owned_patches(owner, patches, strength))
                    for key in patches:
                        if key not in loaded:
                            log.warning('NOT LOADED {}'.format(key))
                    owner.applied_resources.append(weights)
                # Keep original descriptor/strength references for the existing
                # in-call ownership contract; publication identity is separate.
                ordered.append({'descriptor': descriptor, 'weights': weights})
                state = prepared = patches = None
            return adopt_prepared_lora_resources(PreparedLoRAResources(result, ordered, False))
        finally:
            # Pure pinned descriptions survive; no temporary NN/patch tensors,
            # callbacks or file handles are published as a fake host model.
            owner = transformer = state = prepared = patches = None
            gc.collect()
