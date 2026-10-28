# ComfyUI-Nano-Banana-Resizer

A ComfyUI node that maps an image's nominal aspect ratio to the exact documented Nano Banana output resolution. It does not perform the resize itself.

## Usage

Connect an image, select a preset, and connect the `width` and `height` outputs to your resize node. Send the resized image and returned `aspect_ratio` to the Nano Banana generator, and select the same model and resolution (1K, 2K, or 4K) there. `aspect_ratio` defaults to `auto`; the node chooses the nearest supported nominal ratio by relative shape difference, independently of the input's pixel count. You can select one of the supported ratios explicitly. Ratios outside the model's range map to its nearest supported ratio.

For example, a 3571×4464 input with `NB 2 (4K)` now returns **3712×4608** and **4:5**.

The width and height outputs are target dimensions for a separate resizing policy. Choose padding to preserve the full image without stretching, or cropping/stretching if that suits your workflow. Input size alone does not force the generator's output size: use the returned ratio and matching resolution in its settings. This calculator cannot prevent generative content drift.

The existing method choices (`Clamp (reccomended)`, `Dynamic (legacy)`, and `Static`) are retained for saved workflows. They are aliases of the same exact lookup algorithm; the method value no longer changes the selected resolution.

The historical `NB 2 (1K/2K/4K)` names mean Nano Banana Pro at those scales. They do not mean Flash 3.1. Explicit `Nano Banana 2 Flash (1K/2K/4K)` presets are also available and add the four extreme ratios supported by that table.

## Presets

The tables below are from Google's official [Gemini image generation documentation](https://ai.google.dev/gemini-api/docs/image-generation?hl=pl).

### Nano Banana (NB 1)

| Aspect ratio | 1:1 | 2:3 | 3:2 | 3:4 | 4:3 | 4:5 | 5:4 | 9:16 | 16:9 | 21:9 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Resolution | 1024×1024 | 832×1248 | 1248×832 | 864×1184 | 1184×864 | 896×1152 | 1152×896 | 768×1344 | 1344×768 | 1536×672 |

### Nano Banana Pro

Pro 1K uses 1024×1024, 848×1264, 1264×848, 896×1200, 1200×896, 928×1152, 1152×928, 768×1376, 1376×768, and 1584×672 for the ratios above, in the same order. Pro 2K and 4K multiply every Pro 1K dimension by 2 and 4.

### Nano Banana 2 Flash

Flash uses the Pro 1K table and adds 1:4 = 512×2048, 1:8 = 384×3072, 4:1 = 2048×512, and 8:1 = 3072×384 at 1K. Flash 2K and 4K multiply every 1K dimension by 2 and 4.

All selected output dimensions and the returned aspect ratio come from the same table entry, so they can be wired together directly.
