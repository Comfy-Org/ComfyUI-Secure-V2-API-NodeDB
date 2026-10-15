"""Typed producer contract proposed to JACK; no neural object crosses the wire.

This source is unintegrated. Its exact field layout must be adopted by the
shared consumer before either loader can be counted as converted/qualified.
"""
from typing import Literal, TypedDict

from .wan_control_loader_preflight import preflight_control_loader

from .wan_workflow_resources import describe_asset, validate_resource


class AuxiliaryAsset(TypedDict):
    format: Literal['wan-workflow-asset-v1']
    kind: Literal['controlnet', 'loras']
    name: str
    bytes: int
    sha256: str


class ControlResource(TypedDict):
    format: Literal['wan-controlnet-loader-resource-v1']
    family: Literal['thedenk']
    weights: AuxiliaryAsset
    model_name: str
    base_precision: str
    load_device: str
    quantization: str


class Uni3CResource(TypedDict):
    format: Literal['wan-controlnet-loader-resource-v1']
    family: Literal['uni3c']
    weights: AuxiliaryAsset
    model_name: str
    base_precision: str
    load_device: str
    quantization: str
    attention_mode: str
    compile_args: dict[str, object] | None


CONTROL_FORMAT = 'wan-controlnet-loader-resource-v1'
COMMON_FIELDS = {'format', 'family', 'weights', 'model_name', 'base_precision', 'load_device', 'quantization'}


def native_precision_key(base_precision):
    # Original computes this lookup before asset lookup. Keep hidden accepted
    # spellings too; UI choices are intentionally the original three values.
    return {'fp8_e4m3fn': 'float8_e4m3fn', 'fp8_e4m3fn_fast': 'float8_e4m3fn',
            'bf16': 'bfloat16', 'fp16': 'float16', 'fp16_fast': 'float16',
            'fp32': 'float32'}[base_precision]


def validate_control_resource(value: ControlResource | Uni3CResource):
    if type(value) is not dict or value.get('format') != CONTROL_FORMAT:
        raise ValueError('Invalid owned Wan ControlNet loader resource')
    family = value.get('family')
    expected = COMMON_FIELDS if family == 'thedenk' else COMMON_FIELDS | {'attention_mode', 'compile_args'}
    if family not in ('thedenk', 'uni3c') or set(value) != expected:
        raise ValueError('Invalid owned Wan ControlNet resource fields')
    weights = validate_resource(value['weights'])
    if weights['kind'] != 'controlnet' or value['model_name'] != weights['name']:
        raise ValueError('Wan ControlNet resource does not match its catalogue selection')
    native_precision_key(value['base_precision'])
    return value


async def describe_control_resource(assets, model, base_precision, load_device, quantization) -> ControlResource:
    native_precision_key(base_precision)
    weights = await describe_asset(assets, 'controlnet', model)
    await preflight_control_loader(assets, weights, 'thedenk')
    return {'format': CONTROL_FORMAT, 'family': 'thedenk', 'weights': weights,
            'model_name': model, 'base_precision': base_precision,
            'load_device': load_device, 'quantization': quantization}


async def describe_uni3c_resource(assets, model, base_precision, load_device, quantization,
                                attention_mode, compile_args=None) -> Uni3CResource:
    native_precision_key(base_precision)
    weights = await describe_asset(assets, 'controlnet', model)
    await preflight_control_loader(assets, weights, 'uni3c')
    return {'format': CONTROL_FORMAT, 'family': 'uni3c', 'weights': weights,
            'model_name': model, 'base_precision': base_precision, 'load_device': load_device,
            'quantization': quantization, 'attention_mode': attention_mode, 'compile_args': compile_args}
