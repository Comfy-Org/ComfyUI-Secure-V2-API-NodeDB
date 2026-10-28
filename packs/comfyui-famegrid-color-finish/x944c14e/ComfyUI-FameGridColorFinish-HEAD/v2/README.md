# ComfyUI FameGrid Color Finish

A lightweight, deterministic ComfyUI finishing node from [FameGrid](https://famegrid.ai). It applies FameGrid's color-and-detail recipe without calling an API or downloading additional models.

## What it does

- Adds a `color_strength` control (default `1.0`) that scales saturation, lightness, and all tonal color-balance adjustments together.
- Adds a separate `sharpen_strength` control (default `0.6`).
- A value of `0` bypasses that part of the finish; `1` applies the full recipe.
- Preserves pre-balance lightness to limit exposure shifts.
- Preserves alpha channels.
- Processes ComfyUI image batches directly with PyTorch.

The node is deterministic for a given pair of settings. It does not perform adaptive white balance, automatic contrast normalization, skin detection, or image analysis.

## Install

### Git

Open a terminal in your ComfyUI `custom_nodes` directory and run:

```bash
git clone https://github.com/Elevenheights/ComfyUI-FameGridColorFinish.git
```

Restart ComfyUI after installation.

### ComfyUI Manager

Choose **Install via Git URL**, enter:

```text
https://github.com/Elevenheights/ComfyUI-FameGridColorFinish.git
```

Then restart ComfyUI.

## Use

Add **FameGrid → Color → Color Finish (FameGrid)** and connect an `IMAGE` input. Adjust **color strength** and **sharpen strength** as needed, then connect its output to `Save Image` or the next image-processing node.

No additional Python dependencies are required beyond ComfyUI's existing PyTorch installation.

## License

MIT. See [LICENSE](LICENSE).
