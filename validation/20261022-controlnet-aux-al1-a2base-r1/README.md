ControlNet Aux revision 9: the shared restricted zip proof (`_restricted_globals.py`) now scans a checkpoint's `data.pkl` only when its bytes are byte-identical to the record torch itself decodes (`PyTorchFileReader.get_record`), closing the A-L1 residual.

Status `PASS_TIER_L` once (selection `m_b9b9964928`, run by MERVYN). The data-only intake (`INTAKE.json`, CLEAN) re-verified:
- the receipt, the mirror, the bound spec, pins and launcher r4, the memory gate and the container limits;
- the helpers the run loaded (candidate 2cecd6a4 with `torch_record`; the base helper af7b3018 without it);
- the anchors: `torch_record` equals the bytes `torch.load` reads for `data.pkl` (fresh archive and one real checkpoint); an injected differing record refuses with no scan and no decode; an injected read failure gives the existing clean refusal; a fresh archive is still accepted;
- the three families: UniFormer, Metric3D vit-small and DiffusionEdge main and swin_b accepted on the patched helper with their pinned globals and decoded under weights_only, each file pinned by sha256.

Scope: no node execution, no guest and no model forward; the driver exercises the helper and torch.load directly, since A-L1 changed only the helper's internal byte check.

Not established:
- live behaviour (requests #21, #23, #24 and #25);
- the sandbox;
- GPU;
- whole-node certification.
