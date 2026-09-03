# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/wywywywy/ComfyUI-pause`
- Full commit: `e7189e5e66ae72267523a9ee38d8ce10e317d47c`
- Git tree: `ee4efca27666905f48c679da1f2c3b5f76624a7c`
- Release key: `xe7189e5`
- Commit date: `2026-04-25T22:45:32+01:00`

The pristine sibling is an exact materialization of all 11 tracked files at
that commit. The compatibility source was read-only throughout conversion.

## Census and behavior

The root mapping registers exactly `PauseWorkflowNode` and
`PauseWorkflowNodeWithSound`. Each is an output node in `utils`, requires an
`any1` value, accepts optional `any2`, and returns those two values unchanged
after the user continues. The second node additionally requests a bundled
notification sound in the frontend.

Upstream also registers three POST routes, emits one custom event, polls a
class-global status dictionary, sleeps while blocked, and monkeypatches the
global frontend interrupt method. Those are implementation mechanisms, not
the feature. V2 has one frontend module and retains the Continue/Cancel node
buttons, paused color, modal decision, packaged MP3 notification, and global
run-interruption cleanup through bounded APIs.

## Authority and API result

Both nodes declare only `ui.interact` and `execution.interrupt`. A bounded
`prompt-await` request replaces the ambient route/event/status loop. The broker
owns the prompt-scoped token, pack and node routing, response endpoint, JSON
bound, pending-request ceiling, and timeout. V2 validates the closed response
actions `continue` and `cancel`; cancel or the 540-second safety timeout asks
the host to interrupt the current prompt and fails execution.

The frontend runs in the Secure Nodes sandbox/opaque iframe, imports only
`/comfy/api/v2.js`, listens only to the pack-filtered broker event, and posts
only to the broker response route. The sound URL is a pack-local static asset.
There is no parent DOM/window, arbitrary host import, filesystem, network,
subprocess, model, secret, raw tensor, storage, or runtime-install authority.

No shared/core API change and no pack algorithm in core were needed.

## Frozen API pair

This release is sealed against:

- Python stub SHA-256:
  `5c94bedf783e9e92971d0369fabc23b10d6f7169fc86fecdee64a3607d9f3142`
- TypeScript stub SHA-256:
  `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`
