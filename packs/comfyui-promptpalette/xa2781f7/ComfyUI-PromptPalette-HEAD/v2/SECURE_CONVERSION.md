# Secure Nodes V2 conversion

Upstream is pinned at `a2781f7fb279722933b3d2c78aa2f7fb84e7163f`.

## Census

- Python nodes: **1** (`PromptPalette`)
- Frontend extensions: **1** (`PromptPalette`)
- HTTP routes: **0**

The conversion preserves phrase parsing, blank rows, full-line and trailing
comments, prompt-weight editing, the edit/display toggle, delimiter and line
break choices, and the optional linked prefix.

The two upstream frontend implementations (legacy canvas and Nodes 2 DOM) are
replaced by one renderer-independent mounted UI. It mutates the host-owned
`text` widget through its typed handle, so comments and weight changes remain
ordinary workflow state across save/reload. The mount owns and releases its
DOM and listeners; it never reads ambient host DOM or installs global input
handlers. User-authored phrases and comments are assigned with `textContent`.

This pack requires no frontend permissions, SDK capabilities, backend routes,
filesystem, storage, network, raw tensors, or model access.
