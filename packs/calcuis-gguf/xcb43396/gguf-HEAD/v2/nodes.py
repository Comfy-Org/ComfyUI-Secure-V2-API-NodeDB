"""Full13 draft registrations; pending branches fail closed, never impersonate City96."""
import posixpath

from comfy_api.latest import io, sdk
from .bounds import logical_name, output_prefix, state_bounds
from .state_math import boost, cut
from .range_reader import RangeReader
from .safetensor_bytes import state_from_asset_ranges
from .conversion_artifact import prepare_conversion
from .gguf_state import gguf_state, gguf_diffusion_state, gguf_text_state, rechunk
from .clip_types import resolve_clip_type
from .catalogue_pins import SUPPORTED_PT_EXTENSIONS

DTYPES = ['default', 'target', 'float32', 'float16', 'bfloat16']
CLIP_TYPES = ['stable_diffusion', 'stable_cascade', 'sd3', 'stable_audio', 'mochi', 'ltxv', 'pixart', 'cosmos', 'lumina2', 'wan', 'hidream', 'chroma', 'ace', 'omnigen2', 'qwen_image', 'hunyuan_image', 'flux2', 'ovis', 'longcat_image', 'cogvideox', 'lens', 'pixeldit', 'ideogram4', 'boogu', 'krea2', 'joyimage', 'mage', 'minimax', 'yue2']
DUAL_CLIP_TYPES = ['sdxl', 'sd3', 'flux', 'hunyuan_video', 'hidream', 'hunyuan_image', 'hunyuan_video_15', 'kandinsky5', 'kandinsky5_image', 'ltxv', 'newbie', 'ace']


class ConversionPendingError(RuntimeError):
    """Explicit compatibility prerequisite, not rejection of useful intent."""


# Extension sets of the original's lists; folder_paths compares extensions case-insensitively.
GGUF_EXTENSIONS = frozenset({'.gguf'})  # model_gguf, select_gguf
SAFETENSORS_EXTENSIONS = frozenset({'.safetensors'})  # select_safetensors
LISTED_EXTENSIONS = frozenset(SUPPORTED_PT_EXTENSIONS) | GGUF_EXTENSIONS  # clip+clip_gguf, vae+vae_gguf, audio_encoders+encoder_gguf


def canonical_name(name):
    """The spelling folder_paths lists: relative, '/'-separated, no empty, '.' or '..' segment, no backslash.

    The host resolver normalises the other spellings to the same file, so they would pass as aliases.
    """
    return (type(name) is str and bool(name) and '\\' not in name and not name.startswith('/')
            and all(part not in ('', '.', '..') for part in name.split('/')))


async def catalogue_member(folder, name, extensions):
    """Queue-time stand-in for the original static list membership (remote combos carry no options)."""
    if not canonical_name(name):
        return False
    try:
        logical_name(name)
    except ValueError:
        return False
    if posixpath.splitext(name)[1].lower() not in extensions:
        return False
    try:
        return await sdk.ctx().assets.exists(folder, name)
    except ValueError:
        return False


async def catalogue_check(folder, inputs, extensions):
    for field, name in inputs:
        if name is None:  # linked input: core type-checks the link; pig.py has no VALIDATE_INPUTS
            continue
        if not await catalogue_member(folder, name, extensions):
            return f"Value not in list: {field}: '{name}'"
    return True


TAESD_PRESETS = {'taesd': ('taesd_encoder.', 'taesd_decoder.'), 'taesdxl': ('taesdxl_encoder.', 'taesdxl_decoder.'),
                 'taesd3': ('taesd3_encoder.', 'taesd3_decoder.'), 'taef1': ('taef1_encoder.', 'taef1_decoder.')}


async def taesd_listed(name):
    """pig.py VaeGGUF.vae_list: a preset is listed only when an encoder and a decoder file exist in vae_approx."""
    try:
        approx = await sdk.ctx().assets.list('vae_approx')
    except ValueError:
        return False
    if type(approx) is not list:
        return False
    return all(any(type(entry) is str and entry.startswith(prefix) for entry in approx) for prefix in TAESD_PRESETS[name])


def catalogue_input(name, folder):
    return io.Combo.Input(name, options=[], remote=io.RemoteOptions(route='/models/' + folder, refresh_button=True))


def schema(cls, inputs, outputs):
    return io.Schema(node_id=cls.__name__, display_name=cls.TITLE, category='gguf', inputs=inputs, outputs=outputs, is_output_node=cls.__name__ in {'GGUFSave', 'GGUFRun', 'GGUFUndo', 'TENSORCut', 'TENSORBoost'})


class LoaderGGUF(io.ComfyNode):
    TITLE = 'GGUF Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets')

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('gguf_name', 'diffusion_models')], [io.Model.Output()])

    @classmethod
    async def validate_inputs(cls, gguf_name):
        # pig.py lists model_gguf: the diffusion_models/unet folders filtered to .gguf.
        return await catalogue_check('diffusion_models', [('gguf_name', gguf_name)], GGUF_EXTENSIONS)

    @classmethod
    async def execute(cls, gguf_name, dequant_dtype=None, patch_dtype=None, patch_on_device=None):
        # pig.py load_model: the plain loader passes None for all three; the advanced schema supplies them.
        logical_name(gguf_name)
        if not gguf_name.lower().endswith('.gguf'):  # model_gguf lists any-case .gguf
            raise ValueError('GGUF Loader lists .gguf diffusion models only (original model_gguf folder)')
        if dequant_dtype not in (None, *DTYPES) or patch_dtype not in (None, *DTYPES) or patch_on_device not in (None, True, False):
            raise ValueError('closed dtype/bool policy required')
        assets = sdk.ctx().assets
        state, metadata = await gguf_diffusion_state(assets, await assets.resolve('diffusion_models', gguf_name))
        # Host GGML ops + patcher (SDK207): GGMLOps dequant/patch dtypes, load_diffusion_model_state_dict(metadata=...),
        # GGUF patcher with patch_on_device. A model type that cannot be detected raises without a host path.
        return io.NodeOutput(await sdk.ctx().models.ggml_diffusion_from_state_dict(
            state, metadata, dequant_dtype=dequant_dtype, patch_dtype=patch_dtype, patch_on_device=patch_on_device))


class LoaderGGUFAdvanced(LoaderGGUF):
    TITLE = 'GGUF Loader (Advanced)'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('gguf_name', 'diffusion_models'), io.Combo.Input('dequant_dtype', options=DTYPES, default='default'), io.Combo.Input('patch_dtype', options=DTYPES, default='default'), io.Boolean.Input('patch_on_device', default=False)], [io.Model.Output()])

    @classmethod
    async def validate_inputs(cls, gguf_name):
        # Declared on each class: the manifest generator records only methods in the class's own __dict__.
        return await catalogue_check('diffusion_models', [('gguf_name', gguf_name)], GGUF_EXTENSIONS)


async def text_encoder_state(name):
    """pig.py load_data: case-sensitive '.gguf' -> load_gguf_clip; any other name -> comfy.utils.load_torch_file(safe_load=True).

    The host weight loader makes the same split: SafeTensors ('.safetensors'/'.sft' in any case) parsed directly,
    every other container through comfy.utils.load_torch_file(safe_load=True), Comfy's weights-only loader.
    """
    assets = sdk.ctx().assets
    asset = await assets.resolve('text_encoders', name)
    if name.endswith('.gguf'):
        return await gguf_text_state(assets, asset)
    return await sdk.ValueRef.from_value(await assets.load_state_dict(asset))


async def ggml_text_encoders(names, clip_type):
    """pig.py load_patcher: load_text_encoder_state_dicts(GGMLOps, initial_device offload) + GGUF patcher (SDK207)."""
    states = [await text_encoder_state(name) for name in names]
    return await sdk.ctx().models.ggml_text_encoders_from_state_dicts(states, resolve_clip_type(clip_type))


class ClipLoaderGGUF(io.ComfyNode):
    TITLE = 'GGUF CLIP Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets', 'raw')

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name', 'text_encoders'), io.Combo.Input('type', options=CLIP_TYPES), io.Combo.Input('device', options=['default', 'cpu'], optional=True, advanced=True)], [io.Clip.Output()])

    @classmethod
    async def validate_inputs(cls, clip_name):
        # pig.py lists clip + clip_gguf: text_encoders/clip names, any supported extension or .gguf.
        return await catalogue_check('text_encoders', [('clip_name', clip_name)], LISTED_EXTENSIONS)

    @classmethod
    async def execute(cls, clip_name, type='stable_diffusion', device='default'):
        logical_name(clip_name)
        if type not in CLIP_TYPES or device not in ('default', 'cpu'):
            raise ValueError('closed text encoder type/device required')
        if clip_name.endswith('.safetensors'):
            return io.NodeOutput(await sdk.ctx().models.load_text_encoder(clip_name, model_type=type, device=device))
        # GGML branch: device is unused (the original returns get_device('default') as an extra tuple element,
        # which core never reads for a one-output node).
        return io.NodeOutput(await ggml_text_encoders([clip_name], type))


class DualClipLoaderGGUF(ClipLoaderGGUF):
    TITLE = 'GGUF DualCLIP Loader'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name1', 'text_encoders'), catalogue_input('clip_name2', 'text_encoders'), io.Combo.Input('type', options=DUAL_CLIP_TYPES), io.Combo.Input('device', options=['default', 'cpu'], optional=True, advanced=True)], [io.Clip.Output()])

    @classmethod
    async def validate_inputs(cls, clip_name1, clip_name2):
        return await catalogue_check('text_encoders', [('clip_name1', clip_name1), ('clip_name2', clip_name2)], LISTED_EXTENSIONS)

    @classmethod
    async def execute(cls, clip_name1, clip_name2, type, device='default'):
        logical_name(clip_name1)
        logical_name(clip_name2)
        if type not in DUAL_CLIP_TYPES or device not in ('default', 'cpu'):
            raise ValueError('closed text encoder type/device required')
        if device != 'default' and clip_name1.endswith('.safetensors') and clip_name2.endswith('.safetensors'):
            raise ConversionPendingError('two SafeTensors text encoders with an explicit device use comfy.sd.load_clip(two paths, device) in the original; the SDK has only a single-file typed loader')
        # Otherwise both files take the GGML path, SafeTensors included; device only feeds the ignored extra element.
        return io.NodeOutput(await ggml_text_encoders([clip_name1, clip_name2], type))


class TripleClipLoaderGGUF(ClipLoaderGGUF):
    TITLE = 'GGUF TripleCLIP Loader'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name' + str(index), 'text_encoders') for index in (1, 2, 3)], [io.Clip.Output()])

    @classmethod
    async def validate_inputs(cls, clip_name1, clip_name2, clip_name3):
        return await catalogue_check('text_encoders', [('clip_name1', clip_name1), ('clip_name2', clip_name2), ('clip_name3', clip_name3)],
                                     LISTED_EXTENSIONS)

    @classmethod
    async def execute(cls, clip_name1, clip_name2, clip_name3):
        for name in (clip_name1, clip_name2, clip_name3):
            logical_name(name)
        # pig.py: no type input, default 'sd3'; core builds SD3 CLIP for any three state dicts.
        return io.NodeOutput(await ggml_text_encoders([clip_name1, clip_name2, clip_name3], 'sd3'))


class QuadrupleClipLoaderGGUF(ClipLoaderGGUF):
    TITLE = 'GGUF QuadrupleCLIP Loader'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name' + str(index), 'text_encoders') for index in (1, 2, 3, 4)], [io.Clip.Output()])

    @classmethod
    async def validate_inputs(cls, clip_name1, clip_name2, clip_name3, clip_name4):
        return await catalogue_check('text_encoders', [('clip_name1', clip_name1), ('clip_name2', clip_name2),
                                                       ('clip_name3', clip_name3), ('clip_name4', clip_name4)], LISTED_EXTENSIONS)

    @classmethod
    async def execute(cls, clip_name1, clip_name2, clip_name3, clip_name4):
        for name in (clip_name1, clip_name2, clip_name3, clip_name4):
            logical_name(name)
        # pig.py: no type input, default 'hunyuan_video'; core builds HiDream CLIP for any four state dicts.
        return io.NodeOutput(await ggml_text_encoders([clip_name1, clip_name2, clip_name3, clip_name4], 'hunyuan_video'))


class VaeGGUF(io.ComfyNode):
    TITLE = 'GGUF VAE Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets')

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('vae_name', 'vae/choices')], [io.Vae.Output()])

    @classmethod
    async def validate_inputs(cls, vae_name):
        # pig.py vae_list: vae folder files, vae_gguf .gguf files, and TAESD presets with both approx halves present.
        if vae_name is None:  # linked input
            return True
        if vae_name in TAESD_PRESETS:
            return True if await taesd_listed(vae_name) else f"Value not in list: vae_name: '{vae_name}'"
        return await catalogue_check('vae', [('vae_name', vae_name)], LISTED_EXTENSIONS)

    @classmethod
    async def execute(cls, vae_name):
        logical_name(vae_name)
        if vae_name.endswith('.gguf'):
            # pig.py: vae_gguf (the vae folders) -> load_gguf_clip -> comfy.sd.VAE(sd=sd)
            assets = sdk.ctx().assets
            state = await gguf_state(assets, await assets.resolve('vae', vae_name))
            return io.NodeOutput(await sdk.ctx().models.vae_from_state_dict(state))
        return io.NodeOutput(await sdk.ctx().models.load_vae(vae_name))


class AudioEncoderLoaderGGUF(io.ComfyNode):
    TITLE = 'GGUF AudioEncoder Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets', 'raw')

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('audio_encoder_name', 'audio_encoders')], [io.Custom("AUDIO_ENCODER").Output()])

    @classmethod
    async def validate_inputs(cls, audio_encoder_name):
        # pig.py get_encoder_list: audio_encoders files plus encoder_gguf .gguf files.
        return await catalogue_check('audio_encoders', [('audio_encoder_name', audio_encoder_name)], LISTED_EXTENSIONS)

    @classmethod
    async def execute(cls, audio_encoder_name):
        logical_name(audio_encoder_name)
        # pig.py: encoder_gguf (the audio_encoders folders) -> load_gguf_clip, else load_torch_file(safe_load=True);
        # then core load_audio_encoder_from_sd (which raises for an unsupported/invalid model).
        assets = sdk.ctx().assets
        asset = await assets.resolve('audio_encoders', audio_encoder_name)
        if audio_encoder_name.endswith('.gguf'):
            state = await gguf_state(assets, asset)
        else:
            state = await sdk.ValueRef.from_value(await assets.load_state_dict(asset))
        return io.NodeOutput(await sdk.ctx().models.audio_encoder_from_state_dict(state))


async def safe_state(name, output_itemsize=4):
    logical_name(name)
    if not name.lower().endswith('.safetensors'):  # select_safetensors lists any-case .safetensors
        raise ValueError('SafeTensors catalogue entry required')
    # Current canonical host declares diffusion_models. The legacy fallback
    # selected checkpoints only when the entire catalogue was absent, NOT
    # when one name was missing. Never substitute a same-named checkpoint.
    assets = sdk.ctx().assets
    asset = await assets.resolve('diffusion_models', name)
    return await state_from_asset_ranges(assets, asset, output_itemsize)


class TENSORBoost(io.ComfyNode):
    TITLE = 'TENSOR Booster'
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'output')

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('select_safetensors', 'diffusion_models')], [])

    @classmethod
    async def validate_inputs(cls, select_safetensors):
        # pig.py select_safetensors: the diffusion_models paths filtered to .safetensors. Restated on TENSORCut/GGUFSave/GGUFRun:
        # the manifest generator records only methods in the class's own __dict__.
        return await catalogue_check('diffusion_models', [('select_safetensors', select_safetensors)], SAFETENSORS_EXTENSIONS)

    @classmethod
    async def execute(cls, select_safetensors):
        result = boost(await safe_state(select_safetensors))
        ref = await sdk.ValueRef.from_value(result)
        await sdk.ctx().output.save_state_dict(ref, output_prefix(select_safetensors, '_fp32'))
        return io.NodeOutput()


class TENSORCut(TENSORBoost):
    TITLE = 'TENSOR Cutter (Beta)'

    @classmethod
    async def validate_inputs(cls, select_safetensors):
        return await catalogue_check('diffusion_models', [('select_safetensors', select_safetensors)], SAFETENSORS_EXTENSIONS)

    @classmethod
    async def execute(cls, select_safetensors):
        result = cut(await safe_state(select_safetensors))
        ref = await sdk.ValueRef.from_value(result)
        await sdk.ctx().output.save_state_dict(ref, output_prefix(select_safetensors, '_fp8_e4m3fn'))
        return io.NodeOutput()


class GGUFSave(TENSORBoost):
    TITLE = 'GGUF Convertor (Alpha)'
    MODE = 'alpha'

    @classmethod
    async def validate_inputs(cls, select_safetensors):
        return await catalogue_check('diffusion_models', [('select_safetensors', select_safetensors)], SAFETENSORS_EXTENSIONS)

    @classmethod
    async def execute(cls, select_safetensors):
        artifact = prepare_conversion(await safe_state(select_safetensors), select_safetensors, mode=cls.MODE)
        try:
            # Native name <stem>-f16.gguf / -bf16.gguf; managed counter-suffixed publication replaces the legacy
            # overwrite/input() prompt. Bytes are the native writer's, streamed in 1 MiB pieces.
            suffix = artifact.filename[len(select_safetensors.rsplit('.', 1)[0]):-len('.gguf')]
            await sdk.ctx().output.save_binary(rechunk(artifact.writer.iter_chunks()), output_prefix(select_safetensors, suffix),
                                               max_bytes=artifact.writer.total_bytes, extension='.gguf')
        finally:
            artifact.close()
        return io.NodeOutput()


class GGUFRun(GGUFSave):
    TITLE = 'GGUF Convertor (Zero)'
    MODE = 'zero'

    @classmethod
    async def validate_inputs(cls, select_safetensors):
        return await catalogue_check('diffusion_models', [('select_safetensors', select_safetensors)], SAFETENSORS_EXTENSIONS)


class GGUFUndo(TENSORBoost):
    TITLE = 'GGUF Convertor (Reverse)'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('select_gguf', 'diffusion_models')], [])

    @classmethod
    async def validate_inputs(cls, select_gguf):
        # pig.py select_gguf: the diffusion_models paths filtered to .gguf.
        return await catalogue_check('diffusion_models', [('select_gguf', select_gguf)], GGUF_EXTENSIONS)

    @classmethod
    async def execute(cls, select_gguf):
        logical_name(select_gguf)
        if not select_gguf.lower().endswith('.gguf'):  # select_gguf lists any-case .gguf
            raise ValueError('GGUF catalogue entry required')
        assets = sdk.ctx().assets
        asset = await assets.resolve('diffusion_models', select_gguf)
        reader = await RangeReader(assets, asset, await assets.size(asset)).parse()
        state = await reader.fp16_state()
        ref = await sdk.ValueRef.from_value(state)
        await sdk.ctx().output.save_state_dict(ref, output_prefix(select_gguf, '_fp16'), metadata=reader.metadata())
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (LoaderGGUF, ClipLoaderGGUF, DualClipLoaderGGUF, TripleClipLoaderGGUF, QuadrupleClipLoaderGGUF, AudioEncoderLoaderGGUF, LoaderGGUFAdvanced, VaeGGUF, GGUFUndo, GGUFSave, GGUFRun, TENSORCut, TENSORBoost)}
NODE_DISPLAY_NAME_MAPPINGS = {key: cls.TITLE for key, cls in NODE_CLASS_MAPPINGS.items()}
