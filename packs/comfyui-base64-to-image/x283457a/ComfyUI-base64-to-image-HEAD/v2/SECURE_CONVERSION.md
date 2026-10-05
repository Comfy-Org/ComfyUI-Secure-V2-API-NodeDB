# Secure Nodes V2 conversion

- Upstream: <https://github.com/glowcone/comfyui-base64-to-image>
- Pinned commit: `283457a6779e5456e15c7865a7126931a4992419`
- Census: 1 Python node, 0 frontend extensions, 0 JavaScript-only nodes,
  and 0 backend routes.
- Disposition: 1 supported, 0 rejected, 0 pending.

`LoadImageFromBase64` decodes the untrusted string entirely in the isolated
guest. It retains upstream OpenCV BGR/BGRA-to-RGB behavior, returns the alpha
channel as the mask, and returns an all-ones mask for an RGB image. Encoded and
decoded byte limits plus dimension and pixel limits are checked before OpenCV
allocates the decoded tensor. It requests only the public `raw` capability and
has no file, network, model, graph, storage, output, or frontend authority.

The upstream `pyproject.toml` declares `license = "LICENSE"`, but the pinned
repository does not contain that file. The conversion does not invent or
change the upstream licensing terms.
