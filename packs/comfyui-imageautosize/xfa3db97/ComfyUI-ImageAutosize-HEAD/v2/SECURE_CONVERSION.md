# Secure conversion record

Upstream is pinned at `fa3db9751d84a254985a07c91e58cee4d25a9779`.

## Census

- Python nodes: 3 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.

## Behavior and authority

All three V3 nodes retain their exact IDs, schemas, scaling calculations,
interpolation choices, crop anchors, pad behavior, transform reuse, and restore
workflow. The custom transform crosses the guest boundary as a validated plain
object instead of a process-local dataclass instance.

The pack declares only `raw`. Image or mask materializations are private to the
isolated guest and bounded to 4,096 batch entries, 16,384 pixels per dimension,
and 268,435,456 elements. It has no file, network, model, UI, or host-process
authority.
