# Secure Nodes V2 conversion

Upstream: `https://github.com/younyokel/comfyui_prompt_formatter`

Pinned commit: `47d29099fbe96f9fd5a9a5a97ea68877c66199a9`

## Census

- Python nodes: 3 supported, 0 rejected, 0 pending.
- Frontend extensions: 1 supported, 0 rejected, 0 pending.
- Legacy backend routes: 2 removed; the formatter and tag conversion now run
  locally inside the isolated extension.

The conversion preserves the `CLIPTextEncodeFormatter`, `TextOnlyFormatter`,
and `TextAppendFormatter` IDs, schemas, display names, string behavior, and
CLIP conditioning behavior. CLIP execution uses the typed `ClipRef` broker, so
the encoder object never crosses into the guest.

The frontend uses `comfy.defs.extend` and typed widget handles. Each supported
node owns its three buttons and one-step undo state. Remount and removal dispose
all listeners, so state and events cannot leak between nodes.

The pinned `settings.json` and `blacklisted_tags.txt` defaults are treated as
immutable pack resources. The converted pack does not create or modify files,
register routes, call `fetch`, or access ambient browser globals.

There are no deliberate behavior gaps and no frontend permissions.
