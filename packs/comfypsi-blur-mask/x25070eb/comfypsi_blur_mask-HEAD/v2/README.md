# Blur Mask — Secure Nodes V2

Preserves the pinned separable Gaussian mask convolution and 225px initial node
width. The algorithm remains pack-owned and requires `raw` only; frontend code
uses typed definition and node-size handles, with no ambient canvas access.

See `SECURE_CONVERSION.md` for provenance, safety bounds and validation.
