ControlNet Aux revision 10 (docs only): the A-L1 review N1 follow-up, tested. A bounded attempt compared the pre-A-L1 helper (af7b3018) and the published revision 9 helper (2cecd6a4) on a mismatched-name archive built with ordinary `zipfile.writestr`.

Status `PASS_TIER_N1` (selection `m_0fa5950f81`, run by MERVYN). The data-only intake (`INTAKE.json`, CLEAN) re-verified the receipt, mirror, bound spec/pins/launcher, memory gate and container limits; the helpers the run loaded; and every row.

- The `torch.serialization` spy showed the loader reader is exactly `torch.PyTorchFileReader` and `torch_record` equals its `data.pkl` read.
- `zipfile` selected `x/data.pkl` while torch resolved `archive/Data.pkl`; the pre-fix helper accepted the archive and revision 9 refused it.
- A plain `torch.save` archive is accepted by both (control).

Scope: no node execution, no guest, no model forward, no weights and no selection. The pinned checkpoints were never affected; this is defence-in-depth on which record the proof scans.
