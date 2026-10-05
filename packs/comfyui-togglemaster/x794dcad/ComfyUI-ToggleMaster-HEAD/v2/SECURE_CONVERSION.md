# Secure Nodes V2 conversion

Upstream: <https://github.com/jonstreeter/comfyui-togglemaster>

Pinned commit: `794dcadf8c33c19a8242c4f8ff7edcf8b0883f7c`

Release: `x794dcad`

## Census

- Backend: 1 supported, 0 rejected, 0 pending.
- Frontend: 2 supported, 0 rejected, 0 pending.
- Backend routes: none.

`DynamicTextConcatenate` preserves its ten optional linked string inputs,
delimiter choices, numeric input order, empty-value handling, and dynamic
2-to-10 socket presentation.

The frontend-only `Wireless Master Toggle` preserves title-regex and color
intersection filtering, navigation, visible/all-graph scope, sorting,
exclusive modes, automatic refresh, and saved properties. Graph-qualified
node handles prevent same-ID nodes in different subgraphs from aliasing.
`always one` enforces the documented invariant, including after external mode
changes. All document subscriptions and debounce timers are owned and released
when the node is removed or its mounted UI is destroyed.

## Security boundary

The conversion has no permissions. It uses only typed graph, node, slot, and
mounted-widget handles. It has no ambient DOM, parent window, network,
filesystem, backend route, or subprocess access. The upstream `node.zip` is a
distribution artifact and remains pristine-only; it is not shipped inside the
V2 implementation.

## Deliberate compatibility detail

The upstream behavior for an invalid title regular expression is retained: the
invalid title filter is ignored, while a valid color filter still applies. If
there is no valid title expression and no color token, the target list is
empty.
