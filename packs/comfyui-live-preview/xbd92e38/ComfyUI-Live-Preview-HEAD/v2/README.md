# ComfyUI Live Preview — Secure Nodes V2

This conversion preserves the image pass-through node and its large live denoising-preview window. The window is rendered through the typed graph-overlay API, can be moved and resized, and stores only bounded per-user geometry.

The conversion does not access the ambient page, canvas internals, global browser storage, private backend routes, or the network.
