"""
File    : advanced_vae_decoder_X21.py
Purpose : Experimental node to decode latent images back into pixels with advanced tweaks.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jun 24, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
     ComfyUI nodes designed to power the "Z-Image/Z-Image Turbo" models.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

 ComfyUI V3 Schema oficial documentation:
 - https://docs.comfy.org/custom-nodes/v3_migration

"""
import torch
from comfy_api.latest   import io, sdk



class AdvancedVAEDecoderX21(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    xTITLE         = "Advanced VAE Decoder ^X2.1"
    xDESCRIPTION   = (
        "An experimental alternative to the native ComfyUI VAEDecode node. "
        "It features options to bypass the standard output clamp so pixels "
        "can fall outside the [0.0, 1.0] range, and force tiled decoding to "
        "reduce VRAM usage on large images."
        )
    xCATEGORY      = ""
    xCOMFY_NODE_ID = ""
    xDEPRECATED    = False

    #__ INPUT / OUTPUT ____________________________________
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            display_name  = cls.xTITLE,
            description   = cls.xDESCRIPTION,
            category      = cls.xCATEGORY,
            node_id       = cls.xCOMFY_NODE_ID,
            is_deprecated = cls.xDEPRECATED,
            search_aliases=["decode", "decode latent", "latent to image", "render latent"],
            inputs=[
                io.Latent.Input      ("samples",
                                      tooltip="The latent representation to be decoded into an image."
                                     ),
                io.Vae.Input         ("vae",
                                      tooltip="The VAE model used to decode the latent input."
                                     ),
                io.Boolean.Input     ("allow_extended_range",
                                      tooltip="When enabled, the standard numerical clamping on the VAE "
                                              "output is bypassed, permitting pixel values to exist outside "
                                              "the typical [0.0, 1.0] range, which could be beneficial for "
                                              "preserving high dynamic range data. Disable if image artifacts "
                                              "or distortion appear."
                                     ),
                io.Boolean.Input     ("low_vram_mode",
                                      tooltip="When enabled, force the VAE decoding process to be split into smaller "
                                              "tiles. While this significantly reduces VRAM usage on large images, "
                                              "it results in slower processing speeds and a slight reduction in final "
                                              "image quality. This option should remain disabled unless you are operating "
                                              "under severe GPU memory constraints."
                                     ),
            ],
            outputs=[
                io.Image.Output(tooltip="The decoded image."),
            ],
        )

    #__ FUNCTION __________________________________________
    @classmethod
    async def execute(cls,
                vae                 : sdk.VaeRef,
                samples             : sdk.LatentRef,
                allow_extended_range: bool,
                low_vram_mode       : bool,
                ):

        samples = await samples.value()
        # extract latents from the samples object
        latents: torch.Tensor = samples["samples"]
        if latents.is_nested:
            latents = latents.unbind()[0]

        # The reviewed host policy applies the original affine processing
        # before clamp, locally to this decode, without changing the shared VAE.
        # decode latents to images
        if low_vram_mode:
            # when low_vram_mode is enabled,
            # decode the latents using the "VAEDecodeTiled" node
            images_tuple = ((await (await vae.decode_tensor_tiled(
                await sdk.LatentRef.from_value(samples), tile_size=512,
                allow_extended_range=allow_extended_range)).raw()),)
            images = images_tuple[0] if isinstance(images_tuple, tuple) else images_tuple
        else:
            # otherwise, decode the latents using the standard method
            images = await (await vae.decode_tensor(
                await sdk.LatentRef.from_value({"samples": latents}),
                allow_extended_range=allow_extended_range)).raw()
            if len(images.shape) == 5:
                images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
            elif len(images.shape) == 3:
                images = images.unsqueeze(0)


        # return the decoded images
        return (await sdk.ImageRef._from_raw(images), )


AdvancedVAEDecoderX21.xTITLE = '⚗️🔬| Advanced VAE Decoder ^X2.1'
AdvancedVAEDecoderX21.xDESCRIPTION = 'An experimental alternative to the native ComfyUI VAEDecode node. It features options to bypass the standard output clamp so pixels can fall outside the [0.0, 1.0] range, and force tiled decoding to reduce VRAM usage on large images.\n⚠️ Because this node is experimental, its parameters, behavior, or availability may change or be removed entirely without prior notice.'
AdvancedVAEDecoderX21.xCATEGORY = '⚡Z-Image/__experimental'
AdvancedVAEDecoderX21.xCOMFY_NODE_ID = 'AdvancedVAEDecoderX21 //ZImagePowerNodes'
AdvancedVAEDecoderX21.xDEPRECATED = False
