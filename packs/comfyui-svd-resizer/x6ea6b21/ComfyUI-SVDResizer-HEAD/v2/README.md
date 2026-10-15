# SVDResizer — Secure Nodes V2

Resize images using the six original interpolation modes, optionally fitting
the original proportions. Returns the image and its actual width and height.
The workflow node ID is `SVDRsizer`, as upstream spells it.

Pixel math stays pack-owned under the isolated raw tier. There is no durable
state or host file/network authority. See SECURE_CONVERSION.md for evidence.
