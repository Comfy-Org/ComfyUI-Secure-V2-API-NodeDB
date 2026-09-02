# Secure Nodes V2 conversion

This conversion targets MinorBoy/ComfyUI_essentials_mb at commit
`09e7dce4aa3d734151b772da4a4b3abe1c62e7e2`.

## Census and disposition

- Backend nodes: **85 supported, 0 rejected, 0 pending**.
- Frontend registrations: **4 supported, 0 rejected, 0 pending**.
- Routes, server hooks, and startup mutations: **none**.

The fork retains the same 85 node identities as the already converted
ComfyUI_essentials pack. Its two functional differences are preserved here:
`DrawText+` uses typed COLOR inputs with explicit text/background alpha, and
`SDXLEmptyLatentSizePicker+` includes the fork's additional portrait,
landscape, and high-resolution choices. Categories remain under
`essentials_mb/**`, so workflows continue to distinguish the fork.

Ordinary image, mask, latent, audio, and value algorithms run in the guest
through typed refs. Fonts and LUTs are immutable pack assets. Live MODEL,
CLIP, sampling, preview, and model-weight behavior use the same closed SDK
operations proven by the parent Essentials conversion. The four frontend
registrations are expressed through the opaque V2 facade and do not access
the parent DOM or raw graph objects.

## Authority

Nodes receive only the capabilities their individual implementations need:
`raw`, `assets`, `ui`, `sample`, or `models`. There is no ambient filesystem,
network, subprocess, server-route, or host-import authority.

This fork requires no new Secure Nodes API. Consequently it adds no new V2
Python API TDD decision or surface; it composes only already documented,
shipped primitives.
