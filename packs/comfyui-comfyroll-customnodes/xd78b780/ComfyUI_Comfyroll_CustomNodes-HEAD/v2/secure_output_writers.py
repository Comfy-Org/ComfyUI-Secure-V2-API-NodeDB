"""Three bounded managed writers; source pixels/names pack-side, atomic policy host-owned."""
import datetime
import re
import numpy as np
import torch
from PIL import Image
from comfy_api.latest import io, sdk
from .secure_managed_image_lists import _logical, WorkloadError
from .secure_schedules import _guard

def _image_budget(images):
    if not isinstance(images, torch.Tensor) or images.layout != torch.strided or images.ndim != 4:
        raise WorkloadError('Output requires bounded dense BHWC')
    b, h, w, c = images.shape
    if b > 16 or max(h, w) > 4096 or c > 4 or (images.numel() * images.element_size() > 32 * 1024 * 1024) or (b * h * w * max(4, c) * 24 > 128 * 1024 * 1024):
        raise WorkloadError('Output image workload exceeds bound')

def _native_pil_checks(images, file_format=None):
    for image in images:
        pil = Image.fromarray(np.clip(image.cpu().numpy() * 255.0, 0, 255).astype(np.uint8))
        if file_format == 'jpg' and pil.mode not in ('RGB', 'L', 'CMYK'):
            raise OSError('cannot write mode ' + pil.mode + ' as JPEG')

async def _names(folder, prefix):
    names = await sdk.ctx().assets.list(folder, prefix=prefix, recursive=False)
    if len(names) > 4096:
        raise WorkloadError('Output counter catalogue exceeds bound')
    marker = prefix + '/' if prefix else ''
    out = []
    for name in names:
        _logical(name, False)
        if not name.startswith(marker) or '/' in name[len(marker):]:
            raise ValueError('Output counter requires immediate logical filenames')
        out.append(name[len(marker):])
    return out

def _target(prefix, name):
    return _logical(prefix + '/' + name if prefix else name, False)

async def _save(images, filenames, folder, format, *, metadata=False, overwrite=False):
    _native_pil_checks(images, format)
    return await sdk.ctx().output.save_images(await sdk.ImageRef.from_value(images), filenames=filenames, folder_type=folder, overwrite=overwrite, image_format=format, compress_level=4, quality=80 if format == 'webp' else 75, lossless=False, optimize=False, jpeg_subsampling='auto', webp_method=6, tiff_compression='none', save_metadata=metadata)

def _image_counter(names, filename_prefix, filename):
    prefix_len = len(filename_prefix.rsplit('/', 1)[-1])

    def key(name):
        prefix = name[:prefix_len + 1]
        try:
            digits = int(name[prefix_len + 1:].split('_')[0])
        except Exception:
            digits = 0
        return (digits, prefix)
    try:
        return max((a for a in map(key, names) if a[1][:-1] == filename and a[1][-1] == '_'))[0] + 1
    except ValueError:
        return 1

def _xy_counter(names, prefix):
    highest = -1
    for filename in names:
        if filename.startswith(prefix):
            try:
                highest = max(highest, int(re.search('\\d+', filename[len(prefix):]).group()))
            except ValueError:
                continue
    return highest + 1

class CR_ImageOutput(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'output', 'ui')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Output', display_name='💾 CR Image Output', category='🧩 Comfyroll Studio/✨ Essential/📦 Core', is_output_node=True, inputs=[io.Image.Input('images'), io.Combo.Input('output_type', options=['Preview', 'Save', 'UI (no batch)']), io.String.Input('filename_prefix', default='CR'), io.Combo.Input('prefix_presets', options=['None', 'yyyyMMdd']), io.Combo.Input('file_format', options=['png', 'jpg', 'webp', 'tif']), io.Boolean.Input('trigger', default=False, optional=True)], outputs=[io.Boolean.Output(display_name='trigger')], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo])

    @classmethod
    async def execute(cls, images, file_format, prefix_presets, filename_prefix='CR', trigger=False, output_type='Preview', prompt=None, extra_pnginfo=None):
        _guard(dict(file_format=file_format, prefix_presets=prefix_presets, filename_prefix=filename_prefix, trigger=trigger, output_type=output_type))
        _image_budget(images)
        date = datetime.datetime.now()
        if prefix_presets != 'None':
            filename_prefix += '_' + f'{date.year}{date.month:02d}{date.day:02d}'
        if filename_prefix[0] == '_':
            filename_prefix = filename_prefix[1:]
        _logical(filename_prefix, False)
        prefix, separator, filename = filename_prefix.rpartition('/')
        if not separator:
            prefix = ''
            filename = filename_prefix
        folder = 'temp' if output_type == 'Preview' else 'output'
        names = await _names(folder, prefix)
        counter = _image_counter(names, filename_prefix, filename)
        if output_type == 'UI (no batch)':
            _native_pil_checks(images)
            ui = {'images': []} if images.shape[0] == 0 else await sdk.ctx().ui.preview_images(await sdk.ImageRef.from_value(images))
            return io.NodeOutput(trigger, ui=ui)
        {'png': True, 'jpg': True, 'webp': True, 'tif': True}[file_format]
        filenames = [_target(prefix, f'{filename}_{counter + i:05}_.{file_format}') for i in range(images.shape[0])]
        ui = {'images': []} if not filenames else await _save(images, filenames, folder, file_format, metadata=file_format == 'png')
        return io.NodeOutput(trigger, ui=ui)

class CR_XYSaveGridImage(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'output')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR XY Save Grid Image', display_name='📉 CR XY Save Grid Image', category='🧩 Comfyroll Studio/✨ Essential/📉 XY Grid', is_output_node=True, inputs=[io.Combo.Input('mode', options=['Save', 'Preview']), io.Combo.Input('output_folder', options=[], remote=io.RemoteOptions(route='/secure-nodes/assets/output?kind=directory', refresh_button=True)), io.Image.Input('image'), io.String.Input('filename_prefix', default='CR'), io.Combo.Input('file_format', options=['webp', 'jpg', 'png', 'tif']), io.String.Input('output_path', default='', multiline=False, optional=True), io.Boolean.Input('trigger', default=False, optional=True)], outputs=[], hidden=[])

    @classmethod
    async def execute(cls, mode, output_folder, image, file_format, output_path='', filename_prefix='CR', trigger=False):
        _guard(dict(mode=mode, output_folder=output_folder, file_format=file_format, output_path=output_path, filename_prefix=filename_prefix, trigger=trigger))
        if trigger == False:
            return ()
        _image_budget(image)
        prefix = _logical(output_path if output_path != '' else output_folder)
        _logical(filename_prefix, False)
        if '/' in filename_prefix:
            raise ValueError('XY filename prefix requires an immediate logical label')
        if mode not in ('Save', 'Preview'):
            raise ValueError('XY mode must be Save or Preview')
        folder = 'output' if mode == 'Save' else 'temp'
        if folder == 'temp':
            prefix = ''
        counter = _xy_counter(await _names(folder, prefix), filename_prefix)
        selected = image[0].unsqueeze(0)
        {'png': True, 'jpg': True, 'webp': True, 'tif': True}[file_format]
        ui = await _save(selected, [_target(prefix, f'{filename_prefix}_{counter:05}.{file_format}')], folder, file_format)
        return io.NodeOutput(ui=ui)

class CR_OutputFlowFrames(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'output')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Output Flow Frames', display_name='⌨️ CR Output Flow Frames', category='🧩 Comfyroll Studio/🎥 Animation/⌨️ IO', is_output_node=True, inputs=[io.Combo.Input('output_folder', options=[], remote=io.RemoteOptions(route='/secure-nodes/assets/output?kind=directory', refresh_button=True)), io.Image.Input('current_image'), io.String.Input('filename_prefix', default='CR'), io.Int.Input('current_frame', default=0, min=0, max=9999999, force_input=True), io.Image.Input('interpolated_img', optional=True), io.String.Input('output_path', default='', multiline=False, optional=True)], outputs=[], hidden=[])

    @classmethod
    async def execute(cls, output_folder, current_image, current_frame, output_path='', filename_prefix='CR', interpolated_img=None):
        _guard(dict(output_folder=output_folder, current_frame=current_frame, output_path=output_path, filename_prefix=filename_prefix))
        _image_budget(current_image)
        if interpolated_img is not None:
            _image_budget(interpolated_img)
        values = [current_image] + ([] if interpolated_img is None else [interpolated_img])
        if sum((value.numel() * value.element_size() + value.shape[0] * value.shape[1] * value.shape[2] * max(4, value.shape[3]) * 24 for value in values)) > 128 * 1024 * 1024:
            raise WorkloadError('Flow combined image workload exceeds bound')
        prefix = _logical(output_path if output_path != '' else output_folder)
        _logical(filename_prefix, False)
        if '/' in filename_prefix:
            raise ValueError('Flow filename prefix requires an immediate logical label')
        first = current_image[0].unsqueeze(0)
        second = None if interpolated_img is None else interpolated_img[0].unsqueeze(0)
        _native_pil_checks(first)
        if second is not None:
            _native_pil_checks(second)
        first_name = f'{filename_prefix}_{current_frame:05}' + ('_0' if interpolated_img is not None else '') + '.png'
        ui = await _save(first, [_target(prefix, first_name)], 'output', 'png', overwrite=True)
        if interpolated_img is not None:
            await _save(second, [_target(prefix, f'{filename_prefix}_{current_frame:05}_1.png')], 'output', 'png', overwrite=True)
        return io.NodeOutput(ui=ui)
NODE_CLASS_MAPPINGS = {'CR Image Output': CR_ImageOutput, 'CR XY Save Grid Image': CR_XYSaveGridImage, 'CR Output Flow Frames': CR_OutputFlowFrames}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Image Output': '💾 CR Image Output', 'CR XY Save Grid Image': '📉 CR XY Save Grid Image', 'CR Output Flow Frames': '⌨️ CR Output Flow Frames'}
