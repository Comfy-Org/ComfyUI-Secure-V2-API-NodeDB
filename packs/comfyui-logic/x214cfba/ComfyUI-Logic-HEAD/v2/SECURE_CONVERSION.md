# ComfyUI-Logic Secure Nodes V2 conversion ledger

Source tuple: `comfyui-logic`, `https://github.com/theUpsider/ComfyUI-Logic`,
`214cfba933291be224156d37bc30c25742076b44`, `x214cfba`.

Exact source census: **7 registered backend node IDs, 0 frontend
registrations, 0 routes, 0 model downloads.** Upstream is 260 executable lines.

## Backend ledger

- `Compare-🔬` — **supported**.
- `Int-🔬` — **supported**.
- `Float-🔬` — **supported**.
- `Bool-🔬` — **supported**.
- `String-🔬` — **supported**.
- `If ANY return A else B-🔬` — **supported**.
- `DebugPrint-🔬` — **supported**.

Backend tally: **7 supported, 0 pending, 0 security-rejected.**

## Frontend ledger

Upstream ships no `web/` or `js/` directory. Frontend tally: 0 supported,
0 pending, 0 rejected.

## What changed and why

No API gap. Every node is a pure data transformation and needed no new host
surface, no permissions, and no capabilities: the sealed manifest grants none.

Two mechanical substitutions:

- Upstream declared its wildcard sockets with a hand-rolled
  `AlwaysEqualProxy` — a `str` subclass whose `__eq__` always returns `True`,
  so ComfyUI's type check passes for anything. V2 ships that wire type as
  `io.AnyType`, so the shim is gone and the sockets behave identically.
- Upstream's `nodes.py` did `import nodes` at module scope, purely to build
  `IfExecuteNode`'s dropdown. The converted module imports only
  `comfy_api.latest`.

One inert attribute dropped: upstream wrote `{"default": 0}` on `Compare`'s
two wildcard sockets. A wildcard type has no widget, so those sockets are
link-only and the default was never rendered or used. `io.AnyType` has no
`default` for that reason, and dropping it changes nothing observable.

`DebugPrint` keeps `print`. The guest's stdout is captured by the transport
and surfaced with the execution, so the value still reaches the operator and
the node's contract (an output node returning nothing) is unchanged.

## The node that is absent, and why that is not a rejection

Upstream defines `IfExecuteNode`, which reads the host's global
`nodes.NODE_CLASS_MAPPINGS`, offers every installed node in a dropdown, and
instantiates the chosen class by name. That is host-registry introspection
rather than dataflow, and it would have been the one genuinely unconvertible
behaviour in this pack.

It is **not** recorded as a rejection, because upstream does not register it:
it is commented out of the pinned `NODE_CLASS_MAPPINGS`. The census is 7 nodes
both before and after conversion.
`test_the_pack_matches_the_pinned_upstream_registration_exactly` parses the
pristine mappings and asserts exactly that, so "absent upstream" is a verified
fact rather than a claim.

## Verification

`backend/tests/test_logic_pack_conversion.py` — 95 tests: exact census, schema
and sealed manifest including the emoji node IDs; the registration set parsed
from the pristine source; an AST proof that the guest imports only
`comfy_api.latest` while the pristine sibling does `import nodes`; a full
differential of `Compare` against the transcribed upstream operator table over
6 operators × 11 value pairs (ints, floats, bools, strings, mixed); operator
table completeness; passthrough fidelity for all four primitives; ternary
truthiness across 9 falsy/truthy values; `DebugPrint` stdout and output-node
contract; wildcard socket types; every node executed in one real out-of-process
guest; and distribution-pair reconstruction.
