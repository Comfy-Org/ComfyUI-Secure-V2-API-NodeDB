# Secure Nodes V2 conversion

Upstream: `https://github.com/Lhyejin/ComfyUI-Fill-Image-for-Outpainting`

Pinned commit: `4c21e317c04b2e87fe3c2f9c2fcbae94be250b80`

The single registered node is supported. Its three image-fill algorithms remain
pack-owned and execute in the bounded raw-compute tier. The conversion preserves
the original first-image behavior, quantization, mask result, OpenCV algorithms,
and iterative edge padding. It has no frontend extension, route, filesystem,
network, model, or process authority.
