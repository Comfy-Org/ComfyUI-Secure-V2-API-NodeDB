# H3 Project Suite — Secure Nodes V2

This directory contains the Secure Nodes V2 conversion of H3 Project Suite,
pinned to upstream commit `015db2c5687908ad07bfa9b9c463802c8a273e07`.

The conversion preserves all seven registered nodes:

- H3 Context
- H3 Context Trim
- H3 Import Source
- H3 Context Save Latent
- H3 Context Load Latent
- H3 Project Hub
- H3 Project Save

The continuation math remains pack-owned. H3 video and audio tensors cross the
sandbox as a heterogeneous nested latent, while the host keeps VAE operations,
MiniMax guide-conditioning, managed assets, output encoding, and tenant storage
behind typed SDK references. The V2 build does not import or monkey-patch
ComfyUI core.

The project sidebar supports project creation, take selection, approval,
rejection, reopening the last approved clip, auto-approval, and bounded project
status. It can branch at an approved take by copying the bounded manifest while
reusing immutable managed output references. UI is mounted through the V2 sidebar API and all state changes go
through pack-private, capability-scoped routes.

## Deliberate current limitations

The upstream panel's master export, visual drift/level analysis, source-file
filmstrip importer and trash cleanup are not exposed by this
conversion yet. The graph-level H3 Import Source node is supported. These gaps
are explicit; the secure build does not emulate them through raw filesystem,
server, or ambient browser access.

## Validation

`tests/test_secure_conversion.py` checks the node census and schemas, 24 fps
frame mapping, sample-locked audio trim, native H3 guide placement, project
state transitions, the frontend authority boundary, and execution through a
real secure guest. The real-guest coverage includes heterogeneous H3
video/audio latent transport.

See `SECURITY.md` and `SECURE_CONVERSION.md` for the authority and fidelity
audit.
