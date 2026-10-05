# Secure Nodes V2 conversion

Upstream: `https://github.com/Tropfchen/ComfyUI-yaResolutionSelector`

Pinned commit: `926d0faf98b029f1ca99c5a85bd9d8ea360e0857`

Both registered Python nodes and the single frontend extension are supported.
The exact shipped ratio catalogue, dimension math, output UI values, readout,
and quick-node menu actions are retained.

The shipped ratio list is immutable in a cloud package. The legacy import-time
write to `ratios.txt` and deletion from ComfyUI's global web directory are
removed. Frontend behavior uses typed mounted widgets and graph handles, with
no ambient DOM, filesystem, network, storage, or backend authority.
