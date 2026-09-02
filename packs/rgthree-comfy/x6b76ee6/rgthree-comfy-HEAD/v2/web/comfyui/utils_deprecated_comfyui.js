// This file is itself a compatibility shim, and the thing it is compatible with is
// exactly what this migration retires. Its own error message says so:
//
//     "Cannot set widget Config. This is due to ComfyUI removing the ability to
//      call legacy JavaScript APIs that are now deprecated without new, supported
//      APIs."
//
// REFUSED, not a pending gap: rediscovering the host's private state by symbol
// enumeration. `getWidgetGetConfigSymbols` walks
// `Object.getOwnPropertySymbols(input.widget)`, calls each symbol's value to see what
// comes back, and decides by the *shape* of the result which one is core's `GET_CONFIG`
// or `CONFIG`. Those symbols are unexported internals of
// `src/extensions/core/widgetInputs.ts`; making them reachable is what publishing them
// would mean, and a pack guessing at them by probing cannot be told apart from a bug
// when the guess stops matching. It also writes through them —
// `widget[GET_CONFIG] = () => config` — so a pack is editing the host's own record of
// what an input accepts.
//
// REFUSED, not a pending gap: reaching into another node's class. `setWidgetConfig`
// calls `originNode.recreateWidget()` and `originNode.onLastDisconnect()` on core's
// PrimitiveNode and reads `app.configuringGraph`. Those are core's methods on core's
// node; one pack driving another node's private lifecycle is the coupling this migration
// exists to delete, and `app.configuringGraph` is the application telling on itself
// mid-load.
//
// REFUSED, not a pending gap: `setWidgetConfig(slot, null)` does `delete slot.widget`,
// turning a widget-backed input back into a plain socket by removing a field the host
// owns and serializes. `inputs.add(name, type, {widget: 'name'})` declares a slot as the
// socket form of a widget when it is created, which is the supported direction.
//
// The capability is not lost, and it was never this pack's to provide. Narrowing two
// input specs to their intersection and refusing a join whose ranges or combo values do
// not overlap is core's own behaviour, in the same file these symbols come from:
// `widgetInputs.ts` exports `getWidgetConfig`, `setWidgetConfig` and `mergeIfValid`, and
// `PrimitiveNode._isValidConnection` calls the last of them to refuse exactly the joins
// this file was refusing. What this shim added was applying it to rgthree's own Reroute
// as well, and a Reroute that carries a `*` type has no spec of its own to narrow.
//
// DROPPED: the constraint carried along a chain of rgthree Reroutes. A primitive wired
// through one no longer narrows to the far end's min/max/step or combo values, and a
// join core would have refused directly is accepted through the reroute. Both nodes work;
// the primitive's widget shows its own range rather than the target's.
//
// The spec-merging half (`mergeInputSpec`, `mergeNumericInputSpec`,
// `mergeComboInputSpec`, `lcm`/`gcd`) is pure and would survive untouched, but its only
// caller is `mergeIfValid`, and its only consumer is reroute.js.
//
// INOPERABLE: nothing. This file registers no node type; it narrowed what a Reroute
// would accept.

export {}
