import torch
import torch.nn.functional as F
from comfy_api.latest import io, sdk

from ._ltx_utils import GuideOps, get_noise_mask

class LTXSequencer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        inputs = [
            io.Conditioning.Input("positive", tooltip="Positive conditioning to which guide keyframe info will be added"),
            io.Conditioning.Input("negative", tooltip="Negative conditioning to which guide keyframe info will be added"),
            io.Vae.Input("vae", tooltip="Video VAE used to encode the guide images"),
            io.Latent.Input("latent", tooltip="Video latent, guides are added to the end of this latent"),
            io.Image.Input("multi_input", tooltip="Batched images from MultiImageLoader"),
        ]
        
        inputs.append(io.Int.Input("num_images", default=1, min=0, max=50, step=1, display_name="images_loaded", tooltip="Select how many index/strength widgets to configure."))
        
        # New global settings widgets
        inputs.append(io.Combo.Input("insert_mode", options=["frames", "seconds"], default="frames", tooltip="Select the method for determining insertion points."))
        inputs.append(io.Int.Input("frame_rate", default=24, min=1, max=120, step=1, tooltip="Video FPS (used for calculating second insertions)."))

        for i in range(1, 51):  # 1 to 50 images
            inputs.extend([
                io.Int.Input(
                    f"insert_frame_{i}",
                    default=0,
                    min=-9999,
                    max=9999,
                    step=1,
                    tooltip=f"Frame insert point for image {i} (in pixel space).",
                    optional=True,
                ),
                io.Float.Input(
                    f"insert_second_{i}",
                    default=0.0,
                    min=0.0,
                    max=9999.0,
                    step=0.1,
                    tooltip=f"Second insert point for image {i}.",
                    optional=True,
                ),
                io.Float.Input(
                    f"strength_{i}", 
                    default=1.0, 
                    min=0.0, 
                    max=1.0, 
                    step=0.01, 
                    tooltip=f"Strength for image {i}.",
                    optional=True,
                ),
            ])

        return io.Schema(
            node_id="LTXSequencer",
            display_name="LTX Sequencer",
            category="WhatDreamsCost",
            description="Add multiple guide images at specified frame indices or seconds with strengths. Number of widgets is dynamically configured.",
            inputs=inputs,
            outputs=[
                io.Conditioning.Output(display_name="positive"),
                io.Conditioning.Output(display_name="negative"),
                io.Latent.Output(display_name="latent", tooltip="Video latent with added guides"),
            ],
        )

    @classmethod
    async def execute(cls, positive, negative, vae, latent, multi_input, num_images, **kwargs) -> io.NodeOutput:
        positive_value = await positive.value()
        negative_value = await negative.value()
        latent_value = await latent.value()
        images = await multi_input.raw()
        scale_factors = await vae.downscale_index_formula()
        if scale_factors is None:
            raise ValueError("this VAE does not publish its downscale formula")
        
        # Clone latents to avoid overwriting previous nodes' operations
        latent_image = latent_value["samples"].clone()
        
        # Helper logic to fetch or generate a noise mask
        noise_mask = get_noise_mask(latent_value)

        _, _, latent_length, latent_height, latent_width = latent_image.shape
        batch_size = images.shape[0] if images is not None else 0

        # Retrieve selected insertion settings
        insert_mode = kwargs.get("insert_mode", "frames")
        frame_rate = kwargs.get("frame_rate", 24)

        # Process inputs up to num_images, extracting dynamic frame/strength values from kwargs
        for i in range(1, num_images + 1):
            # Skip if this image index exceeds the batch
            if i > batch_size:
                continue

            img = images[i-1:i]  # Extract the single image frame from the batch
            if img is None:
                continue

            # Calculate the final frame index based on the chosen mode
            f_idx = None
            if insert_mode == "frames":
                f_idx = kwargs.get(f"insert_frame_{i}")
            elif insert_mode == "seconds":
                sec = kwargs.get(f"insert_second_{i}")
                if sec is not None:
                    f_idx = int(sec * frame_rate)

            if f_idx is None:
                continue
                
            strength = kwargs.get(f"strength_{i}", 1.0)

            # Execution logic mirrored from LTXVAddGuideMulti
            time_scale, width_scale, height_scale = scale_factors
            frame_count = (img.shape[0] - 1) // time_scale * time_scale + 1
            img = img[:frame_count]
            pixels = F.interpolate(
                img.movedim(-1, 1),
                size=(int(latent_height * height_scale), int(latent_width * width_scale)),
                mode="bilinear",
                align_corners=False,
            ).movedim(1, -1)[..., :3]
            t = (await (await vae.encode(await sdk.ImageRef._from_raw(pixels))).value())["samples"]

            frame_idx, latent_idx = GuideOps.get_latent_index(positive_value, latent_length, len(pixels), f_idx, scale_factors)
            assert latent_idx + t.shape[2] <= latent_length, "Conditioning frames exceed the length of the latent sequence."

            positive_value, negative_value, latent_image, noise_mask = GuideOps.append_keyframe(
                positive_value,
                negative_value,
                frame_idx,
                latent_image,
                noise_mask,
                t,
                strength,
                scale_factors,
            )

        return io.NodeOutput(
            await sdk.CondRef.from_value(positive_value),
            await sdk.CondRef.from_value(negative_value),
            await sdk.LatentRef.from_value({"samples": latent_image, "noise_mask": noise_mask}),
        )


NODE_CLASS_MAPPINGS = {"LTXSequencer": LTXSequencer}
