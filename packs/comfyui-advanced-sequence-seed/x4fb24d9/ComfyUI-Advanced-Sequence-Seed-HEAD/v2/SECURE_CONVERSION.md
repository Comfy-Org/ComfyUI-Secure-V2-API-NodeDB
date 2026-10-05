# Secure Nodes V2 conversion

Upstream: `https://github.com/florestefano1975/ComfyUI-Advanced-Sequence-Seed`

Pinned commit: `4fb24d9b3c96a781d4f391cba1e73b86dc2911f3`

Pinned tree: `c493c22ceea8ad8ff9fca61f567e9fb64b584419`

The single Python node and single frontend extension are supported. All seven
number sequences, selection bounds, optional noise, fixed-seed reuse, output
schema, output-node status, and cache fingerprint behavior are preserved.

The legacy backend sent one global browser event after execution, and the
frontend applied that seed to every matching node in the current graph. The V2
node returns the seed as execution UI data instead. The typed frontend receives
that data on the exact executing node, so separate node instances and graph
documents cannot overwrite one another. Widget enablement is managed through
typed handles and its subscription is released on removal.

There are no deliberate behavior gaps and no permissions.
