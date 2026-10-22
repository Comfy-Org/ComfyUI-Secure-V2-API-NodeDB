ControlNet Aux revision 8: Metric3D's vit-large backbone under a 2 GiB per-checkpoint budget, tested by two bounded attempts on the a2 base (Depth with the vit-giant2 refusal row; Normal).

Status `PASS_M3D` twice (selection `m_a3743ee519`, run by MERVYN). The data-only intakes (`INTAKE_DEPTH.json`, `INTAKE_NORMAL.json`, both CLEAN) re-verified:
- the receipts, the mirror, the bound spec, pins and launcher r4, and the container limits;
- the vit-large facts and the derived selection; the Normal attempt derived the same bytes as the Depth attempt, and both are rebuilt byte-exactly in `test-only-selection-derived/`;
- each parity row, recomputed from the recorded digests;
- the giant2 refusal: exact text, no sealed read, no vendor import.

Scope: the guest parity ran with the sandbox off (`sandbox_kind: none`), as in revisions 4 to 7.

Not established:
- live behaviour (requests #21, #23 and #24);
- the sandbox;
- GPU;
- inputs other than the revision 4 checker;
- whole-node certification.
