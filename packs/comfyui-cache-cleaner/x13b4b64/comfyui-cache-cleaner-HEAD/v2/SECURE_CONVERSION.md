# Secure conversion report

- Upstream: `https://github.com/AIToldMeTo/comfyui-cache-cleaner`
- Pin: `13b4b64fefdd4bffdf95c0ff06cc328081979ca9`
- Census: 1 Python node, 0 frontend extensions, 0 routes.
- Supported: `CacheCleaner` (1/1).
- Permissions: `models.manage` only.

The legacy node posted to its own unrestricted loopback `/api/free` endpoint
and included the server bind address in its output. V2 invokes the existing
bounded `models.memory_cleanup` broker and reports that the address is managed
by the secure host. Optional wildcard, image, and model values retain their
opaque identities and are returned unchanged. No pack network access remains.
