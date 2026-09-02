# Secure Nodes V2 conversion

Pinned upstream commit: `721492b66c9cede8ae23ae10615462ad80cfd061`.

## Census

- Backend: 22 supported, 0 rejected, 0 pending.
- Frontend: 1 supported, 0 rejected, 0 pending.

## Boundary and behavior

The pack's resolution previews, texture synthesis, noise blending, region-mask
generation, mask processing, validation, and overlay algorithms remain in this
pack and use the permissioned raw-compute tier. They receive only typed image
and mask refs and have no filesystem, network, subprocess, download, secret,
or host-object access.

Sampling uses the generic bounded sampling capability. Flux Union ControlNet
uses the typed ControlNet ref, including its closed union-type selector.
Regional prompting uses the generic conditioning-mask primitive: the pack
still selects regions, feathering, strengths, and composition, while the host
keeps model and conditioning objects opaque.

The legacy Flux Attention Control replaced process-global Flux attention
functions and depended on XFormers. That API call was not its intended
behavior; its intent was spatial regional prompting. V2 implements that intent
with execution-scoped masked conditioning, so it no longer mutates global
attention state or needs XFormers. Flux Attention Cleanup remains as a working
compatibility node and reports that there is no global state to clean.

The frontend mutual-exclusion extension uses only definition lifecycle and
widget-handle events from `/comfy/api/v2.js`. It has no parent DOM/window,
same-origin, legacy app object, timer, or direct canvas access.

No API, vendor, weight, dependency, credential, or intended-behavior gap
remains.
