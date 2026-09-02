# CG Use Everywhere — Secure Nodes 2.0 conversion

Pinned upstream commit: `50ae9f8c5d8b9538589663c90a15d4067a02969c`

Status: **7 supported backend nodes, 0 rejected**.

The seven Python nodes are value/pass-through definitions and execute entirely
inside the guest. The pack's defining behavior—broadcasting a connected value
to matching unconnected inputs—is implemented by the frontend V2 `supply`
primitive. The host performs graph-local source resolution and priority
arbitration while building the prompt, without exposing or mutating the host's
prompt object.

The converted frontend is copied from the read-only Magic Patch corpus because
the JavaScript at this pinned commit is byte-identical to the corpus source.
The current upstream stylesheet is loaded inside the pack iframe from a URL
relative to the module.

The pack keeps its own matching, restriction, dynamic-input, Combo Clone, and
materialization logic. Core contributes only the general `supply`/resolved
supply primitives, node handles, commands, dialogs, and title badges. A small
`UE` badge replaces the renderer-specific title-bar drawing, and saved
pre-1.16 widget/socket choices are recovered from each node's read-only
`onConfigured` data. The conversion also corrects upstream's inverted loop
condition in its saved-version comparator (`result == 0`, not `!= 0`).

Legacy animated virtual-link curves are cosmetic and are not part of prompt
resolution. Broadcasts within a root graph or within a subgraph are supported;
an implicit broadcast across a subgraph boundary is deliberately not created,
because it would make one subgraph instance execute differently based on
invisible state outside that instance. This is a scope rule, not a rejected
node: all seven registered node types work.

No node requires host filesystem access, networking, subprocesses, additional
Python packages, or model weights.
