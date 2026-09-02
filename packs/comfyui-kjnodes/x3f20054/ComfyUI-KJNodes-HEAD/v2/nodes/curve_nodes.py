from __future__ import annotations
import ast as _curve_a_ast
import os as _curve_a_os
import sys as _curve_a_sys
import types as _curve_a_types
from comfy_api.latest import io as _curve_a_io, sdk as _curve_a_sdk
from . import _packload as _curve_a_packload
_curve_a_SOURCE = 'nodes/curve_nodes.py'
_curve_a_REFUSED_AT_MODULE_SCOPE = ('folder_paths',)
_curve_a_MOD = None

def _curve_a_mod():
    global _curve_a_MOD
    if _curve_a_MOD is None:
        try:
            _curve_a_MOD = _curve_a_packload.load(_curve_a_SOURCE)
        except ImportError:
            _curve_a_MOD = _curve_a_without_refused_imports()
    return _curve_a_MOD

def _curve_a_is_refused_import(node) -> bool:
    if isinstance(node, _curve_a_ast.Import):
        return any((a.name in _curve_a_REFUSED_AT_MODULE_SCOPE for a in node.names))
    if isinstance(node, _curve_a_ast.ImportFrom):
        return node.level == 0 and node.module in _curve_a_REFUSED_AT_MODULE_SCOPE
    return False

def _curve_a_without_refused_imports() -> _curve_a_types.ModuleType:
    """Upstream's module, executed minus the imports a guest refuses.

    Only reached after `_packload.load` has already walked the pack far enough
    to fail, so the synthetic ancestor packages exist and upstream's
    `from ..utility.utility import ...` resolves exactly as it did there; the
    leaf's own execution is all that is redone.

    Registered under a name of its own, NOT `…nodes.curve_nodes`: this is a
    partial view of the module, and leaving it in `_packload`'s cache would
    serve it to a caller on a host, where the whole thing is available.
    """
    modname = f'{_curve_a_packload.PKG}.nodes.curve_nodes_without_folder_paths'
    path = _curve_a_os.path.join(_curve_a_packload.ROOT, *_curve_a_SOURCE.split('/'))
    with open(path, encoding='utf-8') as handle:
        source = handle.read()
    tree = _curve_a_ast.parse(source, path)
    tree.body = [n for n in tree.body if not _curve_a_is_refused_import(n)]
    mod = _curve_a_types.ModuleType(modname)
    mod.__file__ = path
    mod.__package__ = f'{_curve_a_packload.PKG}.nodes'
    _curve_a_sys.modules[modname] = mod
    try:
        exec(compile(tree, path, 'exec'), mod.__dict__)
    except BaseException:
        _curve_a_sys.modules.pop(modname, None)
        raise
    return mod

async def _curve_a_materialized(value):
    """A `FLOAT` input as upstream expects to receive it.

    A list or a `None` crosses as itself and arrives unchanged. A tensor
    crosses as a ref, and upstream type-dispatches on what it is handed, so it
    has to be the tensor again by the time upstream sees it.
    """
    return await value.raw() if isinstance(value, _curve_a_sdk.TensorRef) else value

class CreateGradientFromCoordsSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='CreateGradientFromCoordsSecure', display_name='🔒 Create Gradient From Coords (secure)', category='KJNodes/image', description='Creates a gradient image from coordinates.', inputs=[_curve_a_io.String.Input('coordinates', force_input=True), _curve_a_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _curve_a_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1), _curve_a_io.String.Input('start_color', default='white'), _curve_a_io.String.Input('end_color', default='black'), _curve_a_io.Float.Input('multiplier', default=1.0, min=0.01, max=100.0, step=0.01)], outputs=[_curve_a_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, coordinates, frame_width, frame_height, start_color, end_color, multiplier) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().CreateGradientFromCoords().generate(coordinates, frame_width, frame_height, start_color, end_color, multiplier)
        return _curve_a_io.NodeOutput(await _curve_a_sdk.ImageRef._from_raw(out[0]))

class GradientToFloatSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='GradientToFloatSecure', display_name='🔒 Gradient To Float (secure)', category='KJNodes/image', description='Calculates list of floats from image.', inputs=[_curve_a_io.Image.Input('image'), _curve_a_io.Int.Input('steps', default=10, min=2, max=10000, step=1)], outputs=[_curve_a_io.Float.Output(display_name='float_x'), _curve_a_io.Float.Output(display_name='float_y')])

    @classmethod
    async def execute(cls, image, steps) -> _curve_a_io.NodeOutput:
        pixels = await image.raw()
        out = _curve_a_mod().GradientToFloat().sample(pixels, steps)
        return _curve_a_io.NodeOutput(*out)

class MaskOrImageToWeightSecure(_curve_a_io.ComfyNode):
    """Upstream's own `output_type` set, unnarrowed.

    `pandas series` and `tensor` make the FLOAT output a live object rather
    than data, and a live object does not cross the guest wire — it is refused
    by `transport/wire.py` with its type named. That is upstream's shape, not
    something this conversion introduced, and narrowing the combo here would
    hide it while changing the node.
    """
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='MaskOrImageToWeightSecure', display_name='🔒 Mask Or Image To Weight (secure)', category='KJNodes/weights', description='Gets the mean values from mask or image batch and returns that as the selected output type.', inputs=[_curve_a_io.Combo.Input('output_type', options=['list', 'pandas series', 'tensor', 'string'], default='list'), _curve_a_io.Image.Input('images', optional=True), _curve_a_io.Mask.Input('masks', optional=True)], outputs=[_curve_a_io.Float.Output(display_name='FLOAT'), _curve_a_io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, output_type, images=None, masks=None) -> _curve_a_io.NodeOutput:
        pixels = await images.raw() if images is not None else None
        alpha = await masks.raw() if masks is not None else None
        out = _curve_a_mod().MaskOrImageToWeight().execute(output_type, pixels, alpha)
        return _curve_a_io.NodeOutput(*out)

class WeightScheduleConvertSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='WeightScheduleConvertSecure', display_name='🔒 Weight Schedule Convert (secure)', category='KJNodes/weights', description='Converts different value lists/series to another type.', inputs=[_curve_a_io.Float.Input('input_values', default=0.0, force_input=True), _curve_a_io.Combo.Input('output_type', options=['match_input', 'list', 'pandas series', 'tensor'], default='list'), _curve_a_io.Boolean.Input('invert', default=False), _curve_a_io.Int.Input('repeat', default=1, min=1, max=255, step=1), _curve_a_io.Int.Input('remap_to_frames', default=0, optional=True), _curve_a_io.Float.Input('interpolation_curve', force_input=True, optional=True), _curve_a_io.Boolean.Input('remap_values', default=False, optional=True), _curve_a_io.Float.Input('remap_min', default=0.0, min=-100000, max=100000.0, step=0.01, optional=True), _curve_a_io.Float.Input('remap_max', default=1.0, min=-100000, max=100000.0, step=0.01, optional=True)], outputs=[_curve_a_io.Float.Output(display_name='FLOAT'), _curve_a_io.String.Output(display_name='STRING'), _curve_a_io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, input_values, output_type, invert, repeat, remap_to_frames=0, interpolation_curve=None, remap_values=False, remap_min=0.0, remap_max=1.0) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().WeightScheduleConvert().execute(await _curve_a_materialized(input_values), output_type, invert, repeat, remap_to_frames=remap_to_frames, interpolation_curve=await _curve_a_materialized(interpolation_curve), remap_min=remap_min, remap_max=remap_max, remap_values=remap_values)
        return _curve_a_io.NodeOutput(*out)

class FloatToMaskSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='FloatToMaskSecure', display_name='🔒 Float To Mask (secure)', category='KJNodes/masking/generate', description='Generates a batch of masks based on the input float values.\nThe batch size is determined by the length of the input float values.\nEach mask is generated with the specified width and height.', inputs=[_curve_a_io.Float.Input('input_values', default=0, force_input=True), _curve_a_io.Int.Input('width', default=100, min=1), _curve_a_io.Int.Input('height', default=100, min=1)], outputs=[_curve_a_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, input_values, width, height) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().FloatToMask().execute(await _curve_a_materialized(input_values), width, height)
        return _curve_a_io.NodeOutput(await _curve_a_sdk.MaskRef._from_raw(out[0]))

class WeightScheduleExtendSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='WeightScheduleExtendSecure', display_name='🔒 Weight Schedule Extend (secure)', category='KJNodes/weights', description='Extends, and converts if needed, different value lists/series', inputs=[_curve_a_io.Float.Input('input_values_1', default=0.0, force_input=True), _curve_a_io.Float.Input('input_values_2', default=0.0, force_input=True), _curve_a_io.Combo.Input('output_type', options=['match_input', 'list', 'pandas series', 'tensor'], default='match_input')], outputs=[_curve_a_io.Float.Output(display_name='FLOAT')])

    @classmethod
    async def execute(cls, input_values_1, input_values_2, output_type) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().WeightScheduleExtend().execute(await _curve_a_materialized(input_values_1), await _curve_a_materialized(input_values_2), output_type)
        return _curve_a_io.NodeOutput(*out)

class FloatToSigmasSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='FloatToSigmasSecure', display_name='🔒 Float To Sigmas (secure)', category='KJNodes/noise', description='Creates a sigmas tensor from list of float values.', inputs=[_curve_a_io.Float.Input('float_list', default=0.0, force_input=True)], outputs=[_curve_a_io.Sigmas.Output(display_name='SIGMAS')])

    @classmethod
    async def execute(cls, float_list) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().FloatToSigmas().customsigmas(await _curve_a_materialized(float_list))
        return _curve_a_io.NodeOutput(await _curve_a_sdk.TensorRef._from_raw(out[0]))

class SigmasToFloatSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='SigmasToFloatSecure', display_name='🔒 Sigmas To Float (secure)', category='KJNodes/noise', description='Creates a float list from sigmas tensors.', inputs=[_curve_a_io.Sigmas.Input('sigmas')], outputs=[_curve_a_io.Float.Output(display_name='float')])

    @classmethod
    async def execute(cls, sigmas) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().SigmasToFloat().customsigmas(await sigmas.raw())
        return _curve_a_io.NodeOutput(*out)

class InterpolateCoordsSecure(_curve_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _curve_a_io.Schema:
        return _curve_a_io.Schema(node_id='InterpolateCoordsSecure', display_name='🔒 Interpolate Coords (secure)', category='KJNodes/experimental', description='Interpolates coordinates based on a curve.', inputs=[_curve_a_io.String.Input('coordinates', force_input=True), _curve_a_io.Float.Input('interpolation_curve', force_input=True)], outputs=[_curve_a_io.String.Output(display_name='coordinates')])

    @classmethod
    async def execute(cls, coordinates, interpolation_curve) -> _curve_a_io.NodeOutput:
        out = _curve_a_mod().InterpolateCoords().interpolate(coordinates, await _curve_a_materialized(interpolation_curve))
        return _curve_a_io.NodeOutput(*out)
import ast as _curve_b_ast
import os as _curve_b_os
import sys as _curve_b_sys
import types as _curve_b_types
from comfy_api.latest import io as _curve_b_io, sdk as _curve_b_sdk
from . import _packload as _curve_b_packload
_curve_b_Tracking = _curve_b_io.Custom('TRACKING')
_curve_b_REFUSED_AT_MODULE_SCOPE = 'folder_paths'
_curve_b_MOD = None

def _curve_b_ensure_pyplot() -> None:
    """Import `matplotlib.pyplot` so upstream's implicit reference resolves.

    `curve_nodes.py` does `import matplotlib`, then `matplotlib.use("Agg")`,
    then reaches `matplotlib.pyplot.subplots(...)` — WITHOUT ever importing that
    submodule. In the host process it works by accident: something else in a
    ComfyUI startup has already imported pyplot, which binds it as an attribute
    of the package. A guest is a minimal process where nothing has, so the same
    line raises `module 'matplotlib' has no attribute 'pyplot'`.

    An upstream latent bug that only an isolated process exposes. Importing the
    submodule is not faking a host — pyplot is ordinary library code, and this
    supplies exactly what upstream assumed someone else had done.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot

def _curve_b_mod():
    """Upstream's `curve_nodes`, executed with its one refused import elided.

    Registered under a name of its own rather than `…nodes.curve_nodes`, so a
    later `_packload.load("nodes/curve_nodes.py")` — which succeeds on a host,
    where `folder_paths` exists — is not served this partial view from cache.
    """
    global _curve_b_MOD
    if _curve_b_MOD is not None:
        return _curve_b_MOD
    package = f'{_curve_b_packload.PKG}.nodes'
    _curve_b_packload._ensure_package(_curve_b_packload.PKG, _curve_b_packload.ROOT)
    _curve_b_packload._ensure_package(package, _curve_b_os.path.join(_curve_b_packload.ROOT, 'nodes'))
    path = _curve_b_os.path.join(_curve_b_packload.ROOT, 'nodes', 'curve_nodes.py')
    if not _curve_b_os.path.exists(path):
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that imports it must be revisited')
    source = open(path, encoding='utf-8').read()
    tree = _curve_b_ast.parse(source, filename=path)
    kept = [node for node in tree.body if not (isinstance(node, _curve_b_ast.Import) and [alias.name for alias in node.names] == [_curve_b_REFUSED_AT_MODULE_SCOPE])]
    if len(kept) == len(tree.body):
        raise RuntimeError(f'nothing imports {_curve_b_REFUSED_AT_MODULE_SCOPE} at the top of {path} any more; this loader exists only to elide that import, so upstream changed shape and it must be revisited')
    tree.body = kept
    name = f'{package}.curve_nodes_without_{_curve_b_REFUSED_AT_MODULE_SCOPE}'
    module = _curve_b_types.ModuleType(name)
    module.__file__ = path
    module.__package__ = package
    _curve_b_sys.modules[name] = module
    try:
        exec(compile(tree, path, 'exec'), module.__dict__)
    except BaseException:
        _curve_b_sys.modules.pop(name, None)
        raise
    _curve_b_MOD = module
    return module

def _curve_b_given(**kwargs):
    """Only the arguments actually supplied, so upstream's defaults stand.

    An unconnected optional input never reaches `execute`, and forwarding
    `None` in its place would override a default this file must not restate.
    """
    return {name: value for name, value in kwargs.items() if value is not None}

def _curve_b_split_ui(returned):
    """Upstream returns a plain tuple, or `{"ui": …, "result": …}` with a
    background image to echo back to the canvas."""
    if isinstance(returned, dict):
        return (returned['result'], returned.get('ui'))
    return (returned, None)

class PlotCoordinatesSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='PlotCoordinatesSecure', display_name='🔒 Plot Coordinates (secure)', category='KJNodes/experimental', description='Plots coordinates to sequence of images using Matplotlib.', inputs=[_curve_b_io.String.Input('coordinates', force_input=True), _curve_b_io.String.Input('text', default='title'), _curve_b_io.Int.Input('width', default=512, min=8, max=4096, step=8), _curve_b_io.Int.Input('height', default=512, min=8, max=4096, step=8), _curve_b_io.Int.Input('bbox_width', default=128, min=8, max=4096, step=8), _curve_b_io.Int.Input('bbox_height', default=128, min=8, max=4096, step=8), _curve_b_io.Float.Input('size_multiplier', default=[1.0], force_input=True, optional=True)], outputs=[_curve_b_io.Image.Output(display_name='images'), _curve_b_io.Int.Output(display_name='width'), _curve_b_io.Int.Output(display_name='height'), _curve_b_io.Int.Output(display_name='bbox_width'), _curve_b_io.Int.Output(display_name='bbox_height')])

    @classmethod
    async def execute(cls, coordinates, text, width, height, bbox_width, bbox_height, size_multiplier=None) -> _curve_b_io.NodeOutput:
        _curve_b_ensure_pyplot()
        out = _curve_b_mod().PlotCoordinates().append(coordinates, text, width, height, bbox_width, bbox_height, **_curve_b_given(size_multiplier=size_multiplier))
        return _curve_b_io.NodeOutput(await _curve_b_sdk.ImageRef._from_raw(out[0]), *out[1:])

class SplineEditorSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='SplineEditorSecure', display_name='🔒 Spline Editor (secure)', category='KJNodes/weights', description='Samples a drawn spline into a mask batch, a coordinate string and a list of floats. Work in progress upstream; the canvas editor belongs to the original node, so drive this one through its coordinates input.', is_experimental=True, inputs=[_curve_b_io.String.Input('points_store', advanced=True), _curve_b_io.String.Input('coordinates', advanced=True), _curve_b_io.Int.Input('mask_width', default=512, min=8, max=4096, step=8), _curve_b_io.Int.Input('mask_height', default=512, min=8, max=4096, step=8), _curve_b_io.Int.Input('points_to_sample', default=16, min=2, max=1000, step=1), _curve_b_io.Combo.Input('sampling_method', options=['path', 'time', 'controlpoints', 'speed'], default='time'), _curve_b_io.Combo.Input('interpolation', options=['cardinal', 'monotone', 'basis', 'linear', 'step-before', 'step-after', 'polar', 'polar-reverse', 'bezier'], default='cardinal'), _curve_b_io.Float.Input('tension', default=0.5, min=0.0, max=1.0, step=0.01), _curve_b_io.Int.Input('repeat_output', default=1, min=1, max=4096, step=1), _curve_b_io.Combo.Input('float_output_type', options=['list', 'pandas series', 'tensor'], default='list'), _curve_b_io.Float.Input('min_value', default=0.0, min=-10000.0, max=10000.0, step=0.01, optional=True), _curve_b_io.Float.Input('max_value', default=1.0, min=-10000.0, max=10000.0, step=0.01, optional=True), _curve_b_io.Image.Input('bg_image', optional=True)], outputs=[_curve_b_io.Mask.Output(display_name='mask'), _curve_b_io.String.Output(display_name='coord_str'), _curve_b_io.Float.Output(display_name='float'), _curve_b_io.Int.Output(display_name='count'), _curve_b_io.String.Output(display_name='normalized_str')])

    @classmethod
    async def execute(cls, points_store, coordinates, mask_width, mask_height, points_to_sample, sampling_method, interpolation, tension, repeat_output, float_output_type, min_value=None, max_value=None, bg_image=None) -> _curve_b_io.NodeOutput:
        background = await bg_image.raw() if bg_image is not None else None
        returned = _curve_b_mod().SplineEditor().splinedata(mask_width, mask_height, coordinates, float_output_type, interpolation, points_to_sample, sampling_method, points_store, tension, repeat_output, **_curve_b_given(min_value=min_value, max_value=max_value, bg_image=background))
        out, ui = _curve_b_split_ui(returned)
        return _curve_b_io.NodeOutput(await _curve_b_sdk.MaskRef._from_raw(out[0]), *out[1:], ui=ui)

class CreateShapeMaskOnPathSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='CreateShapeMaskOnPathSecure', display_name='🔒 Create Shape Mask On Path (secure)', category='KJNodes/masking/generate', description='Creates a mask or batch of masks with the specified shape. Locations are center locations.', is_deprecated=True, inputs=[_curve_b_io.Combo.Input('shape', options=['circle', 'square', 'triangle'], default='circle'), _curve_b_io.String.Input('coordinates', force_input=True), _curve_b_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('shape_width', default=128, min=8, max=4096, step=1), _curve_b_io.Int.Input('shape_height', default=128, min=8, max=4096, step=1), _curve_b_io.Float.Input('size_multiplier', default=[1.0], force_input=True, optional=True)], outputs=[_curve_b_io.Mask.Output(display_name='mask'), _curve_b_io.Mask.Output(display_name='mask_inverted')])

    @classmethod
    async def execute(cls, shape, coordinates, frame_width, frame_height, shape_width, shape_height, size_multiplier=None) -> _curve_b_io.NodeOutput:
        out = _curve_b_mod().CreateShapeMaskOnPath().createshapemask(coordinates, frame_width, frame_height, shape_width, shape_height, shape, **_curve_b_given(size_multiplier=size_multiplier))
        return _curve_b_io.NodeOutput(await _curve_b_sdk.MaskRef._from_raw(out[0]), await _curve_b_sdk.MaskRef._from_raw(out[1]))

class CreateShapeImageOnPathSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='CreateShapeImageOnPathSecure', display_name='🔒 Create Shape Image On Path (secure)', category='KJNodes/image', description='Creates an image or batch of images with the specified shape. Locations are center locations.', inputs=[_curve_b_io.Combo.Input('shape', options=['circle', 'square', 'triangle'], default='circle'), _curve_b_io.String.Input('coordinates', force_input=True), _curve_b_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('shape_width', default=128, min=2, max=4096, step=1), _curve_b_io.Int.Input('shape_height', default=128, min=2, max=4096, step=1), _curve_b_io.String.Input('shape_color', default='white'), _curve_b_io.String.Input('bg_color', default='black'), _curve_b_io.Float.Input('blur_radius', default=0.0, min=0.0, max=100, step=0.1), _curve_b_io.Float.Input('intensity', default=1.0, min=0.01, max=100.0, step=0.01), _curve_b_io.Float.Input('size_multiplier', default=[1.0], force_input=True, optional=True), _curve_b_io.Float.Input('trailing', default=1.0, min=0.0, max=10.0, step=0.01, optional=True), _curve_b_io.Int.Input('border_width', default=0, min=0, max=100, step=1, optional=True), _curve_b_io.String.Input('border_color', default='black', optional=True)], outputs=[_curve_b_io.Image.Output(display_name='image'), _curve_b_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, shape, coordinates, frame_width, frame_height, shape_width, shape_height, shape_color, bg_color, blur_radius, intensity, size_multiplier=None, trailing=None, border_width=None, border_color=None) -> _curve_b_io.NodeOutput:
        out = _curve_b_mod().CreateShapeImageOnPath().createshapemask(coordinates, frame_width, frame_height, shape_width, shape_height, shape_color, bg_color, blur_radius, shape, intensity, **_curve_b_given(size_multiplier=size_multiplier, trailing=trailing, border_width=border_width, border_color=border_color))
        return _curve_b_io.NodeOutput(await _curve_b_sdk.ImageRef._from_raw(out[0]), await _curve_b_sdk.MaskRef._from_raw(out[1]))

class CreateInstanceDiffusionTrackingSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='CreateInstanceDiffusionTrackingSecure', display_name='🔒 Create InstanceDiffusion Tracking (secure)', category='KJNodes/InstanceDiffusion', description='Creates tracking data to be used with InstanceDiffusion: https://github.com/logtd/ComfyUI-InstanceDiffusion\nInstanceDiffusion prompt format: "class_id.class_name": "prompt", for example: "1.head": "((head))"', inputs=[_curve_b_io.String.Input('coordinates', force_input=True), _curve_b_io.Int.Input('width', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('height', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('bbox_width', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('bbox_height', default=512, min=16, max=4096, step=1), _curve_b_io.String.Input('class_name', default='class_name'), _curve_b_io.Int.Input('class_id', default=0, min=0, max=255, step=1), _curve_b_io.String.Input('prompt', default='prompt', multiline=True), _curve_b_io.Float.Input('size_multiplier', default=[1.0], force_input=True, optional=True), _curve_b_io.Boolean.Input('fit_in_frame', default=True, optional=True)], outputs=[_curve_b_Tracking.Output(display_name='tracking'), _curve_b_io.String.Output(display_name='prompt'), _curve_b_io.Int.Output(display_name='width'), _curve_b_io.Int.Output(display_name='height'), _curve_b_io.Int.Output(display_name='bbox_width'), _curve_b_io.Int.Output(display_name='bbox_height')])

    @classmethod
    async def execute(cls, coordinates, width, height, bbox_width, bbox_height, class_name, class_id, prompt, size_multiplier=None, fit_in_frame=None) -> _curve_b_io.NodeOutput:
        out = _curve_b_mod().CreateInstanceDiffusionTracking().tracking(coordinates, class_name, class_id, width, height, bbox_width, bbox_height, prompt, **_curve_b_given(size_multiplier=size_multiplier, fit_in_frame=fit_in_frame))
        return _curve_b_io.NodeOutput(*out)

class AppendInstanceDiffusionTrackingSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='AppendInstanceDiffusionTrackingSecure', display_name='🔒 Append InstanceDiffusion Tracking (secure)', category='KJNodes/InstanceDiffusion', description='Appends tracking data to be used with InstanceDiffusion: https://github.com/logtd/ComfyUI-InstanceDiffusion', inputs=[_curve_b_Tracking.Input('tracking_1', extra_dict={'forceInput': True}), _curve_b_Tracking.Input('tracking_2', extra_dict={'forceInput': True}), _curve_b_io.String.Input('prompt_1', default='', force_input=True, optional=True), _curve_b_io.String.Input('prompt_2', default='', force_input=True, optional=True)], outputs=[_curve_b_Tracking.Output(display_name='tracking'), _curve_b_io.String.Output(display_name='prompt')])

    @classmethod
    async def execute(cls, tracking_1, tracking_2, prompt_1=None, prompt_2=None) -> _curve_b_io.NodeOutput:
        out = _curve_b_mod().AppendInstanceDiffusionTracking().append(tracking_1, tracking_2, **_curve_b_given(prompt_1=prompt_1, prompt_2=prompt_2))
        return _curve_b_io.NodeOutput(*out)

class PointsEditorSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='PointsEditorSecure', display_name='🔒 Points Editor (secure)', category='KJNodes/experimental', description='Turns drawn points and bounding boxes into coordinate strings, a bbox, a bbox mask and a crop of the background image. Work in progress upstream; the canvas editor belongs to the original node, so drive this one through its coordinates and bboxes inputs.', is_experimental=True, inputs=[_curve_b_io.String.Input('points_store', advanced=True), _curve_b_io.String.Input('coordinates', socketless=True, advanced=True), _curve_b_io.String.Input('neg_coordinates', socketless=True, advanced=True), _curve_b_io.String.Input('bbox_store', advanced=True), _curve_b_io.String.Input('bboxes', socketless=True, advanced=True), _curve_b_io.Combo.Input('bbox_format', options=['xyxy', 'xywh']), _curve_b_io.Int.Input('width', default=512, min=8, max=4096, step=8), _curve_b_io.Int.Input('height', default=512, min=8, max=4096, step=8), _curve_b_io.Boolean.Input('normalize', default=False), _curve_b_io.Image.Input('bg_image', optional=True)], outputs=[_curve_b_io.String.Output(display_name='positive_coords'), _curve_b_io.String.Output(display_name='negative_coords'), _curve_b_io.BBOX.Output(display_name='bbox'), _curve_b_io.Mask.Output(display_name='bbox_mask'), _curve_b_io.Image.Output(display_name='cropped_image')])

    @classmethod
    async def execute(cls, points_store, coordinates, neg_coordinates, bbox_store, bboxes, bbox_format, width, height, normalize, bg_image=None) -> _curve_b_io.NodeOutput:
        background = await bg_image.raw() if bg_image is not None else None
        returned = _curve_b_mod().PointsEditor().pointdata(points_store, bbox_store, width, height, coordinates, neg_coordinates, normalize, bboxes, **_curve_b_given(bbox_format=bbox_format, bg_image=background))
        out, ui = _curve_b_split_ui(returned)
        return _curve_b_io.NodeOutput(out[0], out[1], out[2], await _curve_b_sdk.MaskRef._from_raw(out[3]), await _curve_b_sdk.ImageRef._from_raw(out[4]), ui=ui)

class CutAndDragOnPathSecure(_curve_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _curve_b_io.Schema:
        return _curve_b_io.Schema(node_id='CutAndDragOnPathSecure', display_name='🔒 Cut And Drag On Path (secure)', category='KJNodes/image', description='Cuts the masked area from the image, and drags it along the path. If inpaint is enabled, and no bg_image is provided, the cut area is filled using cv2 TELEA algorithm.', inputs=[_curve_b_io.Image.Input('image'), _curve_b_io.String.Input('coordinates', force_input=True), _curve_b_io.Mask.Input('mask'), _curve_b_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _curve_b_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1), _curve_b_io.Boolean.Input('inpaint', default=True), _curve_b_io.Image.Input('bg_image', optional=True)], outputs=[_curve_b_io.Image.Output(display_name='image'), _curve_b_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, image, coordinates, mask, frame_width, frame_height, inpaint, bg_image=None) -> _curve_b_io.NodeOutput:
        pixels = await image.raw()
        matte = await mask.raw()
        background = await bg_image.raw() if bg_image is not None else None
        out = _curve_b_mod().CutAndDragOnPath().cutanddrag(pixels, coordinates, matte, frame_width, frame_height, inpaint, **_curve_b_given(bg_image=background))
        return _curve_b_io.NodeOutput(await _curve_b_sdk.ImageRef._from_raw(out[0]), await _curve_b_sdk.MaskRef._from_raw(out[1]))
import ast as _remaining_b_ast
import copy as _remaining_b_copy
import pathlib as _remaining_b_pathlib
from comfy_api.latest import io as _remaining_b_io, sdk as _remaining_b_sdk
from . import _packload as _remaining_b_packload
_remaining_b_MASK_SOURCE = 'nodes/mask_nodes.py'
_remaining_b_CURVE_SOURCE = 'nodes/curve_nodes.py'
_remaining_b_FONTS = ['FreeMono.ttf', 'FreeMonoBoldOblique.otf', 'TTNorms-Black.otf']
_remaining_b_CODE = {}
_remaining_b_Tracking = _remaining_b_io.Custom('TRACKING')

class _remaining_b_FontPathToContent(_remaining_b_ast.NodeTransformer):

    def __init__(self) -> None:
        self.replacements = 0

    def visit_Call(self, node):
        node = self.generic_visit(node)
        func = node.func
        if not (isinstance(func, _remaining_b_ast.Attribute) and func.attr == 'get_full_path' and isinstance(func.value, _remaining_b_ast.Name) and (func.value.id == 'folder_paths') and (len(node.args) >= 2) and isinstance(node.args[0], _remaining_b_ast.Constant) and (node.args[0].value == 'kjnodes_fonts')):
            return node
        self.replacements += 1
        return _remaining_b_ast.copy_location(_remaining_b_ast.Name(id='font', ctx=_remaining_b_ast.Load()), node)

class _remaining_b_CmapCompatibility(_remaining_b_ast.NodeTransformer):

    def __init__(self) -> None:
        self.replacements = 0

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if not (isinstance(node.func, _remaining_b_ast.Attribute) and node.func.attr == 'get_cmap' and isinstance(node.func.value, _remaining_b_ast.Name) and (node.func.value.id == 'cm')):
            return node
        self.replacements += 1
        return _remaining_b_ast.copy_location(_remaining_b_ast.Call(func=_remaining_b_ast.Name(id='_get_cmap', ctx=_remaining_b_ast.Load()), args=node.args, keywords=node.keywords), node)

def _remaining_b_compiled(relpath: str, class_name: str, method_name: str, *, helpers=(), font_content=False, cmap_compatibility=False):
    key = (relpath, class_name, method_name, tuple(helpers), font_content, cmap_compatibility)
    cached = _remaining_b_CODE.get(key)
    if cached is not None:
        return cached
    path = _remaining_b_pathlib.Path(_remaining_b_packload.ROOT, *relpath.split('/'))
    text = path.read_text(encoding='utf-8')
    tree = _remaining_b_ast.parse(text, filename=str(path))
    body = []
    for node in tree.body:
        if isinstance(node, (_remaining_b_ast.FunctionDef, _remaining_b_ast.AsyncFunctionDef)) and node.name in helpers:
            body.append(_remaining_b_copy.deepcopy(node))
        if not isinstance(node, _remaining_b_ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (_remaining_b_ast.FunctionDef, _remaining_b_ast.AsyncFunctionDef)) and item.name == method_name:
                method = _remaining_b_copy.deepcopy(item)
                method.decorator_list = []
                body.append(method)
    if not any((getattr(node, 'name', None) == method_name for node in body)):
        raise RuntimeError(f'{class_name}.{method_name} not found in upstream {path}')
    if font_content:
        transform = _remaining_b_FontPathToContent()
        body = [transform.visit(node) for node in body]
        if transform.replacements != 1:
            raise RuntimeError(f'expected one kjnodes_fonts lookup in {class_name}.{method_name}, found {transform.replacements}')
    if cmap_compatibility:
        transform = _remaining_b_CmapCompatibility()
        body = [transform.visit(node) for node in body]
        if transform.replacements != 1:
            raise RuntimeError(f'expected one cm.get_cmap call in {class_name}.{method_name}, found {transform.replacements}')
    module = _remaining_b_ast.fix_missing_locations(_remaining_b_ast.Module(body=body, type_ignores=[]))
    code = compile(module, f'<kjnodes.{class_name}.{method_name}>', 'exec')
    _remaining_b_CODE[key] = code
    return code

def _remaining_b_namespace() -> dict:
    import json
    from io import BytesIO
    import numpy as np
    import torch
    import matplotlib
    from PIL import Image, ImageDraw, ImageFilter
    from PIL import ImageFont as PillowImageFont
    from torchvision import transforms
    utility = _remaining_b_packload.load('utility/utility.py')

    def _get_cmap(name, count):
        return matplotlib.colormaps.get_cmap(name).resampled(count)

    class ImageFont:

        @staticmethod
        def truetype(content, size, *args, **kwargs):
            if isinstance(content, (bytes, bytearray)):
                content = BytesIO(content)
            return PillowImageFont.truetype(content, size, *args, **kwargs)
    return {'Image': Image, 'ImageDraw': ImageDraw, 'ImageFilter': ImageFilter, 'ImageFont': ImageFont, '_get_cmap': _get_cmap, 'json': json, 'np': np, 'pil2tensor': utility.pil2tensor, 'torch': torch, 'transforms': transforms}

def _remaining_b_upstream(relpath: str, class_name: str, method_name: str, *, helpers=(), cmap_compatibility=False):
    namespace = _remaining_b_namespace()
    exec(_remaining_b_compiled(relpath, class_name, method_name, helpers=helpers, font_content=True, cmap_compatibility=cmap_compatibility), namespace)
    return namespace[method_name]

async def _remaining_b_font_content(name: str) -> bytes:
    assets = _remaining_b_sdk.current_context().assets
    ref = await assets.resolve('kjnodes_fonts', name)
    return await assets.read_bytes(ref)

async def _remaining_b_value(value):
    if isinstance(value, (_remaining_b_sdk.AudioRef, _remaining_b_sdk.CondRef, _remaining_b_sdk.LatentRef, _remaining_b_sdk.VideoRef)):
        return await value.value()
    return value

class CreateTextOnPathSecure(_remaining_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls) -> _remaining_b_io.Schema:
        return _remaining_b_io.Schema(node_id='CreateTextOnPathSecure', display_name='🔒 Create Text On Path (secure)', category='KJNodes/masking/generate', description='Creates image and mask batches with text centered on supplied coordinates.', inputs=[_remaining_b_io.String.Input('coordinates', force_input=True), _remaining_b_io.String.Input('text', default='text', multiline=True), _remaining_b_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _remaining_b_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1), _remaining_b_io.Combo.Input('font', options=_remaining_b_FONTS, default=_remaining_b_FONTS[0]), _remaining_b_io.Int.Input('font_size', default=42), _remaining_b_io.Combo.Input('alignment', options=['left', 'center', 'right'], default='center'), _remaining_b_io.String.Input('text_color', default='white'), _remaining_b_io.Float.Input('size_multiplier', default=[1.0], force_input=True, optional=True)], outputs=[_remaining_b_io.Image.Output(display_name='image'), _remaining_b_io.Mask.Output(display_name='mask'), _remaining_b_io.Mask.Output(display_name='mask_inverted')])

    @classmethod
    async def execute(cls, coordinates, text, frame_width, frame_height, font, font_size, alignment, text_color, size_multiplier=None) -> _remaining_b_io.NodeOutput:
        render = _remaining_b_upstream(_remaining_b_CURVE_SOURCE, 'CreateTextOnPath', 'createtextmask', helpers=('parse_color',))
        args = [None, coordinates, frame_width, frame_height, await _remaining_b_font_content(font), font_size, text, text_color, alignment]
        out = render(*args) if size_multiplier is None else render(*args, size_multiplier=size_multiplier)
        return _remaining_b_io.NodeOutput(await _remaining_b_sdk.ImageRef._from_raw(out[0]), await _remaining_b_sdk.MaskRef._from_raw(out[1]), await _remaining_b_sdk.MaskRef._from_raw(out[2]))

class DrawInstanceDiffusionTrackingSecure(_remaining_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls) -> _remaining_b_io.Schema:
        return _remaining_b_io.Schema(node_id='DrawInstanceDiffusionTrackingSecure', display_name='🔒 Draw InstanceDiffusion Tracking (secure)', category='KJNodes/InstanceDiffusion', description='Draws InstanceDiffusion tracking boxes and labels over an image batch.', inputs=[_remaining_b_io.Image.Input('image'), _remaining_b_Tracking.Input('tracking', extra_dict={'forceInput': True}), _remaining_b_io.Int.Input('box_line_width', default=2, min=1, max=10, step=1), _remaining_b_io.Boolean.Input('draw_text', default=True), _remaining_b_io.Combo.Input('font', options=_remaining_b_FONTS, default=_remaining_b_FONTS[0]), _remaining_b_io.Int.Input('font_size', default=20)], outputs=[_remaining_b_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, image, tracking, box_line_width, draw_text, font, font_size) -> _remaining_b_io.NodeOutput:
        draw = _remaining_b_upstream(_remaining_b_CURVE_SOURCE, 'DrawInstanceDiffusionTracking', 'draw', cmap_compatibility=True)
        font_content = await _remaining_b_font_content(font) if draw_text else b''
        out = draw(None, await image.raw(), await _remaining_b_value(tracking), box_line_width, draw_text, font_content, font_size)
        return _remaining_b_io.NodeOutput(await _remaining_b_sdk.ImageRef._from_raw(out[0]))
import ast as _remaining_s_ast
import json as _remaining_s_json
import pathlib as _remaining_s_pathlib
import numpy as _remaining_s_np
import torch as _remaining_s_torch
from comfy_api.latest import io as _remaining_s_io, sdk as _remaining_s_sdk
from . import _packload as _remaining_s_packload
_remaining_s_PLOT = None

def _remaining_s_plot_function():
    global _remaining_s_PLOT
    if _remaining_s_PLOT is not None:
        return _remaining_s_PLOT
    source_path = _remaining_s_pathlib.Path(_remaining_s_packload.ROOT) / 'nodes' / 'curve_nodes.py'
    with source_path.open(encoding='utf-8') as source_file:
        tree = _remaining_s_ast.parse(source_file.read(), filename=str(source_path))
    function = next((item for item in tree.body if isinstance(item, _remaining_s_ast.FunctionDef) and item.name == 'plot_coordinates_to_tensor'))
    namespace = {'np': _remaining_s_np, 'torch': _remaining_s_torch}
    exec(compile(_remaining_s_ast.Module(body=[function], type_ignores=[]), '<KJNodes.plot_coordinates_to_tensor>', 'exec'), namespace)
    _remaining_s_PLOT = namespace['plot_coordinates_to_tensor']
    return _remaining_s_PLOT

def _remaining_s_plot(coordinates, height, width, bbox_height, bbox_width, size_multiplier, text):
    import matplotlib.pyplot
    return _remaining_s_plot_function()(coordinates, height, width, bbox_height, bbox_width, size_multiplier, text)

class GLIGENTextBoxApplyBatchCoordsSecure(_remaining_s_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_s_io.Schema:
        return _remaining_s_io.Schema(node_id='GLIGENTextBoxApplyBatchCoordsSecure', display_name='🔒 GLIGEN Text Box Apply Batch Coords (secure)', category='KJNodes/experimental', description='Schedules GLIGEN text-box positions across a latent batch.', inputs=[_remaining_s_io.Conditioning.Input('conditioning_to'), _remaining_s_io.Latent.Input('latents'), _remaining_s_io.Clip.Input('clip'), _remaining_s_io.Gligen.Input('gligen_textbox_model'), _remaining_s_io.String.Input('coordinates', force_input=True), _remaining_s_io.String.Input('text', multiline=True), _remaining_s_io.Int.Input('width', default=128, min=8, max=4096, step=8), _remaining_s_io.Int.Input('height', default=128, min=8, max=4096, step=8), _remaining_s_io.Float.Input('size_multiplier', default=[1.0], force_input=True, optional=True)], outputs=[_remaining_s_io.Conditioning.Output('conditioning', display_name='conditioning'), _remaining_s_io.Image.Output('coord_preview', display_name='coord_preview')])

    @classmethod
    async def execute(cls, conditioning_to, latents, clip, gligen_textbox_model, coordinates, text, width, height, size_multiplier=None) -> _remaining_s_io.NodeOutput:
        coordinate_data = _remaining_s_json.loads(coordinates.replace("'", '"'))
        points = [(coord['x'], coord['y']) for coord in coordinate_data]
        latent_value = await latents.value()
        batch_size = sum((tensor.size(0) for tensor in latent_value.values()))
        if len(points) != batch_size:
            print('GLIGENTextBoxApplyBatchCoords WARNING: The number of coordinates does not match the number of latents')
        multipliers = [1.0] if size_multiplier is None else size_multiplier
        if len(multipliers) != batch_size:
            multipliers = multipliers * (batch_size // len(multipliers)) + multipliers[:batch_size % len(multipliers)]
        boxes = []
        for index in range(batch_size):
            x, y = points[index]
            boxes.append((int(height // 8 * multipliers[index]), int(width // 8 * multipliers[index]), (y - height // 2) // 8, (x - width // 2) // 8))
        conditioning = await gligen_textbox_model.apply_batched(conditioning_to, clip, text, boxes)
        image_height = latent_value['samples'].shape[-2] * 8
        image_width = latent_value['samples'].shape[-1] * 8
        preview = _remaining_s_plot(points, image_height, image_width, height, width, multipliers, text)
        return _remaining_s_io.NodeOutput(conditioning, await _remaining_s_sdk.ImageRef._from_raw(preview))

NODE_CLASS_MAPPINGS = {
    'CreateGradientFromCoordsSecure': CreateGradientFromCoordsSecure,
    'FloatToMaskSecure': FloatToMaskSecure,
    'FloatToSigmasSecure': FloatToSigmasSecure,
    'GradientToFloatSecure': GradientToFloatSecure,
    'InterpolateCoordsSecure': InterpolateCoordsSecure,
    'MaskOrImageToWeightSecure': MaskOrImageToWeightSecure,
    'SigmasToFloatSecure': SigmasToFloatSecure,
    'WeightScheduleConvertSecure': WeightScheduleConvertSecure,
    'WeightScheduleExtendSecure': WeightScheduleExtendSecure,
    'PlotCoordinatesSecure': PlotCoordinatesSecure,
    'SplineEditorSecure': SplineEditorSecure,
    'CreateShapeMaskOnPathSecure': CreateShapeMaskOnPathSecure,
    'CreateShapeImageOnPathSecure': CreateShapeImageOnPathSecure,
    'CreateInstanceDiffusionTrackingSecure': CreateInstanceDiffusionTrackingSecure,
    'AppendInstanceDiffusionTrackingSecure': AppendInstanceDiffusionTrackingSecure,
    'PointsEditorSecure': PointsEditorSecure,
    'CutAndDragOnPathSecure': CutAndDragOnPathSecure,
    'CreateTextOnPathSecure': CreateTextOnPathSecure,
    'DrawInstanceDiffusionTrackingSecure': DrawInstanceDiffusionTrackingSecure,
    'GLIGENTextBoxApplyBatchCoordsSecure': GLIGENTextBoxApplyBatchCoordsSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'CreateGradientFromCoordsSecure': '🔒 Create Gradient From Coords (secure)',
    'FloatToMaskSecure': '🔒 Float To Mask (secure)',
    'FloatToSigmasSecure': '🔒 Float To Sigmas (secure)',
    'GradientToFloatSecure': '🔒 Gradient To Float (secure)',
    'InterpolateCoordsSecure': '🔒 Interpolate Coords (secure)',
    'MaskOrImageToWeightSecure': '🔒 Mask Or Image To Weight (secure)',
    'SigmasToFloatSecure': '🔒 Sigmas To Float (secure)',
    'WeightScheduleConvertSecure': '🔒 Weight Schedule Convert (secure)',
    'WeightScheduleExtendSecure': '🔒 Weight Schedule Extend (secure)',
    'PlotCoordinatesSecure': '🔒 Plot Coordinates (secure)',
    'SplineEditorSecure': '🔒 Spline Editor (secure)',
    'CreateShapeMaskOnPathSecure': '🔒 Create Shape Mask On Path (secure)',
    'CreateShapeImageOnPathSecure': '🔒 Create Shape Image On Path (secure)',
    'CreateInstanceDiffusionTrackingSecure': '🔒 Create InstanceDiffusion Tracking (secure)',
    'AppendInstanceDiffusionTrackingSecure': '🔒 Append InstanceDiffusion Tracking (secure)',
    'PointsEditorSecure': '🔒 Points Editor (secure)',
    'CutAndDragOnPathSecure': '🔒 Cut And Drag On Path (secure)',
    'CreateTextOnPathSecure': '🔒 Create Text On Path (secure)',
    'DrawInstanceDiffusionTrackingSecure': '🔒 Draw InstanceDiffusion Tracking (secure)',
    'GLIGENTextBoxApplyBatchCoordsSecure': '🔒 GLIGEN Text Box Apply Batch Coords (secure)',
}
