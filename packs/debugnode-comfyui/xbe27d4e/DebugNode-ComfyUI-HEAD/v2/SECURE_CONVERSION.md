# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/webfiltered/DebugNode-ComfyUI`
- Pinned commit: `be27d4e6ac89a1dc44c707c37439c4b214beb571`
- Release key: `xbe27d4e`
- Pristine non-V2 tree SHA-256: `c893e4e537f1ac3b30b966467f1a21ebab831194204deababf66c06618e685e1`
- The pinned source worktree was clean when captured.

## Exact census

- Backend registrations: 1. `WTFDebugNode` (`🐜 WTF?`) is supported.
- Frontend registrations: 1. The `WTFDebugNode` execution readout is supported.
- Routes: 0.
- Non-node intents: 0 beyond the registered node's readout behavior.
- Working: 1/1 backend nodes and 1/1 frontend registrations.
- Rejected: 0/1 backend nodes and 0/1 frontend registrations.
- Pending API gaps: none.

## Frozen public artifacts

- `comfy-api.pyi`: SHA-256 `9fa75d099086e25a456aad642306fd8d12a5d8f3d1a090b45393018a5b8258a8` (57,021 bytes; 1,040 lines).
- `comfy-api.d.ts`: SHA-256 `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`.
- The Python stub contains the frozen bounded `Ref.describe` contract used by this release.

## Behavior and authorities

`WTFDebugNode` remains an output node with a wildcard list input and no graph
outputs.  It reports the input type and, when available, length, shape, first
item description, and value summary.  The visible result remains capped at the
upstream frontend's 100-item hard limit.

The node declares only the `inspect` permission.  Exact built-in primitives
and JSON-like containers are formatted by pack code with a 32,768-character
budget and a depth bound.  Every live ComfyUI value remains an opaque
`sdk.Ref`; the pack obtains only the host's fixed seven-field
`Ref.describe(32768)` projection.  Tensor values, model contents, paths, and
unknown-object behavior never cross the boundary.  The pack has no filesystem,
network, subprocess, dynamic-import, model, or tensor authority.

The frontend has one `comfy.defs.extend('WTFDebugNode', ...)` registration.  It
creates non-serializing, disabled readouts, reconciles stale pack-owned widgets,
and requests automatic height.  The legacy extension mutated wildcard link
records solely to repair their colour; V2 links are typed and rendered by the
host, so the guest neither mutates serialized graph links nor needs a second
registration for that cosmetic effect.

## Verification

The focused conversion suite pins the pristine source digest and exact census,
derives the reachable guest-module closure from the manifest with an AST walk,
checks the sole `inspect` permission and bounded projection shape, proves
primitive/container formatting, tensor and hostile-object redaction, exercises
successful execution in a real `GuestSession` process with live PID evidence,
checks the missing-permission denial, and runs the frontend through a real
opaque `sandbox="allow-scripts"` iframe.  The final suite additionally pins the
frozen API stubs, checked patch pair, reconstruction roundtrip, cache hygiene,
and owned write set.
