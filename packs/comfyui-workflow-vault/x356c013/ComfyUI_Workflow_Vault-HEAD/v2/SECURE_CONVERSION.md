# Secure conversion evidence

- Upstream: `https://github.com/avillabon/ComfyUI_Workflow_Vault`
- Pinned commit: `356c0130503e216fb24b859289b9a93f44129c3f`
- Pristine census: **0 Python nodes**, **1 frontend extension**, **41 routes**
  (9 GET and 32 POST), 13 Python files, 25 JavaScript modules, one stylesheet,
  and one bundled SVG.
- Secure census: **0 Python nodes**, **1 mounted frontend extension**, **0
  private routes**.

## Preserved behavior

- named vault profiles and isolated entry browsing;
- workflow create, search, edit, archive, duplicate, and delete;
- bounded version history with promotion and exact version opening;
- open as a new workflow tab or replace the current document;
- bounded media examples through the file picker/download broker;
- JSON archive import/export, notes, tags, descriptions, and storage usage;
- sidebar, action-bar save entry point, modal browsing, and dialog-scoped keys;
- canvas-scoped open/save commands.

## Security boundary

Pack-owned `comfy.storage` replaces configurable server paths and all legacy
routes. Writes are transactional by generation, split below the storage value
limit, and bounded to 12 MiB, 250 entries, 20 profiles, 50 versions per entry,
20 examples per entry, and 2 MiB per example. The host supplies user and pack
isolation. The importer validates all ids, profile ownership, workflows,
media, counts, and total encoded size before committing.

Legacy filesystem discovery, folder opening/reveal, server-side FFmpeg, and
automatic directory migration are intentionally absent: none can be expressed
without ambient host authority. Legacy users migrate through an explicit,
bounded export/import file gesture. All UI is built from `textContent` in the
host-provided mounted container; there is no ambient `window`, `document`,
`localStorage`, `indexedDB`, raw `fetch`, or backend facade usage.
