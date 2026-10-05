# ComfyUI-Mosaic — Secure Nodes V2

This conversion preserves the Mosaic Creator and Mosaic Detector nodes inside an
isolated raw-compute guest. It requires no filesystem, network, model, storage,
graph, backend, or frontend authority.

The upstream `WEB_DIRECTORY` declaration is inert at the pinned revision: the
repository contains no `web/` directory and no frontend code. This conversion
therefore exposes exactly the two registered Python nodes and no frontend surface.
