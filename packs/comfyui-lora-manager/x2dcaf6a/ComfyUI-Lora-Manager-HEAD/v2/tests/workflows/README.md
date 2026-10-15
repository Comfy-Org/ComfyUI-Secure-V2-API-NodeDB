# LoRA Manager TEST workflows (installed run)

API-format prompts (`{"prompt": {...}}`), one per node family, intended for `v2/tests/workflows/`.
CPU-sized: SD1.5, LCM LoRA, 4 steps, 256x256, cfg 1.5, sampler `lcm`, scheduler `sgm_uniform`.

## Required runtime assets

- `checkpoints/v1-5-pruned-emaonly-fp16.safetensors` (must be available in the runtime model store).
- `loras/lcm-sd15-lora.safetensors`: copy of the shared-cache file `lcm-sd15-lora-8f90d840e075.safetensors`
  (sha256 8f90d840e075ff588a58e22c6586e2ae9a6f7922996ee6649a7f01072333afe4), 128 MB.
- `diffusion_models/sd15-unet-c925663b059e.safetensors`: SD1.5 UNet extracted from the checkpoint (shared-cache file; see its
  `.provenance.json`), 1.72 GB, for the Unet Loader case.
- `input/lm-fixture.png`: 256x256 PNG with A1111 `parameters` text (supply a fixture with seed 7, steps 4, sampler lcm and scheduler normal), for the
  Load Image Metadata case.

List widget values are wrapped as `{"__value__": [...]}` exactly as the ComfyUI frontend does; core reads a bare
list as a link.

## Cases

- `lora-manager-basic-sd15`: Checkpoint Loader, Lora Loader, TriggerWord Toggle, Prompt, Save Image. Expect: One 256x256 PNG; Lora Loader applies lcm-sd15-lora at 1.0; trigger words flow into the positive prompt.
- `lora-stacker-combiner-sd15`: Lora Stacker, Lora Stack Combiner, Lora Loader (stack input), Prompt, Save Image. Expect: One PNG; stack carries lcm-sd15-lora at 0.5 through the combiner into the loader.
- `lora-pool-randomizer-sd15`: Lora Pool, Lora Randomizer, Lora Loader, Save Image. Expect: One PNG; pool filtered to lcm-sd15-lora, randomizer picks exactly that LoRA at 1.0.
- `lora-pool-cycler-sd15`: Lora Pool, Lora Cycler, Lora Loader, Save Image. Expect: One PNG; cycler selects lcm-sd15-lora (index 1 of 1).
- `lora-text-syntax-sd15`: Text, LoRA Text Loader, LoRA Syntax -> Path, Metadata Overwrite, Save Image. Expect: One PNG; saved metadata additional data is the library-relative name lcm-sd15-lora.safetensors. Negative check: no absolute host path appears anywhere in the saved PNG metadata.
- `lora-metadata-debug-sd15`: Debug Metadata, Metadata Overwrite, Save Image, Checkpoint Loader, Prompt. Expect: One PNG whose metadata shows the overwritten prompt/seed/steps/cfg/size; Debug Metadata UI output present.
- `lora-hook-clip-sd15`: Create Hook LoRA, core SetClipHooks, Save Image. Expect: One PNG; CLIP hooks applied through SetClipHooks. BLOCKED: SetClipHooks host operation deployment (GERALD Core #17041 / backend #22).
- `lora-unet-loader-sd15`: Unet Loader, Checkpoint Loader (CLIP/VAE), Prompt, Save Image. Expect: One PNG sampled with the SD1.5 UNet loaded through Unet Loader from diffusion_models/sd15-unet-c925663b059e.safetensors.
- `lora-load-image-metadata-sd15`: Load Image Metadata, Metadata Overwrite, Save Image. Expect: Reads input/lm-fixture.png (A1111 parameters); recovered prompt/seed/steps/cfg flow into the saved PNG metadata. Save Image takes its image through core ImageScaleBy (x1.0) so Metadata Overwrite always starts first: both are
  output nodes and core orders output ids by hash seed, so wiring Save straight to the loader is racy (as in the original).

## Not covered by these workflows

- WanVideo Lora Select / From Text: Needs JACK's WanVideoWrapper consumer nodes and Wan models.
- Lora Info: Frontend-only node (backend no-op); frontend/browser tests remain open.

Eight cases are ready for installed validation; the CLIP Hook case remains blocked on its stated host operation. These prompts are not installed-runtime certificates.
