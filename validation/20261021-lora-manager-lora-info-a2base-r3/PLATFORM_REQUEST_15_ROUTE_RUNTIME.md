# Platform request #15 (GERALD): bind a runtime to pack route calls

Requested by NED for MERVYN (m_9e5a6312ee), 2026-10-21. Found while porting LoRA Manager's Lora Info node.
Backend: a1 894ead3 (deployed 745b88f plus the broker additions).

## The gap

A pack's declared route cannot use the SDK domains its permissions grant, except `storage`.

1. `packroutes._dispatch` (packroutes.py 189-220) starts a fresh `GuestSession` and calls `serve_route` with the route's
   declared permissions.
2. `GuestSession.serve_route` (transport/host.py 5785-5819) sets `self._caps` but never binds an execution runtime.
   `self._runtime` stays `None` (initialised at host.py 169; only `execute` sets it, at 5623).
3. Every host `assets.*` handler (`_h_assets_resolve`, `exists`, `list`, `size`, `read_range`, `read_bytes`, ...) runs
   inside `self._scope()` (host.py 426-431). That raises `"no active execution for this guest"` when there is no runtime.
4. `storage.get/set` don't use `_scope`, so they work from routes. `models.*` and `ops.*` also go through `_scope`.

So a route that declares `assets` passes the permission check and is then refused on its first asset call. No live
route hits this yet: Z-Image's two routes serve static catalogue data.

## Who needs it

LoRA Manager's Lora Info node (in progress). Its routes read the selected LoRA's sidecar `.metadata.json` through
read-only `assets` (existing notes and the Civitai descriptions) and check that a file exists before saving notes to
pack storage. Without the fix, saved notes work and sidecar notes and descriptions don't. The Tier R test has three
control rows that show the exact refusal on unmodified a1.

## Ask

Bind a request-scoped runtime in `serve_route`:
- built as for a node dispatch (a `Context` from the ctx provider, a fresh ref resolver, the ops provider);
- limited to the route's declared permissions, as nodes are (the existing `_require` checks stay the gate);
- released when the call ends, so its refs can't outlive the request;
- for a sealed pack, with the same tenant and pack-id scoping as the pack's nodes.

## Related observation (no ask; for the route documentation)

The usable route request body on a1 is a little under 1 MiB:
- `packroutes` accepts bodies up to 1 MiB (`MAX_REQUEST_BYTES`, packroutes.py:142, 197-202);
- the host then sends the body to the guest in one wire frame, and `MAX_FRAME` is 1 MiB including the JSON envelope
  (transport/wire.py:43);
- a body near the limit raises `FrameTooLarge` on send (wire.py:450-454), before the handler runs. In production that is
  a 500 "route handler failed".

Tier R r2 records this as row `S:record_value_bound`.

## How it was shown

- **Unchanged a1:** Tier R control rows call all three Lora Info routes and expect the exact refusal text.
- **Parity rows:** these run with a test-harness stand-in (`test/route_runtime_shim.py`, hash recorded). It binds such
  a runtime for the duration of each route call. It is labelled "parity under a harness stand-in for platform
  request #15 (not live behaviour)" and is never part of the pack.
