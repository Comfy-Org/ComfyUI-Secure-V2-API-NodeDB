# Easy Padding — Secure Nodes V2

One image-to-image/mask padding node. The pinned Pillow/NumPy/Torch algorithm
stays in the isolated guest under the `raw` permission. No host files, network,
models, frontend, storage, or process authority is used.

The existing RGB/RGBA conversion, transparency, full batch ordering, uint8
quantization, and inclusive rectangle mask edge are preserved. Outputs are
CPU float32, as upstream. Finite BHWC inputs (2–8192 pixels per dimension),
batch 1–64, paddings 0–4096, and at most 16,777,216 padded pixels are admitted.
The original one-pixel squeeze/Pillow failure is rejected explicitly.
