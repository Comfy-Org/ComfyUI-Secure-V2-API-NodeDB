# Platform requests from the rgthree revision 6 triage (MERVYN, 2026-10-21)

**For:** the host-stack owner. That covers sandbox guest `guest.mjs` (live `c6b97a15`) and `host-entry.mjs` (live
`63d9437e`), in the next host-stack revision; MIKE and JERRY, as for #13.

**Line references:**
- `d.ts` is the published `comfy-api.d.ts` (`53c296aa`, as shipped in rgthree revision 5's `v2/`).
- `guest` and `host` are the live r3 bytes.

**Status:** none of these requests has been sent. R6-1 replaces the text of pending request #13.

**What revision 6 does meanwhile:**
- R6-1, R6-2, R6-8 and R6-10: the pack works around the gap within the contract, so the request does not block it.
- R6-3: only the residual errors on other packs' types remain.
- R6-4 to R6-7 and R6-9: the pack waits for the platform.

## R6-1: `onNodeChanged` must deliver the node as a handle (replaces #13)

- **Contract:**
  - `NodeChangeEvent.node: NodeHandle` (d.ts 1274), with `graphId` (1276-1280).
  - "Each event names the graph it came from, and resolves its node there" (254-256).
- **Live:**
  - host `_subscribe` maps each event argument through `flatten` (2543-2550). The event object has no `id`, so it is
    `_sanitizeReturn`ed (2144-2166).
  - The node becomes plain data: `id`, `graphId`, `type`, `comfyClass` and sanitised slot collections, with no methods.
  - guest delivers the arguments as they arrive (3053-3058).
  - Node views themselves are complete (guest 2008-2009). Only this payload is not.
- **Ask:** in the guest, before calling the listener, replace `event.node` with `nodeIn(event.graphId, event.node.id)`
  (guest 2227-2237) when that resolves; otherwise keep the copy. A listener must never receive `undefined`: the Relay
  and Repeater read `event.node`'s id and graph before anything else. Do the same for node arguments of `onNodeDragEnd` and `onNodeMoved`.
- **Acceptance:** `comfy.onNodeChanged((e) => e.node.getProperties(), { scope: 'document' })` returns the properties
  for a node in the root graph and for one in a subgraph that is not on screen.
- **rgthree:** `label.js:118`, `node_mode_relay.js:132`, `node_mode_repeater.js:115`. Revision 6 works around it
  (`changedNode`, `base_node.js`).

## R6-2: a declared setting must read its stored value from the first `get`

- **Contract:**
  - `declare`: "Call once, at extension load: a value already stored for this id survives" (d.ts 1977-1981).
  - Packs gate features on `get` at load. In process, the stored value is readable then.
- **Live:**
  - guest `declare` seeds the cache with `defaultValue` (2636-2638).
  - The stored value arrives in the `settingsdeclare` reply (2650-2652; host 2079-2086, whose comment says it "must
    correct the cache before gates read it").
  - A gate that reads at evaluation gets the default. Power Conductor never registered (row 9a).
- **Ask:** seed the cache with the stored value. The boot message could carry the user's stored values for the pack's
  setting namespace, or for all settings, which a pack can already read. Then `declare(def); get(def.id)` returns the
  stored value synchronously.
  - Until then, document that `get` returns the default until the reply arrives. The guest already runs the def's own
    `onChange` at that point.
- **Acceptance:** with `rgthree.unreleased.power_conductor.enabled` stored `true`, `comfy.settings.get` returns `true`
  in the same turn as `declare`.
- **rgthree:** `power_conductor.js` (revision 6 works around it), `progress_bar.js` and `comfy_ui_bar.js`. Revision 6
  announces the late value as `config-change`.

## R6-3: `comfy.defs.extend` selector semantics in the guest

- **Contract:**
  - An extension applies when its type is defined. The in-process registry applies earlier registrations of every
    selector kind at `define`, and errors only for a *name* registered after its `define`.
  - `DefSelector` covers a string, an array, a RegExp, a predicate and a category (d.ts 780-800).
  - Module bodies run before definitions register (266-267).
- **Live (guest `extend` 578-604, `define` 617-686):**
  1. A pattern, predicate or category is matched only against the catalogue that exists when `extend` is called, and is
     never kept for later `define`s (587-590). A pack's own types defined later never get it.
  2. A waiting array selector is removed at its first match (665-672). Its other names never get it.
  3. Expansion ships one per-type string extend for each match (581-586), including types the host has already
     defined. The host then logs "comfy.defs.extend('X') was called after comfy.defs.define('X')" for another pack's
     types. KJNodes' GetNode and SetNode appeared in one of BART's loads.
- **Ask:**
  - Keep non-string selectors registered in the worker and apply them in `define` (like 665-672, without removing
    them).
  - Keep an array selector until each of its names is defined.
  - Skip, or let the host match, types that are already defined, so they no longer produce the "after define" error.
- **Acceptance:** revision 5's `menu_queue_node.js` (a `/./` extension at evaluation) gives each type the pack defines
  later exactly one copy of the items, with 0 host errors.
- **rgthree:** revision 6 names its own types one by one (`extendEveryNodeType`). It still triggers (3) for other packs'
  already-defined types, through its every-node pattern and `menu_copy_image.js:54`.

## R6-4: `widgets.mount` must pass the value handle

- **Contract:**
  - `MountDef.render(container, value: MountedValue)` (d.ts 2754).
  - `defaultValue` makes it a value-holding widget (2783-2792).
  - `serialize` and `sendToPrompt` (2768, 2782), and `destroy` (2756).
  - `MountedValue` provides `get`, `set` and `onChange` (2803-2808).
- **Live:** guest `mount` calls `def?.render?.(container)` (2135). It sends no `defaultValue`, `serialize` or
  `sendToPrompt`, never calls `destroy`, and the host widget holds no value.
- **Ask:**
  - Create the host widget with `defaultValue`, `serialize` and `sendToPrompt`.
  - Pass `render` a `MountedValue`: `get` from the snapshot, `set` → nodeop, `onChange` fed by the widget's change
    events (as `subwidget`, host 2117-2130).
  - Call `destroy` when the widget is removed.
- **Acceptance:**
  - Power Conductor's code box shows, takes typing, and survives save and reload.
  - The Power Primitive multiline value and Display Any's output render.
- **rgthree:** `power_conductor.js:177`, `power_puter.js:99`, `power_primitive.js:32`, `display_any.js:14`,
  `seed.js:88`. This is also row 9b.

## R6-5: `widgets.canvas` must return `{ widget, redraw }` and pass `draw` its theme and value

- **Contract:**
  - `CanvasHandle.widget: WidgetHandle` (d.ts 2917-2921).
  - `CanvasDef.draw(context, size, theme, value)` (2858-2863), with `CanvasTheme` (2840-2851).
  - `defaultValue` makes the surface hold a value (2895-2913).
- **Live:** guest `canvas` returns `{ redraw }` only (2152-2193) and calls `def.draw(ctx, [...size])` (2165).
- **Ask:**
  - Return a widget view for the canvas widget, as `mount` does at 2147.
  - Resolve the `CanvasTheme` tokens host-side and send them with `canvassize`.
  - Back `defaultValue` with a widget value, and pass it to `draw` as the fourth argument.
- **Acceptance:**
  - `canvas({...}).widget.setHeight(h)` works.
  - Power Lora Loader rows and the Power Puter chips draw in theme colours, and their values save.
- **rgthree:** `utils_widgets.js:170-189` (Power Lora Loader, Image Comparer), `power_puter.js:123-138`,
  `utils_canvas.js:55`.

## R6-6: `onPropertyChanged` events need `setValue` and `reject`

- **Contract:** `PropertyChangeEvent.setValue(value)` ("Replaces what is stored. Last writer wins") and `reject()`
  (d.ts 951-959).
- **Live:**
  - host `_sendNodeHook` sanitises the argument (3068). For `onPropertyChanged` it sends after the write commits
    (3070-3079).
  - The guest passes the data copy to the hook (3270-3274), so `e.setValue` is undefined.
- **Ask:** in the guest, wrap the `onPropertyChanged` argument:
  - `setValue(v)` → `node.setProperty(e.name, v)`;
  - `reject()` → `node.setProperty(e.name, e.previous)`.

  This is post-commit, which the declared "last writer wins" allows.
- **Acceptance:** Seed's `randomMax` set above 2^50 reads back clamped. The Fast Actions Button `shortcutKey` " Ab"
  reads back "a".
- **rgthree:** `seed.js:196-203`, `fast_actions_button.js:287-292`.

## R6-7: a guest-local `comfy.ui.showMenu`

- **Contract:**
  - `showMenu(def: MenuDef): MenuHandle` (d.ts 2486-2498).
  - `MenuItemDef.run` (2525), `submenu` (2524) and `disabled` (2522).
  - `MenuDef.event: MouseEvent` (2534), and `MenuHandle.close` (2538-2540).
  - No serialisable alternative is declared.
- **Live:** the guest's `ui` proxy has no `showMenu` (1154-1163). The call goes through the generic RPC, and
  `postMessage` throws DataCloneError on the `run` closures and on the event's methods (393-398).
- **Ask:** implement it like `showDialog` and `commands.register`:
  - Keep the `run` closures in the worker, keyed by item id.
  - Send `{ title, items: [{ id, label, disabled, submenu }], position: { clientX, clientY } }`.
  - The host renders its own menu and posts back the chosen id. `close()` asks the host to close it.
- **Acceptance:** Power Lora Loader's "Add Lora" picker opens under the pointer, and choosing an entry adds a row.
- **rgthree:** `utils_menu.js:20/35/49`, `power_lora_loader.js:236/248`, `power_puter.js:203/227`, `rgthree.js:75`,
  `comfy_ui_bar.js:76`.

## R6-8: `comfy.queue.run({ nodes })` must accept handles

- **Contract:** `RunOptions.nodes?: readonly NodeHandle[]` (d.ts 1521-1530), and `run(options?)` (1581).
- **Live:**
  - guest `queue.run` falls to the generic proxy (2801, 2828 → 410-419).
  - Views hold functions, so `postMessage` throws DataCloneError and nothing is queued.
  - The host's `_reviveArg` is the identity (2168).
- **Ask:**
  - Map `options.nodes` to ids in the guest, as `select` and `centerOn` already do (2420-2431).
  - Map them back to handles host-side, before `comfy.queue.run`.
- **Acceptance:** `comfy.queue.run({ nodes: comfy.graph.selection() })` queues the selected output nodes.
- **rgthree:** `menu_queue_node.js`. Revision 6 works around it by sending `{ id }` when the handles are refused.

## R6-9: `comfy.defs.nodeColor` must be synchronous

- **Contract:** `nodeColor(name): NodeColor | undefined` (d.ts 918). `typeColor` (902) and `isTypeCompatible` (923)
  are synchronous too.
- **Live:**
  - The guest's `defs` proxy serves `extend`, `define`, `get`, `has`, `all` and `onRefreshed` locally (733-742). It
    sends everything else to the RPC proxy (744), so `nodeColor` returns a Promise.
  - Named `matchColors` never match.
- **Ask:** answer `nodeColor`, `typeColor` and `isTypeCompatible` synchronously in the guest:
  - send the palette table and link-type colours with the boot and `defs` messages;
  - send them again when the palette changes.
- **Acceptance:** a Fast Groups Muter with `matchColors: "red"` lists the red groups.
- **rgthree:** `fast_groups_muter.js:69` (also Fast Groups Bypasser).

## R6-10: unconfirmed nodes from `graph.add` / `duplicate` / `replace`

- **Contract:** `add(type, init?): NodeHandle` returns a usable handle (d.ts 974). `duplicate` and `replace` return
  `NodeHandle | undefined` (1108-1133).
- **Live:**
  - guest `pendingNode` (2399-2406) returns a view with no snapshot until the host answers. Its reads throw (1980-1989).
  - Its slot collections read as empty instead (`list()` 1779-1782, `length` 1947).
  - A loop that grows inputs, `while (inputs.length < n) inputs.add(...)`, therefore never ends. Revision 5's Node
    Combiner upgrade did exactly that and would have stopped the pack's worker.
  - Its `id` throws, so nothing can be connected to the new node in the same turn.
- **Ask:**
  1. An unconfirmed view's collections throw like its other reads, rather than answering 0 or empty.
  2. Make it possible to wire a new node in the same turn, either by:
     - letting `connectTo` take a pending view and resolve it when the host answers; or
     - giving the view a `ready` promise, which needs a d.ts change.
- **Acceptance:** revision 5's `updateCombinerToCollector` either completes, or fails at once with the "read before the
  host confirmed this node" error.
- **rgthree:** `node_collector.js`. Revision 6 avoids it with `graph.replace` plus a claim in the Collector's
  `onCreated`.
