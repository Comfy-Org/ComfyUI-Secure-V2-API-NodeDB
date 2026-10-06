# AutoSplitGridImage — Secure Nodes V2

Two nodes preserve the pinned pack's image behavior: `GridImageSplitter` makes
a split-line preview and resized cell batch; `EvenImageResizer` crops odd-sized
dimensions to even sizes. Algorithms remain pack-local in the raw compute guest.
There is no frontend extension and no filesystem, network, model or graph access.

Grid cells intentionally come from the first input image, while preview lines
are drawn across the whole input batch, exactly as upstream. Cells are quantized
to RGB uint8, resized with OpenCV Lanczos4, centered and returned as float32.

Malformed, nonfinite, excessively large or undersized inputs fail closed. Grid
output is conservatively bounded by `rows * cols * height * width` before the
algorithm allocates resized cells. Some pathological border/grid combinations
still produce upstream's empty-cell errors; this conversion does not invent
replacement cells or change the grid algorithm.
