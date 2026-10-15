# rgthree Label repair: source checks complete

**Status: final source checks and cloud build pass. Installation and browser
acceptance are pending operator integration.** DANNY owns that integration;
JERRY must be notified before restarts or frontend replacement.

This increment replaces the empty V2 Label module with `Label (rgthree)` and
restores its text, eight saved properties, drawing, editing and pinned
interaction through generic public frontend APIs. The pack changes remain
limited to the Label module, its drawing helper and public declarations.
Those three files are byte-identical to the original source freeze in this PR;
the final integration fixes changed only the frontend prerequisites and tests.

The current [integration handoff](INTEGRATION_HANDOFF.json) binds the tested
12-file [frontend patch](prerequisites/frontend.patch) and unchanged three-file
host patch to the selected 6,781-file frontend snapshot. The immutable snapshot
includes recorded local changes on base `f712b7a8440855b8d88b66c35184b23440e8fa1d`.
[Source hashes](SOURCE_MANIFEST.json) and the [execution profile](EXECUTION_PROFILE.json)
identify the exact inputs. The final checks passed with the existing dependencies,
network disabled, an 8 GiB container limit, 6 GiB Node heap and two CPUs.

A read-only [compatibility comparison](BASELINE_COMPATIBILITY.json) confirms the
R3 source retains the converted-pack presence and ownership-loading fix. DANNY
then verified that all 6,781 selected R5 source files match the frozen baseline.
The separate native tree's 179 deltas are unselected and none was applied;
[the source audit](NATIVE_DELTA_AUDIT.json) records why those changes must not
replace the selected loading behavior. No rebase or rebuild is required.
The operator candidate is the exact R3 dist with the current login overrides
preserved separately. Installation and browser acceptance remain pending.
The complete baseline inventory is in
[BASELINE_SOURCE_MANIFEST.json](BASELINE_SOURCE_MANIFEST.json).

- Full repository typecheck passed. All 28 actual Vitest cases passed: three
  canvas failure/lifecycle cases, 22 existing Vue node cases and three public
  API contract cases. See [final checks](final-checks/checks.json).
- The final focused replay passed 112 checks: all 111 original checks plus
  parsing the added lifecycle-test source. The three lifecycle behavior cases
  are the separate Vitest tests above. [Results](focused/final-integration/results.json)
  cover original drawing-operation parity, editing/lifecycle, bounded canvas
  and bitmap transport, pinned routing and public declarations.
- Lint exited successfully with zero errors, four new architecture warnings
  and 15 warnings on imports present in the baseline. No warning was suppressed;
  the dependency-layer refactor remains deferred. See [warning details](LINT_WARNINGS.json).
  Formatting passed for all 12 affected files.
- The [cloud build](build/checks.json) passed and packaged all eight host assets.
  The [dist manifest](DIST_MANIFEST.json) records 1,053 files and 83,859,321 bytes.
  Binary build/source ZIPs are retained as operator artifacts and are not included
  in this validation directory.

The [final API generation receipt](PUBLIC_API_GENERATION_FINAL.json) confirms
402 public members and byte-identical pack declarations. The generated member
list and its repository-formatted output are distinguished explicitly.
[Distribution replay](DISTRIBUTION_REPLAY.json) remains valid: the official
recipe reconstructs all 226 V2 files with their modes and preserves all 258
original files. The final prerequisite fixes do not change that pack identity.

The local registry contains this exact source revision, as recorded in the
[extracted registry readback](REGISTRY_STATUS.json):

- Revision: `d9c88479fcf38880ac97e41b4512a6961ee4a72e103f8fb40d881643ff7be182`
- Source: `2e84016294011274361c39868a8f5c5d4dedddd69bb07a7ba1a37705975c0c9d`

It is registered with `prepared: false`, `comfy_verified: false` and
`verification: null`. Registration does not establish runtime or browser
acceptance. [Operator status](OPERATOR_INTEGRATION_STATUS.json) is
`PENDING_OPERATOR_INTEGRATION`. The remaining acceptance work is
[the browser checklist](BROWSER_ACCEPTANCE.json) in both Classic canvas and Vue
Nodes, including actual drawing, editing, pinned click-through, save/reload and
cleanup. The existing fixture requires no model or queued render. This record
makes no whole-pack completion claim and adds zero accepted packs.

Historical evidence remains explicit. `SOURCE_HANDOFF.json`,
`PUBLIC_API_GENERATION.json`, `GENERATION_CLARIFICATION.json` and
`focused/finalD` / `focused/finalE` describe the original source freeze and its
two 111-check runs. Their source hashes remain unchanged. The previous README,
contract, evidence map and frontend patch are in `historical/source-r1/`;
bounded failed attempts are in `historical/integration-attempts/`. The earlier
R2 deployment-deferral sentence survives only in its historical handoff and is
superseded by the current operator status. Focused-result limitations describe
that harness alone; the separate full-source checks and build are recorded above.

New evidence uses logical placeholders for private workstation paths.
[Import provenance](SOURCE_IMPORTS.json) preserves original and published hashes;
[the evidence map](EVIDENCE_MAP.json) indexes the current and historical files.
