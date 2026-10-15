"""Ordered pinned LoRA resources and explicit per-transformer patch ownership.

This module does not implement native patch math. Consumers must supply the
real reviewed patch executor; no recipe is silently treated as applied LoRA.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from .wan_workflow_context import clone_options, model_options
from .wan_workflow_resources import validate_resource, inspect_header, private_weight_file

LORA_PLAN_FORMAT = 'wan-ordered-lora-resource-plan-v1'
LORA_PLAN_KEY = 'lora_resource_plan'


def validate_lora_plan(plan):
    if type(plan) is not dict or set(plan) != {'format', 'entries'} or plan['format'] != LORA_PLAN_FORMAT:
        raise ValueError('Invalid owned ordered LoRA resource plan')
    if type(plan['entries']) is not list:
        raise TypeError('LoRA entries must be an ordered list')
    for entry in plan['entries']:
        if type(entry) is not dict or set(entry) != {'weights', 'selection'}:
            raise ValueError('Invalid pinned LoRA entry')
        if validate_resource(entry['weights'])['kind'] != 'loras':
            raise ValueError('LoRA weights require the loras catalogue')
        if type(entry['selection']) is not dict or 'path' not in entry['selection']:
            raise ValueError('Original LoRA selector data is missing')
        if entry['selection']['path'] != entry['weights']['name']:
            raise ValueError('Logical LoRA selection/resource mismatch')
    return plan




def adopt_prepared_lora_resources(prepared):
    """Adopt the child's PreparedLoRAResources without taking producer ownership.

    The child already cloned the model context and preserved last-merge and
    scheduling behavior. Keep each new descriptor's in-call identity; publication
    retains the existing explicit cross-wire alias limits.
    """
    if prepared.unchanged_model_identity:
        if prepared.ordered_resources is not None:
            raise ValueError('Unchanged LoRA preparation cannot contain resources')
        return prepared.model_context
    options = model_options(prepared.model_context)
    previous = options.get(LORA_PLAN_KEY)
    entries = [] if previous is None else list(validate_lora_plan(previous)['entries'])
    for entry in prepared.ordered_resources:
        if type(entry) is not dict or set(entry) != {'descriptor', 'weights'}:
            raise ValueError('Unexpected child pinned LoRA resource shape')
        entries.append({'weights': entry['weights'], 'selection': entry['descriptor']})
    options[LORA_PLAN_KEY] = validate_lora_plan({'format': LORA_PLAN_FORMAT, 'entries': entries})
    return prepared.model_context


@dataclass
class OwnedPatchState:
    """Actual tensors/patch data scoped to one real transformer, never Core MODEL.

    A clone copies each patch list while retaining patch values and shared
    backups for the same NN. A new NN cannot inherit another NN's backups.
    """
    transformer: object
    patches: dict = field(default_factory=dict)
    backups: dict = field(default_factory=dict)
    applied_resources: list = field(default_factory=list)
    generation: object = None
    weight_inplace_update: bool = False
    current_generation: object = None

    def fork(self, transformer):
        if transformer is not self.transformer:
            raise ValueError('Prior patch ownership belongs to a different transformer')
        return OwnedPatchState(transformer, {key: value[:] for key, value in self.patches.items()},
                               self.backups, list(self.applied_resources), self.generation,
                               self.weight_inplace_update, self.current_generation)


@asynccontextmanager
async def read_lora_state(context, entry, *, devices, max_bytes=None, max_tensors=None):
    """One pinned file at a time. Keep original safe tensor state/key ordering."""
    from safetensors.torch import load_file
    devices.validate_cpu_scope()
    validate_lora_plan({'format': LORA_PLAN_FORMAT, 'entries': [entry]})
    state = None
    if max_bytes is not None and entry['weights']['bytes'] > max_bytes:
        raise NotImplementedError('LoRA resource exceeds the selected finite execution domain')
    header = await inspect_header(context.assets, entry['weights'])
    if max_tensors is not None and len(header) > max_tensors:
        raise NotImplementedError('LoRA tensor count exceeds the selected finite execution domain')
    async with private_weight_file(context.assets, entry['weights']) as path:
        try:
            state = load_file(str(path), device=str(devices.offload_device))
            yield state
        finally:
            state = None


async def apply_ordered_lora_plan(context, transformer, plan, *, devices,
                                  executor, prior=None):
    """Invoke a real owned patch executor once for each original ordered entry.

    executor is a local pack callback, not transported or SDK host code. Its
    contract is async(transformer,state,selection,ownership)->None. It must
    preserve native key normalization, unsupported-control guards, layer
    filters, image-key policy, patch state/aliasing and RNG. This orchestration
    does not claim those math semantics are implemented.
    """
    if not callable(executor):
        raise NotImplementedError('Native owned LoRA patch executor is not implemented')
    plan = validate_lora_plan(plan)
    owned = OwnedPatchState(transformer) if prior is None else prior.fork(transformer)
    for entry in plan['entries']:
        async with read_lora_state(context, entry, devices=devices) as state:
            await executor(transformer, state, entry['selection'], owned)
            owned.applied_resources.append(clone_options(entry['weights']))
        del state
    return owned
