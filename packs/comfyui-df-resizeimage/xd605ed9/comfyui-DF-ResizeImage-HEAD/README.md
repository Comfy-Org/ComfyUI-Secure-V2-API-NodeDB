# comfyui-DF-ResizeImage

This custom node resizes an image while forcing the final width and height to be multiples of a chosen value.

## Features

- Resize by long side while keeping aspect ratio.
- Resize by short side while keeping aspect ratio.
- Resize by scale factor.
- Set output by long side and short side directly.
- Return the resized image together with the final width and height.
- Default alignment is `multiple_of = 16`.

## Example

If the input image is `1111 x 1126` and you choose:

- `mode = long_side`
- `long_side = 1536`
- `multiple_of = 16`
- `rounding = nearest`

The output size will be `1520 x 1536`.

## Install

1. Clone this repository to `ComfyUI/custom_nodes/comfyui-DF-ResizeImage`.
2. Restart ComfyUI.

## Inputs

- `image`: ComfyUI image input.
- `mode`: `long_side`, `short_side`, `scale_factor`, or `long_and_short`.
- `interpolation`: `bicubic`, `bilinear`, `area`, or `nearest`.
- `multiple_of`: force both sides to be multiples of this number.
- `rounding`: how values are snapped to the multiple. Use `nearest` for the example above.
- `long_side`: used by `long_side` and `long_and_short`.
- `short_side`: used by `short_side` and `long_and_short`.
- `scale_factor`: used by `scale_factor`.

## Outputs

- `image`: resized image.
- `width`: final output width.
- `height`: final output height.
