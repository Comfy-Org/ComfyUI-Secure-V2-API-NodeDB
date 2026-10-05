# ComfyUI Image Properties SG — Secure Nodes V2

This build supports Nodes V2 and secure cloud execution. It preserves the four
original nodes for loading, viewing, previewing, and saving images while showing
dimensions, resolution, aspect ratio, tensor/file size, and available generation
metadata.

The save node supports PNG, JPEG, WebP, BMP, and TIFF with the original quality
and compression choices. Only PNG carries ComfyUI workflow metadata, matching
the upstream behavior.

All filesystem and output operations are brokered. The frontend uses mounted,
node-scoped UI and does not access ambient graph or browser globals.

See `SECURE_CONVERSION.md` for the pinned source, complete support census, and
verification details.
