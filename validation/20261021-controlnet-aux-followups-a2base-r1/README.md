ControlNet Aux revision 6: the review follow-ups (restricted-decode hardening for UniFormer, Metric3D and DiffusionEdge), re-tested by one combined bounded attempt on the a2 base.

Status `PASS_COMBINED` (selection `m_9a8f3aa8de`, run by MERVYN). The data-only intake (`INTAKE.json`, CLEAN) re-verified:
- the receipt and the Windows mirror;
- the bound spec, pins and launcher r4, and the container limits;
- the port and selection hashes against the sealed packet;
- every parity row, recomputed from the recorded digests;
- every fail-closed and unit row, with its exact text, read count and buffer release.

The phases ran in separate interpreters:
- A: UniFormer, SemSeg and Metric3D Depth/Normal;
- P: DiffusionEdge;
- U: helper unit rows.

Scope: the guest parity ran with the sandbox off (`sandbox_kind: none`), as in revisions 4 and 5. The fail-closed rows ran in process.

Not established:
- live behaviour (requests #21, #23, #24 and #25, and the operator-staged weights);
- the sandbox;
- GPU;
- whole-node certification;
- the Metric3D vit-large and vit-giant2 backbones (over the 512 MiB read limit).
