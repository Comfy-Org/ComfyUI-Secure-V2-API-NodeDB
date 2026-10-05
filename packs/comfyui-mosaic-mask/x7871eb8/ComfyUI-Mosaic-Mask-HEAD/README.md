# ComfyUI-Mosaic-Mask

ComfyUI-Mosaic-Mask detects regular mosaic grids in images and returns the detected areas as a ComfyUI mask.

![Example](./example/example.png)

## Features

- Detects mosaic-like grid patterns with OpenCV template matching.
- Supports image batches.
- Returns a standard `0.0` to `1.0` ComfyUI `MASK`.
- Keeps the largest disconnected regions and optionally expands them.

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/okgo4/ComfyUI-Mosaic-Mask.git
python -m pip install -r ComfyUI-Mosaic-Mask/requirements.txt
```

Restart ComfyUI after installation.

## Usage

Load `example.json` or add `MosaicMask` from the `Mosaic Masking` category.

- `top_n`: maximum number of disconnected regions to keep, ordered by area.
- `kernel_size`: dilation kernel size. Use `0` or `1` for no expansion.
- `threshold`: template matching threshold. Higher values reduce false positives but may miss mosaics.
- `min_grid_size` / `max_grid_size`: bundled template range to search. The default is 10 through 20; lower the minimum to detect finer grids.

The node includes grid templates from size 5 through 20. It works best with axis-aligned, regular square mosaics. Rotated grids, perspective distortion, unsupported scales, and naturally repetitive textures may produce missed detections or false positives.

A smoothing node may still be added for softer mask edges, but it is no longer required to normalize the output.

## Thanks

Special thanks to the [mosaic_detector](https://github.com/summer4an/mosaic_detector) project.
