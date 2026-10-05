# Secure conversion record

- Upstream: `https://github.com/codeprimate/ComfyUI-MaskContourProcessor`
- Pinned commit: `aa2b22b3f4fd2c2e0f81be39e8b5077ab18126c2`
- Census: 1 Python node, 0 runtime frontend extensions, 0 routes
- Authority: bounded pack-owned raw tensor computation only

`algorithm.py` is a byte-exact copy of the pinned node algorithm. The V2
wrapper validates tensor shape, dtype, finiteness, dimensions, batch size, and
all published controls before entering it.

## Deliberate robustness correction

The pinned implementation divides by zero or indexes an empty contour for
empty and degenerate masks. The secure wrapper detects only those undefined
geometries and returns the original mask after the requested Gaussian blur.
Ordinary contours continue through the byte-exact pinned implementation and
are tested differentially.

The upstream `web/` directory is a standalone browser demonstration. It is not
registered by the Python package, does not call `app.registerExtension`, and
is intentionally retained only in the pristine snapshot.
