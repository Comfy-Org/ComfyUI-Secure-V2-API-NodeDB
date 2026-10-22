ControlNet Aux revision 7: DiffusionEdge_Preprocessor's urban and natrual environments, inspected and tested on the revision 6 bytes by one bounded attempt on the a2 base.

Status `PASS_ENVS` (selection `m_5bd5ac9fcf`, run by MERVYN). The data-only intake (`INTAKE.json`, CLEAN) re-verified:
- the receipt and the Windows mirror;
- the bound spec, pins and launcher r4, and the container limits;
- the pins, format, globals, decode identity and budget for each main checkpoint;
- the derived selection, accepted by the pack's own validator; it is rebuilt byte-exactly in `test-only-selection-derived/`;
- each parity row, recomputed from the recorded digests.

Scope: the guest parity ran with the sandbox off (`sandbox_kind: none`), as in revisions 4 to 6.

Not established:
- live behaviour (requests #21 and #25, and operator staging of each environment main);
- the sandbox;
- GPU;
- inputs other than the revision 5 fixture;
- whole-node certification.
