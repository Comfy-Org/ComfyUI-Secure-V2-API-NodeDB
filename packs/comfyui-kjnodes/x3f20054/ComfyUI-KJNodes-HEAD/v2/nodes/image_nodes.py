from __future__ import annotations
import asyncio as _capture_asyncio
from comfy_api.latest import io as _capture_io, sdk as _capture_sdk

def _capture_screen_schema(node_id: str, display_name: str, maximum: int) -> _capture_io.Schema:
    return _capture_io.Schema(node_id=node_id, display_name=display_name, category='KJNodes/image', description='Captures an area specified by screen coordinates. Can be used for realtime diffusion with autoqueue.', inputs=[_capture_io.Int.Input('x', default=0, min=0, max=maximum, step=1), _capture_io.Int.Input('y', default=0, min=0, max=maximum, step=1), _capture_io.Int.Input('width', default=512, min=0, max=maximum, step=1), _capture_io.Int.Input('height', default=512, min=0, max=maximum, step=1), _capture_io.Int.Input('num_frames', default=1, min=1, max=255, step=1), _capture_io.Float.Input('delay', default=0.1, min=0.0, max=10.0, step=0.01)], outputs=[_capture_io.Image.Output(display_name='image')])

async def _capture_capture_screen_batch(x, y, width, height, num_frames, delay):
    import torch
    frames = []
    capture = _capture_sdk.ctx().capture
    region = (x, y, x + width, y + height)
    for index in range(num_frames):
        image = await capture.screen(region=region)
        frames.append(await image.raw())
        await image.release()
        if index + 1 < num_frames:
            await _capture_asyncio.sleep(delay)
    return await _capture_sdk.ImageRef._from_raw(torch.cat(frames, dim=0))

class ImageGrabPILSecure(_capture_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('capture.screen', 'raw')

    @classmethod
    def define_schema(cls) -> _capture_io.Schema:
        return _capture_screen_schema('ImageGrabPILSecure', '🔒 Image Grab PIL (secure)', 4096)

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('NaN')

    @classmethod
    async def execute(cls, x, y, width, height, num_frames, delay) -> _capture_io.NodeOutput:
        return _capture_io.NodeOutput(await _capture_capture_screen_batch(x, y, width, height, num_frames, delay))

class ScreencapMssSecure(_capture_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('capture.screen', 'raw')

    @classmethod
    def define_schema(cls) -> _capture_io.Schema:
        return _capture_screen_schema('ScreencapMssSecure', '🔒 Screencap (mss) (secure)', 10000)

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('NaN')

    @classmethod
    async def execute(cls, x, y, width, height, num_frames, delay) -> _capture_io.NodeOutput:
        return _capture_io.NodeOutput(await _capture_capture_screen_batch(x, y, width, height, num_frames, delay))

class WebcamCaptureCV2Secure(_capture_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('capture.camera', 'raw')

    @classmethod
    def define_schema(cls) -> _capture_io.Schema:
        return _capture_io.Schema(node_id='WebcamCaptureCV2Secure', display_name='🔒 Webcam Capture CV2 (secure)', category='KJNodes/experimental', description='Captures a frame from a webcam. Can be used for realtime diffusion with autoqueue.', inputs=[_capture_io.Int.Input('x', default=0, min=0, max=4096, step=1), _capture_io.Int.Input('y', default=0, min=0, max=4096, step=1), _capture_io.Int.Input('width', default=512, min=0, max=4096, step=1), _capture_io.Int.Input('height', default=512, min=0, max=4096, step=1), _capture_io.Int.Input('cam_index', default=0, min=0, max=255, step=1), _capture_io.Boolean.Input('release', default=False)], outputs=[_capture_io.Image.Output(display_name='image')])

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('NaN')

    @classmethod
    async def execute(cls, x, y, width, height, cam_index, release) -> _capture_io.NodeOutput:
        image = await _capture_sdk.ctx().capture.camera(index=cam_index, width=width, height=height)
        frame = await image.raw()
        await image.release()
        cropped = frame[:, y:y + height, x:x + width]
        return _capture_io.NodeOutput(await _capture_sdk.ImageRef._from_raw(cropped))
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

class InsertImagesToBatchIndexedSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='InsertImagesToBatchIndexedSecure', display_name='🔒 Insert Images To Batch Indexed (secure)', category='KJNodes/image', description='Inserts images at the specified indices into the original image batch.', inputs=[_image_d_io.Image.Input('original_images'), _image_d_io.Image.Input('images_to_insert'), _image_d_io.String.Input('indexes', default='0, 1, 2', multiline=True), _image_d_io.Combo.Input('mode', options=['replace', 'insert'], default='replace', optional=True)], outputs=[_image_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, original_images, images_to_insert, indexes, mode='replace') -> _image_d_io.NodeOutput:
        insert = _image_d_upstream(_image_d_IMAGE_NODES, 'InsertImagesToBatchIndexed', 'insertimagesfrombatch')
        out = insert(None, await original_images.raw(), await images_to_insert.raw(), indexes, mode)
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(out[0]))

class MergeImageChannelsSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='MergeImageChannelsSecure', display_name='🔒 Merge Image Channels (secure)', category='KJNodes/image', description='Merges channel data into an image.', inputs=[_image_d_io.Image.Input('red'), _image_d_io.Image.Input('green'), _image_d_io.Image.Input('blue'), _image_d_io.Mask.Input('alpha', optional=True)], outputs=[_image_d_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, red, green, blue, alpha=None) -> _image_d_io.NodeOutput:
        merge = _image_d_upstream(_image_d_IMAGE_NODES, 'MergeImageChannels', 'merge')
        out = merge(None, await red.raw(), await green.raw(), await blue.raw(), None if alpha is None else await alpha.raw())
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(out[0]))

class PadImageBatchInterleavedSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='PadImageBatchInterleavedSecure', display_name='🔒 Pad Image Batch Interleaved (secure)', category='KJNodes/image', description='Inserts empty frames between the images in a batch.', inputs=[_image_d_io.Image.Input('images'), _image_d_io.Int.Input('empty_frames_per_image', default=1, min=0, max=4096, step=1), _image_d_io.Float.Input('pad_frame_value', default=0.0, min=0.0, max=1.0, step=0.01), _image_d_io.Boolean.Input('add_after_last', default=False)], outputs=[_image_d_io.Image.Output(display_name='images'), _image_d_io.Mask.Output(display_name='masks')])

    @classmethod
    async def execute(cls, images, empty_frames_per_image, pad_frame_value, add_after_last) -> _image_d_io.NodeOutput:
        pad = _image_d_upstream(_image_d_IMAGE_NODES, 'PadImageBatchInterleaved', 'pad')
        padded, mask = pad(None, await images.raw(), empty_frames_per_image, pad_frame_value, add_after_last)
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(padded), await _image_d_sdk.MaskRef._from_raw(mask))

class RemapImageRangeSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='RemapImageRangeSecure', display_name='🔒 Remap Image Range (secure)', category='KJNodes/image', description='Remaps the image values to the specified range.', inputs=[_image_d_io.Image.Input('image'), _image_d_io.Float.Input('min', default=0.0, min=-10.0, max=1.0, step=0.01), _image_d_io.Float.Input('max', default=1.0, min=0.0, max=10.0, step=0.01), _image_d_io.Boolean.Input('clamp', default=True)], outputs=[_image_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, image, min, max, clamp) -> _image_d_io.NodeOutput:
        remap = _image_d_upstream(_image_d_IMAGE_NODES, 'RemapImageRange', 'remap')
        out = remap(None, await image.raw(), min, max, clamp)
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(out[0]))

class ReplaceImagesInBatchSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='ReplaceImagesInBatchSecure', display_name='🔒 Replace Images In Batch (secure)', category='KJNodes/image', description='Replaces the images in a batch, starting from the specified start index, with the replacement images.', inputs=[_image_d_io.Int.Input('start_index', default=1, min=0, max=4096, step=1), _image_d_io.Image.Input('original_images', optional=True), _image_d_io.Image.Input('replacement_images', optional=True), _image_d_io.Mask.Input('original_masks', optional=True), _image_d_io.Mask.Input('replacement_masks', optional=True)], outputs=[_image_d_io.Image.Output(display_name='IMAGE'), _image_d_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, start_index, original_images=None, replacement_images=None, original_masks=None, replacement_masks=None) -> _image_d_io.NodeOutput:
        replace = _image_d_upstream(_image_d_IMAGE_NODES, 'ReplaceImagesInBatch', 'replace')
        images, masks = replace(None, None if original_images is None else await original_images.raw(), None if replacement_images is None else await replacement_images.raw(), start_index, None if original_masks is None else await original_masks.raw(), None if replacement_masks is None else await replacement_masks.raw())
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(images), await _image_d_sdk.MaskRef._from_raw(masks))

class ReverseImageBatchSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='ReverseImageBatchSecure', display_name='🔒 Reverse Image Batch (secure)', category='KJNodes/image', description='Reverses the order of the images in a batch.', inputs=[_image_d_io.Image.Input('images')], outputs=[_image_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images) -> _image_d_io.NodeOutput:
        reverse = _image_d_upstream(_image_d_IMAGE_NODES, 'ReverseImageBatch', 'reverseimagebatch')
        out = reverse(None, await images.raw())
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(out[0]))

class ShuffleImageBatchSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='ShuffleImageBatchSecure', display_name='🔒 Shuffle Image Batch (secure)', category='KJNodes/image', inputs=[_image_d_io.Image.Input('images'), _image_d_io.Int.Input('seed', default=123, min=0, max=18446744073709551615, step=1)], outputs=[_image_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images, seed) -> _image_d_io.NodeOutput:
        shuffle = _image_d_upstream(_image_d_IMAGE_NODES, 'ShuffleImageBatch', 'shuffle')
        out = shuffle(None, await images.raw(), seed)
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(out[0]))

class SplitImageChannelsSecure(_image_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _image_d_io.Schema:
        return _image_d_io.Schema(node_id='SplitImageChannelsSecure', display_name='🔒 Split Image Channels (secure)', category='KJNodes/image', description='Splits image channels into images where the selected channel is repeated for all channels, and the alpha as a mask.', inputs=[_image_d_io.Image.Input('image')], outputs=[_image_d_io.Image.Output(display_name='red'), _image_d_io.Image.Output(display_name='green'), _image_d_io.Image.Output(display_name='blue'), _image_d_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, image) -> _image_d_io.NodeOutput:
        split = _image_d_upstream(_image_d_IMAGE_NODES, 'SplitImageChannels', 'split')
        red, green, blue, alpha = split(None, await image.raw())
        return _image_d_io.NodeOutput(await _image_d_sdk.ImageRef._from_raw(red), await _image_d_sdk.ImageRef._from_raw(green), await _image_d_sdk.ImageRef._from_raw(blue), await _image_d_sdk.MaskRef._from_raw(alpha))
import ast as _input_folders_ast
import copy as _input_folders_copy
import os as _input_folders_os
import pathlib as _input_folders_pathlib
import tempfile as _input_folders_tempfile
from io import BytesIO as _input_folders_BytesIO
from comfy_api.latest import io as _input_folders_io, sdk as _input_folders_sdk
from . import _packload as _input_folders_packload
_input_folders_IMAGE_HELPERS = None
_input_folders_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.tga')
_input_folders_VIDEO_EXTENSIONS = ('.webm', '.mp4', '.mkv', '.gif', '.mov')

def _input_folders_kjnodes_source() -> _input_folders_pathlib.Path:
    return _input_folders_pathlib.Path(_input_folders_packload.ROOT).resolve() / 'nodes' / 'image_nodes.py'

def _input_folders_image_helpers():
    global _input_folders_IMAGE_HELPERS
    if _input_folders_IMAGE_HELPERS is not None:
        return _input_folders_IMAGE_HELPERS
    source_path = _input_folders_kjnodes_source()
    tree = _input_folders_ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    source_class = next((node for node in tree.body if isinstance(node, _input_folders_ast.ClassDef) and node.name == 'LoadImagesFromFolderKJ'))
    methods = [_input_folders_copy.deepcopy(node) for node in source_class.body if isinstance(node, _input_folders_ast.FunctionDef) and node.name in {'resize_with_aspect_ratio', 'get_edge_color'}]
    helper_class = _input_folders_ast.ClassDef(name='_ImageHelpers', bases=[], keywords=[], body=methods, decorator_list=[])
    from PIL import Image, ImageStat
    namespace = {'Image': Image, 'ImageStat': ImageStat}
    module = _input_folders_ast.fix_missing_locations(_input_folders_ast.Module(body=[helper_class], type_ignores=[]))
    exec(compile(module, f'<kjnodes:{source_path}>', 'exec'), namespace)
    _input_folders_IMAGE_HELPERS = namespace['_ImageHelpers']()
    return _input_folders_IMAGE_HELPERS

async def _input_folders_input_names(prefix: str, recursive: bool, extensions) -> list[str]:
    names = await _input_folders_sdk.ctx().assets.list('input', prefix=prefix, recursive=recursive)
    return sorted((name for name in names if _input_folders_pathlib.PurePosixPath(name).suffix.lower() in extensions))

class LoadImagesFromFolderKJSecure(_input_folders_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls) -> _input_folders_io.Schema:
        return _input_folders_io.Schema(node_id='LoadImagesFromFolderKJSecure', display_name='🔒 Load Images From Folder KJ (secure)', category='KJNodes/image', description='Loads a sorted batch from a logical input-folder name. Filesystem paths are not accepted.', inputs=[_input_folders_io.String.Input('folder', default=''), _input_folders_io.Int.Input('width', default=1024, min=-1, step=1), _input_folders_io.Int.Input('height', default=1024, min=-1, step=1), _input_folders_io.Combo.Input('keep_aspect_ratio', options=['crop', 'pad', 'stretch'], default='crop'), _input_folders_io.Int.Input('image_load_cap', default=0, min=0, step=1, optional=True), _input_folders_io.Int.Input('start_index', default=0, min=0, step=1, optional=True), _input_folders_io.Boolean.Input('include_subfolders', default=False, optional=True)], outputs=[_input_folders_io.Image.Output('image'), _input_folders_io.Mask.Output('mask'), _input_folders_io.Int.Output('count'), _input_folders_io.String.Output('image_path')])

    @classmethod
    async def execute(cls, folder, width, height, keep_aspect_ratio, image_load_cap=0, start_index=0, include_subfolders=False) -> _input_folders_io.NodeOutput:
        import numpy as np
        import torch
        from PIL import Image, ImageOps
        if not folder:
            raise FileNotFoundError("Folder '' cannot be found.")
        names = await _input_folders_input_names(folder, bool(include_subfolders), _input_folders_IMAGE_EXTENSIONS)
        names = names[int(start_index):]
        if int(image_load_cap) > 0:
            names = names[:int(image_load_cap)]
        if not names:
            raise FileNotFoundError(f'No files in directory {folder!r}.')
        images = []
        masks = []
        helpers = _input_folders_image_helpers()
        assets = _input_folders_sdk.ctx().assets
        target_width = int(width)
        target_height = int(height)
        total = len(names)
        for index, name in enumerate(names):
            ref = await assets.resolve('input', name)
            content = await assets.read_bytes(ref)
            with Image.open(_input_folders_BytesIO(content)) as source:
                image = ImageOps.exif_transpose(source)
                if target_width == -1 and target_height == -1:
                    target_width, target_height = image.size
                if image.size != (target_width, target_height):
                    image = helpers.resize_with_aspect_ratio(image, target_width, target_height, keep_aspect_ratio)
                pixels = np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0
                images.append(torch.from_numpy(pixels)[None])
                if 'A' in image.getbands():
                    alpha = np.asarray(image.getchannel('A'), dtype=np.float32) / 255.0
                    mask = 1.0 - torch.from_numpy(alpha)
                    if mask.shape != (target_height, target_width):
                        mask = torch.nn.functional.interpolate(mask.unsqueeze(0).unsqueeze(0), size=(target_height, target_width), mode='bilinear', align_corners=False).squeeze()
                else:
                    mask = torch.zeros((target_height, target_width), dtype=torch.float32)
                masks.append(mask)
            await _input_folders_sdk.ctx().progress.update(index + 1, total)
        if len(images) == 1:
            output_image = images[0]
            output_mask = masks[0]
        else:
            output_image = torch.cat(images, dim=0)
            output_mask = torch.stack(masks, dim=0)
        return _input_folders_io.NodeOutput(await _input_folders_sdk.ImageRef._from_raw(output_image), await _input_folders_sdk.MaskRef._from_raw(output_mask), len(images), names)

def _input_folders_target_size(width, height, custom_width, custom_height):
    if custom_width == 0 and custom_height == 0:
        pass
    elif custom_height == 0:
        height *= custom_width / width
        width = custom_width
    elif custom_width == 0:
        width *= custom_height / height
        height = custom_height
    else:
        width = custom_width
        height = custom_height
    return (int(width + 0.5), int(height + 0.5))

def _input_folders_decode_video(content: bytes, suffix: str, force_rate: float, custom_width: int, custom_height: int, frame_load_cap: int, skip_first_frames: int, select_every_nth: int):
    import cv2
    import numpy as np
    import torch
    from ._tensor_utils import common_upscale
    handle, temporary_path = _input_folders_tempfile.mkstemp(suffix=suffix)
    try:
        with _input_folders_os.fdopen(handle, 'wb') as file:
            file.write(content)
        capture = cv2.VideoCapture(temporary_path)
        try:
            if not capture.isOpened() or not capture.grab():
                raise ValueError('video could not be loaded with cv')
            fps = capture.get(cv2.CAP_PROP_FPS)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if width <= 0 or height <= 0:
                retrieved, frame = capture.retrieve()
                if not retrieved:
                    raise ValueError('video did not contain a readable frame')
                height, width, _ = frame.shape
            base_frame_time = 1.0 / fps
            target_frame_time = base_frame_time if float(force_rate) == 0 else 1.0 / float(force_rate)
            time_offset = target_frame_time
            total_frame_count = 0
            total_frames_evaluated = -1
            frames = []
            while capture.isOpened():
                if time_offset < target_frame_time:
                    if not capture.grab():
                        break
                    time_offset += base_frame_time
                if time_offset < target_frame_time:
                    continue
                time_offset -= target_frame_time
                total_frame_count += 1
                if total_frame_count <= int(skip_first_frames):
                    continue
                total_frames_evaluated += 1
                if total_frames_evaluated % int(select_every_nth) != 0:
                    continue
                retrieved, frame = capture.retrieve()
                if not retrieved:
                    break
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = np.asarray(frame, dtype=np.float32)
                torch.from_numpy(frame).div_(255)
                frames.append(frame)
                if int(frame_load_cap) > 0 and len(frames) >= int(frame_load_cap):
                    break
        finally:
            capture.release()
    finally:
        try:
            _input_folders_os.unlink(temporary_path)
        except FileNotFoundError:
            pass
    if not frames:
        raise RuntimeError('No frames generated')
    target_width, target_height = _input_folders_target_size(width, height, int(custom_width), int(custom_height))
    result = torch.from_numpy(np.stack(frames))
    if (target_width, target_height) != (width, height):
        result = common_upscale(result.movedim(-1, 1), target_width, target_height, 'lanczos', 'center').movedim(1, -1)
    return result

def _input_folders_add_label(video, label_text: str):
    import numpy as np
    import torch
    from PIL import Image, ImageDraw, ImageFont
    if video.dim() == 4:
        _, height, width, channels = video.shape
    else:
        height, width, channels = video.shape
    font_size = max(16, width // 20)
    try:
        font = ImageFont.truetype('arial.ttf', font_size)
    except OSError:
        font = ImageFont.load_default()
    dummy = Image.new('RGB', (width, 10), (0, 0, 0))
    text_bbox = ImageDraw.Draw(dummy).textbbox((0, 0), label_text, font=font)
    extra_padding = max(12, font_size // 2)
    label_height = text_bbox[3] - text_bbox[1] + extra_padding
    label = Image.new('RGB', (width, label_height), (0, 0, 0))
    draw = ImageDraw.Draw(label)
    draw.text((width // 2 - (text_bbox[2] - text_bbox[0]) // 2, 4), label_text, font=font, fill=(255, 255, 255))
    label_tensor = torch.from_numpy(np.asarray(label).astype(np.float32) / 255.0)
    if channels == 1:
        label_tensor = label_tensor.mean(dim=2, keepdim=True)
    elif channels == 4:
        alpha = torch.ones((label_height, width, 1), dtype=label_tensor.dtype)
        label_tensor = torch.cat([label_tensor, alpha], dim=2)
    if video.dim() == 4:
        label_tensor = label_tensor.unsqueeze(0).expand(video.shape[0], -1, -1, -1)
        return torch.cat([label_tensor, video], dim=1)
    return torch.cat([label_tensor, video], dim=0)

class LoadVideosFromFolderSecure(_input_folders_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls) -> _input_folders_io.Schema:
        return _input_folders_io.Schema(node_id='LoadVideosFromFolderSecure', display_name='🔒 Load Videos From Folder (secure)', category='KJNodes/misc', description='Loads sorted videos from a logical input-folder name. Selected bytes are decoded inside the sandbox.', inputs=[_input_folders_io.String.Input('video', default=''), _input_folders_io.Float.Input('force_rate', default=0, min=0, max=60, step=1), _input_folders_io.Int.Input('custom_width', default=0, min=0, max=4096), _input_folders_io.Int.Input('custom_height', default=0, min=0, max=4096), _input_folders_io.Int.Input('frame_load_cap', default=0, min=0, max=10000), _input_folders_io.Int.Input('skip_first_frames', default=0, min=0, max=10000), _input_folders_io.Int.Input('select_every_nth', default=1, min=1, max=1000), _input_folders_io.Combo.Input('output_type', options=['batch', 'grid'], default='batch'), _input_folders_io.Int.Input('grid_max_columns', default=4, min=1, max=16), _input_folders_io.Boolean.Input('add_label', default=False)], outputs=[_input_folders_io.Image.Output('IMAGE')])

    @classmethod
    async def execute(cls, video, force_rate, custom_width, custom_height, frame_load_cap, skip_first_frames, select_every_nth, output_type, grid_max_columns, add_label=False) -> _input_folders_io.NodeOutput:
        import torch
        if not video:
            raise FileNotFoundError("Folder '' cannot be found.")
        names = await _input_folders_input_names(video, False, _input_folders_VIDEO_EXTENSIONS)
        if not names:
            raise FileNotFoundError(f'No videos in directory {video!r}.')
        assets = _input_folders_sdk.ctx().assets
        loaded_videos = []
        for index, name in enumerate(names):
            ref = await assets.resolve('input', name)
            content = await assets.read_bytes(ref)
            loaded = _input_folders_decode_video(content, _input_folders_pathlib.PurePosixPath(name).suffix, force_rate, custom_width, custom_height, frame_load_cap, skip_first_frames, select_every_nth)
            if add_label:
                loaded = _input_folders_add_label(loaded, _input_folders_pathlib.PurePosixPath(name).stem)
            loaded_videos.append(loaded)
            await _input_folders_sdk.ctx().progress.update(index + 1, len(names))
        if output_type == 'batch':
            output = torch.cat(loaded_videos)
        else:
            rows = (len(loaded_videos) + int(grid_max_columns) - 1) // int(grid_max_columns)
            total_slots = rows * int(grid_max_columns)
            while len(loaded_videos) < total_slots:
                loaded_videos.append(torch.zeros_like(loaded_videos[0]))
            row_tensors = []
            for row_index in range(rows):
                start = row_index * int(grid_max_columns)
                row = loaded_videos[start:start + int(grid_max_columns)]
                max_height = max((item.shape[1] for item in row))
                padded = []
                for item in row:
                    pad_height = max_height - item.shape[1]
                    if pad_height > 0:
                        if item.dim() == 4:
                            item = torch.nn.functional.pad(item, (0, 0, 0, 0, 0, pad_height, 0, 0))
                        else:
                            item = torch.nn.functional.pad(item, (0, 0, 0, 0, pad_height, 0))
                    padded.append(item)
                row_tensors.append(torch.cat(padded, dim=2))
            output = torch.cat(row_tensors, dim=1)
        return _input_folders_io.NodeOutput(await _input_folders_sdk.ImageRef._from_raw(output))
import ast as _remaining_a_ast
import copy as _remaining_a_copy
import pathlib as _remaining_a_pathlib
from comfy_api.latest import io as _remaining_a_io, sdk as _remaining_a_sdk
from . import _packload as _remaining_a_packload
_remaining_a_METHODS = {}
_remaining_a_TREES = {}

def _remaining_a_source_root():
    return _remaining_a_pathlib.Path(_remaining_a_packload.ROOT).resolve()

def _remaining_a_tree(relpath: str):
    cached = _remaining_a_TREES.get(relpath)
    if cached is not None:
        return cached
    path = _remaining_a_source_root().joinpath(*relpath.split('/'))
    text = path.read_text(encoding='utf-8')
    parsed = (path, text, _remaining_a_ast.parse(text, filename=str(path)))
    _remaining_a_TREES[relpath] = parsed
    return parsed

def _remaining_a_upstream(relpath: str, class_name: str, method_name: str, helpers=()):
    key = (relpath, class_name, method_name, tuple(helpers))
    cached = _remaining_a_METHODS.get(key)
    if cached is not None:
        return cached
    path, text, tree = _remaining_a_tree(relpath)
    body = []
    for node in tree.body:
        if isinstance(node, (_remaining_a_ast.FunctionDef, _remaining_a_ast.AsyncFunctionDef)) and node.name in helpers:
            body.append(_remaining_a_copy.deepcopy(node))
        if not isinstance(node, _remaining_a_ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (_remaining_a_ast.FunctionDef, _remaining_a_ast.AsyncFunctionDef)) and item.name == method_name:
                method = _remaining_a_copy.deepcopy(item)
                method.decorator_list = []
                body.append(method)
    if not body or not any((getattr(node, 'name', None) == method_name for node in body)):
        raise RuntimeError(f'{class_name}.{method_name} not found in upstream {path}')
    import torch
    namespace = {'io': _remaining_a_io, 'torch': torch}
    exec(compile(_remaining_a_ast.Module(body=body, type_ignores=[]), f'<kjnodes.{class_name}.{method_name}>', 'exec'), namespace)
    _remaining_a_METHODS[key] = namespace[method_name]
    return namespace[method_name]

async def _remaining_a_read_value(ref):
    value = getattr(ref, 'value', None)
    if value is not None:
        return await value()
    return await ref.raw()

def _remaining_a_mask_inputs(count: int):
    inputs = []
    for index in range(1, count + 1):
        inputs.extend([_remaining_a_io.Conditioning.Input(f'positive_{index}'), _remaining_a_io.Conditioning.Input(f'negative_{index}')])
    inputs.extend((_remaining_a_io.Mask.Input(f'mask_{index}') for index in range(1, count + 1)))
    inputs.extend((_remaining_a_io.Float.Input(f'mask_{index}_strength', default=1.0, min=0.0, max=10.0, step=0.01) for index in range(1, count + 1)))
    inputs.append(_remaining_a_io.Combo.Input('set_cond_area', options=['default', 'mask bounds'], default='default'))
    return inputs

class _remaining_a_ConditioningSetMaskBase(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    COUNT = 0
    ORIGINAL = ''
    NODE_ID = ''
    DISPLAY_NAME = ''

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id=cls.NODE_ID, display_name=cls.DISPLAY_NAME, category='KJNodes/masking/conditioning', description='Bundles multiple conditioning mask and combine nodes into one, with the same behavior as ComfyUI native nodes.', inputs=_remaining_a_mask_inputs(cls.COUNT), outputs=[_remaining_a_io.Conditioning.Output('combined_positive'), _remaining_a_io.Conditioning.Output('combined_negative')])

    @classmethod
    async def execute(cls, **kwargs) -> _remaining_a_io.NodeOutput:
        values = dict(kwargs)
        for index in range(1, cls.COUNT + 1):
            values[f'positive_{index}'] = await kwargs[f'positive_{index}'].value()
            values[f'negative_{index}'] = await kwargs[f'negative_{index}'].value()
            values[f'mask_{index}'] = await kwargs[f'mask_{index}'].raw()
        append = _remaining_a_upstream('nodes/nodes.py', cls.ORIGINAL, 'append', helpers=('append_helper',))
        positive, negative = append(None, **values)
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.CondRef.from_value(positive), await _remaining_a_sdk.CondRef.from_value(negative))
_remaining_a_DIMENSION_PRESETS = ['512 x 512 (1:1)', '768 x 512 (1.5:1)', '960 x 512 (1.875:1)', '1024 x 512 (2:1)', '1024 x 576 (1.778:1)', '1536 x 640 (2.4:1)', '1344 x 768 (1.75:1)', '1216 x 832 (1.46:1)', '1152 x 896 (1.286:1)', '1024 x 1024 (1:1)']

class ImageTensorListSecure(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id='ImageTensorListSecure', display_name='🔒 Image Tensor List (secure)', category='KJNodes/image', description='Creates an image list from the input images.', inputs=[_remaining_a_io.Image.Input('image1'), _remaining_a_io.Image.Input('image2')], outputs=[_remaining_a_io.Image.Output('image')])

    @classmethod
    async def execute(cls, image1, image2) -> _remaining_a_io.NodeOutput:
        append = _remaining_a_upstream('nodes/image_nodes.py', 'ImageTensorList', 'append')
        out = append(None, await _remaining_a_read_value(image1), await _remaining_a_read_value(image2))
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.ValueRef.from_value(out[0]))
import ast as _remaining_d_ast
import copy as _remaining_d_copy
import pathlib as _remaining_d_pathlib
import random as _remaining_d_random
from comfy_api.latest import io as _remaining_d_io, sdk as _remaining_d_sdk
from . import _packload as _remaining_d_packload
from ._allocator import _allocating_like as _remaining_d_allocating_like, _allocating_on as _remaining_d_allocating_on, _allocator as _remaining_d_allocator
from ._tensor_utils import common_upscale as _remaining_d_common_upscale, composite as _remaining_d_composite, image_alpha_fix as _remaining_d_image_alpha_fix, repeat_to_batch_size as _remaining_d_repeat_to_batch_size
_remaining_d_PACK_ROOT = _remaining_d_pathlib.Path(_remaining_d_packload.ROOT)
_remaining_d_SOURCE = _remaining_d_PACK_ROOT / 'nodes' / 'image_nodes.py'
_remaining_d_UTILITY_SOURCE = _remaining_d_PACK_ROOT / 'utility' / 'utility.py'
_remaining_d_FONTS = ['FreeMono.ttf', 'FreeMonoBoldOblique.otf', 'TTNorms-Black.otf']
_remaining_d_CODE: dict[tuple, object] = {}

class _remaining_d_FontLookupToContent(_remaining_d_ast.NodeTransformer):

    def __init__(self) -> None:
        self.replacements = 0

    def visit_Call(self, node):
        node = self.generic_visit(node)
        func = node.func
        folder_lookup = isinstance(func, _remaining_d_ast.Attribute) and func.attr == 'get_full_path' and isinstance(func.value, _remaining_d_ast.Name) and (func.value.id == 'folder_paths') and (len(node.args) >= 2) and isinstance(node.args[0], _remaining_d_ast.Constant) and (node.args[0].value == 'kjnodes_fonts')
        bundled_font = isinstance(func, _remaining_d_ast.Attribute) and func.attr == 'join' and isinstance(func.value, _remaining_d_ast.Attribute) and (func.value.attr == 'path') and isinstance(func.value.value, _remaining_d_ast.Name) and (func.value.value.id == 'os') and any((isinstance(arg, _remaining_d_ast.Constant) and arg.value == 'TTNorms-Black.otf' for arg in node.args))
        if not folder_lookup and (not bundled_font):
            return node
        self.replacements += 1
        return _remaining_d_ast.copy_location(_remaining_d_ast.Name(id='font', ctx=_remaining_d_ast.Load()), node)

class _remaining_d_PackHelperRefs(_remaining_d_ast.NodeTransformer):
    REPLACEMENTS = {'comfy.utils.repeat_to_batch_size': 'repeat_to_batch_size', 'node_helpers.image_alpha_fix': 'image_alpha_fix'}

    @staticmethod
    def _dotted_name(node):
        parts = []
        while isinstance(node, _remaining_d_ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, _remaining_d_ast.Name):
            return None
        parts.append(node.id)
        return '.'.join(reversed(parts))

    def visit_Attribute(self, node):
        replacement = self.REPLACEMENTS.get(self._dotted_name(node))
        if replacement is not None:
            return _remaining_d_ast.copy_location(_remaining_d_ast.Name(id=replacement, ctx=_remaining_d_ast.Load()), node)
        return self.generic_visit(node)

def _remaining_d_source_tree(path: _remaining_d_pathlib.Path) -> _remaining_d_ast.Module:
    return _remaining_d_ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

def _remaining_d_method_code(class_name: str, method_name: str, *, font_lookups=0):
    key = ('method', class_name, method_name, font_lookups)
    if key in _remaining_d_CODE:
        return _remaining_d_CODE[key]
    method = None
    for node in _remaining_d_source_tree(_remaining_d_SOURCE).body:
        if isinstance(node, _remaining_d_ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (_remaining_d_ast.FunctionDef, _remaining_d_ast.AsyncFunctionDef)) and item.name == method_name:
                    method = _remaining_d_copy.deepcopy(item)
                    method.decorator_list = []
                    break
    if method is None:
        raise RuntimeError(f'{class_name}.{method_name} not found in upstream {_remaining_d_SOURCE}')
    if font_lookups:
        transform = _remaining_d_FontLookupToContent()
        method = transform.visit(method)
        if transform.replacements != font_lookups:
            raise RuntimeError(f'expected {font_lookups} font lookup(s) in {class_name}.{method_name}, found {transform.replacements}')
    method = _remaining_d_PackHelperRefs().visit(method)
    module = _remaining_d_ast.fix_missing_locations(_remaining_d_ast.Module(body=[method], type_ignores=[]))
    code = compile(module, f'<kjnodes.{class_name}.{method_name}>', 'exec')
    _remaining_d_CODE[key] = code
    return code

def _remaining_d_class_code(*class_names: str):
    key = ('classes', *class_names)
    if key in _remaining_d_CODE:
        return _remaining_d_CODE[key]
    wanted = set(class_names)
    body = [_remaining_d_PackHelperRefs().visit(_remaining_d_copy.deepcopy(node)) for node in _remaining_d_source_tree(_remaining_d_SOURCE).body if isinstance(node, _remaining_d_ast.ClassDef) and node.name in wanted]
    found = {node.name for node in body}
    if found != wanted:
        raise RuntimeError(f'upstream class extraction mismatch: wanted {wanted}, found {found}')
    module = _remaining_d_ast.fix_missing_locations(_remaining_d_ast.Module(body=body, type_ignores=[]))
    code = compile(module, '<kjnodes.image_resize_classes>', 'exec')
    _remaining_d_CODE[key] = code
    return code

def _remaining_d_string_to_color_code():
    key = ('utility', 'string_to_color')
    if key in _remaining_d_CODE:
        return _remaining_d_CODE[key]
    body = [_remaining_d_copy.deepcopy(node) for node in _remaining_d_source_tree(_remaining_d_UTILITY_SOURCE).body if isinstance(node, _remaining_d_ast.FunctionDef) and node.name == 'string_to_color']
    if len(body) != 1:
        raise RuntimeError(f'expected one string_to_color function, found {len(body)}')
    module = _remaining_d_ast.fix_missing_locations(_remaining_d_ast.Module(body=body, type_ignores=[]))
    code = compile(module, '<kjnodes.utility.string_to_color>', 'exec')
    _remaining_d_CODE[key] = code
    return code

class _remaining_d_ImageFont:

    @staticmethod
    def truetype(content, size, *args, **kwargs):
        from io import BytesIO
        from PIL import ImageFont
        if isinstance(content, (bytes, bytearray)):
            content = BytesIO(content)
        return ImageFont.truetype(content, size, *args, **kwargs)

class _remaining_d_ProgressBar:

    def __init__(self, total) -> None:
        self.total = total

    def update(self, amount) -> None:
        return None

def _remaining_d_base_namespace() -> dict:
    import logging
    import math
    import numpy as np
    import torch
    import torch.nn.functional as F
    from PIL import Image, ImageColor, ImageDraw
    namespace = {'F': F, 'Image': Image, 'ImageColor': ImageColor, 'ImageDraw': ImageDraw, 'ImageFont': _remaining_d_ImageFont, 'MAX_RESOLUTION': 16384, 'ProgressBar': _remaining_d_ProgressBar, 'PromptServer': None, 'common_upscale': _remaining_d_common_upscale, 'composite': _remaining_d_composite, 'image_alpha_fix': _remaining_d_image_alpha_fix, 'io': _remaining_d_io, 'logging': logging, 'math': math, 'model_management': _remaining_d_allocator, 'np': np, 'random': _remaining_d_random, 'repeat_to_batch_size': _remaining_d_repeat_to_batch_size, 'torch': torch}
    exec(_remaining_d_string_to_color_code(), namespace)
    return namespace

def _remaining_d_upstream_method(class_name: str, method_name: str, *, font_lookups=0):
    namespace = _remaining_d_base_namespace()
    exec(_remaining_d_method_code(class_name, method_name, font_lookups=font_lookups), namespace)
    return namespace[method_name]

def _remaining_d_image_resize_instance():
    namespace = _remaining_d_base_namespace()
    exec(_remaining_d_class_code('ImageResizeKJv2', 'ImagePadKJ'), namespace)
    return namespace['ImageResizeKJv2']()

def _remaining_d_image_and_mask_execute():
    namespace = _remaining_d_base_namespace()
    exec(_remaining_d_method_code('ImageAndMaskPreview', 'execute'), namespace)
    return namespace['execute']

async def _remaining_d_font_content(name: str) -> bytes:
    assets = _remaining_d_sdk.current_context().assets
    ref = await assets.resolve('kjnodes_fonts', name)
    return await assets.read_bytes(ref)

class AddLabelSecure(_remaining_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls) -> _remaining_d_io.Schema:
        return _remaining_d_io.Schema(node_id='AddLabelSecure', display_name='🔒 Add Label (secure)', category='KJNodes/text', description='Creates a text label beside or over an image batch. Fonts are read through the asset broker.', inputs=[_remaining_d_io.Image.Input('image'), _remaining_d_io.Int.Input('text_x', default=10, min=0, max=4096, step=1), _remaining_d_io.Int.Input('text_y', default=2, min=0, max=4096, step=1), _remaining_d_io.Int.Input('height', default=48, min=-1, max=4096, step=1), _remaining_d_io.Int.Input('font_size', default=32, min=0, max=4096, step=1), _remaining_d_io.String.Input('font_color', default='white'), _remaining_d_io.String.Input('label_color', default='black'), _remaining_d_io.Combo.Input('font', options=_remaining_d_FONTS, default=_remaining_d_FONTS[0]), _remaining_d_io.String.Input('text', default='Text'), _remaining_d_io.Combo.Input('direction', options=['up', 'down', 'left', 'right', 'overlay'], default='up'), _remaining_d_io.String.Input('caption', default='', force_input=True, optional=True)], outputs=[_remaining_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, image, text_x, text_y, height, font_size, font_color, label_color, font, text, direction, caption=None) -> _remaining_d_io.NodeOutput:
        add_label = _remaining_d_upstream_method('AddLabel', 'addlabel', font_lookups=2)
        out = add_label(None, await image.raw(), text_x, text_y, text, height, font_size, font_color, label_color, await _remaining_d_font_content(font), direction, '' if caption is None else caption)
        return _remaining_d_io.NodeOutput(await _remaining_d_sdk.ImageRef._from_raw(out[0]))

class ImageBatchTestPatternSecure(_remaining_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls) -> _remaining_d_io.Schema:
        return _remaining_d_io.Schema(node_id='ImageBatchTestPatternSecure', display_name='🔒 Image Batch Test Pattern (secure)', category='KJNodes/text', description='Generates a batch of numbered images in a brokered font.', inputs=[_remaining_d_io.Int.Input('batch_size', default=1, min=1, max=4096, step=1), _remaining_d_io.Int.Input('start_from', default=0, min=0, max=4096, step=1), _remaining_d_io.Int.Input('text_x', default=256, min=0, max=4096, step=1), _remaining_d_io.Int.Input('text_y', default=256, min=0, max=4096, step=1), _remaining_d_io.Int.Input('width', default=512, min=16, max=4096, step=1), _remaining_d_io.Int.Input('height', default=512, min=16, max=4096, step=1), _remaining_d_io.Combo.Input('font', options=_remaining_d_FONTS, default=_remaining_d_FONTS[0]), _remaining_d_io.Int.Input('font_size', default=255, min=8, max=4096, step=1)], outputs=[_remaining_d_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, batch_size, start_from, text_x, text_y, width, height, font, font_size) -> _remaining_d_io.NodeOutput:
        import torch
        generate = _remaining_d_upstream_method('ImageBatchTestPattern', 'execute', font_lookups=1)
        with _remaining_d_allocating_on(torch.device('cpu'), torch.float32):
            upstream = generate(None, batch_size, await _remaining_d_font_content(font), font_size, start_from, width, height, text_x, text_y)
        return _remaining_d_io.NodeOutput(await _remaining_d_sdk.ImageRef._from_raw(upstream.result[0]))

class ImageResizeKJv2Secure(_remaining_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_d_io.Schema:
        return _remaining_d_io.Schema(node_id='ImageResizeKJv2Secure', display_name='🔒 Image Resize KJ v2 (secure)', category='KJNodes/image', description='Resizes an image and optional mask.', inputs=[_remaining_d_io.Image.Input('image'), _remaining_d_io.Int.Input('width', default=512, min=0, max=16384, step=1), _remaining_d_io.Int.Input('height', default=512, min=0, max=16384, step=1), _remaining_d_io.Combo.Input('upscale_method', options=['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'nvidia_rtx_vsr'], default='nearest-exact'), _remaining_d_io.Combo.Input('keep_proportion', options=['stretch', 'resize', 'pad', 'pad_edge', 'pad_edge_pixel', 'crop', 'pillarbox_blur', 'total_pixels'], default='stretch'), _remaining_d_io.String.Input('pad_color', default='0, 0, 0'), _remaining_d_io.Combo.Input('crop_position', options=['center', 'top', 'bottom', 'left', 'right'], default='center'), _remaining_d_io.Int.Input('divisible_by', default=2, min=0, max=512, step=1), _remaining_d_io.Mask.Input('mask', optional=True), _remaining_d_io.Combo.Input('device', options=['cpu', 'gpu'], default='cpu', optional=True)], outputs=[_remaining_d_io.Image.Output('image', display_name='IMAGE'), _remaining_d_io.Int.Output('width', display_name='width'), _remaining_d_io.Int.Output('height', display_name='height'), _remaining_d_io.Mask.Output('mask', display_name='mask')])

    @classmethod
    async def execute(cls, image, width, height, upscale_method, keep_proportion, pad_color, crop_position, divisible_by, mask=None, device=None) -> _remaining_d_io.NodeOutput:
        image_value = await image.raw()
        mask_value = None if mask is None else await mask.raw()
        with _remaining_d_allocating_like(image_value):
            out = _remaining_d_image_resize_instance().resize(image_value, width, height, keep_proportion, upscale_method, divisible_by, pad_color, crop_position, None, device=device or 'cpu', mask=mask_value)
        return _remaining_d_io.NodeOutput(await _remaining_d_sdk.ImageRef._from_raw(out[0]), out[1], out[2], await _remaining_d_sdk.MaskRef._from_raw(out[3]))

class FastPreviewSecure(_remaining_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'ui')

    @classmethod
    def define_schema(cls) -> _remaining_d_io.Schema:
        return _remaining_d_io.Schema(node_id='FastPreviewSecure', display_name='🔒 Fast Preview (secure)', category='KJNodes/experimental', description='Previews the first image at a bounded resolution.', inputs=[_remaining_d_io.Image.Input('image'), _remaining_d_io.Combo.Input('format', options=['JPEG', 'PNG'], default='JPEG'), _remaining_d_io.Int.Input('max_size', default=768, min=128, max=4096, step=64)], is_output_node=True)

    @classmethod
    async def execute(cls, image, format, max_size) -> _remaining_d_io.NodeOutput:
        import numpy as np
        import torch
        from PIL import Image
        value = await image.raw()
        array = value[0].cpu().mul(255).clamp(0, 255).byte().numpy()
        height, width = array.shape[:2]
        pil_image = Image.fromarray(array)
        if width > max_size or height > max_size:
            scale = max_size / max(width, height)
            pil_image = pil_image.resize((int(width * scale), int(height * scale)), Image.BILINEAR)
        if format == 'JPEG' and pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        preview = torch.from_numpy(np.asarray(pil_image).copy()).float().div(255.0).unsqueeze(0)
        ref = await _remaining_d_sdk.ImageRef._from_raw(preview)
        ui_value = await _remaining_d_sdk.current_context().ui.preview_images(ref)
        ui_value['fast_preview'] = [True]
        return _remaining_d_io.NodeOutput(ui=ui_value)

class PreviewImageOrMaskSecure(_remaining_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'ui')

    @classmethod
    def define_schema(cls) -> _remaining_d_io.Schema:
        return _remaining_d_io.Schema(node_id='PreviewImageOrMaskSecure', display_name='🔒 Preview Image Or Mask (secure)', category='KJNodes/misc', description='Previews an image or mask through the UI broker.', search_aliases=['output'], inputs=[_remaining_d_io.MultiType.Input('input', [_remaining_d_io.Image, _remaining_d_io.Mask])], is_output_node=True)

    @classmethod
    async def execute(cls, input) -> _remaining_d_io.NodeOutput:
        value = await input.raw()
        ui_domain = _remaining_d_sdk.current_context().ui
        if value.ndim == 3:
            ref = await _remaining_d_sdk.MaskRef._from_raw(value)
            ui_value = await ui_domain.preview_mask(ref)
        else:
            ref = await _remaining_d_sdk.ImageRef._from_raw(value)
            ui_value = await ui_domain.preview_images(ref)
        return _remaining_d_io.NodeOutput(ui=ui_value)

class ImageAndMaskPreviewSecure(_remaining_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'ui')

    @classmethod
    def define_schema(cls) -> _remaining_d_io.Schema:
        return _remaining_d_io.Schema(node_id='ImageAndMaskPreviewSecure', display_name='🔒 Image And Mask Preview (secure)', category='KJNodes/masking', description='Previews an image, a mask, or their colorized composite.', inputs=[_remaining_d_io.Float.Input('mask_opacity', default=1.0, min=0.0, max=1.0, step=0.01), _remaining_d_io.String.Input('mask_color', default='255, 255, 255'), _remaining_d_io.Boolean.Input('pass_through', default=False), _remaining_d_io.Image.Input('image', optional=True), _remaining_d_io.Mask.Input('mask', optional=True)], outputs=[_remaining_d_io.Image.Output(display_name='composite')], is_output_node=True)

    @classmethod
    async def execute(cls, mask_opacity, mask_color, pass_through, image=None, mask=None) -> _remaining_d_io.NodeOutput:
        image_value = None if image is None else await image.raw()
        mask_value = None if mask is None else await mask.raw()
        if image_value is None and mask_value is None:
            raise ValueError('ImageAndMaskPreview requires an image or mask')

        class _PreviewSink:
            preview = None

            def save_images(self, preview, *args, **kwargs):
                self.preview = preview
                return {'ui': {}}
        sink = _PreviewSink()
        out = _remaining_d_image_and_mask_execute()(sink, mask_opacity, mask_color, pass_through, image=image_value, mask=mask_value)
        preview = out[0] if pass_through else sink.preview
        ref = await _remaining_d_sdk.ImageRef._from_raw(preview)
        if pass_through:
            return _remaining_d_io.NodeOutput(ref)
        ui_value = await _remaining_d_sdk.current_context().ui.preview_images(ref)
        return _remaining_d_io.NodeOutput(ui=ui_value)
from comfy_api.latest import io as _remaining_h_io, sdk as _remaining_h_sdk

class SaveImageWithAlphaSecure(_remaining_h_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output',)

    @classmethod
    def define_schema(cls) -> _remaining_h_io.Schema:
        return _remaining_h_io.Schema(node_id='SaveImageWithAlphaSecure', display_name='🔒 Save Image With Alpha (secure)', category='KJNodes/image', description='Saves an image and mask as a PNG with the mask as the alpha channel.', inputs=[_remaining_h_io.Image.Input('images'), _remaining_h_io.Mask.Input('mask'), _remaining_h_io.String.Input('filename_prefix', default='ComfyUI')], is_output_node=True)

    @classmethod
    async def execute(cls, images, mask, filename_prefix) -> _remaining_h_io.NodeOutput:
        ui = await _remaining_h_sdk.ctx().output.save_images_with_alpha(images, mask, filename_prefix=filename_prefix, compress_level=4)
        return _remaining_h_io.NodeOutput(ui=ui)

class SaveImageKJSecure(_remaining_h_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output',)

    @classmethod
    def define_schema(cls) -> _remaining_h_io.Schema:
        return _remaining_h_io.Schema(node_id='SaveImageKJSecure', display_name='🔒 Save Image KJ (secure)', category='KJNodes/image', description='Saves input images within the ComfyUI output directory.', inputs=[_remaining_h_io.Image.Input('images', tooltip='The images to save.'), _remaining_h_io.String.Input('filename_prefix', default='ComfyUI', tooltip='The prefix for the file to save. This may include ComfyUI filename formatting.'), _remaining_h_io.String.Input('output_folder', default='output', tooltip='Logical subfolder within the ComfyUI output directory.'), _remaining_h_io.String.Input('caption_file_extension', default='.txt', optional=True, tooltip='The extension for the caption file. Limited to plain-text and data formats.'), _remaining_h_io.String.Input('caption', force_input=True, optional=True, tooltip='String to save beside each image.')], outputs=[_remaining_h_io.String.Output('filename')], is_output_node=True)

    @classmethod
    async def execute(cls, images, filename_prefix, output_folder, caption_file_extension='.txt', caption=None) -> _remaining_h_io.NodeOutput:
        ui = await _remaining_h_sdk.ctx().output.save_images(images, filename_prefix=filename_prefix, subfolder=output_folder, compress_level=4, caption=caption, caption_extension=caption_file_extension)
        records = ui.get('images', [])
        if not records:
            raise RuntimeError('output broker saved no images')
        return _remaining_h_io.NodeOutput(records[-1]['filename'])

class SaveStringKJSecure(_remaining_h_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output',)

    @classmethod
    def define_schema(cls) -> _remaining_h_io.Schema:
        return _remaining_h_io.Schema(node_id='SaveStringKJSecure', display_name='🔒 Save String KJ (secure)', category='KJNodes/misc', description='Saves the input string within the ComfyUI output directory.', inputs=[_remaining_h_io.String.Input('string', force_input=True, tooltip='String to save to a text or data file.'), _remaining_h_io.String.Input('filename_prefix', default='text', tooltip='The prefix for the file to save. This may include ComfyUI filename formatting.'), _remaining_h_io.String.Input('output_folder', default='output', tooltip='Logical subfolder within the ComfyUI output directory.'), _remaining_h_io.String.Input('file_extension', default='.txt', optional=True, tooltip='The extension for the saved file. Limited to plain-text and data formats.')], outputs=[_remaining_h_io.String.Output('filename')], is_output_node=True)

    @classmethod
    async def execute(cls, string, filename_prefix, output_folder, file_extension='.txt') -> _remaining_h_io.NodeOutput:
        filename = await _remaining_h_sdk.ctx().output.save_text(string, filename_prefix=filename_prefix, subfolder=output_folder, extension=file_extension)
        return _remaining_h_io.NodeOutput(filename)
from comfy_api.latest import io as _remaining_p_io

class ImageUpscaleWithModelBatchedSecure(_remaining_p_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls):
        return _remaining_p_io.Schema(node_id='ImageUpscaleWithModelBatchedSecure', display_name='🔒 Image Upscale With Model Batched (secure)', category='KJNodes/image', inputs=[_remaining_p_io.UpscaleModel.Input('upscale_model'), _remaining_p_io.Image.Input('images'), _remaining_p_io.Int.Input('per_batch', default=16, min=1, max=4096, step=1), _remaining_p_io.Float.Input('downscale_ratio', default=1.0, min=0.01, max=1.0, step=0.01, optional=True), _remaining_p_io.Combo.Input('downscale_method', options=['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'], default='lanczos', optional=True), _remaining_p_io.Combo.Input('precision', options=['float32', 'float16', 'bfloat16'], default='float32', optional=True)], outputs=[_remaining_p_io.Image.Output(display_name='images')])

    @classmethod
    async def execute(cls, upscale_model, images, per_batch, downscale_ratio=1.0, downscale_method='lanczos', precision='float32'):
        return _remaining_p_io.NodeOutput(await upscale_model.upscale(images, per_batch=per_batch, downscale_ratio=downscale_ratio, downscale_method=downscale_method, precision=precision))
from comfy_api.latest import io as _remaining_r_io, sdk as _remaining_r_sdk

def _remaining_r_string_to_color(color_string: str):
    import logging
    import numpy as np
    from PIL import ImageColor
    color = [0, 0, 0]
    if ',' in color_string:
        try:
            values = [float(channel.strip()) for channel in color_string.split(',')]
            if all((0 <= value <= 1 for value in values)):
                color = [int(value * 255) for value in values]
            else:
                color = [int(value) for value in values]
        except ValueError:
            logging.warning('Invalid color format: %s. Using default black.', color_string)
    elif color_string.startswith('#') or (color_string.lstrip('#').isalnum() and (not color_string.lstrip('#').replace('.', '', 1).isdigit())):
        stripped = color_string.lstrip('#')
        if len(stripped) in (6, 8) and all((char in '0123456789ABCDEFabcdef' for char in stripped)):
            color = [int(stripped[index:index + 2], 16) for index in range(0, len(stripped), 2)]
        else:
            try:
                color = list(ImageColor.getrgb(color_string))
            except ValueError:
                logging.warning('Invalid color name or hex format: %s. Using default black.', color_string)
    else:
        try:
            value = float(color_string.strip())
            value = int(value * 255) if 0 <= value <= 1 else int(value)
            color = [value, value, value]
        except ValueError:
            logging.warning('Invalid color format: %s. Using default black.', color_string)
    return np.clip(color, 0, 255).tolist()

class LoadAndResizeImageSecure(_remaining_r_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls) -> _remaining_r_io.Schema:
        return _remaining_r_io.Schema(node_id='LoadAndResizeImageSecure', display_name='🔒 Load & Resize Image (secure)', category='KJNodes/image', inputs=[_remaining_r_io.Combo.Input('image', options=[], upload=_remaining_r_io.UploadType.image, image_folder=_remaining_r_io.FolderType.input), _remaining_r_io.Boolean.Input('resize', default=False), _remaining_r_io.Int.Input('width', default=512, min=0, max=16384, step=8), _remaining_r_io.Int.Input('height', default=512, min=0, max=16384, step=8), _remaining_r_io.Int.Input('repeat', default=1, min=1, max=4096, step=1), _remaining_r_io.Boolean.Input('keep_proportion', default=False), _remaining_r_io.Int.Input('divisible_by', default=2, min=0, max=512, step=1), _remaining_r_io.Combo.Input('mask_channel', options=['alpha', 'red', 'green', 'blue'], default='alpha'), _remaining_r_io.String.Input('background_color', default='', tooltip='Fills transparent pixels with this color.')], outputs=[_remaining_r_io.Image.Output('image'), _remaining_r_io.Mask.Output('mask'), _remaining_r_io.Int.Output('width'), _remaining_r_io.Int.Output('height'), _remaining_r_io.String.Output('image_name')])

    @classmethod
    async def execute(cls, image, resize, width, height, repeat, keep_proportion, divisible_by, mask_channel, background_color) -> _remaining_r_io.NodeOutput:
        from io import BytesIO
        import numpy as np
        import torch
        from PIL import Image, ImageOps, ImageSequence
        assets = _remaining_r_sdk.ctx().assets
        asset = await assets.resolve('input', image)
        content = await assets.read_bytes(asset)
        with Image.open(BytesIO(content)) as source:
            source_format = source.format
            loaded = ImageOps.exif_transpose(source)
            if background_color:
                color = _remaining_r_string_to_color(background_color)
                background = tuple(color + ([255] if len(color) == 3 else []))
            else:
                background = None
            source_width, source_height = loaded.size
            if resize:
                if keep_proportion:
                    ratio = min(width / source_width, height / source_height)
                    width = round(source_width * ratio)
                    height = round(source_height * ratio)
                else:
                    width = source_width if width == 0 else width
                    height = source_height if height == 0 else height
                if divisible_by > 1:
                    width -= width % divisible_by
                    height -= height % divisible_by
            else:
                width, height = (source_width, source_height)
            output_images = []
            output_masks = []
            first_size = None
            for raw_frame in ImageSequence.Iterator(loaded):
                frame = ImageOps.exif_transpose(raw_frame)
                if frame.mode == 'I':
                    frame = frame.point(lambda value: value * (1 / 255))
                if frame.mode == 'P' or 'A' in frame.getbands():
                    frame = frame.convert('RGBA')
                alpha_mask = None
                if 'A' in frame.getbands() and background is not None:
                    alpha = np.asarray(frame.getchannel('A'), dtype=np.float32)
                    alpha_mask = 1.0 - torch.from_numpy(alpha / 255.0)
                    frame = Image.alpha_composite(Image.new('RGBA', frame.size, background), frame)
                rgb = frame.convert('RGB')
                if first_size is None:
                    first_size = rgb.size
                if rgb.size != first_size:
                    continue
                if resize:
                    rgb = rgb.resize((width, height), Image.Resampling.BILINEAR)
                image_array = np.asarray(rgb, dtype=np.float32) / 255.0
                output_images.append(torch.from_numpy(image_array)[None])
                channel = mask_channel[0].upper()
                if channel in frame.getbands():
                    mask_frame = frame
                    if resize:
                        mask_frame = frame.resize((width, height), Image.Resampling.BILINEAR)
                    mask_array = np.asarray(mask_frame.getchannel(channel), dtype=np.float32)
                    mask = torch.from_numpy(mask_array / 255.0)
                    if channel == 'A' and alpha_mask is not None:
                        mask = alpha_mask
                    elif channel == 'A':
                        mask = 1.0 - mask
                else:
                    mask = torch.zeros((1, 64, 64), dtype=torch.float32)
                output_masks.append(mask.unsqueeze(0))
        if len(output_images) > 1 and source_format != 'MPO':
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]
            if repeat > 1:
                output_image = output_image.repeat(repeat, 1, 1, 1)
                output_mask = output_mask.repeat(repeat, 1, 1)
        return _remaining_r_io.NodeOutput(await _remaining_r_sdk.ImageRef._from_raw(output_image), await _remaining_r_sdk.MaskRef._from_raw(output_mask), width, height, image)
import numpy as _remaining_v_np
import torch as _remaining_v_torch
from PIL import Image as _remaining_v_Image
from comfy_api.latest import io as _remaining_v_io, sdk as _remaining_v_sdk

class PreviewAnimationSecure(_remaining_v_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'ui')

    @classmethod
    def define_schema(cls):
        return _remaining_v_io.Schema(node_id='PreviewAnimationSecure', display_name='Preview Animation', category='KJNodes/image', is_output_node=True, inputs=[_remaining_v_io.Float.Input('fps', default=8.0, min=0.01, max=1000.0, step=0.01), _remaining_v_io.Image.Input('images', optional=True), _remaining_v_io.Mask.Input('masks', optional=True)])

    @staticmethod
    def _pil_images(images, masks):
        frames = []
        if images is not None:
            for image in images:
                array = _remaining_v_np.clip(image.detach().cpu().numpy() * 255.0, 0, 255).astype(_remaining_v_np.uint8)
                frames.append(_remaining_v_Image.fromarray(array))
        if masks is not None and images is not None:
            for mask in masks:
                if not frames:
                    break
                mask_array = _remaining_v_np.clip(mask.detach().cpu().numpy() * 255.0, 0, 255).astype(_remaining_v_np.uint8)
                mask_image = _remaining_v_Image.fromarray(mask_array, mode='L')
                image = frames.pop(0).convert('RGBA')
                overlay = _remaining_v_Image.new('RGBA', image.size, (255, 255, 255, 255))
                overlay.putalpha(mask_image)
                frames.append(_remaining_v_Image.alpha_composite(image, overlay))
        elif masks is not None:
            for mask in masks:
                array = _remaining_v_np.clip(mask.detach().cpu().numpy() * 255.0, 0, 255).astype(_remaining_v_np.uint8)
                frames.append(_remaining_v_Image.fromarray(array))
        return frames

    @classmethod
    async def execute(cls, fps, images=None, masks=None):
        image_value = await images.raw() if images is not None else None
        mask_value = await masks.raw() if masks is not None else None
        frames = cls._pil_images(image_value, mask_value)
        if not frames:
            return _remaining_v_io.NodeOutput(ui={'images': [], 'animated': (None,), 'text': 'empty'})
        mode = 'RGBA' if images is not None and masks is not None else frames[0].mode
        arrays = [_remaining_v_np.asarray(frame.convert(mode)).copy() for frame in frames]
        tensor = _remaining_v_torch.from_numpy(_remaining_v_np.stack(arrays)).to(_remaining_v_torch.float32).div_(255.0)
        ref = await _remaining_v_sdk.ImageRef._from_raw(tensor)
        ui = await _remaining_v_sdk.ctx().ui.preview_animation(ref, fps=float(fps))
        return _remaining_v_io.NodeOutput(ui=ui)

class FastPreviewBatchSecure(_remaining_v_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('ui',)

    @classmethod
    def define_schema(cls):
        return _remaining_v_io.Schema(node_id='FastPreviewBatchSecure', display_name='Fast Preview Batch', category='KJNodes/experimental', description='Encodes an image or mask batch as an H.264 detail stream and a tiled JPEG for the interactive grid.', is_output_node=True, inputs=[_remaining_v_io.MultiType.Input('input', [_remaining_v_io.Image, _remaining_v_io.Mask]), _remaining_v_io.Int.Input('max_thumb_size', default=512, min=512, max=1024, step=8), _remaining_v_io.Int.Input('crf', default=25, min=0, max=51, step=1), _remaining_v_io.Int.Input('max_grid_frames', default=1024, min=1, max=4096, step=1)])

    @classmethod
    async def execute(cls, input, max_thumb_size, crf, max_grid_frames):
        ui = await _remaining_v_sdk.ctx().ui.preview_batch(input, max_thumb_size=int(max_thumb_size), crf=int(crf), max_grid_frames=int(max_grid_frames))
        return _remaining_v_io.NodeOutput(ui=ui)
import ast as _video_components_ast
import copy as _video_components_copy
import pathlib as _video_components_pathlib
from io import BytesIO as _video_components_BytesIO
from comfy_api.latest import io as _video_components_io, sdk as _video_components_sdk
from . import _packload as _video_components_packload
from ._tensor_utils import common_upscale as _video_components_common_upscale
_video_components_RESIZE_PARAMS = None
_video_components_IMAGE_PAD = None

def _video_components_source_path() -> _video_components_pathlib.Path:
    return _video_components_pathlib.Path(_video_components_packload.ROOT) / 'nodes' / 'image_nodes.py'

def _video_components_compute_resize_params(mode, position, width, height, src_w, src_h):
    global _video_components_RESIZE_PARAMS
    if _video_components_RESIZE_PARAMS is None:
        path = _video_components_source_path()
        tree = _video_components_ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        source_class = next((node for node in tree.body if isinstance(node, _video_components_ast.ClassDef) and node.name == 'EncodeVideoComponents'))
        method = next((_video_components_copy.deepcopy(node) for node in source_class.body if isinstance(node, _video_components_ast.FunctionDef) and node.name == '_compute_resize_params'))
        method.decorator_list = []
        namespace = {'math': __import__('math')}
        module = _video_components_ast.fix_missing_locations(_video_components_ast.Module(body=[method], type_ignores=[]))
        exec(compile(module, f'<kjnodes:{path}>', 'exec'), namespace)
        _video_components_RESIZE_PARAMS = namespace['_compute_resize_params']
    return _video_components_RESIZE_PARAMS(mode, position, width, height, src_w, src_h)

def _video_components_image_pad():
    global _video_components_IMAGE_PAD
    if _video_components_IMAGE_PAD is None:
        import logging
        from typing import List
        import numpy as np
        import torch
        import torch.nn.functional as F
        from PIL import ImageColor
        image_path = _video_components_source_path()
        image_tree = _video_components_ast.parse(image_path.read_text(encoding='utf-8'), filename=str(image_path))
        image_class = next((node for node in image_tree.body if isinstance(node, _video_components_ast.ClassDef) and node.name == 'ImagePadKJ'))
        pad = next((_video_components_copy.deepcopy(node) for node in image_class.body if isinstance(node, _video_components_ast.FunctionDef) and node.name == 'pad'))
        pad.decorator_list = []
        utility_path = image_path.parents[1] / 'utility' / 'utility.py'
        utility_tree = _video_components_ast.parse(utility_path.read_text(encoding='utf-8'), filename=str(utility_path))
        string_to_color = next((_video_components_copy.deepcopy(node) for node in utility_tree.body if isinstance(node, _video_components_ast.FunctionDef) and node.name == 'string_to_color'))
        string_to_color.decorator_list = []
        namespace = {'F': F, 'ImageColor': ImageColor, 'List': List, 'common_upscale': _video_components_common_upscale, 'logging': logging, 'np': np, 'torch': torch}
        module = _video_components_ast.fix_missing_locations(_video_components_ast.Module(body=[string_to_color, pad], type_ignores=[]))
        exec(compile(module, f'<kjnodes:{image_path}>', 'exec'), namespace)
        _video_components_IMAGE_PAD = namespace['pad']
    return _video_components_IMAGE_PAD

def _video_components_torch_dtype(name: str):
    import torch
    value = getattr(torch, name, None)
    if value not in {torch.float16, torch.bfloat16, torch.float32, torch.float64}:
        raise TypeError(f'unsupported VAE input dtype {name!r}')
    return value

class EncodeVideoComponentsSecure(_video_components_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _video_components_io.Schema:
        positions = ['center', 'top', 'bottom', 'left', 'right']
        options = [_video_components_io.DynamicCombo.Option(key='stretch', inputs=[]), _video_components_io.DynamicCombo.Option(key='resize', inputs=[]), _video_components_io.DynamicCombo.Option(key='total_pixels', inputs=[]), _video_components_io.DynamicCombo.Option(key='crop', inputs=[_video_components_io.Combo.Input('crop_position', options=positions)]), _video_components_io.DynamicCombo.Option(key='pad', inputs=[_video_components_io.String.Input('pad_color', default='0, 0, 0'), _video_components_io.Combo.Input('pad_position', options=positions)]), _video_components_io.DynamicCombo.Option(key='pad_edge', inputs=[_video_components_io.Combo.Input('pad_position', options=positions)]), _video_components_io.DynamicCombo.Option(key='pad_edge_pixel', inputs=[_video_components_io.Combo.Input('pad_position', options=positions)]), _video_components_io.DynamicCombo.Option(key='pillarbox_blur', inputs=[_video_components_io.Combo.Input('pad_position', options=positions)])]
        return _video_components_io.Schema(node_id='EncodeVideoComponentsSecure', display_name='🔒 Encode Video Components (secure)', category='KJNodes/image', description='Decodes an opaque VIDEO inside the sandbox, then asks the selected VAE handle to encode the resized frames.', inputs=[_video_components_io.Video.Input('video'), _video_components_io.Vae.Input('vae'), _video_components_io.Int.Input('width', default=768, min=0, max=16384, step=2), _video_components_io.Int.Input('height', default=512, min=0, max=16384, step=2), _video_components_io.Int.Input('max_frames', default=0, min=0, max=999999), _video_components_io.Combo.Input('upscale_method', options=['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'], default='lanczos'), _video_components_io.DynamicCombo.Input('keep_proportion', options=options, display_name='Keep Proportion')], outputs=[_video_components_io.Latent.Output('latent'), _video_components_io.Audio.Output('audio'), _video_components_io.Float.Output('fps'), _video_components_io.Int.Output('frame_count')])

    @classmethod
    async def execute(cls, video, vae, width, height, max_frames, upscale_method, keep_proportion) -> _video_components_io.NodeOutput:
        import itertools
        import av
        import numpy as np
        import torch
        encoded = await video.encoded_source()
        source_value = await encoded.value()
        content = source_value['data'].cpu().numpy().tobytes()
        start_time = float(source_value.get('start_time', 0.0))
        duration = float(source_value.get('duration', 0.0))
        target_dtype = _video_components_torch_dtype(await vae.input_dtype())
        mode = keep_proportion['keep_proportion']
        position = keep_proportion.get('crop_position') or keep_proportion.get('pad_position', 'center')
        pad_color = keep_proportion.get('pad_color', '0, 0, 0')
        use_gpu = upscale_method != 'lanczos'
        device = torch.device('mps' if use_gpu and torch.backends.mps.is_available() else 'cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
        with av.open(_video_components_BytesIO(content), mode='r') as container:
            video_stream = container.streams.video[0]
            start_pts = int(start_time / video_stream.time_base)
            end_pts = int((start_time + duration) / video_stream.time_base) if duration else 0
            container.seek(start_pts, stream=video_stream)
            resize_width = resize_height = crop_region = None
            padding = (0, 0, 0, 0)
            frames = []
            for frame in container.decode(video_stream):
                if frame.pts < start_pts:
                    continue
                if duration and frame.pts >= end_pts:
                    break
                if int(max_frames) > 0 and len(frames) >= int(max_frames):
                    break
                if resize_width is None:
                    resize_width, resize_height, crop_region, padding = _video_components_compute_resize_params(mode, position, int(width), int(height), frame.width, frame.height)
                image = torch.from_numpy(frame.to_ndarray(format='rgb24')).to(device=device, dtype=torch.float32).div_(255.0)
                if crop_region is not None:
                    x, y, crop_width, crop_height = crop_region
                    image = image[y:y + crop_height, x:x + crop_width, :]
                image = _video_components_common_upscale(image.unsqueeze(0).movedim(-1, 1), resize_width, resize_height, upscale_method, crop='disabled').movedim(1, -1).squeeze(0).to(dtype=target_dtype, device='cpu')
                frames.append(image)
            frame_rate = video_stream.average_rate if video_stream.average_rate else 1
        stack = torch.stack(frames) if frames else torch.zeros(0, int(height), int(width), 3, dtype=target_dtype)
        pad_left, pad_right, pad_top, pad_bottom = padding
        pillarbox_blur = mode == 'pillarbox_blur'
        if (mode.startswith('pad') or pillarbox_blur) and any((pad_left, pad_right, pad_top, pad_bottom)):
            pad_mode = 'pillarbox_blur' if pillarbox_blur else 'edge' if mode == 'pad_edge' else 'edge_pixel' if mode == 'pad_edge_pixel' else 'color'
            pad = _video_components_image_pad()
            stack, _ = pad(None, stack, pad_left, pad_right, pad_top, pad_bottom, 0, pad_color, pad_mode)
        frame_ref = await _video_components_sdk.ImageRef._from_raw(stack)
        latent, frame_count = await vae.encode_video(frame_ref)
        audio_value = None
        with av.open(_video_components_BytesIO(content), mode='r') as container:
            if len(container.streams.audio):
                audio_stream = container.streams.audio[-1]
                if start_time > 0:
                    audio_start_pts = int(start_time / audio_stream.time_base)
                    container.seek(audio_start_pts, stream=audio_stream)
                audio_frames = []
                resample = av.audio.resampler.AudioResampler(format='fltp').resample
                audio_iterator = itertools.chain.from_iterable(map(resample, container.decode(audio_stream)))
                first_frame = None
                to_skip = 0
                for audio_frame in audio_iterator:
                    offset_seconds = start_time - audio_frame.time
                    to_skip = int(offset_seconds * audio_stream.sample_rate)
                    if to_skip < audio_frame.samples:
                        first_frame = audio_frame
                        break
                if first_frame is not None:
                    audio_frames.append(first_frame.to_ndarray()[..., to_skip:])
                    for audio_frame in audio_iterator:
                        if duration and audio_frame.time > start_time + duration:
                            break
                        audio_frames.append(audio_frame.to_ndarray())
                if audio_frames:
                    audio_data = np.concatenate(audio_frames, axis=1)
                    if duration:
                        audio_data = audio_data[..., :int(duration * audio_stream.sample_rate)]
                    audio_value = {'waveform': torch.from_numpy(audio_data).unsqueeze(0), 'sample_rate': int(audio_stream.sample_rate or 1)}
        audio = None if audio_value is None else await _video_components_sdk.AudioRef.from_value(audio_value)
        return _video_components_io.NodeOutput(latent, audio, float(frame_rate), frame_count)

class DecodeAndSaveVideoSecure(_video_components_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output',)

    @classmethod
    def define_schema(cls) -> _video_components_io.Schema:
        return _video_components_io.Schema(node_id='DecodeAndSaveVideoSecure', display_name='🔒 Decode and Save Video (secure)', category='KJNodes/image', description='Decodes latent video/audio through VAE handles and publishes a confined output without exposing a path.', inputs=[_video_components_io.Latent.Input('video_latent'), _video_components_io.Latent.Input('audio_latent', optional=True), _video_components_io.Float.Input('fps', default=25.0, min=0.0, max=999.0, step=0.01), _video_components_io.String.Input('filename_prefix', default='video/ComfyUI'), _video_components_io.Combo.Input('format', options=['auto', 'mp4'], default='auto'), _video_components_io.Combo.Input('codec', options=['auto', 'h264'], default='auto'), _video_components_io.Vae.Input('video_vae'), _video_components_io.Vae.Input('audio_vae', optional=True), _video_components_io.DynamicCombo.Input('tiling', options=[_video_components_io.DynamicCombo.Option(key='disabled', inputs=[]), _video_components_io.DynamicCombo.Option(key='enabled', inputs=[_video_components_io.Int.Input('tile_size', default=512, min=64, max=4096, step=32), _video_components_io.Int.Input('overlap', default=64, min=0, max=4096, step=32), _video_components_io.Int.Input('temporal_size', default=4096, min=8, max=4096, step=4), _video_components_io.Int.Input('temporal_overlap', default=16, min=4, max=4096, step=4)])])], hidden=[_video_components_io.Hidden.prompt, _video_components_io.Hidden.extra_pnginfo], is_output_node=True)

    @classmethod
    async def execute(cls, video_latent, video_vae, filename_prefix, format, codec, tiling, audio_latent=None, audio_vae=None, fps=25.0) -> _video_components_io.NodeOutput:
        tiled = tiling['tiling'] == 'enabled'
        images = await video_vae.decode_video(video_latent, tiled=tiled, tile_size=tiling.get('tile_size', 512), overlap=tiling.get('overlap', 64), temporal_size=tiling.get('temporal_size', 4096), temporal_overlap=tiling.get('temporal_overlap', 16))
        if audio_latent is not None:
            if audio_vae is None:
                raise ValueError('Audio VAE must be provided if audio latent is provided.')
            audio = await audio_vae.decode_audio(audio_latent)
        else:
            audio = None
        ui_result = await _video_components_sdk.ctx().output.save_video(images, audio=audio, fps=float(fps), filename_prefix=filename_prefix, format=format, codec=codec)
        return _video_components_io.NodeOutput(ui=ui_result)
import ast as _w3_a_ast
import pathlib as _w3_a_pathlib
from contextlib import contextmanager as _w3_a_contextmanager
from comfy_api.latest import io as _w3_a_io, sdk as _w3_a_sdk
from . import _packload as _w3_a_packload
_w3_a_SOURCE = 'nodes/image_nodes.py'
_w3_a_MODULE_HELPERS = ('crossfade', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out', 'easing_functions')
_w3_a_PARSED = None
_w3_a_NAMESPACE = None
_w3_a_METHODS: dict[tuple[str, str], object] = {}

class _w3_a_Placement:
    """`comfy.model_management`'s device getter, answered from an input tensor.

    `tier_audit.py` files `comfy.model_management` under `placement`, a
    capability a guest already has: the host chose a device when it materialized
    the input, so the answer is sitting on the tensor rather than behind a host
    call. `__getattr__` refuses every other member by name, so loading a model
    or freeing VRAM cannot be reached through this by accident and widening the
    surface takes an edit here.
    """

    def __init__(self) -> None:
        self._tensor = None

    @_w3_a_contextmanager
    def bound_to(self, tensor):
        prior, self._tensor = (self._tensor, tensor)
        try:
            yield
        finally:
            self._tensor = prior

    def get_torch_device(self):
        if self._tensor is None:
            raise RuntimeError("placement was asked for outside any materialized input's scope — the guest has nothing to answer from, and guessing a device is exactly the decision it must not make")
        return self._tensor.device

    def __getattr__(self, name):
        raise AttributeError(f'comfy.model_management.{name} is unavailable in a guest. This stand-in answers get_torch_device only, because a materialized input already determines it; {name} is host policy and must not be decided inside the sandbox.')
_w3_a_placement = _w3_a_Placement()

def _w3_a_parsed():
    global _w3_a_PARSED
    if _w3_a_PARSED is None:
        path = _w3_a_pathlib.Path(_w3_a_packload.ROOT, *_w3_a_SOURCE.split('/'))
        if not path.exists():
            raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
        text = path.read_text(encoding='utf-8')
        _w3_a_PARSED = (text, _w3_a_ast.parse(text, filename=str(path)))
    return _w3_a_PARSED

def _w3_a_defines(stmt) -> set[str]:
    if isinstance(stmt, _w3_a_ast.FunctionDef):
        return {stmt.name}
    if isinstance(stmt, _w3_a_ast.Assign):
        return {t.id for t in stmt.targets if isinstance(t, _w3_a_ast.Name)}
    return set()

def _w3_a_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is reached from
    `execute`, inside the guest, never from `define_schema`. `common_upscale` is
    pure tensor math reached through the guest's `comfy.utils` facade — the
    guest-lib capability, which already exists — and not the real module.
    """
    global _w3_a_NAMESPACE
    if _w3_a_NAMESPACE is None:
        import logging
        import math
        import os
        from concurrent.futures import ThreadPoolExecutor
        import torch
        from ._tensor_utils import common_upscale
        ns = {'torch': torch, 'math': math, 'os': os, 'logging': logging, 'ThreadPoolExecutor': ThreadPoolExecutor, 'common_upscale': common_upscale, 'io': _w3_a_io, 'model_management': _w3_a_placement}
        text, tree = _w3_a_parsed()
        wanted = set(_w3_a_MODULE_HELPERS)
        for stmt in tree.body:
            defined = _w3_a_defines(stmt) & wanted
            if not defined:
                continue
            wanted -= defined
            exec(compile(_w3_a_ast.get_source_segment(text, stmt), f"<kjnodes.{'+'.join(sorted(defined))}>", 'exec'), ns)
        if wanted:
            raise RuntimeError(f"upstream {_w3_a_SOURCE} no longer defines {', '.join(sorted(wanted))} — the pack changed shape and this conversion must be revisited")
        _w3_a_NAMESPACE = ns
    return _w3_a_NAMESPACE

def _w3_a_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 5000-line module per dispatch would re-pay that cost every
    time. The methods are extracted undecorated, so the caller supplies the
    leading `self`/`cls` as an ordinary first argument; none of the eight
    touches it.
    """
    key = (class_name, method)
    cached = _w3_a_METHODS.get(key)
    if cached is not None:
        return cached
    text, tree = _w3_a_parsed()
    for node in _w3_a_ast.walk(tree):
        if not (isinstance(node, _w3_a_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_a_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_a_namespace())
            exec(compile(_w3_a_ast.get_source_segment(text, item), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_a_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_a_SOURCE} — the pack changed shape and this conversion must be revisited')
_w3_a_COLOR_MATCH_DESCRIPTION = 'color-matcher enables color transfer across images, which comes in handy for automatic color-grading of photographs, paintings and film sequences as well as light-field and stopmotion corrections. The mappings are Reinhard et al., the Monge-Kantorovich Linearization (MKL) of Pitie et al., and an analytical solution to a Multi-Variate Gaussian Distribution (MVGD) transfer combined with classical histogram matching. https://github.com/hahnec/color-matcher/'
_w3_a_INTERPOLATIONS = ['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out']

class ColorMatchSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='ColorMatchSecure', display_name='🔒 Color Match (secure)', category='KJNodes/image', description=_w3_a_COLOR_MATCH_DESCRIPTION, is_deprecated=True, inputs=[_w3_a_io.Image.Input('image_ref'), _w3_a_io.Image.Input('image_target'), _w3_a_io.Combo.Input('method', options=['mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'], default='mkl'), _w3_a_io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01, optional=True), _w3_a_io.Boolean.Input('multithread', default=True, optional=True)], outputs=[_w3_a_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, image_ref, image_target, method, strength=1.0, multithread=True) -> _w3_a_io.NodeOutput:
        colormatch = _w3_a_upstream('ColorMatch', 'colormatch')
        out = colormatch(None, await image_ref.raw(), await image_target.raw(), method, strength, multithread)
        return _w3_a_io.NodeOutput(await _w3_a_sdk.ImageRef._from_raw(out[0]))

class ColorMatchV2Secure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='ColorMatchV2Secure', display_name='🔒 Color Match V2 (secure)', category='KJNodes/image', description=f"{_w3_a_COLOR_MATCH_DESCRIPTION} The 'reinhard_lab_gpu' method uses Kornia for GPU-accelerated color transfer in Lab color space.", inputs=[_w3_a_io.Image.Input('image_target'), _w3_a_io.Image.Input('image_ref'), _w3_a_io.Combo.Input('method', options=['mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm', 'reinhard_lab_gpu'], default='mkl'), _w3_a_io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01), _w3_a_io.Boolean.Input('multithread', default=True)], outputs=[_w3_a_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, image_target, image_ref, method, strength=1.0, multithread=True) -> _w3_a_io.NodeOutput:
        target, reference = (await image_target.raw(), await image_ref.raw())
        run = _w3_a_upstream('ColorMatchV2', 'execute')
        with _w3_a_placement.bound_to(target):
            out = run(None, target, reference, method, strength, multithread)
        return _w3_a_io.NodeOutput(await _w3_a_sdk.ImageRef._from_raw(out.args[0]))

class CrossFadeImagesSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='CrossFadeImagesSecure', display_name='🔒 Cross Fade Images (secure)', category='KJNodes/image', description='Cross fades images_2 into images_1 over transitioning_frames, starting at transition_start_index, along the chosen easing curve.', inputs=[_w3_a_io.Image.Input('images_1'), _w3_a_io.Image.Input('images_2'), _w3_a_io.Combo.Input('interpolation', options=_w3_a_INTERPOLATIONS), _w3_a_io.Int.Input('transition_start_index', default=1, min=-4096, max=4096, step=1), _w3_a_io.Int.Input('transitioning_frames', default=1, min=0, max=4096, step=1), _w3_a_io.Float.Input('start_level', default=0.0, min=0.0, max=1.0, step=0.01), _w3_a_io.Float.Input('end_level', default=1.0, min=0.0, max=1.0, step=0.01)], outputs=[_w3_a_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images_1, images_2, interpolation, transition_start_index, transitioning_frames, start_level, end_level) -> _w3_a_io.NodeOutput:
        crossfadeimages = _w3_a_upstream('CrossFadeImages', 'crossfadeimages')
        out = crossfadeimages(None, await images_1.raw(), await images_2.raw(), transition_start_index, transitioning_frames, interpolation, start_level, end_level)
        return _w3_a_io.NodeOutput(await _w3_a_sdk.ImageRef._from_raw(out[0]))

class CrossFadeImagesMultiSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='CrossFadeImagesMultiSecure', display_name='🔒 Cross Fade Images Multi (secure)', category='KJNodes/image', description='Joins image batches end to end, cross fading over transitioning_frames between each pair along the chosen easing curve.', inputs=[_w3_a_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w3_a_io.Image.Input('image_1'), _w3_a_io.Combo.Input('interpolation', options=_w3_a_INTERPOLATIONS), _w3_a_io.Int.Input('transitioning_frames', default=1, min=0, max=4096, step=1), _w3_a_io.Image.Input('image_2', optional=True)], outputs=[_w3_a_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, inputcount, image_1, interpolation, transitioning_frames, image_2=None) -> _w3_a_io.NodeOutput:
        images = {'image_1': await image_1.raw()}
        if image_2 is not None:
            images['image_2'] = await image_2.raw()
        crossfadeimages = _w3_a_upstream('CrossFadeImagesMulti', 'crossfadeimages')
        out = crossfadeimages(None, inputcount, transitioning_frames, interpolation, **images)
        return _w3_a_io.NodeOutput(await _w3_a_sdk.ImageRef._from_raw(out[0]))

class GetImageRangeFromBatchSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='GetImageRangeFromBatchSecure', display_name='🔒 Get Image Range From Batch (secure)', category='KJNodes/image', description='Returns a range of images from a batch.', inputs=[_w3_a_io.Int.Input('start_index', default=0, min=-1, max=4096, step=1), _w3_a_io.Int.Input('num_frames', default=1, min=1, max=4096, step=1), _w3_a_io.Image.Input('images', optional=True), _w3_a_io.Mask.Input('masks', optional=True)], outputs=[_w3_a_io.Image.Output(display_name='IMAGE'), _w3_a_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, start_index, num_frames, images=None, masks=None) -> _w3_a_io.NodeOutput:
        imagesfrombatch = _w3_a_upstream('GetImageRangeFromBatch', 'imagesfrombatch')
        chosen_images, chosen_masks = imagesfrombatch(None, start_index, num_frames, None if images is None else await images.raw(), None if masks is None else await masks.raw())
        return _w3_a_io.NodeOutput(None if chosen_images is None else await _w3_a_sdk.ImageRef._from_raw(chosen_images), None if chosen_masks is None else await _w3_a_sdk.MaskRef._from_raw(chosen_masks))

class GetImageSizeAndCountSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='GetImageSizeAndCountSecure', display_name='🔒 Get Image Size And Count (secure)', category='KJNodes/image', description='Returns width, height and batch size of the image, and passes it through unchanged.', inputs=[_w3_a_io.Image.Input('image')], outputs=[_w3_a_io.Image.Output(display_name='image'), _w3_a_io.Int.Output(display_name='width'), _w3_a_io.Int.Output(display_name='height'), _w3_a_io.Int.Output(display_name='count')])

    @classmethod
    async def execute(cls, image) -> _w3_a_io.NodeOutput:
        getsize = _w3_a_upstream('GetImageSizeAndCount', 'getsize')
        returned = getsize(None, await image.raw())
        passed_through, width, height, count = returned['result']
        return _w3_a_io.NodeOutput(await _w3_a_sdk.ImageRef._from_raw(passed_through), width, height, count, ui=returned['ui'])

class GetImagesFromBatchIndexedSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='GetImagesFromBatchIndexedSecure', display_name='🔒 Get Images From Batch Indexed (secure)', category='KJNodes/image', description='Selects and returns the images at the specified indices as an image batch.', inputs=[_w3_a_io.Image.Input('images'), _w3_a_io.String.Input('indexes', default='0, 1, 2', multiline=True)], outputs=[_w3_a_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images, indexes) -> _w3_a_io.NodeOutput:
        indexed = _w3_a_upstream('GetImagesFromBatchIndexed', 'indexedimagesfrombatch')
        out = indexed(None, await images.raw(), indexes)
        return _w3_a_io.NodeOutput(await _w3_a_sdk.ImageRef._from_raw(out[0]))

class GetLatentRangeFromBatchSecure(_w3_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_a_io.Schema:
        return _w3_a_io.Schema(node_id='GetLatentRangeFromBatchSecure', display_name='🔒 Get Latent Range From Batch (secure)', category='KJNodes/latents', description='Returns a range of latents from a batch.', inputs=[_w3_a_io.Latent.Input('latents'), _w3_a_io.Int.Input('start_index', default=0, min=-1, max=4096, step=1), _w3_a_io.Int.Input('num_frames', default=1, min=-1, max=4096, step=1)], outputs=[_w3_a_io.Latent.Output(display_name='LATENT')])

    @classmethod
    async def execute(cls, latents, start_index, num_frames) -> _w3_a_io.NodeOutput:
        latentsfrombatch = _w3_a_upstream('GetLatentRangeFromBatch', 'latentsfrombatch')
        out = latentsfrombatch(None, await latents.value(), start_index, num_frames)
        return _w3_a_io.NodeOutput(await _w3_a_sdk.LatentRef.from_value(out[0]))
import ast as _w3_b_ast
import pathlib as _w3_b_pathlib
from comfy_api.latest import io as _w3_b_io, sdk as _w3_b_sdk
from . import _packload as _w3_b_packload
from ._allocator import _allocator as _w3_b_allocator, _allocating_like as _w3_b_allocating_like
from ._tensor_utils import common_upscale as _w3_b_common_upscale
_w3_b_IMAGE_NODES = 'nodes/image_nodes.py'
_w3_b_HELPERS = ('ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out', 'easing_functions', 'gaussian_blur', 'transition_images')
_w3_b_TREE = None
_w3_b_NAMESPACE = None
_w3_b_METHODS: dict[tuple[str, str], object] = {}

def _w3_b_tree() -> _w3_b_ast.Module:
    """Upstream's module, PARSED — never executed, never imported."""
    global _w3_b_TREE
    if _w3_b_TREE is None:
        path = _w3_b_pathlib.Path(_w3_b_packload.ROOT, *_w3_b_IMAGE_NODES.split('/'))
        if not path.exists():
            raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
        _w3_b_TREE = _w3_b_ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return _w3_b_TREE

def _w3_b_placement():
    return _w3_b_allocator

def _w3_b_placement_scope(tensor):
    """Bind the stand-in to an input's own placement for the duration of a call.

    A no-op where `_placement()` returned the genuine module, which never
    consults it.
    """
    return _w3_b_allocating_like(tensor)

def _w3_b_namespace() -> dict:
    """Every name an extracted body is allowed to see.

    Built lazily and called only from `execute`, inside the guest — never from
    `define_schema`, which runs in the HOST process and must not touch the pack.
    """
    global _w3_b_NAMESPACE
    if _w3_b_NAMESPACE is None:
        import logging
        import math
        import torch
        import torch.nn.functional as F
        ns = {'torch': torch, 'F': F, 'math': math, 'logging': logging, 'common_upscale': _w3_b_common_upscale, 'model_management': _w3_b_placement()}
        by_name = {}
        for node in _w3_b_tree().body:
            if isinstance(node, _w3_b_ast.FunctionDef) and node.name in _w3_b_HELPERS:
                by_name[node.name] = node
            elif isinstance(node, _w3_b_ast.Assign):
                for target in node.targets:
                    if isinstance(target, _w3_b_ast.Name) and target.id in _w3_b_HELPERS:
                        by_name[target.id] = node
        missing = [name for name in _w3_b_HELPERS if name not in by_name]
        if missing:
            raise RuntimeError(f"upstream {_w3_b_IMAGE_NODES} no longer defines {', '.join(missing)} — the pack changed shape and this conversion must be revisited")
        exec(compile(_w3_b_ast.Module(body=[by_name[name] for name in _w3_b_HELPERS], type_ignores=[]), f'<kjnodes.{_w3_b_IMAGE_NODES}>', 'exec'), ns)
        _w3_b_NAMESPACE = ns
    return _w3_b_NAMESPACE

def _w3_b_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached: a guest serves node after node from the same pack, and re-parsing a
    5000-line module per dispatch would re-pay that cost every time. The methods
    are plain undecorated instance methods, so the caller supplies `self` as an
    ordinary first argument; none of the eight uses it.
    """
    cached = _w3_b_METHODS.get((class_name, method))
    if cached is not None:
        return cached
    for node in _w3_b_tree().body:
        if not (isinstance(node, _w3_b_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_b_ast.FunctionDef) and item.name == method):
                continue
            if item.decorator_list:
                raise RuntimeError(f'{class_name}.{method} grew a decorator upstream; it can no longer be lifted out of its class unchanged')
            ns = dict(_w3_b_namespace())
            exec(compile(_w3_b_ast.Module(body=[item], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_b_METHODS[class_name, method] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_b_IMAGE_NODES} — the pack changed shape and this conversion must be revisited')

async def _w3_b_materialized(refs: dict) -> dict:
    """The dynamic `image_N` slots, as tensors.

    `accept_all_inputs` hands over whatever the prompt wired, so a value is
    turned into a tensor only when it actually is a ref; anything that already
    crossed as plain data is forwarded untouched.
    """
    return {name: await value.raw() if isinstance(value, _w3_b_sdk.TensorRef) else value for name, value in refs.items()}

class GetLatentSizeAndCountSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='GetLatentSizeAndCountSecure', display_name='🔒 Get Latent Size And Count (secure)', category='KJNodes/image', description='Returns latent tensor dimensions, and passes the latent through unchanged.', inputs=[_w3_b_io.Latent.Input('latent')], outputs=[_w3_b_io.Latent.Output(display_name='latent'), _w3_b_io.Int.Output(display_name='batch_size'), _w3_b_io.Int.Output(display_name='channels'), _w3_b_io.Int.Output(display_name='frames'), _w3_b_io.Int.Output(display_name='height'), _w3_b_io.Int.Output(display_name='width')])

    @classmethod
    async def execute(cls, latent) -> _w3_b_io.NodeOutput:
        getsize = _w3_b_upstream('GetLatentSizeAndCount', 'getsize')
        returned = getsize(None, await latent.value())
        passthrough, *dims = returned['result']
        return _w3_b_io.NodeOutput(await _w3_b_sdk.LatentRef.from_value(passthrough), *dims, ui=returned['ui'])

class ImageAddMultiSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageAddMultiSecure', display_name='🔒 Image Add Multi (secure)', category='KJNodes/image', description='Add blends multiple images together. You can set how many inputs the node has, with the inputcount and clicking update.', accept_all_inputs=True, inputs=[_w3_b_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w3_b_io.Image.Input('image_1'), _w3_b_io.Image.Input('image_2'), _w3_b_io.Combo.Input('blending', options=['add', 'subtract', 'multiply', 'difference'], default='add'), _w3_b_io.Float.Input('blend_amount', default=0.5, min=0, max=1, step=0.01)], outputs=[_w3_b_io.Image.Output(display_name='images')])

    @classmethod
    async def execute(cls, inputcount, image_1, image_2, blending, blend_amount, **kwargs) -> _w3_b_io.NodeOutput:
        add = _w3_b_upstream('ImageAddMulti', 'add')
        images = await _w3_b_materialized(kwargs)
        images['image_1'] = await image_1.raw()
        images['image_2'] = await image_2.raw()
        out = add(None, inputcount, blending, blend_amount, **images)
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(out[0]))

class ImageBatchExtendWithOverlapSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageBatchExtendWithOverlapSecure', display_name='🔒 Image Batch Extend With Overlap (secure)', category='KJNodes/image', description='Helper node for video generation extension. First input source and overlap amount to get the starting frames for the extension. Then on another copy of the node provide the newly generated frames and choose how to overlap them.', inputs=[_w3_b_io.Image.Input('source_images', tooltip='The source images to extend'), _w3_b_io.Int.Input('overlap', default=13, min=1, max=4096, step=1, tooltip='Number of overlapping frames between source and new images'), _w3_b_io.Combo.Input('overlap_side', options=['source', 'new_images'], default='source', tooltip='Which side to overlap on'), _w3_b_io.Combo.Input('overlap_mode', options=['cut', 'linear_blend', 'ease_in_out', 'filmic_crossfade', 'perceptual_crossfade'], default='linear_blend', tooltip='Method to use for overlapping frames'), _w3_b_io.Image.Input('new_images', optional=True, tooltip='The new images to extend with')], outputs=[_w3_b_io.Image.Output(display_name='source_images', tooltip='The original source images (passthrough)'), _w3_b_io.Image.Output(display_name='start_images', tooltip='The input images used as the starting point for extension'), _w3_b_io.Image.Output(display_name='extended_images', tooltip='The extended images with overlap, if no new images are provided this will be empty')])

    @classmethod
    async def execute(cls, source_images, overlap, overlap_side, overlap_mode, new_images=None) -> _w3_b_io.NodeOutput:
        extend = _w3_b_upstream('ImageBatchExtendWithOverlap', 'imagesfrombatch')
        source, start, extended = extend(None, await source_images.raw(), overlap, overlap_side, overlap_mode, None if new_images is None else await new_images.raw())
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(source), await _w3_b_sdk.ImageRef._from_raw(start), await _w3_b_sdk.ImageRef._from_raw(extended))

class ImageBatchFilterSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageBatchFilterSecure', display_name='🔒 Image Batch Filter (secure)', category='KJNodes/image', description='Removes empty images from a batch', inputs=[_w3_b_io.Image.Input('images'), _w3_b_io.String.Input('empty_color', default='0, 0, 0'), _w3_b_io.Float.Input('empty_threshold', default=0.01, min=0.0, max=1.0, step=0.01), _w3_b_io.Image.Input('replacement_image', optional=True)], outputs=[_w3_b_io.Image.Output(display_name='images'), _w3_b_io.String.Output(display_name='removed_indices')])

    @classmethod
    async def execute(cls, images, empty_color, empty_threshold, replacement_image=None) -> _w3_b_io.NodeOutput:
        filter_ = _w3_b_upstream('ImageBatchFilter', 'filter')
        filtered, removed = filter_(None, await images.raw(), empty_color, empty_threshold, None if replacement_image is None else await replacement_image.raw())
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(filtered), removed)

class ImageBatchJoinWithTransitionSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageBatchJoinWithTransitionSecure', display_name='🔒 Image Batch Join With Transition (secure)', category='KJNodes/image', description='Transitions between two batches of images, starting at a specified index in the first batch. During the transition, frames from both batches are blended frame-by-frame, so the video keeps playing.', inputs=[_w3_b_io.Image.Input('images_1'), _w3_b_io.Image.Input('images_2'), _w3_b_io.Int.Input('start_index', default=0, min=-10000, max=10000, step=1), _w3_b_io.Combo.Input('interpolation', options=['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out']), _w3_b_io.Combo.Input('transition_type', options=['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade']), _w3_b_io.Int.Input('transitioning_frames', default=1, min=1, max=4096, step=1), _w3_b_io.Float.Input('blur_radius', default=0.0, min=0.0, max=100.0, step=0.1), _w3_b_io.Boolean.Input('reverse', default=False), _w3_b_io.Combo.Input('device', options=['CPU', 'GPU'], default='CPU')], outputs=[_w3_b_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images_1, images_2, start_index, interpolation, transition_type, transitioning_frames, blur_radius, reverse, device) -> _w3_b_io.NodeOutput:
        join = _w3_b_upstream('ImageBatchJoinWithTransition', 'transition_batches')
        first = await images_1.raw()
        with _w3_b_placement_scope(first):
            out = join(None, first, await images_2.raw(), start_index, interpolation, transition_type, transitioning_frames, blur_radius, reverse, device)
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(out[0]))

class ImageBatchMultiSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageBatchMultiSecure', display_name='🔒 Image Batch Multi (secure)', category='KJNodes/image', description='Creates an image batch from multiple images. You can set how many inputs the node has, with the inputcount and clicking update.', accept_all_inputs=True, inputs=[_w3_b_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w3_b_io.Image.Input('image_1'), _w3_b_io.Image.Input('image_2', optional=True)], outputs=[_w3_b_io.Image.Output(display_name='images')])

    @classmethod
    async def execute(cls, inputcount, image_1, image_2=None, **kwargs) -> _w3_b_io.NodeOutput:
        combine = _w3_b_upstream('ImageBatchMulti', 'combine')
        images = await _w3_b_materialized(kwargs)
        images['image_1'] = await image_1.raw()
        if image_2 is not None:
            images['image_2'] = await image_2.raw()
        out = combine(None, inputcount, **images)
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(out[0]))

class ImageBatchRepeatInterleavingSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageBatchRepeatInterleavingSecure', display_name='🔒 Image Batch Repeat Interleaving (secure)', category='KJNodes/image', description='Repeats each image in a batch by the specified number of times. Example batch of 5 images: 0, 1, 2, 3, 4 with repeats 2 becomes batch of 10 images: 0, 0, 1, 1, 2, 2, 3, 3, 4, 4', inputs=[_w3_b_io.Image.Input('images'), _w3_b_io.Int.Input('repeats', default=1, min=1, max=4096), _w3_b_io.Mask.Input('mask', optional=True)], outputs=[_w3_b_io.Image.Output(display_name='IMAGE'), _w3_b_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, images, repeats, mask=None) -> _w3_b_io.NodeOutput:
        repeat = _w3_b_upstream('ImageBatchRepeatInterleaving', 'repeat')
        repeated, out_mask = repeat(None, await images.raw(), repeats, None if mask is None else await mask.raw())
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(repeated), await _w3_b_sdk.MaskRef._from_raw(out_mask))

class ImageConcatFromBatchSecure(_w3_b_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_b_io.Schema:
        return _w3_b_io.Schema(node_id='ImageConcatFromBatchSecure', display_name='🔒 Image Concat From Batch (secure)', category='KJNodes/image', description='Concatenates images from a batch into a grid with a specified number of columns.', inputs=[_w3_b_io.Image.Input('images'), _w3_b_io.Int.Input('num_columns', default=3, min=1, max=255, step=1), _w3_b_io.Boolean.Input('match_image_size', default=False), _w3_b_io.Int.Input('max_resolution', default=4096)], outputs=[_w3_b_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images, num_columns, match_image_size, max_resolution) -> _w3_b_io.NodeOutput:
        concat = _w3_b_upstream('ImageConcatFromBatch', 'concat')
        out = concat(None, await images.raw(), num_columns, match_image_size, max_resolution)
        return _w3_b_io.NodeOutput(await _w3_b_sdk.ImageRef._from_raw(out[0]))
import ast as _w3_c_ast
import pathlib as _w3_c_pathlib
from comfy_api.latest import io as _w3_c_io, sdk as _w3_c_sdk
from . import _packload as _w3_c_packload
_w3_c_MAX_RESOLUTION = 16384
_w3_c_SOURCE = 'nodes/image_nodes.py'
_w3_c_METHODS: dict[tuple[str, str], object] = {}
_w3_c_NAMESPACE = None

def _w3_c_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`. `common_upscale`
    comes through the guest's `comfy.utils` facade — pure tensor math, the
    guest-lib capability — and `string_to_color` out of the pack's own
    guest-clean `utility/utility.py`.
    """
    global _w3_c_NAMESPACE
    if _w3_c_NAMESPACE is None:
        import torch
        import torch.nn.functional as F
        from ._tensor_utils import common_upscale
        _w3_c_NAMESPACE = {'torch': torch, 'F': F, 'common_upscale': common_upscale, 'string_to_color': _w3_c_packload.load('utility/utility.py').string_to_color}
    return _w3_c_NAMESPACE

def _w3_c_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 5000-line module per dispatch would re-pay that cost every
    time. The methods are plain instance methods extracted undecorated, so the
    caller supplies `self` as an ordinary first argument.
    """
    key = (class_name, method)
    cached = _w3_c_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_c_pathlib.Path(_w3_c_packload.ROOT, *_w3_c_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_c_ast.walk(_w3_c_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_c_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_c_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_c_namespace())
            exec(compile(_w3_c_ast.Module(body=[_w3_c_ast.parse(_w3_c_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_c_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_c_SOURCE} — the pack changed shape and this conversion must be revisited')
_w3_c_CROP_AND_RESIZE = None

def _w3_c_crop_and_resize():
    """`ImageCropByMaskAndResize` as an object, because its `crop` needs `self`.

    Every other method in this file ignores `self` and is handed `None`. This
    one calls `self.crop_by_mask(...)` once per batch item, so both methods are
    extracted and hung on a throwaway class; attribute access binds them the
    ordinary way and upstream's own bounding-box helper is what runs.
    """
    global _w3_c_CROP_AND_RESIZE
    if _w3_c_CROP_AND_RESIZE is None:
        _w3_c_CROP_AND_RESIZE = type('ImageCropByMaskAndResize', (), {'crop_by_mask': _w3_c_upstream('ImageCropByMaskAndResize', 'crop_by_mask'), 'crop': _w3_c_upstream('ImageCropByMaskAndResize', 'crop')})()
    return _w3_c_CROP_AND_RESIZE
_w3_c_BboxOut = _w3_c_io.Custom('BBOX')

class ImageCropByMaskSecure(_w3_c_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_c_io.Schema:
        return _w3_c_io.Schema(node_id='ImageCropByMaskSecure', display_name='🔒 Image Crop By Mask (secure)', category='KJNodes/image', description='Crops the input images based on the provided mask.', inputs=[_w3_c_io.Image.Input('image'), _w3_c_io.Mask.Input('mask')], outputs=[_w3_c_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, image, mask) -> _w3_c_io.NodeOutput:
        crop = _w3_c_upstream('ImageCropByMask', 'crop')
        out = crop(None, await image.raw(), await mask.raw())
        return _w3_c_io.NodeOutput(await _w3_c_sdk.ImageRef._from_raw(out[0]))

class ImageCropByMaskAndResizeSecure(_w3_c_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_c_io.Schema:
        return _w3_c_io.Schema(node_id='ImageCropByMaskAndResizeSecure', display_name='🔒 Image Crop By Mask And Resize (secure)', category='KJNodes/image', inputs=[_w3_c_io.Image.Input('image'), _w3_c_io.Mask.Input('mask'), _w3_c_io.Int.Input('base_resolution', default=512, min=0, max=_w3_c_MAX_RESOLUTION, step=8), _w3_c_io.Int.Input('padding', default=0, min=0, max=_w3_c_MAX_RESOLUTION, step=1), _w3_c_io.Int.Input('min_crop_resolution', default=128, min=0, max=_w3_c_MAX_RESOLUTION, step=8), _w3_c_io.Int.Input('max_crop_resolution', default=512, min=0, max=_w3_c_MAX_RESOLUTION, step=8)], outputs=[_w3_c_io.Image.Output(display_name='images'), _w3_c_io.Mask.Output(display_name='masks'), _w3_c_BboxOut.Output(display_name='bbox')])

    @classmethod
    async def execute(cls, image, mask, base_resolution, padding, min_crop_resolution, max_crop_resolution) -> _w3_c_io.NodeOutput:
        images, masks, bbox = _w3_c_crop_and_resize().crop(await image.raw(), await mask.raw(), base_resolution, padding, min_crop_resolution, max_crop_resolution)
        return _w3_c_io.NodeOutput(await _w3_c_sdk.ImageRef._from_raw(images), await _w3_c_sdk.MaskRef._from_raw(masks), bbox)

class ImageCropByMaskBatchSecure(_w3_c_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_c_io.Schema:
        return _w3_c_io.Schema(node_id='ImageCropByMaskBatchSecure', display_name='🔒 Image Crop By Mask Batch (secure)', category='KJNodes/image', description='Crops the input images based on the provided masks.', inputs=[_w3_c_io.Image.Input('image'), _w3_c_io.Mask.Input('masks'), _w3_c_io.Int.Input('width', default=512, min=0, max=_w3_c_MAX_RESOLUTION, step=8), _w3_c_io.Int.Input('height', default=512, min=0, max=_w3_c_MAX_RESOLUTION, step=8), _w3_c_io.Int.Input('padding', default=0, min=0, max=4096, step=1), _w3_c_io.Boolean.Input('preserve_size', default=False), _w3_c_io.String.Input('bg_color', default='0, 0, 0', tooltip='Color as RGB values in range 0-255 or 0.0-1.0, or color name or hex code')], outputs=[_w3_c_io.Image.Output(display_name='images'), _w3_c_io.Mask.Output(display_name='masks')])

    @classmethod
    async def execute(cls, image, masks, width, height, padding, preserve_size, bg_color) -> _w3_c_io.NodeOutput:
        crop = _w3_c_upstream('ImageCropByMaskBatch', 'crop')
        images, out_masks = crop(None, await image.raw(), await masks.raw(), width, height, bg_color, padding, preserve_size)
        return _w3_c_io.NodeOutput(await _w3_c_sdk.ImageRef._from_raw(images), await _w3_c_sdk.MaskRef._from_raw(out_masks))

class ImageGridComposite2x2Secure(_w3_c_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_c_io.Schema:
        return _w3_c_io.Schema(node_id='ImageGridComposite2x2Secure', display_name='🔒 Image Grid Composite 2x2 (secure)', category='KJNodes/image', description='Concatenates the 4 input images into a 2x2 grid.', inputs=[_w3_c_io.Image.Input('image1'), _w3_c_io.Image.Input('image2'), _w3_c_io.Image.Input('image3'), _w3_c_io.Image.Input('image4')], outputs=[_w3_c_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, image1, image2, image3, image4) -> _w3_c_io.NodeOutput:
        compositegrid = _w3_c_upstream('ImageGridComposite2x2', 'compositegrid')
        out = compositegrid(None, await image1.raw(), await image2.raw(), await image3.raw(), await image4.raw())
        return _w3_c_io.NodeOutput(await _w3_c_sdk.ImageRef._from_raw(out[0]))

class ImageGridComposite3x3Secure(_w3_c_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_c_io.Schema:
        return _w3_c_io.Schema(node_id='ImageGridComposite3x3Secure', display_name='🔒 Image Grid Composite 3x3 (secure)', category='KJNodes/image', description='Concatenates the 9 input images into a 3x3 grid.', inputs=[_w3_c_io.Image.Input('image1'), _w3_c_io.Image.Input('image2'), _w3_c_io.Image.Input('image3'), _w3_c_io.Image.Input('image4'), _w3_c_io.Image.Input('image5'), _w3_c_io.Image.Input('image6'), _w3_c_io.Image.Input('image7'), _w3_c_io.Image.Input('image8'), _w3_c_io.Image.Input('image9')], outputs=[_w3_c_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, image1, image2, image3, image4, image5, image6, image7, image8, image9) -> _w3_c_io.NodeOutput:
        compositegrid = _w3_c_upstream('ImageGridComposite3x3', 'compositegrid')
        out = compositegrid(None, await image1.raw(), await image2.raw(), await image3.raw(), await image4.raw(), await image5.raw(), await image6.raw(), await image7.raw(), await image8.raw(), await image9.raw())
        return _w3_c_io.NodeOutput(await _w3_c_sdk.ImageRef._from_raw(out[0]))

class ImageGridtoBatchSecure(_w3_c_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_c_io.Schema:
        return _w3_c_io.Schema(node_id='ImageGridtoBatchSecure', display_name='🔒 Image Grid To Batch (secure)', category='KJNodes/image', description='Converts a grid of images to a batch of images.', inputs=[_w3_c_io.Image.Input('image'), _w3_c_io.Int.Input('columns', default=3, min=1, max=8, tooltip='The number of columns in the grid.'), _w3_c_io.Int.Input('rows', default=0, min=1, max=8, tooltip='The number of rows in the grid. Set to 0 for automatic calculation.')], outputs=[_w3_c_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, image, columns, rows) -> _w3_c_io.NodeOutput:
        decompose = _w3_c_upstream('ImageGridtoBatch', 'decompose')
        out = decompose(None, await image.raw(), columns, rows)
        return _w3_c_io.NodeOutput(await _w3_c_sdk.ImageRef._from_raw(out[0]))
import ast as _w3_d_ast
import logging as _w3_d_logging
import pathlib as _w3_d_pathlib
import types as _w3_d_types
from comfy_api.latest import io as _w3_d_io, sdk as _w3_d_sdk
from . import _packload as _w3_d_packload
_w3_d_MAX_RESOLUTION = 16384
_w3_d_IMAGE_NODES = 'nodes/image_nodes.py'
_w3_d_METHODS: dict[tuple[str, str], object] = {}
_w3_d_NAMESPACE = None

def _w3_d_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`. `common_upscale`
    is pure tensor math reached through the guest's `comfy.utils` facade — the
    guest-lib capability, which already exists — and not the real module. `F`
    and `logging` are the names upstream's module scope binds and its methods
    then use without qualification.
    """
    global _w3_d_NAMESPACE
    if _w3_d_NAMESPACE is None:
        import torch
        import torch.nn.functional as F
        from ._tensor_utils import common_upscale
        _w3_d_NAMESPACE = {'torch': torch, 'F': F, 'logging': _w3_d_logging, 'common_upscale': common_upscale, 'string_to_color': _w3_d_packload.load('utility/utility.py').string_to_color}
    return _w3_d_NAMESPACE

def _w3_d_upstream(class_name: str, method: str, **extra):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 5000-line module per dispatch would re-pay that cost every
    time. The methods are plain instance methods extracted undecorated, so the
    caller supplies `self` as an ordinary first argument; none of the seven
    uses it. `extra` supplies the one name a method needs that is neither a
    module nor a helper — see `ImagePadForOutpaintTargetSizeSecure`.
    """
    key = (class_name, method)
    cached = _w3_d_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_d_pathlib.Path(_w3_d_packload.ROOT, *_w3_d_IMAGE_NODES.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_d_ast.walk(_w3_d_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_d_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_d_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_d_namespace(), **extra)
            exec(compile(_w3_d_ast.Module(body=[_w3_d_ast.parse(_w3_d_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_d_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_d_IMAGE_NODES} — the pack changed shape and this conversion must be revisited')

class ImagePassSecure(_w3_d_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImagePassSecure', display_name='🔒 Image Pass (secure)', category='KJNodes/image', description='Passes the image through without modifying it.', inputs=[_w3_d_io.Image.Input('image', optional=True)], outputs=[_w3_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, image=None) -> _w3_d_io.NodeOutput:
        passthrough = _w3_d_upstream('ImagePass', 'passthrough')
        return _w3_d_io.NodeOutput(passthrough(None, image)[0])

class ImageNormalize_Neg1_To_1Secure(_w3_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImageNormalize_Neg1_To_1Secure', display_name='🔒 Image Normalize -1 to 1 (secure)', category='KJNodes/image', description='Normalize the images to be in the range [-1, 1]', inputs=[_w3_d_io.Image.Input('images')], outputs=[_w3_d_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images) -> _w3_d_io.NodeOutput:
        normalize = _w3_d_upstream('ImageNormalize_Neg1_To_1', 'normalize')
        out = normalize(None, await images.raw())
        return _w3_d_io.NodeOutput(await _w3_d_sdk.ImageRef._from_raw(out[0]))

class ImagePadForOutpaintMaskedSecure(_w3_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImagePadForOutpaintMaskedSecure', display_name='🔒 Image Pad For Outpaint Masked (secure)', category='image', inputs=[_w3_d_io.Image.Input('image'), _w3_d_io.Int.Input('left', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=8), _w3_d_io.Int.Input('top', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=8), _w3_d_io.Int.Input('right', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=8), _w3_d_io.Int.Input('bottom', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=8), _w3_d_io.Int.Input('feathering', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Mask.Input('mask', optional=True)], outputs=[_w3_d_io.Image.Output(display_name='IMAGE'), _w3_d_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, image, left, top, right, bottom, feathering, mask=None) -> _w3_d_io.NodeOutput:
        expand = _w3_d_upstream('ImagePadForOutpaintMasked', 'expand_image')
        padded, out_mask = expand(None, await image.raw(), left, top, right, bottom, feathering, None if mask is None else await mask.raw())
        return _w3_d_io.NodeOutput(await _w3_d_sdk.ImageRef._from_raw(padded), await _w3_d_sdk.MaskRef._from_raw(out_mask))

class ImagePadForOutpaintTargetSizeSecure(_w3_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImagePadForOutpaintTargetSizeSecure', display_name='🔒 Image Pad For Outpaint Target Size (secure)', category='image', inputs=[_w3_d_io.Image.Input('image'), _w3_d_io.Int.Input('target_width', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=8), _w3_d_io.Int.Input('target_height', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=8), _w3_d_io.Int.Input('feathering', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Combo.Input('upscale_method', options=['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'], default='nearest-exact'), _w3_d_io.Mask.Input('mask', optional=True)], outputs=[_w3_d_io.Image.Output(display_name='IMAGE'), _w3_d_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, image, target_width, target_height, feathering, upscale_method, mask=None) -> _w3_d_io.NodeOutput:
        expand = _w3_d_upstream('ImagePadForOutpaintTargetSize', 'expand_image', ImagePadForOutpaintMasked=_w3_d_types.SimpleNamespace(expand_image=_w3_d_upstream('ImagePadForOutpaintMasked', 'expand_image')))
        padded, out_mask = expand(None, await image.raw(), target_width, target_height, feathering, upscale_method, None if mask is None else await mask.raw())
        return _w3_d_io.NodeOutput(await _w3_d_sdk.ImageRef._from_raw(padded), await _w3_d_sdk.MaskRef._from_raw(out_mask))

class ImagePrepForICLoraSecure(_w3_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImagePrepForICLoraSecure', display_name='🔒 Image Prep For ICLora (secure)', category='image', inputs=[_w3_d_io.Image.Input('reference_image'), _w3_d_io.Int.Input('output_width', default=1024, min=1, max=4096, step=1), _w3_d_io.Int.Input('output_height', default=1024, min=1, max=4096, step=1), _w3_d_io.Int.Input('border_width', default=0, min=0, max=4096, step=1), _w3_d_io.Image.Input('latent_image', optional=True), _w3_d_io.Mask.Input('latent_mask', optional=True), _w3_d_io.Mask.Input('reference_mask', optional=True)], outputs=[_w3_d_io.Image.Output(display_name='IMAGE'), _w3_d_io.Mask.Output(display_name='MASK')])

    @classmethod
    async def execute(cls, reference_image, output_width, output_height, border_width, latent_image=None, latent_mask=None, reference_mask=None) -> _w3_d_io.NodeOutput:
        expand = _w3_d_upstream('ImagePrepForICLora', 'expand_image')
        padded, padded_mask = expand(None, await reference_image.raw(), output_width, output_height, border_width, None if latent_image is None else await latent_image.raw(), None if reference_mask is None else await reference_mask.raw(), None if latent_mask is None else await latent_mask.raw())
        return _w3_d_io.NodeOutput(await _w3_d_sdk.ImageRef._from_raw(padded), await _w3_d_sdk.MaskRef._from_raw(padded_mask))

class ImageResizeKJSecure(_w3_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImageResizeKJSecure', display_name='🔒 Resize Image (deprecated) (secure)', category='KJNodes/image', description='DEPRECATED!\n\nDue to ComfyUI frontend changes, this node should no longer be used, please check the v2 of the node. This node is only kept to not completely break older workflows.', is_deprecated=True, inputs=[_w3_d_io.Image.Input('image'), _w3_d_io.Int.Input('width', default=512, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Int.Input('height', default=512, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Combo.Input('upscale_method', options=['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'], default='nearest-exact'), _w3_d_io.Boolean.Input('keep_proportion', default=False), _w3_d_io.Int.Input('divisible_by', default=2, min=0, max=512, step=1), _w3_d_io.Image.Input('get_image_size', optional=True), _w3_d_io.Combo.Input('crop', options=['disabled', 'center', 0], default='disabled', optional=True, tooltip='0 will do the default center crop, this is a workaround for the widget order changing with the new frontend, as in old workflows the value of this widget becomes 0 automatically')], outputs=[_w3_d_io.Image.Output(display_name='IMAGE'), _w3_d_io.Int.Output(display_name='width'), _w3_d_io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, image, width, height, upscale_method, keep_proportion, divisible_by, get_image_size=None, crop='disabled') -> _w3_d_io.NodeOutput:
        resize = _w3_d_upstream('ImageResizeKJ', 'resize')
        resized, out_width, out_height = resize(None, await image.raw(), width, height, keep_proportion, upscale_method, divisible_by, None, None, None if get_image_size is None else await get_image_size.raw(), crop)
        return _w3_d_io.NodeOutput(await _w3_d_sdk.ImageRef._from_raw(resized), out_width, out_height)

class ImagePadKJSecure(_w3_d_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_d_io.Schema:
        return _w3_d_io.Schema(node_id='ImagePadKJSecure', display_name='🔒 ImagePad KJ (secure)', category='KJNodes/image', description='Pad the input image and optionally mask with the specified padding.', inputs=[_w3_d_io.Image.Input('image'), _w3_d_io.Int.Input('left', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Int.Input('right', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Int.Input('top', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Int.Input('bottom', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Int.Input('extra_padding', default=0, min=0, max=_w3_d_MAX_RESOLUTION, step=1), _w3_d_io.Combo.Input('pad_mode', options=['edge', 'edge_pixel', 'color', 'pillarbox_blur'], default='edge'), _w3_d_io.String.Input('color', default='0, 0, 0', tooltip='Color as RGB values in range 0-255 or 0.0-1.0, or color name or hex code'), _w3_d_io.Mask.Input('mask', optional=True), _w3_d_io.Int.Input('target_width', default=512, min=0, max=_w3_d_MAX_RESOLUTION, step=1, force_input=True, optional=True), _w3_d_io.Int.Input('target_height', default=512, min=0, max=_w3_d_MAX_RESOLUTION, step=1, force_input=True, optional=True)], outputs=[_w3_d_io.Image.Output(display_name='images'), _w3_d_io.Mask.Output(display_name='masks')])

    @classmethod
    async def execute(cls, image, left, right, top, bottom, extra_padding, pad_mode, color, mask=None, target_width=None, target_height=None) -> _w3_d_io.NodeOutput:
        pad = _w3_d_upstream('ImagePadKJ', 'pad')
        padded, out_masks = pad(None, await image.raw(), left, right, top, bottom, extra_padding, color, pad_mode, None if mask is None else await mask.raw(), target_width, target_height)
        return _w3_d_io.NodeOutput(await _w3_d_sdk.ImageRef._from_raw(padded), await _w3_d_sdk.MaskRef._from_raw(out_masks))
import ast as _w3_e_ast
import pathlib as _w3_e_pathlib
from comfy_api.latest import io as _w3_e_io, sdk as _w3_e_sdk
from . import _packload as _w3_e_packload
_w3_e_MAX_RESOLUTION = 16384
_w3_e_IMAGE_NODES = 'nodes/image_nodes.py'
_w3_e_UTILITY = 'utility/utility.py'
_w3_e_CLASSES: dict[str, type] = {}
_w3_e_NAMESPACE: dict | None = None

def _w3_e_namespace() -> dict:
    """Every name an extracted class is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`. `common_upscale`
    is pure tensor math reached through the guest's `comfy.utils` facade — the
    guest-lib capability, which already exists — and not the real module.
    """
    global _w3_e_NAMESPACE
    if _w3_e_NAMESPACE is None:
        import base64
        import random
        from io import BytesIO
        import numpy as np
        import torch
        import torch.nn.functional as F
        from PIL import Image
        from ._tensor_utils import common_upscale
        _w3_e_NAMESPACE = {'base64': base64, 'random': random, 'BytesIO': BytesIO, 'np': np, 'torch': torch, 'F': F, 'Image': Image, 'common_upscale': common_upscale, 'normalize_bboxes': _w3_e_packload.load(_w3_e_UTILITY).normalize_bboxes, 'io': _w3_e_io}
    return _w3_e_NAMESPACE

def _w3_e_upstream(class_name: str) -> type:
    """Upstream's own `class_name`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 5000-line module per dispatch would re-pay that cost every
    time. The class body is executed as written, so class attributes — which is
    what `ScreencapStream.capture` reaches for through `self` — are present.
    """
    cached = _w3_e_CLASSES.get(class_name)
    if cached is not None:
        return cached
    path = _w3_e_pathlib.Path(_w3_e_packload.ROOT, *_w3_e_IMAGE_NODES.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_e_ast.parse(text, filename=str(path)).body:
        if not (isinstance(node, _w3_e_ast.ClassDef) and node.name == class_name):
            continue
        ns = dict(_w3_e_namespace())
        exec(compile(_w3_e_ast.Module(body=[_w3_e_ast.parse(_w3_e_ast.get_source_segment(text, node)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}>', 'exec'), ns)
        _w3_e_CLASSES[class_name] = ns[class_name]
        return ns[class_name]
    raise RuntimeError(f'{class_name} not found in upstream {_w3_e_IMAGE_NODES} — the pack changed shape and this conversion must be revisited')
_w3_e_Bbox = _w3_e_io.Custom('BBOX,BOUNDING_BOX')

class ImageUncropByMaskSecure(_w3_e_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_e_io.Schema:
        return _w3_e_io.Schema(node_id='ImageUncropByMaskSecure', display_name='🔒 Image Uncrop By Mask (secure)', category='KJNodes/image', inputs=[_w3_e_io.Image.Input('destination'), _w3_e_io.Image.Input('source'), _w3_e_io.Mask.Input('mask'), _w3_e_Bbox.Input('bbox')], outputs=[_w3_e_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, destination, source, mask, bbox) -> _w3_e_io.NodeOutput:
        out = _w3_e_upstream('ImageUncropByMask')().uncrop(await destination.raw(), await source.raw(), await mask.raw(), bbox)
        return _w3_e_io.NodeOutput(await _w3_e_sdk.ImageRef._from_raw(out[0]))

class InsertLatentToIndexSecure(_w3_e_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_e_io.Schema:
        return _w3_e_io.Schema(node_id='InsertLatentToIndexSecure', display_name='🔒 Insert Latent To Index (secure)', category='KJNodes/latents', description='Inserts a latent at the specified index into the original latent batch.', inputs=[_w3_e_io.Latent.Input('source'), _w3_e_io.Latent.Input('destination'), _w3_e_io.Int.Input('index', default=0, min=-1, max=4096, step=1)], outputs=[_w3_e_io.Latent.Output(display_name='LATENT')])

    @classmethod
    async def execute(cls, source, destination, index) -> _w3_e_io.NodeOutput:
        out = _w3_e_upstream('InsertLatentToIndex')().insert(await source.value(), await destination.value(), index)
        return _w3_e_io.NodeOutput(await _w3_e_sdk.LatentRef.from_value(out[0]))

class RandomImageFromBatchSecure(_w3_e_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_e_io.Schema:
        template = _w3_e_io.MatchType.Template('input_type', [_w3_e_io.Image, _w3_e_io.Mask])
        return _w3_e_io.Schema(node_id='RandomImageFromBatchSecure', display_name='🔒 Random Image From Batch (secure)', category='KJNodes/image', search_aliases=['random', 'mask', 'sequence', 'frame'], description='Picks a sequence of frames from an image or mask batch within a selected index range. At randomness=0 the picks are evenly spaced across the range; at randomness=1 they are uniformly random without replacement; values in between blend linearly. Output is always sorted by batch index. Negative indices count from the end (-1 = last).', inputs=[_w3_e_io.MatchType.Input('input', template=template, tooltip='Image or mask batch to sample from.'), _w3_e_io.Int.Input('start_index', default=0, min=-4096, max=4096, tooltip='Inclusive start of the sampling range. Negative values count from the end.'), _w3_e_io.Int.Input('end_index', default=-1, min=-4096, max=4096, tooltip='Inclusive end of the sampling range. -1 means the last frame.'), _w3_e_io.Int.Input('num_frames', default=1, min=1, max=4096, tooltip='How many frames to pick from the range.'), _w3_e_io.Float.Input('randomness', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='0 = evenly spaced across the range, 1 = uniformly random without replacement, in-between = linear blend (jittered even spacing).'), _w3_e_io.Int.Input('min_distance', default=0, min=0, max=4096, tooltip='Minimum gap (in frames) between consecutive picks. 0 = no minimum. Picks are pushed forward to satisfy this; later picks may clamp to the range end.'), _w3_e_io.Int.Input('max_distance', default=0, min=0, max=4096, tooltip='Maximum gap (in frames) between consecutive picks. 0 = no maximum. Picks are pulled in to satisfy this, which may compress the sequence toward the start.'), _w3_e_io.Int.Input('seed', default=0, min=0, max=18446744073709551615, step=1, tooltip='Random seed for reproducible sampling. Ignored when randomness is 0.')], outputs=[_w3_e_io.MatchType.Output(template=template, display_name='output')])

    @classmethod
    async def execute(cls, input, start_index, end_index, num_frames, randomness, min_distance, max_distance, seed) -> _w3_e_io.NodeOutput:
        out = _w3_e_upstream('RandomImageFromBatch').execute(await input.raw(), start_index, end_index, num_frames, randomness, min_distance, max_distance, seed)
        return _w3_e_io.NodeOutput(await type(input)._from_raw(out[0]))

class ScreencapStreamSecure(_w3_e_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_e_io.Schema:
        return _w3_e_io.Schema(node_id='ScreencapStreamSecure', display_name='🔒 Screencap Stream (secure)', category='KJNodes/image', description="Captures a frame from a browser screen/window share stream.\nClick 'Start capture' to select a screen or window to share.\nLive preview is shown in the node. Works with auto-queue.\n\nCrop controls:\n- Drag on preview to draw a crop box\n- Drag inside the box to move it\n- Drag edges or corners to resize\n- Shift+drag to lock aspect ratio\n- Right-click or double-click to clear crop", inputs=[_w3_e_io.String.Input('frame_data', default='', multiline=False), _w3_e_io.Int.Input('crop_width', default=1, min=1, max=_w3_e_MAX_RESOLUTION, step=1), _w3_e_io.Int.Input('crop_height', default=1, min=1, max=_w3_e_MAX_RESOLUTION, step=1)], outputs=[_w3_e_io.Image.Output(display_name='image')])

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('NaN')

    @classmethod
    async def execute(cls, frame_data, crop_width, crop_height) -> _w3_e_io.NodeOutput:
        out = _w3_e_upstream('ScreencapStream')().capture(crop_width, crop_height, frame_data)
        return _w3_e_io.NodeOutput(await _w3_e_sdk.ImageRef._from_raw(out[0]))
import ast as _w3_f_ast
import pathlib as _w3_f_pathlib
from contextlib import contextmanager as _w3_f_contextmanager
from comfy_api.latest import io as _w3_f_io, sdk as _w3_f_sdk
from . import _packload as _w3_f_packload
_w3_f_SOURCE = 'nodes/image_nodes.py'
_w3_f_INTERPOLATIONS = ['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out']
_w3_f_TRANSITIONS = ['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade']

class _w3_f_PlacementOnly:
    """Stands in for `comfy.model_management` — placement, and nothing else.

    Upstream asks `get_torch_device()` where to put a frame. The guest does not
    need to ask anyone: the host already decided when it materialized the input,
    so the answer is sitting on the tensor, and taking it from there is stricter
    than asking — an output cannot land on a device its input was not on.

    Refusal is structural. `__getattr__` fires for every name that is not one of
    the three placement reads, so `load_model_gpu` or `unet_dtype` raises with
    the name visible and the surface cannot widen by accretion.
    """
    ALLOWED = ('get_torch_device', 'intermediate_device', 'intermediate_dtype')

    def __init__(self) -> None:
        self._tensor = None

    @_w3_f_contextmanager
    def bound_to(self, tensor):
        prior, self._tensor = (self._tensor, tensor)
        try:
            yield
        finally:
            self._tensor = prior

    def _w3_f_placement(self):
        if self._tensor is None:
            raise RuntimeError("the placement stand-in was asked for a device outside any materialized input's scope — the guest has nothing to answer from, and guessing a device is exactly the decision it must not make")
        return self._tensor

    def get_torch_device(self):
        return self._placement().device

    def intermediate_device(self):
        return self._placement().device

    def intermediate_dtype(self):
        return self._placement().dtype

    def __getattr__(self, name):
        raise AttributeError(f"comfy.model_management.{name} is unavailable in a guest. This stand-in answers placement only ({', '.join(self.ALLOWED)}), because a materialized input already determines it; {name} is host policy and must not be decided inside the sandbox.")

class _w3_f_SilentProgressBar:
    """Upstream's per-frame progress, dropped rather than forwarded.

    `ProgressBar` publishes straight to the host's event channel, which is the
    one thing a guest may not do. The brokered equivalent is `ctx.progress`, and
    it is `async` while upstream's calls are not — so the per-frame granularity
    collapses to the bracket `execute` reports around the whole call.
    """

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def update(self, *_args, **_kwargs) -> None:
        pass
_w3_f_placement = _w3_f_PlacementOnly()
_w3_f_BASE_NAMESPACE = None
_w3_f_METHODS: dict[tuple[str, str], object] = {}

def _w3_f_base_namespace() -> dict:
    """Every name an extracted body may see that upstream's module scope bound.

    Built lazily and only from `execute`, inside the guest — never from
    `define_schema`, which runs in the host process.
    """
    global _w3_f_BASE_NAMESPACE
    if _w3_f_BASE_NAMESPACE is None:
        import math
        import torch
        import torch.nn.functional as F
        from ._tensor_utils import common_upscale
        _w3_f_BASE_NAMESPACE = {'math': math, 'torch': torch, 'F': F, 'common_upscale': common_upscale, 'model_management': _w3_f_placement, 'ProgressBar': _w3_f_SilentProgressBar}
    return _w3_f_BASE_NAMESPACE

def _w3_f_module_bindings(tree: _w3_f_ast.Module) -> dict[str, tuple[int, _w3_f_ast.stmt]]:
    """Upstream's module-level names, each with its position in the file.

    Functions and assignments only. An `Import` is never a binding here, which
    is what keeps `folder_paths` and friends out of the namespace no matter what
    a body reaches for.
    """
    bindings: dict[str, tuple[int, _w3_f_ast.stmt]] = {}
    for index, stmt in enumerate(tree.body):
        if isinstance(stmt, _w3_f_ast.FunctionDef):
            bindings[stmt.name] = (index, stmt)
        elif isinstance(stmt, _w3_f_ast.Assign):
            for target in stmt.targets:
                if isinstance(target, _w3_f_ast.Name):
                    bindings[target.id] = (index, stmt)
    return bindings

def _w3_f_referenced(node: _w3_f_ast.AST) -> set[str]:
    return {n.id for n in _w3_f_ast.walk(node) if isinstance(n, _w3_f_ast.Name)}

def _w3_f_reachable(seed: _w3_f_ast.AST, bindings: dict[str, tuple[int, _w3_f_ast.stmt]]) -> list[_w3_f_ast.stmt]:
    """The module-level statements `seed` needs, transitively, in source order.

    `transition` calls `transition_images`, which calls `gaussian_blur`;
    `easing_functions` names seven easing functions. Following the references
    rather than listing them means this file holds no copy of upstream's
    structure to drift from.
    """
    needed: dict[int, _w3_f_ast.stmt] = {}
    seen: set[str] = set()
    frontier = _w3_f_referenced(seed) & bindings.keys()
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        index, stmt = bindings[name]
        needed[index] = stmt
        frontier |= (_w3_f_referenced(stmt) & bindings.keys()) - seen
    return [needed[index] for index in sorted(needed)]

def _w3_f_exec_into(text: str, stmt: _w3_f_ast.stmt, namespace: dict, origin: str) -> None:
    source = _w3_f_ast.get_source_segment(text, stmt)
    exec(compile(_w3_f_ast.Module(body=[_w3_f_ast.parse(source).body[0]], type_ignores=[]), origin, 'exec'), namespace)

def _w3_f_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_base_namespace()`.

    Helpers and method share ONE globals dict, which is what lets the lifted
    functions call each other exactly as they do in upstream's module. Cached,
    because a guest serves node after node from the same pack and re-parsing a
    5000-line module per dispatch would re-pay that cost every time. The method
    is extracted undecorated, so the caller passes `self` as an ordinary first
    argument; neither of these two uses it.
    """
    key = (class_name, method)
    cached = _w3_f_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_f_pathlib.Path(_w3_f_packload.ROOT, *_w3_f_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    tree = _w3_f_ast.parse(text, filename=str(path))
    bindings = _w3_f_module_bindings(tree)
    for node in tree.body:
        if not (isinstance(node, _w3_f_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_f_ast.FunctionDef) and item.name == method):
                continue
            origin = f'<kjnodes.{class_name}.{method}>'
            namespace = dict(_w3_f_base_namespace())
            for stmt in [*_w3_f_reachable(item, bindings), item]:
                _w3_f_exec_into(text, stmt, namespace, origin)
            _w3_f_METHODS[key] = namespace[method]
            return namespace[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_f_SOURCE} — the pack changed shape and this conversion must be revisited')

class TransitionImagesInBatchSecure(_w3_f_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_f_io.Schema:
        return _w3_f_io.Schema(node_id='TransitionImagesInBatchSecure', display_name='🔒 Transition Images In Batch (secure)', category='KJNodes/image', description='Creates transitions between images in a batch.', inputs=[_w3_f_io.Image.Input('images'), _w3_f_io.Combo.Input('interpolation', options=_w3_f_INTERPOLATIONS), _w3_f_io.Combo.Input('transition_type', options=_w3_f_TRANSITIONS), _w3_f_io.Int.Input('transitioning_frames', default=1, min=0, max=4096, step=1), _w3_f_io.Float.Input('blur_radius', default=0.0, min=0.0, max=100.0, step=0.1), _w3_f_io.Boolean.Input('reverse', default=False), _w3_f_io.Combo.Input('device', options=['CPU', 'GPU'], default='CPU')], outputs=[_w3_f_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, images, interpolation, transition_type, transitioning_frames, blur_radius, reverse, device) -> _w3_f_io.NodeOutput:
        ctx = _w3_f_sdk.ctx()
        await ctx.progress.update(0.0, 1.0)
        frames = await images.raw()
        transition = _w3_f_upstream('TransitionImagesInBatch', 'transition')
        with _w3_f_placement.bound_to(frames):
            out = transition(None, frames, transitioning_frames, transition_type, interpolation, device, blur_radius, reverse)
        result = await _w3_f_sdk.ImageRef._from_raw(out[0])
        await ctx.progress.update(1.0, 1.0)
        return _w3_f_io.NodeOutput(result)

class TransitionImagesMultiSecure(_w3_f_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_f_io.Schema:
        return _w3_f_io.Schema(node_id='TransitionImagesMultiSecure', display_name='🔒 Transition Images Multi (secure)', category='KJNodes/image', description='Creates transitions between images.', inputs=[_w3_f_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w3_f_io.Image.Input('image_1'), _w3_f_io.Combo.Input('interpolation', options=_w3_f_INTERPOLATIONS), _w3_f_io.Combo.Input('transition_type', options=_w3_f_TRANSITIONS), _w3_f_io.Int.Input('transitioning_frames', default=2, min=2, max=4096, step=1), _w3_f_io.Float.Input('blur_radius', default=0.0, min=0.0, max=100.0, step=0.1), _w3_f_io.Boolean.Input('reverse', default=False), _w3_f_io.Combo.Input('device', options=['CPU', 'GPU'], default='CPU'), _w3_f_io.Image.Input('image_2', optional=True)], outputs=[_w3_f_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, inputcount, image_1, interpolation, transition_type, transitioning_frames, blur_radius, reverse, device, image_2=None) -> _w3_f_io.NodeOutput:
        first = await image_1.raw()
        images = {'image_1': first}
        if image_2 is not None:
            images['image_2'] = await image_2.raw()
        transition = _w3_f_upstream('TransitionImagesMulti', 'transition')
        with _w3_f_placement.bound_to(first):
            out = transition(None, inputcount, transitioning_frames, transition_type, interpolation, device, blur_radius, reverse, **images)
        return _w3_f_io.NodeOutput(await _w3_f_sdk.ImageRef._from_raw(out[0]))
import ast as _w4_a_ast
import pathlib as _w4_a_pathlib
import types as _w4_a_types
from comfy_api.latest import io as _w4_a_io, sdk as _w4_a_sdk
from . import _packload as _w4_a_packload
from ._allocator import _allocator as _w4_a_allocator, _allocating_like as _w4_a_allocating_like
_w4_a_SOURCE = 'nodes/image_nodes.py'
_w4_a_METHODS: dict[tuple[str, str], object] = {}
_w4_a_NAMESPACE = None

class _w4_a_ProgressBar:
    """What upstream's resize loop constructs, and what a guest may not.

    `ProgressBar` posts to the host's event bus; a guest's progress reaches the
    user through the brokered ctx instead, which is why it is absent from the
    guest's `comfy.utils` allowlist. Counting frames into nothing is the honest
    stand-in — the alternative is synthesising a host inside the sandbox to
    obtain a side effect the compute does not depend on.
    """

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def update(self, *_args, **_kwargs) -> None:
        pass

def _w4_a_namespace() -> dict:
    """Every name the extracted methods are allowed to see.

    Deliberately tiny, and deliberately built lazily: this is reached from
    `execute`, inside the guest, never from `define_schema`.
    """
    global _w4_a_NAMESPACE
    if _w4_a_NAMESPACE is None:
        import torch
        import torch.nn.functional as F
        _w4_a_NAMESPACE = {'torch': torch, 'F': F, 'io': _w4_a_io, 'ProgressBar': _w4_a_ProgressBar, 'model_management': _w4_a_allocator}
    return _w4_a_NAMESPACE

def _w4_a_upstream(class_name: str, method: str, **extra):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 5000-line module per dispatch would re-pay that cost every
    time. The methods are extracted undecorated, so the caller supplies the
    leading `self`/`cls` as an ordinary first argument; neither uses it.
    """
    key = (class_name, method)
    cached = _w4_a_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w4_a_pathlib.Path(_w4_a_packload.ROOT, *_w4_a_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w4_a_ast.walk(_w4_a_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w4_a_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w4_a_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w4_a_namespace(), **extra)
            exec(compile(_w4_a_ast.Module(body=[_w4_a_ast.parse(_w4_a_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w4_a_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w4_a_SOURCE} — the pack changed shape and this conversion must be revisited')

def _w4_a_concat_multi():
    """Upstream's `ImageConcatMulti.execute`, plus the class it calls into.

    Its body is a loop over `ImageConcanate.concatenate`, which lives in the
    same module and is read the same way, so the pair is assembled here rather
    than the loop reimplemented around one extracted function.
    """
    return _w4_a_upstream('ImageConcatMulti', 'execute', ImageConcanate=_w4_a_types.SimpleNamespace(concatenate=_w4_a_upstream('ImageConcanate', 'concatenate')))

class ImageConcatMultiSecure(_w4_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w4_a_io.Schema:
        template = _w4_a_io.MatchType.Template('multi_image_or_mask', allowed_types=[_w4_a_io.Image, _w4_a_io.Mask])
        return _w4_a_io.Schema(node_id='ImageConcatMultiSecure', display_name='🔒 Image Concatenate Multi (secure)', category='KJNodes/image', description="Creates an image from multiple images or masks.\nThe output type follows image_1; other inputs are converted to match.\nSlots left unconnected are filled with an empty batch of image_1's shape.", accept_all_inputs=True, inputs=[_w4_a_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w4_a_io.MatchType.Input('image_1', template=template), _w4_a_io.Combo.Input('direction', options=['right', 'down', 'left', 'up'], default='right'), _w4_a_io.Boolean.Input('match_image_size', default=False), _w4_a_io.MultiType.Input('image_2', types=[_w4_a_io.Image, _w4_a_io.Mask], optional=True)], outputs=[_w4_a_io.MatchType.Output(template=template, display_name='output')])

    @classmethod
    async def execute(cls, inputcount, image_1, direction, match_image_size, image_2=None, **kwargs) -> _w4_a_io.NodeOutput:
        first = await image_1.raw()
        second = None if image_2 is None else await image_2.raw()
        extra = {name: await value.raw() if isinstance(value, _w4_a_sdk.TensorRef) else value for name, value in kwargs.items()}
        run = _w4_a_concat_multi()
        with _w4_a_allocating_like(first):
            out = run(None, inputcount, first, direction, match_image_size, image_2=second, **extra)
        concatenated = out.args[0]
        wrap = _w4_a_sdk.MaskRef if concatenated.dim() == 3 else _w4_a_sdk.ImageRef
        return _w4_a_io.NodeOutput(await wrap._from_raw(concatenated))

NODE_CLASS_MAPPINGS = {
    'ImageGrabPILSecure': ImageGrabPILSecure,
    'ScreencapMssSecure': ScreencapMssSecure,
    'WebcamCaptureCV2Secure': WebcamCaptureCV2Secure,
    'InsertImagesToBatchIndexedSecure': InsertImagesToBatchIndexedSecure,
    'MergeImageChannelsSecure': MergeImageChannelsSecure,
    'PadImageBatchInterleavedSecure': PadImageBatchInterleavedSecure,
    'RemapImageRangeSecure': RemapImageRangeSecure,
    'ReplaceImagesInBatchSecure': ReplaceImagesInBatchSecure,
    'ReverseImageBatchSecure': ReverseImageBatchSecure,
    'ShuffleImageBatchSecure': ShuffleImageBatchSecure,
    'SplitImageChannelsSecure': SplitImageChannelsSecure,
    'LoadImagesFromFolderKJSecure': LoadImagesFromFolderKJSecure,
    'LoadVideosFromFolderSecure': LoadVideosFromFolderSecure,
    'ImageTensorListSecure': ImageTensorListSecure,
    'AddLabelSecure': AddLabelSecure,
    'ImageBatchTestPatternSecure': ImageBatchTestPatternSecure,
    'ImageResizeKJv2Secure': ImageResizeKJv2Secure,
    'FastPreviewSecure': FastPreviewSecure,
    'PreviewImageOrMaskSecure': PreviewImageOrMaskSecure,
    'ImageAndMaskPreviewSecure': ImageAndMaskPreviewSecure,
    'SaveImageWithAlphaSecure': SaveImageWithAlphaSecure,
    'SaveImageKJSecure': SaveImageKJSecure,
    'SaveStringKJSecure': SaveStringKJSecure,
    'ImageUpscaleWithModelBatchedSecure': ImageUpscaleWithModelBatchedSecure,
    'LoadAndResizeImageSecure': LoadAndResizeImageSecure,
    'PreviewAnimationSecure': PreviewAnimationSecure,
    'FastPreviewBatchSecure': FastPreviewBatchSecure,
    'EncodeVideoComponentsSecure': EncodeVideoComponentsSecure,
    'DecodeAndSaveVideoSecure': DecodeAndSaveVideoSecure,
    'ColorMatchSecure': ColorMatchSecure,
    'ColorMatchV2Secure': ColorMatchV2Secure,
    'CrossFadeImagesSecure': CrossFadeImagesSecure,
    'CrossFadeImagesMultiSecure': CrossFadeImagesMultiSecure,
    'GetImageRangeFromBatchSecure': GetImageRangeFromBatchSecure,
    'GetImageSizeAndCountSecure': GetImageSizeAndCountSecure,
    'GetImagesFromBatchIndexedSecure': GetImagesFromBatchIndexedSecure,
    'GetLatentRangeFromBatchSecure': GetLatentRangeFromBatchSecure,
    'GetLatentSizeAndCountSecure': GetLatentSizeAndCountSecure,
    'ImageAddMultiSecure': ImageAddMultiSecure,
    'ImageBatchExtendWithOverlapSecure': ImageBatchExtendWithOverlapSecure,
    'ImageBatchFilterSecure': ImageBatchFilterSecure,
    'ImageBatchJoinWithTransitionSecure': ImageBatchJoinWithTransitionSecure,
    'ImageBatchMultiSecure': ImageBatchMultiSecure,
    'ImageBatchRepeatInterleavingSecure': ImageBatchRepeatInterleavingSecure,
    'ImageConcatFromBatchSecure': ImageConcatFromBatchSecure,
    'ImageCropByMaskSecure': ImageCropByMaskSecure,
    'ImageCropByMaskAndResizeSecure': ImageCropByMaskAndResizeSecure,
    'ImageCropByMaskBatchSecure': ImageCropByMaskBatchSecure,
    'ImageGridComposite2x2Secure': ImageGridComposite2x2Secure,
    'ImageGridComposite3x3Secure': ImageGridComposite3x3Secure,
    'ImageGridtoBatchSecure': ImageGridtoBatchSecure,
    'ImageNormalize_Neg1_To_1Secure': ImageNormalize_Neg1_To_1Secure,
    'ImagePadForOutpaintMaskedSecure': ImagePadForOutpaintMaskedSecure,
    'ImagePadForOutpaintTargetSizeSecure': ImagePadForOutpaintTargetSizeSecure,
    'ImagePadKJSecure': ImagePadKJSecure,
    'ImagePassSecure': ImagePassSecure,
    'ImagePrepForICLoraSecure': ImagePrepForICLoraSecure,
    'ImageResizeKJSecure': ImageResizeKJSecure,
    'ImageUncropByMaskSecure': ImageUncropByMaskSecure,
    'InsertLatentToIndexSecure': InsertLatentToIndexSecure,
    'RandomImageFromBatchSecure': RandomImageFromBatchSecure,
    'ScreencapStreamSecure': ScreencapStreamSecure,
    'TransitionImagesInBatchSecure': TransitionImagesInBatchSecure,
    'TransitionImagesMultiSecure': TransitionImagesMultiSecure,
    'ImageConcatMultiSecure': ImageConcatMultiSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'ImageGrabPILSecure': '🔒 Image Grab PIL (secure)',
    'ScreencapMssSecure': '🔒 Screencap (mss) (secure)',
    'WebcamCaptureCV2Secure': '🔒 Webcam Capture CV2 (secure)',
    'InsertImagesToBatchIndexedSecure': '🔒 Insert Images To Batch Indexed (secure)',
    'MergeImageChannelsSecure': '🔒 Merge Image Channels (secure)',
    'PadImageBatchInterleavedSecure': '🔒 Pad Image Batch Interleaved (secure)',
    'RemapImageRangeSecure': '🔒 Remap Image Range (secure)',
    'ReplaceImagesInBatchSecure': '🔒 Replace Images In Batch (secure)',
    'ReverseImageBatchSecure': '🔒 Reverse Image Batch (secure)',
    'ShuffleImageBatchSecure': '🔒 Shuffle Image Batch (secure)',
    'SplitImageChannelsSecure': '🔒 Split Image Channels (secure)',
    'LoadImagesFromFolderKJSecure': '🔒 Load Images From Folder KJ (secure)',
    'LoadVideosFromFolderSecure': '🔒 Load Videos From Folder (secure)',
    'ImageTensorListSecure': '🔒 Image Tensor List (secure)',
    'AddLabelSecure': '🔒 Add Label (secure)',
    'ImageBatchTestPatternSecure': '🔒 Image Batch Test Pattern (secure)',
    'ImageResizeKJv2Secure': '🔒 Image Resize KJ v2 (secure)',
    'FastPreviewSecure': '🔒 Fast Preview (secure)',
    'PreviewImageOrMaskSecure': '🔒 Preview Image Or Mask (secure)',
    'ImageAndMaskPreviewSecure': '🔒 Image And Mask Preview (secure)',
    'SaveImageWithAlphaSecure': '🔒 Save Image With Alpha (secure)',
    'SaveImageKJSecure': '🔒 Save Image KJ (secure)',
    'SaveStringKJSecure': '🔒 Save String KJ (secure)',
    'ImageUpscaleWithModelBatchedSecure': '🔒 Image Upscale With Model Batched (secure)',
    'LoadAndResizeImageSecure': '🔒 Load & Resize Image (secure)',
    'PreviewAnimationSecure': 'Preview Animation (Secure V2)',
    'FastPreviewBatchSecure': 'Fast Preview Batch (Secure V2)',
    'EncodeVideoComponentsSecure': '🔒 Encode Video Components (secure)',
    'DecodeAndSaveVideoSecure': '🔒 Decode and Save Video (secure)',
    'ColorMatchSecure': '🔒 Color Match (secure)',
    'ColorMatchV2Secure': '🔒 Color Match V2 (secure)',
    'CrossFadeImagesSecure': '🔒 Cross Fade Images (secure)',
    'CrossFadeImagesMultiSecure': '🔒 Cross Fade Images Multi (secure)',
    'GetImageRangeFromBatchSecure': '🔒 Get Image Range From Batch (secure)',
    'GetImageSizeAndCountSecure': '🔒 Get Image Size And Count (secure)',
    'GetImagesFromBatchIndexedSecure': '🔒 Get Images From Batch Indexed (secure)',
    'GetLatentRangeFromBatchSecure': '🔒 Get Latent Range From Batch (secure)',
    'GetLatentSizeAndCountSecure': '🔒 Get Latent Size And Count (secure)',
    'ImageAddMultiSecure': '🔒 Image Add Multi (secure)',
    'ImageBatchExtendWithOverlapSecure': '🔒 Image Batch Extend With Overlap (secure)',
    'ImageBatchFilterSecure': '🔒 Image Batch Filter (secure)',
    'ImageBatchJoinWithTransitionSecure': '🔒 Image Batch Join With Transition (secure)',
    'ImageBatchMultiSecure': '🔒 Image Batch Multi (secure)',
    'ImageBatchRepeatInterleavingSecure': '🔒 Image Batch Repeat Interleaving (secure)',
    'ImageConcatFromBatchSecure': '🔒 Image Concat From Batch (secure)',
    'ImageCropByMaskSecure': '🔒 Image Crop By Mask (secure)',
    'ImageCropByMaskAndResizeSecure': '🔒 Image Crop By Mask And Resize (secure)',
    'ImageCropByMaskBatchSecure': '🔒 Image Crop By Mask Batch (secure)',
    'ImageGridComposite2x2Secure': '🔒 Image Grid Composite 2x2 (secure)',
    'ImageGridComposite3x3Secure': '🔒 Image Grid Composite 3x3 (secure)',
    'ImageGridtoBatchSecure': '🔒 Image Grid To Batch (secure)',
    'ImageNormalize_Neg1_To_1Secure': '🔒 Image Normalize -1 to 1 (secure)',
    'ImagePadForOutpaintMaskedSecure': '🔒 Image Pad For Outpaint Masked (secure)',
    'ImagePadForOutpaintTargetSizeSecure': '🔒 Image Pad For Outpaint Target Size (secure)',
    'ImagePadKJSecure': '🔒 ImagePad KJ (secure)',
    'ImagePassSecure': '🔒 Image Pass (secure)',
    'ImagePrepForICLoraSecure': '🔒 Image Prep For ICLora (secure)',
    'ImageResizeKJSecure': '🔒 Resize Image (deprecated) (secure)',
    'ImageUncropByMaskSecure': '🔒 Image Uncrop By Mask (secure)',
    'InsertLatentToIndexSecure': '🔒 Insert Latent To Index (secure)',
    'RandomImageFromBatchSecure': '🔒 Random Image From Batch (secure)',
    'ScreencapStreamSecure': '🔒 Screencap Stream (secure)',
    'TransitionImagesInBatchSecure': '🔒 Transition Images In Batch (secure)',
    'TransitionImagesMultiSecure': '🔒 Transition Images Multi (secure)',
    'ImageConcatMultiSecure': '🔒 Image Concatenate Multi (secure)',
}


class ImageConcanate(_w4_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> _w4_a_io.Schema:
        type_template = _w4_a_io.MatchType.Template(
            "image_or_mask",
            allowed_types=[_w4_a_io.Image, _w4_a_io.Mask],
        )
        return _w4_a_io.Schema(
            node_id="ImageConcanate",
            category="KJNodes/image",
            description=(
                "Concatenates image2 to image1 in the specified direction.\n"
                "Both inputs accept IMAGE or MASK; the output type follows "
                "image1.\n"
                "If image2 is a different type than image1 it's converted.\n"
                "When match_image_size is False, the smaller image is "
                "centered and zero-padded."
            ),
            inputs=[
                _w4_a_io.MatchType.Input(
                    "image1", template=type_template
                ),
                _w4_a_io.MultiType.Input(
                    "image2", types=[_w4_a_io.Image, _w4_a_io.Mask]
                ),
                _w4_a_io.Combo.Input(
                    "direction",
                    options=["right", "down", "left", "up"],
                    default="right",
                ),
                _w4_a_io.Boolean.Input("match_image_size", default=True),
            ],
            outputs=[
                _w4_a_io.MatchType.Output(
                    template=type_template, display_name="output"
                )
            ],
        )

    @classmethod
    async def execute(
        cls, image1, image2, direction, match_image_size
    ) -> _w4_a_io.NodeOutput:
        first = await image1.raw()
        second = await image2.raw()
        concatenate = _w4_a_upstream("ImageConcanate", "concatenate")
        with _w4_a_allocating_like(first):
            output = concatenate(
                first, second, direction, match_image_size
            )
        ref_type = (
            _w4_a_sdk.MaskRef if output.dim() == 3 else _w4_a_sdk.ImageRef
        )
        return _w4_a_io.NodeOutput(await ref_type._from_raw(output))


NODE_CLASS_MAPPINGS["ImageConcanate"] = ImageConcanate
NODE_DISPLAY_NAME_MAPPINGS["ImageConcanate"] = "Image Concatenate"
