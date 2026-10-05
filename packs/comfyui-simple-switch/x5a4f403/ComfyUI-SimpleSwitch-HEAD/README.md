# ComfyUI Simple Switch

ComfyUI custom nodes for returning the first available value from six optional inputs.

## What it does

- `SimpleSwitch`
  - Accepts six optional wildcard inputs: `input01` ... `input06`
  - Returns the first non-empty input in order
  - Preserves original behavior for empty model/clip context dictionaries
  - Uses wildcard typing so it can pass through most ComfyUI value types
  - Preserved as the original implementation behavior
- `SimpleLatentSwitch`
  - Accepts six optional `LATENT` inputs
  - Returns the first non-empty latent in order
  - Useful for generic latent routing where latent subtype does not matter
- `SimpleVideoLatentSwitch`
  - Accepts six optional `LATENT` inputs
  - Returns the first non-nested 5D video latent
  - Use this for LTX video latent branches
- `SimpleAudioLatentSwitch`
  - Accepts six optional `LATENT` inputs
  - Returns the first latent compatible with LTX audio decode
  - Rejects incompatible latent shapes instead of forwarding them blindly

## Credits

This node is isolated and renamed from `EGRYQHNode` in:

- [11dogzi/Comfyui-ergouzi-Nodes](https://github.com/11dogzi/Comfyui-ergouzi-Nodes)
- Source file: `nodes/egryqh.py`

Original author: **11dogzi**

## Installation

Clone into your ComfyUI `custom_nodes` directory:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/boobkake22/ComfyUI-SimpleSwitch.git
```

Restart ComfyUI after installing.

## Usage

1. Add `SimpleSwitch` for general pass-through selection, `SimpleLatentSwitch` for subtype-agnostic latents, `SimpleVideoLatentSwitch` for LTX video branches, or `SimpleAudioLatentSwitch` right before `LTXV Audio VAE Decode`.
2. Connect values to `input01` ... `input06` in your preferred priority order.
3. Use `output` downstream.

## LTX audio note

LTX video latents and LTX audio latents both use the ComfyUI `LATENT` socket type, but
they are not interchangeable. The video path expects a plain 5D video latent, while the
audio path expects a 4D audio latent or a nested AV latent. If you route LTX latents
through the generic wildcard `SimpleSwitch`, or through a subtype-blind latent switch,
you may only discover the mismatch much later at decode time.

Use `SimpleVideoLatentSwitch` for LTX video latent branches and `SimpleAudioLatentSwitch`
immediately before `LTXV Audio VAE Decode` for audio latent branches.

## License

This repo includes the original upstream `LICENSE` from
`11dogzi/Comfyui-ergouzi-Nodes`.
