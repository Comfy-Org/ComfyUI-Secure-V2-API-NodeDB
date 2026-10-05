# Secure Nodes V2 conversion

- Upstream: `https://github.com/laurigates/comfyui-touch-resize`
- Pinned commit: `a52ed4cc2932151d06a096cf02ef0c4c12cb7708`
- Census: 0 Python nodes, 1 frontend extension, 0 routes

The legacy window-level pointer capture and direct LiteGraph mutation were
replaced with a bounded graph overlay, typed node/group selection, intrinsic
node minimum-size reads, and normal typed resize mutations. The host owns
pointer capture, hit testing, document confinement, and teardown.

No behavior gap is retained. The legacy TypeScript build tree and bundled
ambient-host JavaScript are intentionally absent from the V2 package.
