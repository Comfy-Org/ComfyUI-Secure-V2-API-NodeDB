# Secure Nodes V2 conversion

Upstream: `https://github.com/wutipong/ComfyUI-TextUtils`

Pinned commit: `0205574631195bc2a00dcc96ae7598eaef0ce592`

All four registered Python nodes are converted. They retain their exact node IDs,
display names, schemas, list-input/list-output behavior, and string operations.
They execute in the isolated guest with no permissions or host capabilities.

The conversion adds only resource bounds for untrusted text and list inputs. The
upstream project metadata names a `LICENSE` file that is absent at the pinned
commit; this conversion does not invent one.

There is no frontend, route, filesystem, network, model, tensor, or subprocess
surface and no remaining API or behavior gap.
