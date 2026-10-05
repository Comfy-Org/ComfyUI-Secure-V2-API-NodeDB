# Mask Contour Processor — Secure Nodes V2

This conversion preserves the `MaskContourProcessor` node and its flame-like
mask contour effect. The pinned algorithm remains pack-owned and runs in the
isolated raw-compute guest; it receives no filesystem, network, model, graph,
storage, or frontend authority.

The standalone HTML/JavaScript demo under the pristine pack's `web/` directory
was never exported to ComfyUI and is not part of the runtime conversion.

Empty or geometrically degenerate masks previously failed while normalizing an
undefined contour direction. They now return the original mask with the node's
requested Gaussian blur. This is the sole deliberate behavior correction.
