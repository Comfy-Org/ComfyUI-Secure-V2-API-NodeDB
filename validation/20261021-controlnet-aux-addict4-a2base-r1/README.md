ControlNet Aux revision 4: UniFormer-SemSegPreprocessor, SemSegPreprocessor, Metric3D-DepthMapPreprocessor and Metric3D-NormalMapPreprocessor (addict-4 port r1), tested by Tier A test r1 on the a2 base.

Status `PASS_TIER_A` (selection `m_33f13d7f57`, one attempt, run by MERVYN; 04:29:01-04:31:51Z). The data-only intake (`INTAKE.json`, CLEAN) re-verified the receipt, the bound spec, pins and launcher r4, the container limits, the port and test-only selection hashes against the packet, and recomputed every comparison from the recorded digests.

Controls: the pack as it would ship (published selections, `approved: false`) refuses all four nodes with its own "selection pending" text. On live today, dispatch refuses them before that (request #23).

Parity, under a test-only approved selection supplied by the harness (`test-only-selections/`, hashes in `TEST_ONLY_SELECTIONS.json`) and a test-env addict 2.4.0:
- The genuine pristine original (its own interpreter), an ordinary guest and the registered node in process gave exactly equal outputs (max difference 0.0).
- The guest without `assets` was refused.
- Metric3D depth differs from normal, and the original checkpoint path equals the selection discriminator.
- Peak memory was 3.39 GB.

Not established:
- live behaviour (requests #23, #21, #24);
- the sandbox;
- Metric3D vit-large and vit-giant2 (they exceed the 512 MiB read limit and refuse even after approval);
- resolutions other than 64;
- whole-node certification.

The independent review of the port is CLEAR_WITH_NOTES, with no blockers. Its follow-ups (M1, L1-L5) are listed in the report's Revision 4 section and become their own code revision, with a Tier A re-run, before request #21.
