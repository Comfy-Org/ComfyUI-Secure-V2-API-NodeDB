"""Full13 draft registrations; pending branches fail closed, never impersonate City96."""
from comfy_api.latest import io, sdk
from .bounds import logical_name, output_prefix, state_bounds
from .state_math import boost, cut
from .range_reader import RangeReader
from .safetensor_bytes import state_from_asset_ranges
from .conversion_artifact import prepare_conversion
from .gguf_state import gguf_state, rechunk

DTYPES = ['default', 'target', 'float32', 'float16', 'bfloat16']
CLIP_TYPES = ['stable_diffusion', 'stable_cascade', 'sd3', 'stable_audio', 'mochi', 'ltxv', 'pixart', 'cosmos', 'lumina2', 'wan', 'hidream', 'chroma', 'ace', 'omnigen2', 'qwen_image', 'hunyuan_image', 'flux2', 'ovis', 'longcat_image', 'cogvideox', 'lens', 'pixeldit', 'ideogram4', 'boogu', 'krea2', 'joyimage', 'mage', 'minimax', 'yue2']
DUAL_CLIP_TYPES = ['sdxl', 'sd3', 'flux', 'hunyuan_video', 'hidream', 'hunyuan_image', 'hunyuan_video_15', 'kandinsky5', 'kandinsky5_image', 'ltxv', 'newbie', 'ace']


class ConversionPendingError(RuntimeError):
    """Explicit compatibility prerequisite, not rejection of useful intent."""


def catalogue_input(name, folder):
    return io.Combo.Input(name, options=[], remote=io.RemoteOptions(route='/models/' + folder, refresh_button=True))


def schema(cls, inputs, outputs):
    return io.Schema(node_id=cls.__name__, display_name=cls.TITLE, category='gguf', inputs=inputs, outputs=outputs, is_output_node=cls.__name__ in {'GGUFSave', 'GGUFRun', 'GGUFUndo', 'TENSORCut', 'TENSORBoost'})


class LoaderGGUF(io.ComfyNode):
    TITLE = 'GGUF Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('gguf_name', 'diffusion_models')], [io.Model.Output()])

    @classmethod
    async def execute(cls, gguf_name, dequant_dtype='default', patch_dtype='default', patch_on_device=False):
        logical_name(gguf_name)
        if dequant_dtype not in DTYPES or patch_dtype not in DTYPES or type(patch_on_device) is not bool:
            raise ValueError('closed dtype/bool policy required')
        raise ConversionPendingError('calcuis GGMLTensor/GGMLOps/model patcher provider is not proven by the existing City96 service')


class LoaderGGUFAdvanced(LoaderGGUF):
    TITLE = 'GGUF Loader (Advanced)'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('gguf_name', 'diffusion_models'), io.Combo.Input('dequant_dtype', options=DTYPES, default='default'), io.Combo.Input('patch_dtype', options=DTYPES, default='default'), io.Boolean.Input('patch_on_device', default=False)], [io.Model.Output()])


class ClipLoaderGGUF(io.ComfyNode):
    TITLE = 'GGUF CLIP Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name', 'text_encoders'), io.Combo.Input('type', options=CLIP_TYPES), io.Combo.Input('device', options=['default', 'cpu'], optional=True, advanced=True)], [io.Clip.Output()])

    @classmethod
    async def execute(cls, clip_name, type='stable_diffusion', device='default'):
        logical_name(clip_name)
        if type not in CLIP_TYPES or device not in ('default', 'cpu'):
            raise ValueError('closed text encoder type/device required')
        if not clip_name.endswith('.safetensors'):
            raise ConversionPendingError('calcuis GGUF text conversion/provider and original extra tuple output require explicit disposition')
        return io.NodeOutput(await sdk.ctx().models.load_text_encoder(clip_name, model_type=type, device=device))


class DualClipLoaderGGUF(ClipLoaderGGUF):
    TITLE = 'GGUF DualCLIP Loader'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name1', 'text_encoders'), catalogue_input('clip_name2', 'text_encoders'), io.Combo.Input('type', options=DUAL_CLIP_TYPES), io.Combo.Input('device', options=['default', 'cpu'], optional=True, advanced=True)], [io.Clip.Output()])

    @classmethod
    async def execute(cls, clip_name1, clip_name2, type, device='default'):
        logical_name(clip_name1)
        logical_name(clip_name2)
        if type not in DUAL_CLIP_TYPES or device not in ('default', 'cpu'):
            raise ValueError('closed text encoder type/device required')
        raise ConversionPendingError('multi-encoder calcuis provider/device and original extra tuple output are unresolved')


class TripleClipLoaderGGUF(ClipLoaderGGUF):
    TITLE = 'GGUF TripleCLIP Loader'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name' + str(index), 'text_encoders') for index in (1, 2, 3)], [io.Clip.Output()])

    @classmethod
    async def execute(cls, clip_name1, clip_name2, clip_name3):
        for name in (clip_name1, clip_name2, clip_name3):
            logical_name(name)
        raise ConversionPendingError('calcuis triple text encoder provider with sd3 defaults remains unproven')


class QuadrupleClipLoaderGGUF(ClipLoaderGGUF):
    TITLE = 'GGUF QuadrupleCLIP Loader'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('clip_name' + str(index), 'text_encoders') for index in (1, 2, 3, 4)], [io.Clip.Output()])

    @classmethod
    async def execute(cls, clip_name1, clip_name2, clip_name3, clip_name4):
        for name in (clip_name1, clip_name2, clip_name3, clip_name4):
            logical_name(name)
        raise ConversionPendingError('calcuis quadruple text encoder provider with hunyuan_video defaults remains unproven')


class VaeGGUF(io.ComfyNode):
    TITLE = 'GGUF VAE Loader'
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets')

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('vae_name', 'vae/choices')], [io.Vae.Output()])

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
    if not name.endswith('.safetensors'):
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
    async def execute(cls, select_safetensors):
        result = boost(await safe_state(select_safetensors))
        ref = await sdk.ValueRef.from_value(result)
        await sdk.ctx().output.save_state_dict(ref, output_prefix(select_safetensors, '_fp32'))
        return io.NodeOutput()


class TENSORCut(TENSORBoost):
    TITLE = 'TENSOR Cutter (Beta)'

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


class GGUFUndo(TENSORBoost):
    TITLE = 'GGUF Convertor (Reverse)'

    @classmethod
    def define_schema(cls):
        return schema(cls, [catalogue_input('select_gguf', 'diffusion_models')], [])

    @classmethod
    async def execute(cls, select_gguf):
        logical_name(select_gguf)
        if not select_gguf.endswith('.gguf'):
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
