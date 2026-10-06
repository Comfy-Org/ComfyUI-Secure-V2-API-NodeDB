# Auto Crop by NPS — Secure Nodes V2

Preserves the original node's image/mask crop, white border expansion and
clockwise rotation using pack-owned Pillow code in the isolated raw tier.
Optional image and mask are independent, including their batch and geometry.

All five controls serialize in the workflow; the pack needs no durable state.
See SECURE_CONVERSION.md for resource limits, evidence, and licensing provenance.
