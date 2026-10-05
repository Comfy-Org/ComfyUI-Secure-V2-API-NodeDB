# Secure conversion record

Upstream is pinned at `b5c0d414b70f179cb278a7b7203966d925c2fe7c`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 1 supported, 0 rejected, 0 pending.
- JavaScript-only nodes: 0.
- Backend routes: 0.

The actual package loader registers `DisplayValue`; `web/display_value.js`
contains the pack's single frontend extension.

## Behavior and authority

The backend preserves list-aware ANY input, output-node status, primitive and
JSON formatting, the list-valued STRING result, and the `value` UI payload.
Formatted display data is bounded to 1,048,576 characters. The node uses SDK
refs so arbitrary Comfy types remain opaque, but requests no capabilities.

The frontend replaces legacy node-prototype hooks with `comfy.defs.extend` and
an isolated mounted textarea. It preserves read-only display, per-node workflow
serialization, execution replacement, multiline rendering, automatic bounded
height, reload/remount behavior, and teardown. Text is assigned through the
textarea value property. It has no ambient document/window, backend, storage,
network, or graph authority.
