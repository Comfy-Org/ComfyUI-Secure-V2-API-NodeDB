# Secure Nodes V2 conversion

Pinned upstream: `84f588b3ffd96f299d92b20e94ec66d9eec194ef`.

## Census

- Python: 1/1 node supported (`AutoNotesNode`).
- Frontend: 1/1 logical extension supported. The two legacy registration
  calls are mutually exclusive: one is only a canvas-ready startup helper.
- Legacy private routes: 8 removed. Notes and folders now use pack-owned,
  per-user `comfy.storage`.

The sidebar retains note and folder CRUD, tags, pinning, plain-text and safe
Markdown display, scoped save shortcuts, node-menu creation, and all five
automatic trigger kinds. Selection changes, node changes, workflow loads, and
the active workflow display name come from typed V2 events and handles. No
polling, canvas reach-through, ambient DOM, global keyboard listener, fetch, or
pack backend route remains.

Storage is validated and failure-atomic, with bounds of 500 notes, 200 folders,
512 KiB per note, 32 tags and triggers per note, and 4 MiB total. Markdown is
rendered into host-owned elements as text with a small safe formatting subset;
raw HTML is never inserted.

Legacy `user/<name>/autonotes/*.json` is not automatically readable from an
isolated pack. This is an ownership boundary rather than a hidden filesystem
grant; existing data requires an explicit future import path.
