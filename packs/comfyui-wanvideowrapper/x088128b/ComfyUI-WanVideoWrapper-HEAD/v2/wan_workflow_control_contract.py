"""Pinned control recipes and real owned construction; never a model proxy."""
from contextlib import asynccontextmanager
import gc

from .wan_workflow_context import clone_options
from .wan_control_context import native_precision_key
from .wan_control_loader_preflight import preflight_control_loader
from .wan_workflow_resources import describe_asset, validate_resource, inspect_header, private_weight_file

CONTROL_FORMAT = 'wan-controlnet-loader-resource-v1'
_BASE_PRECISIONS = ('fp8_e4m3fn', 'fp8_e4m3fn_fast', 'bf16', 'fp16', 'fp16_fast', 'fp32')
_QUANTIZATIONS = ('disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp8_e4m3fn_fast_no_ffn')


def validate_control_recipe(recipe, expected_family=None):
    if type(recipe) is not dict:
        raise TypeError('Expected a pure owned ControlNet recipe')
    fmt = recipe.get('format')
    family = recipe.get('family')
    keys = {'format', 'family', 'weights', 'model_name', 'base_precision', 'load_device', 'quantization'}
    if family == 'uni3c':
        keys |= {'attention_mode', 'compile_args'}
    elif family != 'thedenk':
        raise ValueError('Unsupported ControlNet family')
    if fmt != CONTROL_FORMAT:
        raise ValueError('Unsupported ControlNet recipe format')
    if set(recipe) != keys or expected_family is not None and family != expected_family:
        raise ValueError('ControlNet recipe fields/type changed')
    resource = validate_resource(recipe['weights'])
    if resource['kind'] != 'controlnet':
        raise ValueError('ControlNet recipes require the controlnet asset catalogue')
    if recipe['model_name'] != resource['name']:
        raise ValueError('ControlNet logical model name differs from pinned weights')
    if recipe['base_precision'] not in _BASE_PRECISIONS:
        raise ValueError('Unsupported original ControlNet precision')
    if recipe['quantization'] not in _QUANTIZATIONS:
        raise ValueError('Unsupported original ControlNet quantization')
    if recipe['load_device'] not in ('main_device', 'offload_device'):
        raise ValueError('Invalid original ControlNet load device')
    if family == 'uni3c':
        if not isinstance(recipe['attention_mode'], str) or not recipe['attention_mode']:
            raise ValueError('Uni3C requires its original attention mode')
        if recipe['compile_args'] is not None and type(recipe['compile_args']) is not dict:
            raise TypeError('Uni3C compile arguments must be a pure dict or None')
    return recipe


async def describe_control_recipe(context, model_name, base_precision, load_device,
                                  quantization, *, family='thedenk',
                                  attention_mode='sdpa', compile_args=None):
    native_precision_key(base_precision)
    recipe = {'format': CONTROL_FORMAT, 'family': family, 'model_name': model_name,
              'weights': await describe_asset(context.assets, 'controlnet', model_name),
              'base_precision': base_precision, 'load_device': load_device,
              'quantization': quantization}
    if family == 'uni3c':
        recipe.update(attention_mode=attention_mode, compile_args=clone_options(compile_args))
    await preflight_control_loader(context.assets, recipe['weights'], family)
    return validate_control_recipe(recipe)


@asynccontextmanager
async def materialize_control_recipe(context, recipe, *, devices):
    """Recheck the exact file, load real tensors, call the preserved constructor.

    devices is owned execution policy, never a graph object or host capability.
    This first contract admits CPU only; native CUDA/default devices, FP8 and
    compilation remain independent gates. No implicit device substitution.
    """
    import torch
    from safetensors.torch import load_file
    from ._wan_controlnet_materializers import materialize_controlnet, materialize_uni3c_controlnet
    recipe = validate_control_recipe(recipe)
    devices.validate_cpu_scope()
    if recipe['base_precision'] not in ('fp32', 'bf16', 'fp16') or recipe['quantization'] != 'disabled':
        raise NotImplementedError('ControlNet FP8/quantized device execution requires its own admission')
    if recipe['family'] == 'uni3c':
        if recipe['attention_mode'] != 'sdpa' or recipe['compile_args'] is not None:
            raise NotImplementedError('Uni3C compiled/alternate attention execution remains gated')
    selected = devices.main_device if recipe['load_device'] == 'main_device' else devices.offload_device
    control = state = None
    await inspect_header(context.assets, recipe['weights'])
    async with private_weight_file(context.assets, recipe['weights']) as path:
        try:
            state = load_file(str(path), device=str(selected))
            # Preserve native autodetection and constructor order. CPU FP8 is
            # not admitted merely because the requested quantization is disabled.
            if any(value.dtype in (torch.float8_e4m3fn, torch.float8_e5m2) for value in state.values()):
                raise NotImplementedError('Detected ControlNet FP8 state requires a separate device domain')
            kwargs = {'main_device': devices.main_device,
                      'offload_device': devices.offload_device,
                      'soft_empty_cache': devices.soft_empty_cache}
            if recipe['family'] == 'uni3c':
                control = materialize_uni3c_controlnet(state, recipe['base_precision'],
                    recipe['load_device'], recipe['quantization'], recipe['attention_mode'],
                    recipe['compile_args'], **kwargs)
            else:
                control = materialize_controlnet(state, recipe['base_precision'],
                    recipe['load_device'], recipe['quantization'], **kwargs)
            state = None
            yield control
        finally:
            state = control = None
            gc.collect()


async def _raw_value(value):
    from comfy_api.latest import sdk
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    return value


async def bind_control_inputs(context, lifetime, options, uni3c_embeds, *, devices):
    """Replace only the two native control-object slots in cloned containers.

    Original tensor objects, strength/start/end/offload and other payload fields
    retain their identities/values. A recipe is never passed to neural math.
    """
    result = clone_options(options)
    transformer = result.get('transformer_options')
    if type(transformer) is not dict:
        raise TypeError('Owned options require transformer_options')
    control = transformer.get('controlnet')
    if control is not None:
        if type(control) is not dict or 'controlnet' not in control:
            raise ValueError('Invalid native ControlNet conditioning container')
        recipe = await _raw_value(control['controlnet'])
        validate_control_recipe(recipe, 'thedenk')
        control['controlnet'] = await lifetime.enter_async_context(
            materialize_control_recipe(context, recipe, devices=devices))
        if 'control_latents' in control:
            control['control_latents'] = await _raw_value(control['control_latents'])
    uni3c = clone_options(uni3c_embeds)
    if uni3c is not None:
        if type(uni3c) is not dict or 'controlnet' not in uni3c:
            raise ValueError('Invalid original Uni3C conditioning container')
        recipe = await _raw_value(uni3c['controlnet'])
        validate_control_recipe(recipe, 'uni3c')
        uni3c['controlnet'] = await lifetime.enter_async_context(
            materialize_control_recipe(context, recipe, devices=devices))
        if uni3c.get('render_latent') is not None:
            uni3c['render_latent'] = await _raw_value(uni3c['render_latent'])
    return result, uni3c
