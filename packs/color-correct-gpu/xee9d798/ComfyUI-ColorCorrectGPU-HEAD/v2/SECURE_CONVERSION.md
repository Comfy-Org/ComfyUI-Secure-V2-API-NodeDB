# Secure conversion

- Upstream: <https://github.com/boobkake22/ComfyUI-ColorCorrectGPU>
- Pinned commit: 'ee9d798ec7c8a95c5f8d6b96c4eef90927762870'
- Pinned tree: 'ba0fe31ad380baee6f612bb2119e55aed0a59609'
- Release ID: 'xee9d798'
- Census: one Python node, no frontend extensions, no routes

## Authority

'ColorCorrectGPU' declares only the 'raw' permission. It uses value-mode image
tensors ('SDK_REFS = False') so the algorithm remains inside the isolated guest.
It has no filesystem, network, subprocess, model, graph, storage, or frontend
authority.

The host owns device placement at the guest boundary. The node performs its
math on the materialized tensor's device, converts temporarily to float32 as
upstream does, and returns the result using the original tensor dtype/device
where that boundary permits.

## Bounds

Input is limited to a non-empty BHWC float tensor with three or four channels,
batch size at most 256, dimensions at most 8192, and at most 134,217,728
elements. The upstream 16-million-pixel chunk target remains in effect.

No behavior is pending or rejected.
