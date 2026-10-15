"""Native loader key/rank preflight on validated SafeTensors metadata.

This moves only the original pre-construction checks into the public producer.
It creates no NN, accepts no tensor substitute and adds no resource wire fields.
Actual checkpoint loading, constructors, devices and learned behavior remain
the owned materializer's separate, unqualified execution domain.
"""
from .wan_workflow_resources import inspect_header


def validate_control_loader_header(header, family):
    """Use only metadata already validated by inspect_header.

    Real tensor.shape is a tuple. Convert the validated metadata shape to a
    tuple so native rank errors keep their exact IndexError message. Do not
    add a friendlier missing-key guard before an earlier native shape access.
    """
    if family == 'thedenk':
        tuple(header['controlnet_blocks.0.bias']['shape'])[0]
        if 'control_encoder.0.0.weight' not in header:
            raise ValueError('Invalid ControlNet model')
    elif family == 'uni3c':
        if 'controlnet_patch_embedding.weight' not in header:
            raise ValueError('Invalid ControlNet model')
        tuple(header['controlnet_patch_embedding.weight']['shape'])[1]
        tuple(header['controlnet_blocks.0.ffn.0.bias']['shape'])[0]
    else:
        raise ValueError('Unsupported ControlNet family')


async def preflight_control_loader(assets, resource, family):
    header = await inspect_header(assets, resource)
    validate_control_loader_header(header, family)
