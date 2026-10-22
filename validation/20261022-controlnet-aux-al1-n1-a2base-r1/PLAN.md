# ControlNet Aux — A-L1 follow-up N1 (tiny gated tier, source only)

Authority: MERVYN m_bc1a909bde. The N1 test additions the A-L1 review deferred. **No helper change** — the published rev 9
helper is tested as-is against the pre-fix helper, both mounted straight from git.

## What it proves
A-L1 made the shared zip proof scan only the record torch itself decodes. N1 shows that on a genuine parser difference —
a well-formed archive whose `data.pkl` Python's `zipfile` and torch's reader resolve to **different records** — the pre-fix
helper accepts and the fix refuses. The archive is built with ordinary `zipfile.writestr` (three STORED records), not
malformed or polyglot bytes.

## Helpers (from git; see HELPERS.json)
- `/helper-fix`   = `_restricted_globals.py` 2cecd6a4, corpus main **b0e56d8d** (Aux rev 9, PR #76) — must **REFUSE**.
- `/helper-prefix` = `_restricted_globals.py` af7b3018, corpus **e1ee6f7b** (Aux rev 8) — must **ACCEPT**.

## Rows (`test-n/n1_driver.py`; one result line PREFIX + JSON)
- **N1_spy** (strengthened anchor): a `torch.serialization` spy records the reader `torch.load` uses for `data.pkl`;
  assert it is exactly an instance of `torch._C.PyTorchFileReader`, and that `torch_record(payload)` equals the bytes it
  reads, on a fresh `torch.save` archive.
- **N1_positive** (control): a fresh `torch.save` archive is accepted by both helpers and returns its globals.
- **N1_mismatch**: records `archive/version`, `archive/Data.pkl` (pickle A), `x/data.pkl` (pickle B), all STORED, each
  `data.pkl` a small valid torch pickle. Python's `zipfile` selects `x/data.pkl` (exact `data.pkl` basename); torch's
  reader resolves `get_record('data.pkl')` case-insensitively under the first entry's dir to `archive/Data.pkl`. So the
  pre-fix helper scans `x/data.pkl` and **ACCEPTS**; the fix helper sees torch's bytes differ and **REFUSES**. The row
  records which refusal the fix gives (the A-L1 "differs" text, or the clean "could not scan" if torch's lookup raised)
  and what `torch_record` resolved to, so it holds whatever torch's exact case handling is.

## Run shape
Launcher r4, one attempt `aux-al1-n1-retest-v1`, CPU, one thread, network none, read-only mounts. Limits: 3 GiB (gate
MemAvailable ≥ 7 GiB; MERVYN gates ≥ 13.0), 300 s, tmpfs 64 MiB, 2 CPUs; expected peak well under 1.5 GB, a few seconds of
work. Mounts: engine/backend/python-env (equal to PINS_C1), and `/helper-fix` `/helper-prefix` `/driver` from the sealed
zip. No weights, no selections. Source only; nothing pushed. On PASS it is evidence for a later docs-only Aux revision.
```
intake:  python3 -I -B tools/intake_n1.py <selection message id>
```
