"""SetLoRAs descriptor preparation, pending JACK-owned patch materialization.

No shared context field is invented here. The typed result is local preparation
data; JACK must explicitly adopt its storage/consumption contract before a node
can publish the result. None retains the original model without touching it.
Full native error ordering also needs the consumer's interleaved state-load,
normalization and patch-install work; this producer alone does not qualify it.
"""
from dataclasses import dataclass
import logging
from typing import NotRequired, TypedDict

from .wan_control_context import AuxiliaryAsset
from .wan_workflow_resources import describe_asset
from .wan_workflow_context import clone_model, transformer_options

log = logging.getLogger(__name__)


class LoRASelection(TypedDict):
    path: str
    name: str
    strength: float | list[float]
    blocks: object
    layer_filter: NotRequired[list[str]]
    low_mem_load: NotRequired[bool]
    merge_loras: NotRequired[bool]


class PinnedLoRASelection(TypedDict):
    descriptor: LoRASelection
    weights: AuxiliaryAsset


@dataclass
class PreparedLoRAResources:
    model_context: dict[str, object]
    ordered_resources: list[PinnedLoRASelection] | None
    unchanged_model_identity: bool


async def prepare_lora_resources(context, model, lora=None) -> PreparedLoRAResources:
    if lora is None:
        return PreparedLoRAResources(model, None, True)
    result = clone_model(model)
    merge_loras = False
    for descriptor in lora:
        merge_loras = descriptor.get('merge_loras', True)
    if merge_loras is True:
        raise ValueError("Set LoRA node does not use low_mem_load and can't merge LoRAs, disable 'merge_loras' in the LoRA select node.")
    options = transformer_options(result)
    options['lora_scheduling_enabled'] = False
    ordered = []
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
        weights = await describe_asset(context.assets, 'loras', name)
        # Preserve descriptor/list identity inside this producer call. Publication
        # later has the explicit cross-wire identity limits of the shared context.
        ordered.append({'descriptor': descriptor, 'weights': weights})
    return PreparedLoRAResources(result, ordered, False)
