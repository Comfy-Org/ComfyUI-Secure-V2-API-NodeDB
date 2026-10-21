ControlNet Aux revision 5: DiffusionEdge_Preprocessor (port r2). It was tested by Tier I (inspection) and Tier P (parity) on the a2 base.

Status `PASS_TIER_I_INSPECTED` (selection `m_698147d79e`, 20:44:36-20:44:58Z) and `PASS_TIER_P` (selection `m_46821c3f67`, 20:57:27-20:59:31Z). One attempt each, run by MERVYN. The data-only intakes (`INTAKE_TIER_I.json`, `INTAKE_TIER_P.json`, both CLEAN) re-verified:
- the receipts and the Windows mirror;
- the bound spec, pins and launcher r4, and the container limits;
- the port and selection hashes against the sealed packet;
- every comparison, recomputed from the recorded digests.

Tier I: main and swin_b are zip archives; vgg16 and LPIPS `vgg.pth` are legacy pickles. Every pickle global is in torch's default allowlist. Each decode is identical with ComfyUI's safe globals registered and through the original's own `torch.load` (`INSPECTION_FACTS.json`).

Tier P, under a test-only approved selection built from those facts (`test-only-selections/approved`, hashes in `TEST_ONLY_SELECTIONS.json`) and a test-env yacs 0.1.8:
- The pack as it would ship refuses with its own "selection pending" text.
- The genuine pristine original (its own interpreter, offline, with an empty albumentations stand-in that upstream imports unused), an ordinary guest and the registered node in process gave exactly equal outputs (max difference 0.0).
- The guest without `assets` was refused, and albumentations was blocked on the converted side.
- Five fail-closed rows refused with their exact texts:
  - a missing global pin (before any read);
  - a legacy archive pinned as zip;
  - a wrong global list;
  - a legacy copy with one extra unpinned global (built in the harness);
  - a wrong torch pin.
- Peak memory was 6.03 GB.

Scope: the guest parity ran with the sandbox off (`sandbox_kind: none`), as in rev 4, and the fail-closed rows ran in process only.

Not established:
- live behaviour (requests #21 and #25, and operator staging of all four weight files);
- the sandbox;
- the urban and natural environments (their checkpoints are not local);
- resolutions other than 320;
- GPU;
- whole-node certification.

The independent review of port r2 was CLEAR_WITH_NOTES, with no high or medium findings. Its five low findings are listed as follow-ups in the report.
