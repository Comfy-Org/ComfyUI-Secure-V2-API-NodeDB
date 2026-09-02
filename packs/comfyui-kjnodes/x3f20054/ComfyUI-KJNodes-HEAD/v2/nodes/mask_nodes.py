from __future__ import annotations
import ast as _image_d_ast
import pathlib as _image_d_pathlib
from comfy_api.latest import io as _image_d_io, sdk as _image_d_sdk
from . import _packload as _image_d_packload
_image_d_MAX_RESOLUTION = 16384
_image_d_IMAGE_NODES = 'nodes/image_nodes.py'
_image_d_MASK_NODES = 'nodes/mask_nodes.py'
_image_d_METHODS: dict[tuple[str, str, str], object] = {}
_image_d_NAMESPACE = None

def _image_d_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`. `common_upscale`
    is pure tensor math reached through the guest's `comfy.utils` facade — the
    guest-lib capability, which already exists — and not the real module.
    """
    global _image_d_NAMESPACE
    if _image_d_NAMESPACE is None:
        import torch
        from ._tensor_utils import common_upscale
        _image_d_NAMESPACE = {'torch': torch, 'common_upscale': common_upscale}
    return _image_d_NAMESPACE

def _image_d_upstream(source: str, class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 5000-line module per dispatch would re-pay that cost every
    time. The methods are plain instance methods extracted undecorated, so the
    caller supplies `self` as an ordinary first argument; none of the nine uses
    it.
    """
    key = (source, class_name, method)
    cached = _image_d_METHODS.get(key)
    if cached is not None:
        return cached
    path = _image_d_pathlib.Path(_image_d_packload.ROOT, *source.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _image_d_ast.walk(_image_d_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _image_d_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _image_d_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_image_d_namespace())
            exec(compile(_image_d_ast.Module(body=[_image_d_ast.parse(_image_d_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _image_d_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {source} — the pack changed shape and this conversion must be revisited')

class ResizeMaskSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='ResizeMaskSecure', display_name='🔒 Resize Mask (secure)', category='KJNodes/masking', description='Resizes the mask or batch of masks to the specified width and height.', inputs=[_image_d_io.Mask.Input('mask'), _image_d_io.Int.Input('width', default=512, min=0, max=_image_d_MAX_RESOLUTION, step=1, display_mode=_image_d_io.NumberDisplay.number), _image_d_io.Int.Input('height', default=512, min=0, max=_image_d_MAX_RESOLUTION, step=1, display_mode=_image_d_io.NumberDisplay.number), _image_d_io.Boolean.Input('keep_proportions', default=False), _image_d_io.Combo.Input('upscale_method', options=['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'], default='nearest-exact'), _image_d_io.Combo.Input('crop', options=['disabled', 'center'], default='disabled')], outputs=[_image_d_io.Mask.Output(display_name='mask'), _image_d_io.Int.Output(display_name='width'), _image_d_io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, mask, width, height, keep_proportions, upscale_method, crop) -> _image_d_io.NodeOutput:
        resize = _image_d_upstream(_image_d_MASK_NODES, 'ResizeMask', 'resize')
        out_mask, out_width, out_height = resize(None, await mask.raw(), width, height, keep_proportions, upscale_method, crop)
        return _image_d_io.NodeOutput(await _image_d_sdk.MaskRef._from_raw(out_mask), out_width, out_height)
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

class CreateTextMaskSecure(_remaining_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls) -> _remaining_b_io.Schema:
        return _remaining_b_io.Schema(node_id='CreateTextMaskSecure', display_name='🔒 Create Text Mask (secure)', category='KJNodes/text', description='Creates a text image and mask, with optional rotation animation.', inputs=[_remaining_b_io.Boolean.Input('invert', default=False), _remaining_b_io.Int.Input('frames', default=1, min=1, max=4096, step=1), _remaining_b_io.Int.Input('text_x', default=0, min=0, max=4096, step=1), _remaining_b_io.Int.Input('text_y', default=0, min=0, max=4096, step=1), _remaining_b_io.Int.Input('font_size', default=32, min=8, max=4096, step=1), _remaining_b_io.String.Input('font_color', default='white'), _remaining_b_io.String.Input('text', default='HELLO!', multiline=True), _remaining_b_io.Combo.Input('font', options=_remaining_b_FONTS, default=_remaining_b_FONTS[0]), _remaining_b_io.Int.Input('width', default=512, min=16, max=4096, step=1), _remaining_b_io.Int.Input('height', default=512, min=16, max=4096, step=1), _remaining_b_io.Int.Input('start_rotation', default=0, min=0, max=359, step=1), _remaining_b_io.Int.Input('end_rotation', default=0, min=-359, max=359, step=1)], outputs=[_remaining_b_io.Image.Output(display_name='image'), _remaining_b_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, invert, frames, text_x, text_y, font_size, font_color, text, font, width, height, start_rotation, end_rotation) -> _remaining_b_io.NodeOutput:
        render = _remaining_b_upstream(_remaining_b_MASK_SOURCE, 'CreateTextMask', 'createtextmask')
        out = render(None, frames, width, height, invert, text_x, text_y, text, font_size, font_color, await _remaining_b_font_content(font), start_rotation, end_rotation)
        return _remaining_b_io.NodeOutput(await _remaining_b_sdk.ImageRef._from_raw(out[0]), await _remaining_b_sdk.MaskRef._from_raw(out[1]))

class CreateAudioMaskSecure(_remaining_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_b_io.Schema:
        return _remaining_b_io.Schema(node_id='CreateAudioMaskSecure', display_name='🔒 Create Audio Mask (secure)', category='KJNodes/deprecated', description='Creates the original audio-reactive circle animation from a V2 AUDIO value instead of an ambient filesystem path.', inputs=[_remaining_b_io.Audio.Input('audio'), _remaining_b_io.Boolean.Input('invert', default=False), _remaining_b_io.Int.Input('frames', default=16, min=1, max=255, step=1), _remaining_b_io.Float.Input('scale', default=0.5, min=0.0, max=2.0, step=0.01), _remaining_b_io.Int.Input('width', default=256, min=16, max=4096, step=1), _remaining_b_io.Int.Input('height', default=256, min=16, max=4096, step=1)], outputs=[_remaining_b_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, audio, invert, frames, scale, width, height) -> _remaining_b_io.NodeOutput:
        import numpy as np
        import torch
        import torch.nn.functional as F
        from PIL import Image, ImageDraw
        value = await audio.value()
        waveform = value['waveform'].float()
        sample_rate = int(value['sample_rate'])
        while waveform.ndim > 1:
            waveform = waveform.mean(dim=0)
        if sample_rate != 22050:
            length = max(1, round(waveform.shape[-1] * 22050 / sample_rate))
            waveform = F.interpolate(waveform[None, None], size=length, mode='linear', align_corners=False)[0, 0]
        window = torch.hann_window(2048, device=waveform.device, dtype=waveform.dtype)
        spectrogram = torch.stft(waveform, n_fft=2048, hop_length=512, window=window, return_complex=True).abs()
        images = []
        for index in range(frames):
            image = Image.new('RGB', (width, height), 'black')
            draw = ImageDraw.Draw(image)
            radius = int(height * spectrogram[:, index].mean().item()) * scale
            center = (width // 2, height // 2)
            draw.ellipse([(center[0] - radius, center[1] - radius), (center[0] + radius, center[1] + radius)], fill='white')
            array = np.asarray(image).astype(np.float32) / 255.0
            images.append(torch.from_numpy(array)[None])
        result = torch.cat(images, dim=0)
        if invert:
            result = 1.0 - result
        return _remaining_b_io.NodeOutput(await _remaining_b_sdk.ImageRef._from_raw(result))
from comfy_api.latest import io as _remaining_q_io, sdk as _remaining_q_sdk
_remaining_q_MODELS = ['Kijai/clipseg-rd64-refined-fp16', 'CIDAS/clipseg-rd64-refined']
_remaining_q_ClipSegModel = _remaining_q_io.Custom('CLIPSEGMODEL')
_remaining_q_CLIPSEG_WEIGHT = _remaining_q_sdk.HuggingFaceWeight(
    repo_id='Kijai/clipseg-rd64-refined-fp16',
    filename='model.safetensors',
    folder='detection',
    sha256='3bfcd7b05b526f849cf18c3102fed42c48ef396377b8e11b777a691029ca1295',
)

class DownloadAndLoadCLIPSegSecure(_remaining_q_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)
    SDK_REQUIRED_WEIGHTS = (_remaining_q_CLIPSEG_WEIGHT,)

    @classmethod
    def define_schema(cls):
        return _remaining_q_io.Schema(node_id='DownloadAndLoadCLIPSegSecure', display_name='🔒 Download And Load CLIPSeg (secure)', category='KJNodes/masking', inputs=[_remaining_q_io.Combo.Input('model', options=_remaining_q_MODELS, default='Kijai/clipseg-rd64-refined-fp16')], outputs=[_remaining_q_ClipSegModel.Output(display_name='clipseg_model')])

    @classmethod
    async def execute(cls, model):
        if model not in _remaining_q_MODELS:
            raise ValueError('model must be a declared CLIPSeg option')
        return _remaining_q_io.NodeOutput(await _remaining_q_sdk.ctx().models.load_clipseg(
            _remaining_q_CLIPSEG_WEIGHT.catalogue_name))

class BatchCLIPSegSecure(_remaining_q_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)
    SDK_REQUIRED_WEIGHTS = (_remaining_q_CLIPSEG_WEIGHT,)

    @classmethod
    def define_schema(cls):
        return _remaining_q_io.Schema(node_id='BatchCLIPSegSecure', display_name='🔒 Batch CLIPSeg (secure)', category='KJNodes/masking', inputs=[_remaining_q_io.Image.Input('images'), _remaining_q_io.String.Input('text'), _remaining_q_io.Float.Input('threshold', default=0.5, min=0.0, max=10.0, step=0.001), _remaining_q_io.Boolean.Input('binary_mask', default=True), _remaining_q_io.Boolean.Input('combine_mask', default=False), _remaining_q_io.Boolean.Input('use_cuda', default=True), _remaining_q_io.Float.Input('blur_sigma', default=0.0, min=0.0, max=100.0, step=0.1, optional=True), _remaining_q_ClipSegModel.Input('opt_model', optional=True), _remaining_q_io.Mask.Input('prev_mask', optional=True), _remaining_q_io.Float.Input('image_bg_level', default=0.5, min=0.0, max=1.0, step=0.01, optional=True), _remaining_q_io.Boolean.Input('invert', default=False, optional=True)], outputs=[_remaining_q_io.Mask.Output('mask', display_name='Mask'), _remaining_q_io.Image.Output('image', display_name='Image')])

    @classmethod
    async def execute(cls, images, text, threshold, binary_mask, combine_mask, use_cuda, blur_sigma=0.0, opt_model=None, prev_mask=None, image_bg_level=0.5, invert=False):
        model = opt_model
        if model is None:
            model = await _remaining_q_sdk.ctx().models.load_clipseg(
                _remaining_q_CLIPSEG_WEIGHT.catalogue_name)
        mask, image = await model.segment(images, text, threshold=threshold, binary_mask=binary_mask, combine_mask=combine_mask, use_accelerator=use_cuda, blur_sigma=blur_sigma, previous_mask=prev_mask, invert=invert, image_background_level=image_bg_level)
        return _remaining_q_io.NodeOutput(mask, image)
import ast as _w3_l_ast
import pathlib as _w3_l_pathlib
from comfy_api.latest import io as _w3_l_io, sdk as _w3_l_sdk
from . import _packload as _w3_l_packload
_w3_l_SOURCE = 'nodes/mask_nodes.py'
_w3_l_FLUID = 'utility/fluid.py'

class _w3_l_Pbar:
    """Upstream's `comfy.utils.ProgressBar`, which a guest does not have.

    A guest's progress reaches the user through the brokered `ctx.progress`; a
    pack-constructed ProgressBar would be reaching for the host directly.
    """

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def update(self, *_args, **_kwargs) -> None:
        pass
_w3_l_NAMESPACE = None

def _w3_l_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`.

    `__package__` is what makes `CreateFluidMask`'s relative import resolve.
    The method is compiled outside any module, so without it Python has nothing
    to measure `..` against and refuses the import.
    """
    global _w3_l_NAMESPACE
    if _w3_l_NAMESPACE is None:
        import logging
        import numpy as np
        import torch
        from tqdm import tqdm
        _w3_l_NAMESPACE = {'torch': torch, 'np': np, 'logging': logging, 'tqdm': tqdm, 'ProgressBar': _w3_l_Pbar, '__package__': f'{_w3_l_packload.PKG}.nodes'}
    return _w3_l_NAMESPACE
_w3_l_CODE: dict[tuple[str, str], object] = {}

def _w3_l_compiled(class_name: str, method: str):
    """Upstream's `class_name.method`, parsed out of its file and compiled.

    The CODE is cached, not the function: a guest serves node after node from
    the same pack and re-parsing a 1700-line module per dispatch would re-pay
    that cost every time, while a shared globals dict would let one dispatch's
    `main_device` answer the next one's question.
    """
    key = (class_name, method)
    cached = _w3_l_CODE.get(key)
    if cached is not None:
        return cached
    path = _w3_l_pathlib.Path(_w3_l_packload.ROOT, *_w3_l_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_l_ast.walk(_w3_l_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_l_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_l_ast.FunctionDef) and item.name == method):
                continue
            source = _w3_l_ast.get_source_segment(text, item)
            code = compile(_w3_l_ast.Module(body=[_w3_l_ast.parse(source).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec')
            _w3_l_CODE[key] = code
            return code
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_l_SOURCE} — the pack changed shape and this conversion must be revisited')

def _w3_l_upstream(class_name: str, method: str, **extra):
    """Upstream's method, bound to `_namespace()` plus what `extra` answers.

    Extracted undecorated, so the caller supplies `self` as an ordinary first
    argument; none of these six methods uses it.
    """
    ns = dict(_w3_l_namespace(), **extra)
    exec(_w3_l_compiled(class_name, method), ns)
    return ns[method]

class BlockifyMaskSecure(_w3_l_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_l_io.Schema:
        return _w3_l_io.Schema(node_id='BlockifyMaskSecure', display_name='🔒 Blockify Mask (secure)', category='KJNodes/masking', description='Creates a block mask by dividing the bounding box of each mask into blocks of the specified size and filling in blocks that contain any part of the original mask.', inputs=[_w3_l_io.Mask.Input('masks'), _w3_l_io.Int.Input('block_size', default=32, min=8, max=512, step=1, tooltip='Size of blocks in pixels (smaller = smaller blocks)'), _w3_l_io.Combo.Input('device', options=['cpu', 'gpu'], default='cpu', optional=True, tooltip='Device to use for processing')], outputs=[_w3_l_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, masks, block_size, device='cpu') -> _w3_l_io.NodeOutput:
        tensor = await masks.raw()
        process = _w3_l_upstream('BlockifyMask', 'process', main_device=tensor.device)
        out = process(None, tensor, block_size, device)
        return _w3_l_io.NodeOutput(await _w3_l_sdk.MaskRef._from_raw(out[0]))

class ColorToMaskSecure(_w3_l_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_l_io.Schema:
        return _w3_l_io.Schema(node_id='ColorToMaskSecure', display_name='🔒 Color To Mask (secure)', category='KJNodes/masking', description='Converts chosen RGB value to a mask. With batch inputs, the per_batch controls the number of images processed at once.', inputs=[_w3_l_io.Image.Input('images'), _w3_l_io.Boolean.Input('invert', default=False), _w3_l_io.Int.Input('red', default=0, min=0, max=255, step=1), _w3_l_io.Int.Input('green', default=0, min=0, max=255, step=1), _w3_l_io.Int.Input('blue', default=0, min=0, max=255, step=1), _w3_l_io.Int.Input('threshold', default=10, min=0, max=255, step=1), _w3_l_io.Int.Input('per_batch', default=16, min=1, max=4096, step=1)], outputs=[_w3_l_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, images, invert, red, green, blue, threshold, per_batch) -> _w3_l_io.NodeOutput:
        clip = _w3_l_upstream('ColorToMask', 'clip')
        out = clip(None, await images.raw(), red, green, blue, threshold, invert, per_batch)
        return _w3_l_io.NodeOutput(await _w3_l_sdk.MaskRef._from_raw(out[0]))

class ConsolidateMasksKJSecure(_w3_l_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_l_io.Schema:
        return _w3_l_io.Schema(node_id='ConsolidateMasksKJSecure', display_name='🔒 Consolidate Masks KJ (secure)', category='KJNodes/masking', description='Consolidates a batch of separate masks by finding the largest group of masks that fit inside a tile of the given width and height (including the padding), and repeating until no more masks can be combined.', inputs=[_w3_l_io.Mask.Input('masks'), _w3_l_io.Int.Input('width', default=512, min=0, max=4096, step=64), _w3_l_io.Int.Input('height', default=512, min=0, max=4096, step=64), _w3_l_io.Int.Input('padding', default=0, min=0, max=4096, step=1)], outputs=[_w3_l_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, masks, width, height, padding) -> _w3_l_io.NodeOutput:
        consolidate = _w3_l_upstream('ConsolidateMasksKJ', 'consolidate')
        out = consolidate(None, await masks.raw(), width, height, padding)
        return _w3_l_io.NodeOutput(await _w3_l_sdk.MaskRef._from_raw(out[0]))

class CreateFadeMaskSecure(_w3_l_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_l_io.Schema:
        return _w3_l_io.Schema(node_id='CreateFadeMaskSecure', display_name='🔒 Create Fade Mask (secure)', category='KJNodes/deprecated', inputs=[_w3_l_io.Boolean.Input('invert', default=False), _w3_l_io.Int.Input('frames', default=2, min=2, max=10000, step=1), _w3_l_io.Int.Input('width', default=256, min=16, max=4096, step=1), _w3_l_io.Int.Input('height', default=256, min=16, max=4096, step=1), _w3_l_io.Combo.Input('interpolation', options=['linear', 'ease_in', 'ease_out', 'ease_in_out'], default='linear'), _w3_l_io.Float.Input('start_level', default=1.0, min=0.0, max=1.0, step=0.01), _w3_l_io.Float.Input('midpoint_level', default=0.5, min=0.0, max=1.0, step=0.01), _w3_l_io.Float.Input('end_level', default=0.0, min=0.0, max=1.0, step=0.01), _w3_l_io.Int.Input('midpoint_frame', default=0, min=0, max=4096, step=1)], outputs=[_w3_l_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, invert, frames, width, height, interpolation, start_level, midpoint_level, end_level, midpoint_frame) -> _w3_l_io.NodeOutput:
        createfademask = _w3_l_upstream('CreateFadeMask', 'createfademask')
        out = createfademask(None, frames, width, height, invert, interpolation, start_level, midpoint_level, end_level, midpoint_frame)
        return _w3_l_io.NodeOutput(await _w3_l_sdk.MaskRef._from_raw(out[0]))

class CreateFadeMaskAdvancedSecure(_w3_l_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_l_io.Schema:
        return _w3_l_io.Schema(node_id='CreateFadeMaskAdvancedSecure', display_name='🔒 Create Fade Mask Advanced (secure)', category='KJNodes/masking/generate', description="Create a batch of masks interpolated between given frames and values. Uses same syntax as Fizz' BatchValueSchedule. First value is the frame index (not that this starts from 0, not 1) and the second value inside the brackets is the float value of the mask in range 0.0 - 1.0.\n\nFor example the default values:\n0:(0.0)\n7:(1.0)\n15:(0.0)\n\nWould create a mask batch fo 16 frames, starting from black, interpolating with the chosen curve to fully white at the 8th frame, and interpolating from that to fully black at the 16th frame.", inputs=[_w3_l_io.String.Input('points_string', default='0:(0.0),\n7:(1.0),\n15:(0.0)\n', multiline=True), _w3_l_io.Boolean.Input('invert', default=False), _w3_l_io.Int.Input('frames', default=16, min=2, max=10000, step=1), _w3_l_io.Int.Input('width', default=512, min=1, max=4096, step=1), _w3_l_io.Int.Input('height', default=512, min=1, max=4096, step=1), _w3_l_io.Combo.Input('interpolation', options=['linear', 'ease_in', 'ease_out', 'ease_in_out', 'none', 'default_to_black'], default='linear')], outputs=[_w3_l_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, points_string, invert, frames, width, height, interpolation) -> _w3_l_io.NodeOutput:
        createfademask = _w3_l_upstream('CreateFadeMaskAdvanced', 'createfademask')
        out = createfademask(None, frames, width, height, invert, points_string, interpolation)
        return _w3_l_io.NodeOutput(await _w3_l_sdk.MaskRef._from_raw(out[0]))

class CreateFluidMaskSecure(_w3_l_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_l_io.Schema:
        return _w3_l_io.Schema(node_id='CreateFluidMaskSecure', display_name='🔒 Create Fluid Mask (secure)', category='KJNodes/masking/generate', inputs=[_w3_l_io.Boolean.Input('invert', default=False), _w3_l_io.Int.Input('frames', default=1, min=1, max=4096, step=1), _w3_l_io.Int.Input('width', default=256, min=16, max=4096, step=1), _w3_l_io.Int.Input('height', default=256, min=16, max=4096, step=1), _w3_l_io.Int.Input('inflow_count', default=3, min=0, max=255, step=1), _w3_l_io.Int.Input('inflow_velocity', default=1, min=0, max=255, step=1), _w3_l_io.Int.Input('inflow_radius', default=8, min=0, max=255, step=1), _w3_l_io.Int.Input('inflow_padding', default=50, min=0, max=255, step=1), _w3_l_io.Int.Input('inflow_duration', default=60, min=0, max=255, step=1)], outputs=[_w3_l_io.Image.Output(display_name='IMAGE'), _w3_l_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, invert, frames, width, height, inflow_count, inflow_velocity, inflow_radius, inflow_padding, inflow_duration) -> _w3_l_io.NodeOutput:
        _w3_l_packload.load(_w3_l_FLUID)
        createfluidmask = _w3_l_upstream('CreateFluidMask', 'createfluidmask')
        images, masks = createfluidmask(None, frames, width, height, invert, inflow_count, inflow_velocity, inflow_radius, inflow_padding, inflow_duration)
        return _w3_l_io.NodeOutput(await _w3_l_sdk.ImageRef._from_raw(images), await _w3_l_sdk.MaskRef._from_raw(masks))
import ast as _w3_m_ast
import os as _w3_m_os
import sys as _w3_m_sys
import types as _w3_m_types
from comfy_api.latest import io as _w3_m_io, sdk as _w3_m_sdk
from . import _packload as _w3_m_packload
_w3_m_MAX_RESOLUTION = 16384
_w3_m_REFUSED_AT_MODULE_SCOPE = ('folder_paths', 'model_management', 'ProgressBar')
_w3_m_MOD = None

def _w3_m_bound(stmt: _w3_m_ast.stmt) -> set[str]:
    """The names an import binds — `import a.b` binds `a`, the rest bind none."""
    if not isinstance(stmt, (_w3_m_ast.Import, _w3_m_ast.ImportFrom)):
        return set()
    return {alias.asname or alias.name.split('.')[0] for alias in stmt.names}

def _w3_m_read(stmt: _w3_m_ast.stmt) -> set[str]:
    return {n.id for n in _w3_m_ast.walk(stmt) if isinstance(n, _w3_m_ast.Name)}

def _w3_m_mod():
    """Upstream's `mask_nodes`, executed with its refused preamble elided.

    Registered under a name of its own rather than `…nodes.mask_nodes`, so a
    later `_packload.load("nodes/mask_nodes.py")` — which succeeds on a host,
    where `folder_paths` and `model_management` exist — is not served this
    partial view from cache.
    """
    global _w3_m_MOD
    if _w3_m_MOD is not None:
        return _w3_m_MOD
    package = f'{_w3_m_packload.PKG}.nodes'
    _w3_m_packload._ensure_package(_w3_m_packload.PKG, _w3_m_packload.ROOT)
    _w3_m_packload._ensure_package(package, _w3_m_os.path.join(_w3_m_packload.ROOT, 'nodes'))
    path = _w3_m_os.path.join(_w3_m_packload.ROOT, 'nodes', 'mask_nodes.py')
    if not _w3_m_os.path.exists(path):
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that imports it must be revisited')
    source = open(path, encoding='utf-8').read()
    tree = _w3_m_ast.parse(source, filename=path)
    refused, kept, dropped = (set(_w3_m_REFUSED_AT_MODULE_SCOPE), [], set())
    for stmt in tree.body:
        if isinstance(stmt, (_w3_m_ast.ClassDef, _w3_m_ast.FunctionDef, _w3_m_ast.AsyncFunctionDef)):
            kept.append(stmt)
            continue
        touched = (_w3_m_bound(stmt) | _w3_m_read(stmt)) & refused
        if touched:
            dropped |= touched
        else:
            kept.append(stmt)
    if dropped != refused:
        raise RuntimeError(f"{', '.join(sorted(refused - dropped))} is no longer reached at the top of {path}; this loader exists only to elide the host surface it names, so upstream changed shape and it must be revisited")
    tree.body = kept
    name = f'{package}.mask_nodes_without_host_surface'
    module = _w3_m_types.ModuleType(name)
    module.__file__ = path
    module.__package__ = package
    _w3_m_sys.modules[name] = module
    try:
        exec(compile(tree, path, 'exec'), module.__dict__)
    except BaseException:
        _w3_m_sys.modules.pop(name, None)
        raise
    _w3_m_MOD = module
    return module

def _w3_m_placed(class_name: str, method: str, device):
    """Upstream's own method, with `main_device` answered from a placement.

    `mask_nodes.py` assigns `main_device = model_management.get_torch_device()`
    at module scope, which is one of the statements `_mod()` elides. Two classes
    here read the name anyway: `GrowMaskWithBlur` moves each mask onto it for
    kornia's morphology, and `DrawMaskOnImage` uses it when asked for "gpu".

    Neither needs the host to answer. A materialized input is ALREADY on the
    device this guest was given, so its own placement is the device — the
    `placement` capability, which a guest has by construction. The method's code
    object is rebound to a copy of the module's globals rather than the module
    being mutated, so nothing about one dispatch outlives it.
    """
    module = _w3_m_mod()
    fn = getattr(getattr(module, class_name), method)
    return _w3_m_types.FunctionType(fn.__code__, {**module.__dict__, 'main_device': device}, fn.__name__, fn.__defaults__, fn.__closure__)

def _w3_m_given(**kwargs):
    """Only the arguments actually supplied, so upstream's defaults stand.

    An unconnected optional input never reaches `execute`, and forwarding `None`
    in its place would override a default this file must not restate.
    """
    return {name: value for name, value in kwargs.items() if value is not None}

class CreateGradientMaskSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='CreateGradientMaskSecure', display_name='🔒 Create Gradient Mask (secure)', category='KJNodes/masking/generate', inputs=[_w3_m_io.Boolean.Input('invert', default=False), _w3_m_io.Int.Input('frames', default=0, min=0, max=255, step=1), _w3_m_io.Int.Input('width', default=256, min=16, max=4096, step=1), _w3_m_io.Int.Input('height', default=256, min=16, max=4096, step=1)], outputs=[_w3_m_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, invert, frames, width, height) -> _w3_m_io.NodeOutput:
        out = _w3_m_mod().CreateGradientMask().createmask(frames, width, height, invert)
        return _w3_m_io.NodeOutput(await _w3_m_sdk.MaskRef._from_raw(out[0]))

class CreateMagicMaskSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='CreateMagicMaskSecure', display_name='🔒 Create Magic Mask (secure)', category='KJNodes/masking/generate', inputs=[_w3_m_io.Int.Input('frames', default=16, min=2, max=4096, step=1), _w3_m_io.Int.Input('depth', default=12, min=1, max=500, step=1), _w3_m_io.Float.Input('distortion', default=1.5, min=0.0, max=100.0, step=0.01), _w3_m_io.Int.Input('seed', default=123, min=0, max=99999999, step=1), _w3_m_io.Int.Input('transitions', default=1, min=1, max=20, step=1), _w3_m_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _w3_m_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1)], outputs=[_w3_m_io.Mask.Output(display_name='mask'), _w3_m_io.Mask.Output(display_name='mask_inverted')])

    @classmethod
    async def execute(cls, frames, depth, distortion, seed, transitions, frame_width, frame_height) -> _w3_m_io.NodeOutput:
        out = _w3_m_mod().CreateMagicMask().createmagicmask(frames, transitions, depth, distortion, seed, frame_width, frame_height)
        return _w3_m_io.NodeOutput(await _w3_m_sdk.MaskRef._from_raw(out[0]), await _w3_m_sdk.MaskRef._from_raw(out[1]))

class CreateShapeMaskSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='CreateShapeMaskSecure', display_name='🔒 Create Shape Mask (secure)', category='KJNodes/masking/generate', description='Creates a mask or batch of masks with the specified shape. Locations are center locations. Grow value is the amount to grow the shape on each frame, creating animated masks.', inputs=[_w3_m_io.Combo.Input('shape', options=['circle', 'square', 'triangle'], default='circle'), _w3_m_io.Int.Input('frames', default=1, min=1, max=4096, step=1), _w3_m_io.Int.Input('location_x', default=256, min=0, max=4096, step=1), _w3_m_io.Int.Input('location_y', default=256, min=0, max=4096, step=1), _w3_m_io.Int.Input('grow', default=0, min=-512, max=512, step=1), _w3_m_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _w3_m_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1), _w3_m_io.Int.Input('shape_width', default=128, min=8, max=4096, step=1), _w3_m_io.Int.Input('shape_height', default=128, min=8, max=4096, step=1)], outputs=[_w3_m_io.Mask.Output(display_name='mask'), _w3_m_io.Mask.Output(display_name='mask_inverted')])

    @classmethod
    async def execute(cls, shape, frames, location_x, location_y, grow, frame_width, frame_height, shape_width, shape_height) -> _w3_m_io.NodeOutput:
        out = _w3_m_mod().CreateShapeMask().createshapemask(frames, frame_width, frame_height, location_x, location_y, shape_width, shape_height, grow, shape)
        return _w3_m_io.NodeOutput(await _w3_m_sdk.MaskRef._from_raw(out[0]), await _w3_m_sdk.MaskRef._from_raw(out[1]))

class CreateVoronoiMaskSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='CreateVoronoiMaskSecure', display_name='🔒 Create Voronoi Mask (secure)', category='KJNodes/masking/generate', inputs=[_w3_m_io.Int.Input('frames', default=16, min=2, max=4096, step=1), _w3_m_io.Int.Input('num_points', default=15, min=1, max=4096, step=1), _w3_m_io.Int.Input('line_width', default=4, min=1, max=4096, step=1), _w3_m_io.Float.Input('speed', default=0.5, min=0.0, max=1.0, step=0.01), _w3_m_io.Int.Input('frame_width', default=512, min=16, max=4096, step=1), _w3_m_io.Int.Input('frame_height', default=512, min=16, max=4096, step=1)], outputs=[_w3_m_io.Mask.Output(display_name='mask'), _w3_m_io.Mask.Output(display_name='mask_inverted')])

    @classmethod
    async def execute(cls, frames, num_points, line_width, speed, frame_width, frame_height) -> _w3_m_io.NodeOutput:
        out = _w3_m_mod().CreateVoronoiMask().createvoronoi(frames, num_points, line_width, speed, frame_width, frame_height)
        return _w3_m_io.NodeOutput(await _w3_m_sdk.MaskRef._from_raw(out[0]), await _w3_m_sdk.MaskRef._from_raw(out[1]))

class DrawMaskOnImageSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='DrawMaskOnImageSecure', display_name='🔒 Draw Mask On Image (secure)', category='KJNodes/masking', description='Applies the provided masks to the input images with Alpha Blending support.', inputs=[_w3_m_io.Image.Input('image'), _w3_m_io.Mask.Input('mask'), _w3_m_io.String.Input('color', default='0, 0, 0', tooltip='Color as RGB/RGBA values in range 0-255 or 0.0-1.0, separated by commas. Ex: 255, 0, 0, 128'), _w3_m_io.Combo.Input('device', options=['cpu', 'gpu'], default='cpu', optional=True, tooltip='Device to use for processing')], outputs=[_w3_m_io.Image.Output(display_name='images')])

    @classmethod
    async def execute(cls, image, mask, color, device=None) -> _w3_m_io.NodeOutput:
        pixels, masks = (await image.raw(), await mask.raw())
        apply = _w3_m_placed('DrawMaskOnImage', 'apply', pixels.device)
        out = apply(None, pixels, masks, color, **_w3_m_given(device=device))
        return _w3_m_io.NodeOutput(await _w3_m_sdk.ImageRef._from_raw(out[0]))

class GetMaskSizeAndCountSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='GetMaskSizeAndCountSecure', display_name='🔒 Get Mask Size & Count (secure)', category='KJNodes/masking', description='Returns the width, height and batch size of the mask, and passes it through unchanged.', inputs=[_w3_m_io.Mask.Input('mask')], outputs=[_w3_m_io.Mask.Output(display_name='mask'), _w3_m_io.Int.Output(display_name='width'), _w3_m_io.Int.Output(display_name='height'), _w3_m_io.Int.Output(display_name='count')])

    @classmethod
    async def execute(cls, mask) -> _w3_m_io.NodeOutput:
        returned = _w3_m_mod().GetMaskSizeAndCount().getsize(await mask.raw())
        passed_through, width, height, count = returned['result']
        return _w3_m_io.NodeOutput(await _w3_m_sdk.MaskRef._from_raw(passed_through), width, height, count, ui=returned['ui'])

class GrowMaskWithBlurSecure(_w3_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_m_io.Schema:
        return _w3_m_io.Schema(node_id='GrowMaskWithBlurSecure', display_name='🔒 Grow Mask With Blur (secure)', category='KJNodes/masking', description='\n# GrowMaskWithBlur\n- mask: Input mask or mask batch\n- expand: Expand or contract mask or mask batch by a given amount\n- incremental_expandrate: increase expand rate by a given amount per frame\n- tapered_corners: use tapered corners\n- flip_input: flip input mask\n- blur_radius: value higher than 0 will blur the mask\n- lerp_alpha: alpha value for interpolation between frames\n- decay_factor: decay value for interpolation between frames\n- fill_holes: fill holes in the mask (slow)', inputs=[_w3_m_io.Mask.Input('mask'), _w3_m_io.Int.Input('expand', default=0, min=-_w3_m_MAX_RESOLUTION, max=_w3_m_MAX_RESOLUTION, step=1), _w3_m_io.Float.Input('incremental_expandrate', default=0.0, min=0.0, max=100.0, step=0.1), _w3_m_io.Boolean.Input('tapered_corners', default=True), _w3_m_io.Boolean.Input('flip_input', default=False), _w3_m_io.Float.Input('blur_radius', default=0.0, min=0.0, max=100, step=0.1), _w3_m_io.Float.Input('lerp_alpha', default=1.0, min=0.0, max=1.0, step=0.01), _w3_m_io.Float.Input('decay_factor', default=1.0, min=0.0, max=1.0, step=0.01), _w3_m_io.Boolean.Input('fill_holes', default=False, optional=True)], outputs=[_w3_m_io.Mask.Output(display_name='mask'), _w3_m_io.Mask.Output(display_name='mask_inverted')])

    @classmethod
    async def execute(cls, mask, expand, incremental_expandrate, tapered_corners, flip_input, blur_radius, lerp_alpha, decay_factor, fill_holes=None) -> _w3_m_io.NodeOutput:
        masks = await mask.raw()
        expand_mask = _w3_m_placed('GrowMaskWithBlur', 'expand_mask', masks.device)
        out = expand_mask(None, masks, expand, tapered_corners, flip_input, blur_radius, incremental_expandrate, lerp_alpha, decay_factor, **_w3_m_given(fill_holes=fill_holes))
        return _w3_m_io.NodeOutput(await _w3_m_sdk.MaskRef._from_raw(out[0]), await _w3_m_sdk.MaskRef._from_raw(out[1]))
import ast as _w3_n_ast
import pathlib as _w3_n_pathlib
from comfy_api.latest import io as _w3_n_io, sdk as _w3_n_sdk
from . import _packload as _w3_n_packload
_w3_n_SOURCE = 'nodes/mask_nodes.py'
_w3_n_MAX_RESOLUTION = 16384

class _w3_n_Pbar:
    """Upstream's `comfy.utils.ProgressBar`, which a guest is refused.

    A guest's progress reaches the user through the brokered `ctx.progress`; a
    pack-constructed ProgressBar would be reaching for the host directly.
    """

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def update(self, *_args, **_kwargs) -> None:
        pass
_w3_n_NAMESPACE = None

def _w3_n_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`.
    """
    global _w3_n_NAMESPACE
    if _w3_n_NAMESPACE is None:
        import logging
        import numpy as np
        import scipy.ndimage
        import torch
        import torch.nn.functional as F
        from torchvision.transforms import functional as TF
        _w3_n_NAMESPACE = {'torch': torch, 'F': F, 'TF': TF, 'np': np, 'scipy': scipy, 'logging': logging, 'ProgressBar': _w3_n_Pbar}
    return _w3_n_NAMESPACE
_w3_n_CODE: dict[tuple[str, str], object] = {}

def _w3_n_compiled(class_name: str, method: str):
    """Upstream's `class_name.method`, parsed out of its file and compiled.

    The CODE is cached, not the function: a guest serves node after node from
    the same pack and re-parsing a 1700-line module per dispatch would re-pay
    that cost every time, while a shared globals dict would let one dispatch's
    names answer the next one's question.
    """
    key = (class_name, method)
    cached = _w3_n_CODE.get(key)
    if cached is not None:
        return cached
    path = _w3_n_pathlib.Path(_w3_n_packload.ROOT, *_w3_n_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_n_ast.walk(_w3_n_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_n_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_n_ast.FunctionDef) and item.name == method):
                continue
            source = _w3_n_ast.get_source_segment(text, item)
            code = compile(_w3_n_ast.Module(body=[_w3_n_ast.parse(source).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec')
            _w3_n_CODE[key] = code
            return code
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_n_SOURCE} — the pack changed shape and this conversion must be revisited')

def _w3_n_upstream(class_name: str, method: str):
    """Upstream's method, bound to `_namespace()`.

    Extracted undecorated, so the caller supplies `self` as an ordinary first
    argument; only `SeparateMasks.separate` uses it.
    """
    ns = dict(_w3_n_namespace())
    exec(_w3_n_compiled(class_name, method), ns)
    return ns[method]

def _w3_n_upstream_instance(class_name: str, *methods):
    """Upstream's methods, hung on a throwaway class and instantiated.

    For the one method here that genuinely uses `self`: attribute lookup on an
    instance binds a class-level function, so `self` is supplied for free and
    upstream's own `self.get_mask_polygon(...)` resolves to upstream's own
    helper rather than to something written here.
    """
    return type(class_name, (), {name: _w3_n_upstream(class_name, name) for name in methods})()

async def _w3_n_materialized(refs: dict) -> dict:
    """The dynamic `mask_N` slots, as tensors.

    `accept_all_inputs` hands over whatever the prompt wired, so a value is
    turned into a tensor only when it actually is a ref; anything that already
    crossed as plain data is forwarded untouched.
    """
    return {name: await value.raw() if isinstance(value, _w3_n_sdk.TensorRef) else value for name, value in refs.items()}

class MaskBatchMultiSecure(_w3_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_n_io.Schema:
        return _w3_n_io.Schema(node_id='MaskBatchMultiSecure', display_name='🔒 Mask Batch Multi (secure)', category='KJNodes/masking', description='Creates an image batch from multiple masks. You can set how many inputs the node has, with the inputcount and clicking update.', accept_all_inputs=True, inputs=[_w3_n_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w3_n_io.Mask.Input('mask_1'), _w3_n_io.Mask.Input('mask_2')], outputs=[_w3_n_io.Mask.Output(display_name='masks')])

    @classmethod
    async def execute(cls, inputcount, mask_1, mask_2, **kwargs) -> _w3_n_io.NodeOutput:
        combine = _w3_n_upstream('MaskBatchMulti', 'combine')
        masks = await _w3_n_materialized(kwargs)
        masks['mask_1'] = await mask_1.raw()
        masks['mask_2'] = await mask_2.raw()
        out = combine(None, inputcount, **masks)
        return _w3_n_io.NodeOutput(await _w3_n_sdk.MaskRef._from_raw(out[0]))

class OffsetMaskSecure(_w3_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_n_io.Schema:
        return _w3_n_io.Schema(node_id='OffsetMaskSecure', display_name='🔒 Offset Mask (secure)', category='KJNodes/masking', description='Offsets the mask by the specified amount.\n - mask: Input mask or mask batch\n - x: Horizontal offset\n - y: Vertical offset\n - angle: Angle in degrees\n - roll: roll edge wrapping\n - duplication_factor: Number of times to duplicate the mask to form a batch\n - border padding_mode: Padding mode for the mask', inputs=[_w3_n_io.Mask.Input('mask'), _w3_n_io.Int.Input('x', default=0, min=-4096, max=_w3_n_MAX_RESOLUTION, step=1, display_mode=_w3_n_io.NumberDisplay.number), _w3_n_io.Int.Input('y', default=0, min=-4096, max=_w3_n_MAX_RESOLUTION, step=1, display_mode=_w3_n_io.NumberDisplay.number), _w3_n_io.Int.Input('angle', default=0, min=-360, max=360, step=1, display_mode=_w3_n_io.NumberDisplay.number), _w3_n_io.Int.Input('duplication_factor', default=1, min=1, max=1000, step=1, display_mode=_w3_n_io.NumberDisplay.number), _w3_n_io.Boolean.Input('roll', default=False), _w3_n_io.Boolean.Input('incremental', default=False), _w3_n_io.Combo.Input('padding_mode', options=['empty', 'border', 'reflection'], default='empty')], outputs=[_w3_n_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, mask, x, y, angle, duplication_factor, roll, incremental, padding_mode) -> _w3_n_io.NodeOutput:
        offset = _w3_n_upstream('OffsetMask', 'offset')
        out = offset(None, await mask.raw(), x, y, angle, roll, incremental, duplication_factor, padding_mode)
        return _w3_n_io.NodeOutput(await _w3_n_sdk.MaskRef._from_raw(out[0]))

class RemapMaskRangeSecure(_w3_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_n_io.Schema:
        return _w3_n_io.Schema(node_id='RemapMaskRangeSecure', display_name='🔒 Remap Mask Range (secure)', category='KJNodes/masking', description='Sets new min and max values for the mask.', inputs=[_w3_n_io.Mask.Input('mask'), _w3_n_io.Float.Input('min', default=0.0, min=-10.0, max=1.0, step=0.01), _w3_n_io.Float.Input('max', default=1.0, min=0.0, max=10.0, step=0.01)], outputs=[_w3_n_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, mask, min, max) -> _w3_n_io.NodeOutput:
        remap = _w3_n_upstream('RemapMaskRange', 'remap')
        out = remap(None, await mask.raw(), min, max)
        return _w3_n_io.NodeOutput(await _w3_n_sdk.MaskRef._from_raw(out[0]))

class RoundMaskSecure(_w3_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_n_io.Schema:
        return _w3_n_io.Schema(node_id='RoundMaskSecure', display_name='🔒 Round Mask (secure)', category='KJNodes/masking', description='Rounds the mask or batch of masks to a binary mask.', inputs=[_w3_n_io.Mask.Input('mask')], outputs=[_w3_n_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, mask) -> _w3_n_io.NodeOutput:
        round_mask = _w3_n_upstream('RoundMask', 'round')
        out = round_mask(None, await mask.raw())
        return _w3_n_io.NodeOutput(await _w3_n_sdk.MaskRef._from_raw(out[0]))

class SeparateMasksSecure(_w3_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_n_io.Schema:
        return _w3_n_io.Schema(node_id='SeparateMasksSecure', display_name='🔒 Separate Masks (secure)', category='KJNodes/masking', description='Separates a mask into multiple masks based on the size of the connected components.', is_output_node=True, inputs=[_w3_n_io.Mask.Input('mask'), _w3_n_io.Int.Input('size_threshold_width', default=256, min=0, max=4096, step=1), _w3_n_io.Int.Input('size_threshold_height', default=256, min=0, max=4096, step=1), _w3_n_io.Combo.Input('mode', options=['convex_polygons', 'area', 'box'], default='convex_polygons'), _w3_n_io.Int.Input('max_poly_points', default=8, min=3, max=32, step=1)], outputs=[_w3_n_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, mask, size_threshold_width, size_threshold_height, mode, max_poly_points) -> _w3_n_io.NodeOutput:
        separator = _w3_n_upstream_instance('SeparateMasks', 'separate', 'get_mask_polygon', 'polygon_to_mask')
        out = separator.separate(await mask.raw(), size_threshold_width, size_threshold_height, max_poly_points, mode)
        return _w3_n_io.NodeOutput(await _w3_n_sdk.MaskRef._from_raw(out[0]))

NODE_CLASS_MAPPINGS = {
    'ResizeMaskSecure': ResizeMaskSecure,
    'CreateAudioMaskSecure': CreateAudioMaskSecure,
    'CreateTextMaskSecure': CreateTextMaskSecure,
    'DownloadAndLoadCLIPSegSecure': DownloadAndLoadCLIPSegSecure,
    'BatchCLIPSegSecure': BatchCLIPSegSecure,
    'BlockifyMaskSecure': BlockifyMaskSecure,
    'ColorToMaskSecure': ColorToMaskSecure,
    'ConsolidateMasksKJSecure': ConsolidateMasksKJSecure,
    'CreateFadeMaskSecure': CreateFadeMaskSecure,
    'CreateFadeMaskAdvancedSecure': CreateFadeMaskAdvancedSecure,
    'CreateFluidMaskSecure': CreateFluidMaskSecure,
    'CreateGradientMaskSecure': CreateGradientMaskSecure,
    'CreateMagicMaskSecure': CreateMagicMaskSecure,
    'CreateShapeMaskSecure': CreateShapeMaskSecure,
    'CreateVoronoiMaskSecure': CreateVoronoiMaskSecure,
    'DrawMaskOnImageSecure': DrawMaskOnImageSecure,
    'GetMaskSizeAndCountSecure': GetMaskSizeAndCountSecure,
    'GrowMaskWithBlurSecure': GrowMaskWithBlurSecure,
    'MaskBatchMultiSecure': MaskBatchMultiSecure,
    'OffsetMaskSecure': OffsetMaskSecure,
    'RemapMaskRangeSecure': RemapMaskRangeSecure,
    'RoundMaskSecure': RoundMaskSecure,
    'SeparateMasksSecure': SeparateMasksSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'ResizeMaskSecure': '🔒 Resize Mask (secure)',
    'CreateAudioMaskSecure': '🔒 Create Audio Mask (secure)',
    'CreateTextMaskSecure': '🔒 Create Text Mask (secure)',
    'DownloadAndLoadCLIPSegSecure': '🔒 Download And Load CLIPSeg (secure)',
    'BatchCLIPSegSecure': '🔒 Batch CLIPSeg (secure)',
    'BlockifyMaskSecure': '🔒 Blockify Mask (secure)',
    'ColorToMaskSecure': '🔒 Color To Mask (secure)',
    'ConsolidateMasksKJSecure': '🔒 Consolidate Masks KJ (secure)',
    'CreateFadeMaskSecure': '🔒 Create Fade Mask (secure)',
    'CreateFadeMaskAdvancedSecure': '🔒 Create Fade Mask Advanced (secure)',
    'CreateFluidMaskSecure': '🔒 Create Fluid Mask (secure)',
    'CreateGradientMaskSecure': '🔒 Create Gradient Mask (secure)',
    'CreateMagicMaskSecure': '🔒 Create Magic Mask (secure)',
    'CreateShapeMaskSecure': '🔒 Create Shape Mask (secure)',
    'CreateVoronoiMaskSecure': '🔒 Create Voronoi Mask (secure)',
    'DrawMaskOnImageSecure': '🔒 Draw Mask On Image (secure)',
    'GetMaskSizeAndCountSecure': '🔒 Get Mask Size & Count (secure)',
    'GrowMaskWithBlurSecure': '🔒 Grow Mask With Blur (secure)',
    'MaskBatchMultiSecure': '🔒 Mask Batch Multi (secure)',
    'OffsetMaskSecure': '🔒 Offset Mask (secure)',
    'RemapMaskRangeSecure': '🔒 Remap Mask Range (secure)',
    'RoundMaskSecure': '🔒 Round Mask (secure)',
    'SeparateMasksSecure': '🔒 Separate Masks (secure)',
}
