# Touch Resize for Secure Nodes V2

This conversion preserves Touch Resize's four zoom-stable corner handles for
exactly one selected node or group. Pointer input is confined to the visible
handle hit regions. All other graph pointer input passes through to ComfyUI.

The extension uses only typed graph handles and a host-owned graph overlay. It
does not access the parent document, canvas internals, or ambient browser
globals.
