# Secure conversion record

Upstream is pinned at `43b21384353cc94f23cdfde65f586d779f91ba47`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- JavaScript-only nodes: 0.
- Backend routes: 0.

The actual package loader registers only `BetterString`. The repository has no
frontend source, routes, models, downloaded resources, or executable assets.

## Behavior and authority

The conversion preserves node ID `BetterString`, display name, category,
required multiline `string` editor, optional force-input `chain` socket, and
the single unnamed STRING output. Blank or whitespace-only chains return the
editor value unchanged. Nonblank chains are right-trimmed, receive a trailing
comma only when absent, then receive two newlines before the editor value.

The node is deterministic string composition. It requests no file, network,
storage, model, tensor, graph, subprocess, frontend, or other host authority.
