# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/yushan777/ComfyUI-Y7-SBS-2Dto3D`
- Pinned commit: `b8c0c7b3ff4ea79542423ecbc9d63756d0945a34`
- Release key: `xb8c0c7b`
- Pristine non-V2 tree SHA-256: `7b4a1953ff906ff0298fce8e106cc1207b3285ca151fbc77c15d2337a0227b7e`
- The pinned source worktree was clean when captured.

## Exact census

- Backend registrations: 2. `Y7_SideBySide` and `Y7_VideoSideBySide` are supported.
- Frontend registrations: 2. `Y7.SideBySideNodes` sizing and `Y7.SBS.HelpPopup` help are supported.
- API/data routes: 0. The single legacy `web.static` registration is redundant infrastructure replaced by V2 `WEB_DIRECTORY` delivery.
- Non-node intents: node documentation/help plus packaged README, examples, workflows, and image assets; all are preserved.
- Working: 2/2 backend nodes and 2/2 frontend registrations.
- Rejected: 0/2 backend nodes and 0/2 frontend registrations.
- Pending API or dependency gaps: none.

## Frozen public artifacts

- `comfy-api.pyi`: SHA-256 `9fa75d099086e25a456aad642306fd8d12a5d8f3d1a090b45393018a5b8258a8`.
- `comfy-api.d.ts`: SHA-256 `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`.

## Behavior and authorities

Both nodes preserve the upstream IMAGE contracts, node IDs, display names,
categories, rendering methods, viewing modes, layouts, approximate depth blur,
and red-cyan anaglyph construction. The video node also preserves sequential
temporal disparity smoothing across guest-side processing batches. Its legacy
temporary `numpy.memmap` was only a scratch spill, so the V2 implementation
uses bounded in-memory batches and concatenation without filesystem access.
Both nodes retain their progress updates through the brokered progress domain.

The tensor and stereo algorithms remain pack-side and both nodes declare only
the `raw` permission. Output is bounded to 4,096 frames, 16,384 pixels per
axis, and 134,217,728 working elements. There is no filesystem, network,
subprocess, secret, model, download, or host-internal authority. `torch` is the
sole managed dependency declared in `pyproject.toml`; there is no runtime
installer file in V2.

The sizing extension uses the typed node size facade. The legacy canvas help
question mark and document-global popup are represented by a host menu and a
host-mounted text dialog, retaining both safe readouts without parent-window,
parent-DOM, renderer-internal, or same-origin access.

## Verification

The focused suite pins the pristine source and exact 2/2 + 2/2 census, derives
the reachable guest-module closure from the manifest with an AST walk, checks
the sole `raw` permission, differentially compares every image method/layout
and the video temporal-smoothing path against the pinned implementation,
exercises successful calls in a real `GuestSession` with immediate live PID
evidence, proves permission denial, and runs both frontend registrations in a
real opaque `sandbox="allow-scripts"` iframe. Final checks pin the frozen API
stubs, checked patch pair, reconstruction roundtrip, cache hygiene, and owned
write set.
