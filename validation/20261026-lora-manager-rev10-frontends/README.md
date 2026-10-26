# LoRA Manager revision 10 unit-test evidence

The frontend change of revision 10 (r4 candidate, sealed SHA256SUMS 4032c17c) was tested with 64 unit tests over hermetic
fakes of two hosts: the live guest c6b97a15 and host-stack r4a with the widget-type bridge (#11). Node v25.9.0 ran with its
permission model on: no network, no child processes, reads limited to the candidate package, writes to its results folder.

- REV10_UNIT_TESTS.json (22cb639b): 64/64. repro/COMPARE.txt: a second run was byte-identical.
- MUTANTS.txt and mutants/: 7 mutants, each failing exactly its intended tests.
- first_attempt/: the retained first run (62/64); its one stale expectation is explained in notes/R4_CHANGES.md.
- test_sources/: the exact test sources, frozen (not executable here). FIXTURES.tsv names the pack's own example workflows
  used as data, by corpus blob and sha256.
- HASH_BINDING.json: the report's inputs hash every tested file; the staged secure_web files are those bytes.

Scope: frontend logic only. No browser, backend, deployed host or original-versus-converted comparison; the browser smoke
plan is notes/BROWSER_SMOKE_PLAN.md.
