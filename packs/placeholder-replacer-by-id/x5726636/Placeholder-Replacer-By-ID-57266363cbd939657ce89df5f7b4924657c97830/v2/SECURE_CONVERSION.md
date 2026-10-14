# Conversion record

The seven pristine files are verified against their pinned Git blob IDs and
modes. `PlaceholderReplacerByID.py` is byte-identical in the V2 tree. The
adapter calls its original `process` method and returns the three values using
the public `NodeOutput` API. No new input limits or parser behavior are added.

The production manifest and Python declaration were generated from the actual
installed SDK, using finalized `GET_SCHEMA`. The TypeScript declaration was
generated from the deployed frontend API source. There is one production node.

The actual gVisor TEST run verified 14 positive cases, including empty IDs,
toggle precedence, duplicate mappings, custom delimiters, unsigned 64-bit IDs,
negative IDs, Unicode and long text. Each case checks the exact types and all
three output strings before forwarding a real image reference for preview.
Three negative cases verified the native empty-delimiter and unconditional
manual-parser errors and an intentionally wrong oracle expectation. A final
valid case verified recovery. Fifteen dependent 64×64 previews were archived.

The independent image fixture uses color 1024 to satisfy the TEST runner's
literal-color constraint. This only changes the test preview rail. Transport
omissions of extensionless LICENSE, .gitignore and declaration companions are
recorded in the validation intake; all remain in the full distribution.

The original source-only 789-comparison worker suite is historical evidence;
it is not added to the 17 actual registered behavior cases above. Runtime
receipts and submitted test sources are under `validation/20261014-placeholder`.
This corpus check-in does not publish a live registry revision.

Actual job IDs:
- fourteen-positive: `baccace72dfc6d9d596c8c8a03e37839`
- intentional-wrong-debug-failure: `a7f9fb0636b73cf731be3ae18e158445`
- native-empty-delimiter-failure: `e21465dc503793040f5d89ef290d797a`
- native-unconditional-manual-parser-failure: `7ab0764d6136724ddf2e536ae95e8836`
- post-error-recovery: `16493e1cf387f8048b7bd8a277117d7c`

The 17 files in `tests/workflows/` retain the original prepared graphs with
preview color 2241348. Actual TEST requests use color 1024 and combine the 14
positive graphs. `tests/EXPECTED_RESULTS.json` distinguishes original fixture
hashes from submitted fixture hashes and links each case to its verified job.
Use the five exact requests under `validation/20261014-placeholder` to reproduce
the run with its TEST-only helpers.
