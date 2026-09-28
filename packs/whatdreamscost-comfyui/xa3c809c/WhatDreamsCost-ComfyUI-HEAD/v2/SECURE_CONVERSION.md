# Secure Nodes V2 conversion

- Upstream: https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
- Pinned commit: `a3c809c8b593a74c2ddcd6c1f83ad85ebebe3c64`
- Backend census: **9 supported, 0 rejected, 0 pending**.
- Frontend census: **8 supported, 0 rejected, 0 pending**.

All nine registered nodes preserve their public IDs and schemas. The eight
frontend modules use the Secure Nodes V2 facade and run in the pack's isolated
frontend realm. LTX Director retains its pack-owned timeline editor and uses a
narrow host-owned `prompt_relay` model transform for cross-attention patching.
Its media analysis, waveform/playback, clipboard, managed-upload, and scoped
keyboard paths use permission-checked host capabilities; see the repository's
`docs/whatdreamscost-v2-conversion-evidence.md`.

## Permissions

- `assets`: catalogue-selected media and SafeTensors metadata.
- `clipboard.read` / `clipboard.write`: user-gesture-scoped timeline and prompt
  clipboard actions.
- `files.upload`: bounded resumable publication into managed ComfyUI input
  storage.
- `media.audio` / `media.video`: bounded waveform/playback and frame sampling
  for managed media.
- `raw`: bounded pack-owned image, video, latent, and guide calculations.

## Deliberate secure adaptations

- Media uploads use the host's resumable managed-file capability. Chunks are
  ordered and bounded, retries are idempotent, completion publishes atomically,
  and the guest never receives an ambient filesystem path.
- Video thumbnails and audio waveforms/playback use typed media capabilities.
  The guest receives bounded samples and opaque playback handles rather than
  raw host objects.
- Clipboard reads and writes require both declared permissions and a recent
  trusted gesture owned by this pack.
- The local-only “open workspace folder” action is disabled. A cloud guest
  must not launch the host OS file manager.
- Timeline styles, menus, pointer handling, and keyboard ownership stay inside
  the mounted editor. They do not append to the host document or install
  global page listeners.
- Timeline JSON import/export uses the bounded host file picker/downloader.
- The editor no longer reaches into an arbitrary upstream node to mutate its
  first widget. Connected prompt values still flow through normal execution.

## Validation boundary

Behavior tests cover schema/census, prompt and timeline calculations, media
processing, guide cropping, sandbox execution, frontend registration and
mounting, resumable uploads (including retry/cancel), real browser video-frame
sampling, real Web Audio decode/schedule, gesture-scoped clipboard calls,
host-owned media elements, scoped keyboard focus, sandbox boundaries, and patch
roundtrip. Model-specific Wan/LTX attention wiring is tested with representative
host model doubles; full GPU generation with the production model weights
remains the only unexercised integration boundary.
