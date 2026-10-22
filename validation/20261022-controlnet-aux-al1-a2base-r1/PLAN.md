# ControlNet Aux — A-L1 code fix + re-test tier (source only)

Authority: MERVYN m_d6f2d05438 (do the A-L1 fix: compare the scanned bytes with torch's own
`PyTorchFileReader.get_record('data.pkl')`; unit rows for the four record-difference cases; then a small re-test tier for
the three families on that helper) and m_cc361af690 (injection plan confirmed; add the two anchors below). Before #21, no rush.

## The change — `v2/_restricted_globals.py` (base corpus main e1ee6f7b, helper af7b3018 → 2cecd6a4)

`checkpoint_pickle_globals` still selects the single, bounded, STORED `data.pkl` record with `zipfile` (L1–L3 unchanged).
It then reads those bytes and requires them to be **byte-identical to torch's own record** before scanning:

- a new module-level `torch_record(payload)` returns `torch._C.PyTorchFileReader(payload).get_record('data.pkl')` — the
  record `torch.load` unpickles;
- the proof scans (`_weights_only_unpickler.get_globals_in_pkl`) only when `torch_record(payload) == data`;
- a difference is one refusal: `restricted torch archive data.pkl differs from the record torch decodes`;
- a read/scan error stays the existing clean refusal: `restricted decode could not scan data.pkl`.

Because the proof now compares against torch's own reader, the four record-difference families the review named
(case-variant name under the first entry's dir; central-directory discovery/offset; NUL-truncated names; Info-ZIP Unicode
path extra field 0x7075) all reduce to one behaviour: torch's bytes differ from the scanned bytes, so the proof refuses.
It no longer depends on *which* parser quirk caused the mismatch. `require_default_allowlisted` is unchanged (AST-identical);
the other refusal texts are unchanged; `torch_record` is called only from `checkpoint_pickle_globals`. See STATIC_CHECKS.json.

## Re-test tier (test-l), one bounded attempt, one phase — `test-l/al1_driver.py`

No node execution, no guest session, no model forward: A-L1 touched only the helper's internal byte check, so the driver
exercises that helper the way the families call it, on genuine checkpoints, plus the anchors. One result line, PREFIX + JSON.

Anchors and unit rows (candidate = `/port/v2` 2cecd6a4; main = `/aux-v2` af7b3018, evidence only):

- **LA_pos** — a fresh in-memory `torch.save` archive: `checkpoint_pickle_globals` returns its globals and
  `require_default_allowlisted` accepts them; the scan counter is ≥ 1 (positive control).
- **LA_cap:fresh** / **FAM capture anchor (uniformer)** — *anchor 1*. A spy on `torch.serialization._open_zipfile_reader`
  records the bytes `torch.load` actually reads for `data.pkl`; they equal `torch_record(payload)`. Checked on the fresh
  archive and on one pinned real checkpoint. (The spy targets torch 2.8's zip reader seam; it asserts exactly one
  `data.pkl` read, so a changed seam fails loudly rather than passing silently.)
- **LA_diff** — *anchor 2*. `torch_record` is replaced to return bytes that differ from the record. The call refuses with
  the new text, and the counters show **no scan** (`get_globals_in_pkl` 0) and **no decode** (`torch.load` 0). No malformed
  or parser-differential archive is built: the difference is injected into the comparison.
- **LA_raise** — `torch_record` is replaced to raise; the existing clean `could not scan data.pkl` refusal is returned, no scan.
- **FAM:<family>** — the three helper families on the patched helper. Each genuine zip checkpoint (uniformer
  upernet_global_small; metric3d vit-small; diffusionedge main and swin_b) is accepted by the candidate with the published
  pinned globals, decodes under `torch.load(weights_only=True)`, and is accepted identically by main's helper (evidence).
  RESOURCE_PINS.json pins each file by sha256 and size; the pinned globals equal the data.pkl opcode scan and the approved
  selection. PASS requires every row `ok` and `status == PASS_TIER_L`.

## Run shape

Launcher r4 (3c33ea26), one attempt `aux-al1-retest-l1-v1`, CPU, one thread, network none, read-only mounts.
Limits: 8 GiB (gate MemAvailable ≥ 12 GiB), 600 s, tmpfs 256 MiB, 2 CPUs. Expected peak about 3.3 GB (torch + comfy, then
the 1.11 GB diffusionedge main decoded under weights_only and released). Mounts: engine, backend, python-env, /weights-a,
/weights-p (all equal to PINS_C1), /aux-v2 at e1ee6f7b (main helper, evidence), and /port, /selections, /driver from the
sealed zip. Source only; nothing is pushed; MERVYN reviews, selects one attempt (no retry), then publishes the fix.
```
intake:  python3 -I -B tools/intake_al1.py <selection message id>
```
