"""Three bounded managed writers; source pixels/names pack-side, atomic policy host-owned."""
import datetime
import re
import numpy as np
import torch
from PIL import Image
from comfy_api.latest import io, sdk
from . import secure_budget as budget
from .secure_managed_image_lists import _logical, WorkloadError
from .secure_schedules import _guard
PENDING='Comfyroll image writer capability pending: managed temp/output folder, overwrite policy and exact format options must be supported together'

def _image_budget(images):
    if not isinstance(images, torch.Tensor) or images.layout != torch.strided or images.ndim != 4:
        raise WorkloadError('Output requires bounded dense BHWC')
    b, h, w, c = images.shape
    if c>4:raise WorkloadError('Output image channel count is unsupported')
    owned=budget.tensor(images)
    # Pillow validation and encoders process frames individually; they do not
    # allocate 24 bytes per channel for the entire input batch simultaneously.
    return budget.projection(owned,[],h*w*c*(images.element_size()+1))

def _native_pil_checks(images, file_format=None):
    for image in images:
        pil = Image.fromarray(np.clip(image.cpu().numpy() * 255.0, 0, 255).astype(np.uint8))
        if file_format == 'jpg' and pil.mode not in ('RGB', 'L', 'CMYK'):
            raise OSError('cannot write mode ' + pil.mode + ' as JPEG')

async def _names(folder, prefix):
    names = await sdk.ctx().assets.list(folder, prefix=prefix, recursive=False)
    budget.data(names)
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
    raise RuntimeError(PENDING)

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
    def validate_inputs(cls,output_type='Preview',file_format='png'):
        if output_type not in ('Preview','Save','UI (no batch)'):return 'Invalid output_type'
        if file_format not in ('png','jpg','webp','tif'):return 'Invalid file_format'
        if output_type=='UI (no batch)' or output_type=='Preview' and file_format=='png':return True
        return PENDING
    @classmethod
    async def execute(cls, images, file_format, prefix_presets, filename_prefix='CR', trigger=False, output_type='Preview', prompt=None, extra_pnginfo=None):
        validation=cls.validate_inputs(output_type=output_type,file_format=file_format)
        if validation is not True:raise RuntimeError(validation)
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
        # Accepted Preview mapping: the public preview domain emits PNG temp
        # files. Their internal names and compression bytes may differ from
        # V1; format and decoded pixels must remain exact. Save stays pending.
        _native_pil_checks(images)
        ui = {'images': []} if images.shape[0] == 0 else await sdk.ctx().ui.preview_images(await sdk.ImageRef.from_value(images))
        return io.NodeOutput(trigger, ui=ui)

class CR_XYSaveGridImage(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'output')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR XY Save Grid Image', display_name='📉 CR XY Save Grid Image', category='🧩 Comfyroll Studio/✨ Essential/📉 XY Grid', is_output_node=True, inputs=[io.Combo.Input('mode', options=['Save', 'Preview']), io.Combo.Input('output_folder', options=[], remote=io.RemoteOptions(route='/secure-nodes/assets/output?kind=directory', refresh_button=True)), io.Image.Input('image'), io.String.Input('filename_prefix', default='CR'), io.Combo.Input('file_format', options=['webp', 'jpg', 'png', 'tif']), io.String.Input('output_path', default='', multiline=False, optional=True), io.Boolean.Input('trigger', default=False, optional=True)], outputs=[], hidden=[])

    @classmethod
    def validate_inputs(cls,trigger=False):
        return PENDING if trigger!=False else True
    @classmethod
    async def execute(cls, mode, output_folder, image, file_format, output_path='', filename_prefix='CR', trigger=False):
        _guard(dict(mode=mode, output_folder=output_folder, file_format=file_format, output_path=output_path, filename_prefix=filename_prefix, trigger=trigger))
        if trigger == False:
            return ()
        raise RuntimeError(PENDING)

class CR_OutputFlowFrames(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'output')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Output Flow Frames', display_name='⌨️ CR Output Flow Frames', category='🧩 Comfyroll Studio/🎥 Animation/⌨️ IO', is_output_node=True, inputs=[io.Combo.Input('output_folder', options=[], remote=io.RemoteOptions(route='/secure-nodes/assets/output?kind=directory', refresh_button=True)), io.Image.Input('current_image'), io.String.Input('filename_prefix', default='CR'), io.Int.Input('current_frame', default=0, min=0, max=9999999, force_input=True), io.Image.Input('interpolated_img', optional=True), io.String.Input('output_path', default='', multiline=False, optional=True)], outputs=[], hidden=[])

    @classmethod
    def validate_inputs(cls,filename_prefix='CR'):return PENDING
    @classmethod
    async def execute(cls, output_folder, current_image, current_frame, output_path='', filename_prefix='CR', interpolated_img=None):
        raise RuntimeError(PENDING)
NODE_CLASS_MAPPINGS = {'CR Image Output': CR_ImageOutput, 'CR XY Save Grid Image': CR_XYSaveGridImage, 'CR Output Flow Frames': CR_OutputFlowFrames}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Image Output': '💾 CR Image Output', 'CR XY Save Grid Image': '📉 CR XY Save Grid Image', 'CR Output Flow Frames': '⌨️ CR Output Flow Frames'}
