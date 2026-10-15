# AutoTrimBG — Secure Nodes V2

The mask-driven crop node preserves its ID, padded crop box, RGBA output,
cropped mask, and green box preview. The algorithm and image helpers remain
byte-identical to the pinned implementation, executed in a raw-compute guest.
No host filesystem, network, model, storage, graph or frontend authority is used.

The published implementation consumes one RGB/RGBA image and the first supplied
mask. Empty masks return the original image and mask, no crop box, and a mask
preview. Fractional masks retain upstream's two-stage alpha compositing.

Inputs must be finite floating-point tensors with matching spatial dimensions.
Image batch is exactly one; mask batch is bounded to 64 and only its first
member is used. Dimensions are bounded to 2..8192 and pixel count to 16,777,216.
Padding retains its published range 0..1000. Invalid inputs fail closed.
