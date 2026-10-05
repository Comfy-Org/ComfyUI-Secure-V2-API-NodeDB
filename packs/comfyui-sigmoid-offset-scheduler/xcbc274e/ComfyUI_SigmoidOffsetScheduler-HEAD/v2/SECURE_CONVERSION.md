# Secure Nodes V2 conversion

Upstream is pinned at `cbc274e54eb9229f16c60e8c30058135140931c2`.

The single registered node preserves its five inputs and `SIGMAS` output. The
pack's legacy mutation of ComfyUI's process-global scheduler tables is replaced
by the declarative `sigmoid_offset` scheduler provider. The provider receives a
bounded host projection of the model's sigma table; the guest never receives a
model object or model weights.

The node uses the typed model-schedule projection method and the public bounded
`SigmasRef.from_values` constructor. It requests only the sigma scalars selected
by the original sigmoid index calculation. No filesystem, network, raw tensor,
process, UI, or persistent-storage authority is granted.
