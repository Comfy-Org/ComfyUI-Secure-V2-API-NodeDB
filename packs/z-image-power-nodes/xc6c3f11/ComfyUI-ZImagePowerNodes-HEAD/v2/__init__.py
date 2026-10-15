"""Z-Image Power Nodes secure conversion in progress."""
from comfy_api.latest import ComfyExtension
class ZImagePowerNodesExtension(ComfyExtension):
    async def get_node_list(self):
        from .nodes.style_string_injector_2 import StyleStringInjector2
        from .nodes.deprecated_nodes.style_string_injector import StyleStringInjector
        from .nodes.my_top_10_styles import MyTop10Styles
        from .nodes.my_top_10_styles_editor import MyTop10StylesEditor
        from .nodes.image_filter import ImageFilter
        from .nodes.image_grid_builder import ImageGridBuilder
        from .nodes.image_labeler_2 import ImageLabeler2
        from .nodes.deprecated_nodes.image_labeler_1 import ImageLabeler
        from .nodes.style_library_v10 import StyleLibraryV10
        from .nodes.palette_library_v20 import PaletteLibraryV20
        from .nodes.empty_zimage_latent_image import EmptyZImageLatentImage
        from .nodes.style_prompt_encoder_2 import StylePromptEncoder2
        from .nodes.style_prompt_encoder_X22_advanced import StylePromptEncoderX22Advanced
        from .nodes.deprecated_nodes.style_prompt_encoder import StylePromptEncoder
        from .nodes.deprecated_nodes.photo_style_prompt_encoder import PhotoStylePromptEncoder
        from .nodes.deprecated_nodes.illustration_style_prompt_encoder import IllustrationStylePromptEncoder
        from .nodes.deprecated_nodes.style_prompt_encoder_X21 import StylePromptEncoderX21
        from .nodes.deprecated_nodes.custom_style_prompt_encoder_X21 import CustomStylePromptEncoderX21
        from .nodes.vae_encode_soft_inpainting import VAEEncodeSoftInpainting
        from .nodes.load_zimage_model import LoadZImageModel
        from .nodes.load_qwen34b_model import LoadQwen34bModel
        from .nodes.zsampler_turbo_2_simple import ZSamplerTurbo2Simple
        from .nodes.zsampler_turbo_2 import ZSamplerTurbo2
        from .nodes.zsampler_turbo_2_advanced import ZSamplerTurbo2Advanced
        from .nodes.deprecated_nodes.zsampler_turbo_1 import ZSamplerTurbo
        from .nodes.deprecated_nodes.zsampler_turbo_1_advanced import ZSamplerTurboAdvanced
        from .nodes.deprecated_nodes.zsampler_turbo_2_laboratory import ZSamplerTurbo2Laboratory
        from .nodes.zsampler_turbo_X21 import ZSamplerTurboX21
        from .nodes.advanced_vae_decoder_X21 import AdvancedVAEDecoderX21
        from .nodes.comfy_kitchen_attention_enabler import ComfyKitchenAttentionEnabler
        from .nodes.save_image import SaveImage
        return [SaveImage,ComfyKitchenAttentionEnabler,AdvancedVAEDecoderX21,ZSamplerTurboX21,ZSamplerTurbo2Laboratory,ZSamplerTurboAdvanced,ZSamplerTurbo,ZSamplerTurbo2Advanced,ZSamplerTurbo2,ZSamplerTurbo2Simple,LoadZImageModel,LoadQwen34bModel,VAEEncodeSoftInpainting,StylePromptEncoder2,StylePromptEncoderX22Advanced,StylePromptEncoder,PhotoStylePromptEncoder,IllustrationStylePromptEncoder,StylePromptEncoderX21,CustomStylePromptEncoderX21,EmptyZImageLatentImage,StyleLibraryV10,PaletteLibraryV20,StyleStringInjector2,StyleStringInjector,MyTop10StylesEditor,MyTop10Styles,ImageFilter,ImageGridBuilder,ImageLabeler2,ImageLabeler]
async def comfy_entrypoint():return ZImagePowerNodesExtension()
WEB_DIRECTORY='./js'
