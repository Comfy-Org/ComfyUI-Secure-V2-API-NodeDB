# Z-Sampler Turbo

![z-sampler turbo node](zsampler_turbo.jpg)

The distinctive feature of this sampler is that it divides the number of steps into three stages: composition, details, and refinement. The sigmas are calculated to keep the image stable from 4 to 9 steps. Naturally, with fewer steps, the final quality decreases, but the resulting images remain quite similar.

Between 7 and 9 steps, the image achieves sufficient quality and detail, making further refining or post-processing unnecessary.

This sampler also enhances prompt adherence, improves overall image coherence, and eliminates the need for a "ModelSamplingAuraFlow" node with its 'shift' parameter adjustment.


## Inputs

### model
Any checkpoint from the "Z-Image Turbo" model. This sampler hasn't been extensively tested with LoRAs applied, nor has it been determined which types of LoRA training might benefit from this three-stage sampling process.

### positive
The positive conditioning input, typically the prompt embedding. There is no negative conditioning because this sampler always operates at CFG 1.0. In the future, it may be worth testing a similar sampling approach with a slightly higher CFG value, but I wanted to avoid adding another variable during testing.

### latent_input
The initial latent image to be denoised, typically an 'Empty Latent' for text-to-image or an encoded image for img2img processing.

### seed
The random number generator seed, ensuring reproducibility with the same value.

### steps
Number of sampling iterations, ranging from 4 to 9.

### denoise
Amount of denoising applied:
 - For standard text-to-image processes, keep at 1.0.
 - For inpainting tasks, values between 0.75 and 0.90 often work well, though smaller values may also be used.
 - For minor adjustments across the entire image without losing composition, small values like 0.20 or 0.10 can be effective.

### initial_noise_calibration
Adjusts the initial noise level to align with model expectations.  
Typically enhances image contrast and saturation, with higher percentages increasing these effects more strongly.
A value of "100%" is usually optimal, but lower percentages like "50%" or even complete disablement might be necessary if less contrast or saturation is desired.  
(More information on this parameter below).

### lowres_bias
A hack to accelerate initial noise calibration by calculating it on a 256x256 image instead of the actual size. Generally, keep this disabled as it may reduce final image quality.


## Outputs

### latent_output
The resulting denoised latent image, ready for VAE decoding or further processing in another sampler node.


## Initial Noise Calibration (INC)

For various reasons, the sampler starts at a point where the model expects the noise to contain a small bias. In earlier versions of the sampler, this bias was not taken into account. However, now the sampler performs an estimation of this bias during the denoising process initialization. This 'calibration' is done by taking one step of pure noise denoising and then measuring the resulting latent image's bias.

In addition to adjusting for this bias, a slight over-amplification of the input noise is also performed. All of these adjustments are encapsulated within the "Initial Noise Calibration" (INC), which ranges from "off" (0%) to 100%, representing the percentage of this calibration applied.

The end result is that when activating the calibration, the generated image has more contrast and saturation. It can even produce nearly pure black (or pure white) images. However, the optimal INC percentage depends on the type of image and personal preference. Below are some guidelines based on my own personal preferences.

### Illustrations

For illustrations that are pure line art without realistic elements, a calibration level of 100% often works well, resulting in vivid colors with smooth gradients or solid hues (without 'textures'), as demonstrated in the example.

If the illustration includes texture or softer color edges (e.g., weathered or vintage-looking drawings, or semi-realistic illustrations with textures), a lower value might be preferable to preserve those characteristics.

**[Workflow](https://raw.githubusercontent.com/martin-rizzo/ComfyUI-ZImagePowerNodes/refs/heads/master/docs/calibration_examples/illustration.json)**
![illustration example](calibration_examples/illustration.jpg)

### Photographs

For photographs, a higher INC percentage (e.g., 100%) can make them appear slightly more artificial, while disabling it may result in less vibrant colors or washed-out images that don't reach pure black or white. This is very subjective, but as a starting point, try 50% and adjust according to your desired outcome.

For photos requiring an overall very dark or light tone, activating the calibration with a high percentage is usually necessary, as without it such images tend towards an average gray tone.  (This example uses the "Noir Photo" style, which might better suit the darker illumination of the left image).

**[Workflow](https://raw.githubusercontent.com/martin-rizzo/ComfyUI-ZImagePowerNodes/refs/heads/master/docs/calibration_examples/photo.json)**
![photo example](calibration_examples/photo.jpg)

### Other Styles

The need for calibration varies greatly depending on the image style and prompt. Images requiring fine texture details rather than intense colors or high contrast may perform better with INC disabled, as demonstrated in this "Stamp" style example.

**[Workflow](https://raw.githubusercontent.com/martin-rizzo/ComfyUI-ZImagePowerNodes/refs/heads/master/docs/calibration_examples/stamp.json)**
![stamp example](calibration_examples/stamp.jpg)

