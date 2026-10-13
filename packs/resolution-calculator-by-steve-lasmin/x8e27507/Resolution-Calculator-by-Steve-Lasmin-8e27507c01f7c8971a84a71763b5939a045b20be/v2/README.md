# Resolution Calculator by Steve Lasmin

A simple ComfyUI custom node that calculates output width and height from a maximum resolution, aspect ratio, and a block-size multiplier.

**Author:** Steve Lasmin  
**Support:** https://boosty.to/stevelasmin

## Features

- Set a **maximum resolution** (total pixel budget)
- Define **aspect ratio** via two separate integer fields (e.g., `16` and `9`)
- Choose a **multiplier** from a dropdown: `16`, `32`, or `64` (default: `32`)
- Outputs two integers: `width` and `height`, both divisible by the selected multiplier

Perfect for:
- Creating **Empty Latent Image** nodes with exact dimensions
- Resizing images before diffusion while keeping aspect ratio locked
- Ensuring dimensions are compatible with VAE/UNet block sizes

## Installation

1. Navigate to your `ComfyUI/custom_nodes/` directory
2. Clone this repository:
   ```bash
   git clone https://github.com/Eklipsis/resolution_calculator_by_steve_lasmin.git
   ```
3. Restart ComfyUI

## Usage

The node appears under **utils → Resolution Calculator by Steve Lasmin**.

| Parameter | Description |
|-----------|-------------|
| `resolution` | Maximum total pixels (width × height) |
| `width_ratio` | Aspect ratio width component |
| `height_ratio` | Aspect ratio height component |
| `multiplier` | Block size (16, 32, or 64). Default: 32 |

### Example

- Resolution: `1024`
- Width ratio: `16`
- Height ratio: `9`
- Multiplier: `32`

**Result:** width = `1088`, height = `608`

## File Structure

```
resolution_calculator_by_steve_lasmin/
├── __init__.py
├── nodes.py
├── README.md
├── LICENSE
├── .gitignore
└── pyproject.toml
```

## License

This project is licensed under the **Creative Commons Attribution-NoDerivatives 4.0 International License**.

- ✅ Free to use (personal and commercial)
- ✅ Free to share
- ❌ **Modifications and derivative works are not allowed without permission**

See [LICENSE](LICENSE) for full terms.

To request permission for modifications, contact: **real.eclipse@gmail.com**

## Support

If you find this node useful, consider supporting the author:  
https://boosty.to/stevelasmin
