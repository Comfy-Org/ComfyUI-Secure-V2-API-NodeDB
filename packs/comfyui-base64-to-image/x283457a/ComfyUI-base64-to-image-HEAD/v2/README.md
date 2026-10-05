# comfyui-base64-to-image — Secure Nodes V2

This conversion preserves the pack's single node:

- **Load Image From Base64** decodes a base64-encoded RGB or RGBA image and
  returns its image and transparency mask.

The conversion runs decoding inside the isolated node guest and applies
bounded byte, dimension, and pixel limits before image allocation.
