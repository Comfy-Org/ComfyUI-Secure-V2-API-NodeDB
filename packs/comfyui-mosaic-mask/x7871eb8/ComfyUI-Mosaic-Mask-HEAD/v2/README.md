# ComfyUI-Mosaic-Mask — Secure Nodes V2

This conversion preserves the pack's bundled-template mosaic detector. It
processes image batches with OpenCV, optionally dilates the detected regions,
and keeps the largest connected components as a standard ComfyUI mask.

The node runs in value mode with raw tensor access. It has no filesystem,
network, model, storage, graph, backend, or frontend authority. The only files
it reads are the 16 immutable grid templates shipped inside this package.
