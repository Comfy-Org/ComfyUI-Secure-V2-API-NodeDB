"""Scoped LayerStyle boundary adapters. Image algorithms stay in original modules."""
from comfy_api.latest import io, sdk

from ._dependencies import DependencyRefusal, node_scope, probe_scope
from ._schema import ROWS, schema_for
from .py import color_correct_HSV, color_correct_RGB, drop_shadow
from .py import image_blend, image_blend_advance, image_scale_by_aspect_ratio_v2

ORIGINAL_CLASSES = {
    'LayerColor: HSV': color_correct_HSV.ColorCorrectHSV,
    'LayerColor: RGB': color_correct_RGB.ColorCorrectRGB,
    'LayerStyle: DropShadow': drop_shadow.DropShadow,
    'LayerUtility: ImageBlend': image_blend.ImageBlend,
    'LayerUtility: ImageBlendAdvance': image_blend_advance.ImageBlendAdvance,
    'LayerUtility: ImageScaleByAspectRatio V2': image_scale_by_aspect_ratio_v2.ImageScaleByAspectRatioV2,
}

QUALIFIED = frozenset({
    'LayerUtility: ImageBlendAdvance', 'LayerColor: HSV', 'LayerColor: RGB',
    'LayerStyle: DropShadow', 'LayerUtility: ImageBlend',
    'LayerUtility: ImageScaleByAspectRatio V2',
})
DEPENDENT_BLEND_MODES = frozenset({
    'color_burn', 'color_dodge', 'linear_burn', 'linear_dodge', 'overlay',
    'soft_light', 'hard_light', 'vivid_light', 'pin_light', 'linear_light', 'hard_mix',
})
BLEND_NODES = frozenset({'LayerUtility: ImageBlendAdvance', 'LayerStyle: DropShadow', 'LayerUtility: ImageBlend'})


def refusal(node_id, fields):
    if node_id not in QUALIFIED:
        return f'comfyui_layerstyle/{node_id} is not yet converted to Secure Nodes V2'
    return None


async def compute(node_id, fields):
    error = refusal(node_id, fields)
    if error:
        raise RuntimeError(error)
    row = ROWS[node_id]
    values = {}
    identities = {}
    for name, value in fields.items():
        if isinstance(value, sdk.TensorRef):
            raw = await value.raw()
            values[name] = raw
            identities[id(raw)] = value
        else:
            values[name] = value
    original = ORIGINAL_CLASSES[node_id]()
    token = node_scope.set(node_id)
    try:
        result = getattr(original, row['method'])(**values)
    finally:
        node_scope.reset(token)
    return result, identities


async def run(node_id, fields):
    result, identities = await compute(node_id, fields)
    row = ROWS[node_id]
    outputs = []
    for value, output in zip(result, row['schema']['outputs'], strict=True):
        if value is None:
            outputs.append(None)
        elif id(value) in identities:
            # Original DropShadow's missing-mask identity path keeps the host ref,
            # including dtype and noncontiguous storage layout.
            outputs.append(identities[id(value)])
        elif output['io_type'] == 'IMAGE':
            outputs.append(await sdk.ImageRef.from_value(value))
        elif output['io_type'] == 'MASK':
            latent = await sdk.LatentRef.from_value({'noise_mask': value})
            outputs.append(await latent.noise_mask())
        else:
            outputs.append(value)
    return io.NodeOutput(*outputs)


def make_node(node_id):
    def define_schema(cls):
        return schema_for(node_id)

    async def validate_inputs(cls, **kwargs):
        error = refusal(node_id, kwargs)
        if error:
            return error
        needs_probe = (node_id in BLEND_NODES and kwargs.get('blend_mode') in DEPENDENT_BLEND_MODES
                       or node_id == 'LayerStyle: DropShadow' and kwargs.get('grow', 6) != 0)
        if needs_probe:
            # Reuse the exact pure control flow up to the dependency boundary.
            # This preserves earlier upstream errors and missing-mask identities.
            # No output ref is published and validation emits no pack log.
            token = probe_scope.set(True)
            try:
                await compute(node_id, kwargs)
            except DependencyRefusal as error:
                return str(error)
            except Exception:
                # Original has no custom validator: execution owns its exact error.
                pass
            finally:
                probe_scope.reset(token)
        return True

    async def execute(cls, **kwargs):
        return await run(node_id, kwargs)

    return type(ROWS[node_id]['class'], (io.ComfyNode,), {
        '__module__': __name__, 'SDK_REFS': True,
        'SDK_PERMISSIONS': ('raw',) if node_id in QUALIFIED else (),
        'define_schema': classmethod(define_schema),
        'validate_inputs': classmethod(validate_inputs), 'execute': classmethod(execute),
    })


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
for _node_id, _row in ROWS.items():
    _class = make_node(_node_id)
    assert _class.__name__ not in globals(), _class.__name__
    globals()[_class.__name__] = _class
    NODE_CLASS_MAPPINGS[_node_id] = _class
    NODE_DISPLAY_NAME_MAPPINGS[_node_id] = _row['schema']['attrs']['display_name']
