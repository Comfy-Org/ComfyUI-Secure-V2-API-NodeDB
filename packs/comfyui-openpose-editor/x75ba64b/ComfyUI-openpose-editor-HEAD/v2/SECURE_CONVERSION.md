# Secure Nodes V2 conversion

Upstream: `https://github.com/huchenlei/ComfyUI-openpose-editor`  
Pinned commit: `75ba64b5704e2f9f02accf4eee42b7458966d5d3`

## What works

- Backend nodes: **1/1 supported** — `huchenlei.LoadOpenposeJSON` parses the
  same JSON text and returns the same `POSE_KEYPOINT` value.
- The node is permission-free and runs in the isolated guest process.

## What is rejected

- Frontend registrations: **0/1 supported, 1/1 rejected** —
  `huchenlei.EditOpenpose` loads executable UI code from the mutable remote
  page `https://huchenlei.github.io/sd-webui-openpose-editor`, then exchanges
  pose data using `postMessage(..., "*")`. Secure Nodes does not restore a
  network-loaded third-party iframe with a wildcard message target. That would
  give code outside the reviewed pack control of workflow data and would make
  the installed pack change whenever the remote site changes.

The legacy JavaScript is therefore absent from V2, as is `WEB_DIRECTORY`.
Opening the remote editor is unavailable; loading, validating, and passing
already-authored OpenPose JSON remains available.

## API status

Pending API gaps: **none**. This conversion adds no SDK or backend surface, so
there is no new V2 Python API decision to document. A future reviewed,
fixed-origin external-editor facility could reconsider the rejected UI, but
the pack does not require or receive ambient DOM, network, or messaging
authority here.
