# rgthree-comfy: browser staging of revisions 5, 6 and 7 on live host stack r3

**What this folder holds:** evidence for rgthree revision 8's dispositions (`v2/SECURE_CONVERSION.md`). Each staging
run is BART's result file, with the smoke plan it followed.

**Setup (all three runs):**
- Mode B overlay: session-only browser routes, nothing installed or deployed.
- Host: host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`, checked on every load.
- The frontend's default renderer (Classic). No run switched to Vue.

| Folder | Pack revision | Run (UTC) | Result | Plan |
| --- | --- | --- | --- | --- |
| `rev5/` | 5 (PR #54) | 2026-10-21, 03:20–04:01 | Every row passes except required row 9 (Power Conductor registration) | `rev5/BROWSER_SMOKE_PLAN.md` |
| `rev6/` | 6 (PR #69) | 2026-10-21, 21:55–22:07 | Every row passes except R4, R7 and R7b (`onNodeChanged`) | `rev6/BROWSER_SMOKE_PLAN.md` |
| `rev7/` | 7 (PR #74) | 2026-10-22, 01:10–01:19 | Gate passes: S1, S2, S3 and S5; S4 recorded | `rev7/BROWSER_SMOKE_PLAN.md` |

**Provenance.** The `STAGING-RESULTS.md` files are byte copies of BART's originals (sha256):

| Copy | sha256 |
| --- | --- |
| `rev5/STAGING-RESULTS.md` | `38ddcde48465330032c139c0bb483f30c3b53d243ba787f46366c507941080cc` |
| `rev6/STAGING-RESULTS.md` | `1fd235e7dd29a3b0098c169789da6d7b568a68cdb8a3e46ad49cdd2fe6c40a26` |
| `rev7/STAGING-RESULTS.md` | `4845be01ee2bb00cab129fadad9f5569b4fb7d2941aaebdc3349e7e49a9142be` |

The plans are the ones handed to BART: revision 5 candidate r2, revision 6 r2 and revision 7 r2.

**Not copied:** the harnesses, the per-load `RESULT.json` logs, the screenshots and the packets. The files name them, but
they stay with BART's workspace.

**Redaction check:** all six files were searched for host paths, workspace ids, tunnel URLs and credentials. None was
found, so nothing is redacted. The files deliberately record no credential values; the revision 5 file explains why no
HAR was kept.
