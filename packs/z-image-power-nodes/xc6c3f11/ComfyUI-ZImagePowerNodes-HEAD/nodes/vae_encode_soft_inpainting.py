"""
File    : vae_encode_soft_inpainting.py
Purpose : 
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Feb 25, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

  ComfyUI V3 schema documentation can be found here:
  - https://docs.comfy.org/custom-nodes/v3_migration

_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import math
import torch
from torchvision.transforms.functional import gaussian_blur
from comfy_api.latest import io
PIXELS_BY_SIZE = {
    "small"  : 1048576,
    "medium" : 1772093,
    "large"  : 2684354,
}


class VAEEncodeSoftInpainting(io.ComfyNode):
    xTITLE         = "VAE Encode (for Soft Inpainting)"
    xDESCRIPTION   = "Encodes the input image and its inpainting mask into latent space using a VAE model."
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
            inputs=[
                io.Image.Input("pixels",
                               tooltip="The input image to encode",
                              ),
                io.Vae.Input  ("vae",
                               tooltip="The VAE model to use for encoding",
                              ),
                io.Mask.Input ("mask",
                               tooltip="Mask indicating the area of the image to apply inpainting.",
                              ),
                io.Combo.Input("output_size", options=[ "same_as_input", "large", "medium (recommended)", "small" ],
                               tooltip="Determines the size of the output latent space.",
                               ),
                io.Float.Input("mask_blur_pixels", min=0.0, max=256, step=5,
                               tooltip="Width in pixels for softening the mask edges. "
                                       "Higher values create a smoother transition with larger masked area.",
                              ),
            ],
            outputs=[
                io.Latent.Output(display_name="LATENT",
                                 tooltip="Latent space representation of the encoded image and mask.",
                                ),
            ],
        )

    #__ FUNCTION __________________________________________
    @classmethod
    def execute(cls, vae, pixels, mask, output_size, mask_blur_pixels):
        # `mask` must have shape [B, C, H, W] or [C, H, W]

        gray_out_masked_pixels = False
        return_binary_mask     = False
        image_height = int( pixels.shape[1] )
        image_width  = int( pixels.shape[2] )
        mask_height  = int( mask.shape[-2] )
        mask_width   = int( mask.shape[-1] )
        mask         = mask.reshape((-1, 1, mask_height, mask_width))

        output_size = output_size.split()[0].lower()
        if output_size in PIXELS_BY_SIZE:
            image_aspect = image_width / image_height
            output_width  = int( math.sqrt( PIXELS_BY_SIZE[output_size] * image_aspect ) )
            output_height = int( math.sqrt( PIXELS_BY_SIZE[output_size] / image_aspect ) )
        else:
            output_width  = int( image_width  )
            output_height = int( image_height )


        # if required, smooth the mask using a Gaussian blur
        kernel_size = int(2 * mask_blur_pixels + 1)
        if kernel_size % 2 == 0: kernel_size += 1
        if mask_blur_pixels > 0 and mask_width>kernel_size and mask_height>kernel_size:
            sigma = float(mask_blur_pixels) / 2.0
            smoothed_mask = gaussian_blur(mask, [kernel_size, kernel_size], [sigma, sigma])
            mask = torch.clamp(smoothed_mask , 0.0, 1.0)

        # resize image and mask to output size
        if mask_width != output_width or mask_height != output_height:
            mask = torch.nn.functional.interpolate(mask  , size=(output_height, output_width), mode="bilinear")
        if image_width != output_width or image_height != output_height:
            pixels = pixels.movedim(-1,1)
            pixels = torch.nn.functional.interpolate(pixels, size=(output_height, output_width), mode="bilinear")
            pixels = pixels.movedim(1,-1)

        # calculate which resolution would be compatible with VAE
        vae_downscale_ratio = vae.spacial_compression_encode()
        vae_height = (output_height // vae_downscale_ratio) * vae_downscale_ratio
        vae_width  = (output_width  // vae_downscale_ratio) * vae_downscale_ratio

        # crop the image and the mask to the VAE compatible resolution
        pixels = pixels.clone()
        if pixels.shape[1] != vae_height or pixels.shape[2] != vae_width:
            y_offset = (output_height % vae_downscale_ratio) // 2
            x_offset = (output_width  % vae_downscale_ratio) // 2
            pixels = pixels[:  , y_offset:(y_offset+vae_height), x_offset:(x_offset+vae_width), :]
            mask   = mask  [:,:, y_offset:(y_offset+vae_height), x_offset:(x_offset+vae_width)   ]

        # if required, gray out the image where the mask is set
        # (this operation is binary, the pixel is grayed out if the mask value is > 0.5)
        if gray_out_masked_pixels:
            mask_binary = (1.0 - mask.round()).squeeze(1)
            for i in range(3):
                pixels[:,:,:,i] = (pixels[:,:,:,i] - 0.5) * mask_binary + 0.5

        # if required, convert the mask values to binary values (0 or 1)
        if return_binary_mask:
            mask = mask.round()

        samples = vae.encode(pixels)
        return ({"samples":samples, "noise_mask": mask}, )


