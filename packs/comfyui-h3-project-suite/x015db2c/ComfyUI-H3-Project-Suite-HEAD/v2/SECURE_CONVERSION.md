# Conversion audit

## Source

- Repository: `https://github.com/Adudeguyman/ComfyUI-H3-Project-Suite`
- Commit: `015db2c5687908ad07bfa9b9c463802c8a273e07`
- Python census: 7/7 registered nodes supported
- Frontend census: 1/1 extension converted to a mounted V2 sidebar

## Behavioral mapping

| Upstream behavior | Secure V2 authority |
| --- | --- |
| H3 native video/audio continuation guides | `CondRef.with_minimax_h3_guides` |
| Heterogeneous H3 AV latent | portable nested tensor transport |
| Video VAE encode and audio VAE encode | typed `VaeRef` operations |
| Lanczos conforming | `ImageRef.resize` |
| Pixel/audio trim and resample math | guest-owned Torch code |
| Saved AV latent | managed `output.save_state_dict` + `assets.load_state_dict` |
| Review MP4 | managed `output.save_video` |
| Project manifest/review state | tenant-scoped `ctx.storage` |
| Project panel | `comfy.ui.addSidebarTab` + `backend.ownFetch` |

No compatibility patches from the upstream build are carried into V2. Current
ComfyUI publishes the required native MiniMax H3 conditioning behavior, and
the SDK exposes it as a validated closed operation.

## Pinned contracts

- `comfy-api.d.ts`: SHA-256 `73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d`
- `comfy-api.pyi`: SHA-256 `aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d`

## Explicit gaps

Master concatenation/export, drift and level-match analysis, panel-driven
source import, and destructive cleanup are not yet implemented.
They are omitted rather than bridged to raw filesystem or server authority.
