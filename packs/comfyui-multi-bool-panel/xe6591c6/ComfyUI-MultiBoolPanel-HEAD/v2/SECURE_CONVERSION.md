# Secure Nodes V2 conversion

This conversion is pinned to upstream commit
`e6591c62c3187c71f70133dfe3dbb9fbe5f8d3cc`.

## Census and behavior

- 1 of 1 Python nodes is supported: `SolidlimeMultiBoolPanel`.
- 1 of 1 frontend extensions is supported: `MultiBoolPanel`.
- The pack has no HTTP routes, settings, dependencies, or bundled runtime
  assets.
- The node keeps the exact `mode` combo and no-output execution contract.
- The frontend preserves title-prefix discovery, case-insensitive row order,
  the 20-row cap, persisted per-mode toggle state, first-boolean-widget
  control, node/group bypass and mute, automatic refresh, and adaptive panel
  height.

## Security boundary

The legacy extension reached into `app.graph._nodes`, `app.graph._groups`,
installed global graph/canvas callback wrappers, assigned node modes directly,
and mounted DOM through `addDOMWidget`. The conversion uses only typed
`GraphHandle`, `GroupHandle`, `NodeHandle`, `WidgetHandle`, lifecycle events,
and `widgets.mount`. It requests no frontend or backend permission.

Mounted panels share one bounded refresh timer and one pair of typed host
subscriptions; the last panel tears them down. A remount with the same
graph/node identity disposes the prior state first, and an inactive graph is
never inspected or mutated. DOM is created only inside the host-provided
mounted container, using its `ownerDocument` and text-only content.

## Deliberate differences

There is no behavior gap. Refresh no longer monkey-patches global canvas or
graph callbacks; it combines typed change notifications with a bounded
120 ms graph-version check so add/remove and group-membership changes retain
the original automatic behavior under both renderers.
