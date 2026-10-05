# ComfyUI Image Selector — Secure Nodes V2

This conversion preserves the four batch selector and duplicator nodes while
keeping IMAGE and LATENT values opaque. Selection and repetition execute as
bounded host operations; the pack receives no raw tensor, file, network, or
host-process authority.

See `SECURE_CONVERSION.md` for the security and compatibility record.
