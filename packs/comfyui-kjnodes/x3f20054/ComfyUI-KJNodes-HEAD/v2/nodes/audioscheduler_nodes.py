from __future__ import annotations
import ast as _audioscheduler_ast
import pathlib as _audioscheduler_pathlib
import sys as _audioscheduler_sys
import types as _audioscheduler_types
from comfy_api.latest import io as _audioscheduler_io, sdk as _audioscheduler_sdk
from . import _packload as _audioscheduler_packload
_audioscheduler_MOD = None

def _audioscheduler_mod():
    global _audioscheduler_MOD
    if _audioscheduler_MOD is None:
        source_path = _audioscheduler_pathlib.Path(
            _audioscheduler_packload.ROOT, 'nodes', 'audioscheduler_nodes.py')
        source = source_path.read_text(encoding='utf-8')
        tree = _audioscheduler_ast.parse(source, filename=str(source_path))
        tree.body = [
            statement
            for statement in tree.body
            if not (
                isinstance(statement, _audioscheduler_ast.ImportFrom)
                and statement.level == 0
                and statement.module == 'nodes'
            )
        ]
        module_name = (
            f'{_audioscheduler_packload.PKG}.nodes.'
            'audioscheduler_nodes_without_host_nodes')
        _audioscheduler_packload._ensure_package(
            _audioscheduler_packload.PKG, _audioscheduler_packload.ROOT)
        _audioscheduler_packload._ensure_package(
            f'{_audioscheduler_packload.PKG}.nodes',
            str(source_path.parent))
        module = _audioscheduler_types.ModuleType(module_name)
        module.__file__ = str(source_path)
        module.__package__ = f'{_audioscheduler_packload.PKG}.nodes'
        module.MAX_RESOLUTION = _audioscheduler_io.MAX_RESOLUTION
        _audioscheduler_sys.modules[module_name] = module
        try:
            exec(compile(tree, str(source_path), 'exec'), module.__dict__)
        except BaseException:
            _audioscheduler_sys.modules.pop(module_name, None)
            raise
        _audioscheduler_MOD = module
    return _audioscheduler_MOD

def _audioscheduler_max_resolution() -> int:
    return _audioscheduler_io.MAX_RESOLUTION
_audioscheduler_NormalizedAmplitude = _audioscheduler_io.Custom('NORMALIZED_AMPLITUDE')
_audioscheduler_BRIDGE = '\nWorks as a bridge to the AudioScheduler -nodes:  \nhttps://github.com/a1lazydog/ComfyUI-AudioScheduler  \n'

class NormalizedAmplitudeToMaskSecure(_audioscheduler_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _audioscheduler_io.Schema:
        return _audioscheduler_io.Schema(node_id='NormalizedAmplitudeToMaskSecure', display_name='🔒 NormalizedAmplitudeToMask (secure)', category='KJNodes/audio', description=_audioscheduler_BRIDGE + 'Creates masks based on the normalized amplitude.\n', inputs=[_audioscheduler_NormalizedAmplitude.Input('normalized_amp'), _audioscheduler_io.Int.Input('width', default=512, min=16, max=4096, step=1), _audioscheduler_io.Int.Input('height', default=512, min=16, max=4096, step=1), _audioscheduler_io.Int.Input('frame_offset', default=0, min=-255, max=255, step=1), _audioscheduler_io.Int.Input('location_x', default=256, min=0, max=4096, step=1), _audioscheduler_io.Int.Input('location_y', default=256, min=0, max=4096, step=1), _audioscheduler_io.Int.Input('size', default=128, min=8, max=4096, step=1), _audioscheduler_io.Combo.Input('shape', options=['none', 'circle', 'square', 'triangle'], default='none'), _audioscheduler_io.Combo.Input('color', options=['white', 'amplitude'], default='amplitude')], outputs=[_audioscheduler_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, normalized_amp, width, height, frame_offset, location_x, location_y, size, shape, color) -> _audioscheduler_io.NodeOutput:
        out = _audioscheduler_mod().NormalizedAmplitudeToMask().convert(normalized_amp, width, height, frame_offset, shape, location_x, location_y, size, color)
        return _audioscheduler_io.NodeOutput(await _audioscheduler_sdk.MaskRef._from_raw(out[0]))

class NormalizedAmplitudeToFloatListSecure(_audioscheduler_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _audioscheduler_io.Schema:
        return _audioscheduler_io.Schema(node_id='NormalizedAmplitudeToFloatListSecure', display_name='🔒 NormalizedAmplitudeToFloatList (secure)', category='KJNodes/audio', description=_audioscheduler_BRIDGE + 'Creates a list of floats from the normalized amplitude.\n', inputs=[_audioscheduler_NormalizedAmplitude.Input('normalized_amp')], outputs=[_audioscheduler_io.Float.Output(display_name='FLOAT')])

    @classmethod
    async def execute(cls, normalized_amp) -> _audioscheduler_io.NodeOutput:
        out = _audioscheduler_mod().NormalizedAmplitudeToFloatList().convert(normalized_amp)
        return _audioscheduler_io.NodeOutput(out[0])

class OffsetMaskByNormalizedAmplitudeSecure(_audioscheduler_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _audioscheduler_io.Schema:
        return _audioscheduler_io.Schema(node_id='OffsetMaskByNormalizedAmplitudeSecure', display_name='🔒 OffsetMaskByNormalizedAmplitude (secure)', category='KJNodes/audio', description=_audioscheduler_BRIDGE + 'Offsets masks based on the normalized amplitude.\n', inputs=[_audioscheduler_NormalizedAmplitude.Input('normalized_amp'), _audioscheduler_io.Mask.Input('mask'), _audioscheduler_io.Int.Input('x', default=0, min=-4096, max=_audioscheduler_max_resolution(), step=1, display_mode=_audioscheduler_io.NumberDisplay.number), _audioscheduler_io.Int.Input('y', default=0, min=-4096, max=_audioscheduler_max_resolution(), step=1, display_mode=_audioscheduler_io.NumberDisplay.number), _audioscheduler_io.Boolean.Input('rotate', default=False), _audioscheduler_io.Float.Input('angle_multiplier', default=0.0, min=-1.0, max=1.0, step=0.001, display_mode=_audioscheduler_io.NumberDisplay.number)], outputs=[_audioscheduler_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, normalized_amp, mask, x, y, rotate, angle_multiplier) -> _audioscheduler_io.NodeOutput:
        pixels = await mask.raw()
        out = _audioscheduler_mod().OffsetMaskByNormalizedAmplitude().offset(pixels, x, y, angle_multiplier, rotate, normalized_amp)
        return _audioscheduler_io.NodeOutput(await _audioscheduler_sdk.MaskRef._from_raw(out[0]))

class ImageTransformByNormalizedAmplitudeSecure(_audioscheduler_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _audioscheduler_io.Schema:
        return _audioscheduler_io.Schema(node_id='ImageTransformByNormalizedAmplitudeSecure', display_name='🔒 ImageTransformByNormalizedAmplitude (secure)', category='KJNodes/audio', description=_audioscheduler_BRIDGE + 'Transforms image based on the normalized amplitude.\n', inputs=[_audioscheduler_NormalizedAmplitude.Input('normalized_amp'), _audioscheduler_io.Float.Input('zoom_scale', default=0.0, min=-1.0, max=1.0, step=0.001, display_mode=_audioscheduler_io.NumberDisplay.number), _audioscheduler_io.Int.Input('x_offset', default=0, min=1 - _audioscheduler_max_resolution(), max=_audioscheduler_max_resolution(), step=1, display_mode=_audioscheduler_io.NumberDisplay.number), _audioscheduler_io.Int.Input('y_offset', default=0, min=1 - _audioscheduler_max_resolution(), max=_audioscheduler_max_resolution(), step=1, display_mode=_audioscheduler_io.NumberDisplay.number), _audioscheduler_io.Boolean.Input('cumulative', default=False), _audioscheduler_io.Image.Input('image')], outputs=[_audioscheduler_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, normalized_amp, zoom_scale, x_offset, y_offset, cumulative, image) -> _audioscheduler_io.NodeOutput:
        pixels = await image.raw()
        out = _audioscheduler_mod().ImageTransformByNormalizedAmplitude().amptransform(pixels, normalized_amp, zoom_scale, cumulative, x_offset, y_offset)
        return _audioscheduler_io.NodeOutput(await _audioscheduler_sdk.ImageRef._from_raw(out[0]))

NODE_CLASS_MAPPINGS = {
    'NormalizedAmplitudeToMaskSecure': NormalizedAmplitudeToMaskSecure,
    'NormalizedAmplitudeToFloatListSecure': NormalizedAmplitudeToFloatListSecure,
    'OffsetMaskByNormalizedAmplitudeSecure': OffsetMaskByNormalizedAmplitudeSecure,
    'ImageTransformByNormalizedAmplitudeSecure': ImageTransformByNormalizedAmplitudeSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'NormalizedAmplitudeToMaskSecure': '🔒 NormalizedAmplitudeToMask (secure)',
    'NormalizedAmplitudeToFloatListSecure': '🔒 NormalizedAmplitudeToFloatList (secure)',
    'OffsetMaskByNormalizedAmplitudeSecure': '🔒 OffsetMaskByNormalizedAmplitude (secure)',
    'ImageTransformByNormalizedAmplitudeSecure': '🔒 ImageTransformByNormalizedAmplitude (secure)',
}
