# Secure Nodes V2 conversion

Upstream: `https://github.com/Endericedragon/comfyui-mdnotes`  
Pinned commit: `80c503631f15229c5a0437fe6eb244b4b98b9037`

## Census and disposition

- Backend nodes: 3 supported, 0 rejected, 0 pending.
- Frontend extensions: 1 supported, 0 rejected, 0 pending.
- Resources: two documentation PNGs and five legacy PrimeIcons font files are
  preserved. The converted editor loads no remote executable resources.

The three nodes retain their IDs, labels, categories, pass-through behavior,
and host-populated model catalogues. The frontend retains model-widget
discovery, its node context menu, an interactive Markdown dialog, formatting
controls, live preview, explicit save, optional save-on-close, fuzzy sibling
matching, and dialog-scoped keyboard handling.

The dialog uses `comfy.ui.showDialog`; settings, menus, notifications, and
dialog-scoped keyboard handling use typed facade handles. Its formatting
toolbar and live Markdown preview are bundled with the pack and build DOM only
inside the host-provided dialog container. It loads no CDN code and has no
ambient `window`, `document`, backend route, or network access.

Existing model-adjacent `.md` notes are read through the bounded
`comfy.models` catalogue. The pack must first resolve the exact logical model
name with `models.list(folder)`, then may read only the adjacent UTF-8 `.md`
sidecar through `models.readSidecar(...)`; no host path is disclosed. UNET
lookup preserves the upstream order by checking `unet` before
`diffusion_models`.

Model sidecars remain read-only. New notes and edits are stored under the
pack's per-user `comfy.storage` namespace, bounded to 512 KiB per note. This
lets authored notes follow the user without granting the pack write access to
shared model directories. A private authored note takes precedence over a
sidecar on later opens, and fuzzy matching remains limited to those private
notes in the same logical model folder.

The legacy custom HTTP routes, arbitrary model-directory writes, and Vditor
CDN/cache service are removed. No `_secure_routes.py` is needed.
