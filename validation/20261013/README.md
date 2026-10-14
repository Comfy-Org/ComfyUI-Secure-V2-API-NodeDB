# Validation evidence for the current two-pack update

`CURRENT_ACCEPTANCE.json` is the current acceptance record: Q mask crop
calculator and JSON Helper, 27 distinct registered behavior cases, and a
catalogue increase from 168 to 170. Steve Resolution Calculator is held out of
this change while distribution permission is unresolved. Its private conversion
and test results are retained; it is not counted as accepted for this merge.

## Historical requests and service receipts

`FINAL_SERVICE_STATE.json`, `FINAL_TEST_INPUTS.json`, the Q and JSON Helper
`FINAL_TEST_REQUEST.json` files, and `q-steve-independent-review.json` are exact
historical evidence. They describe the earlier three-pack test/review attempt.
The reviewed sources and submitted request bytes must not be rewritten to make
their old documentation say something that was not submitted. In particular,
the JSON request contains the original pending conversion note. The current V2
documentation and `CURRENT_ACCEPTANCE.json` supersede that status text.

The service receipt's `released: true` means the editor test session was
released. Its `abandoned` lifecycle status confirms session cleanup. Neither
field means registry publication. No live registry deployment is claimed.

Absolute paths in original receipts identify the historical host inputs. They
are not portable locations or current distribution entrypoints. Use the SHA-256
bindings and `EVIDENCE_MAP.json` to locate matching bytes in this repository.
References without an included matching file remain identified by content hash;
their presence is not a claim that the host environment can be recreated here.

## Current artifacts after review

The Q helper now refuses `-O` and `PYTHONOPTIMIZE=1` without writing a PASS
report and explicitly requires Linux for its resource-limited verifier. Its
normal run makes 5,164 comparisons using genuine installed dependencies.
`Q_VERIFIER_REVIEW_CHECKS.json` records these checks as helper-only evidence,
separate from the retained gVisor service jobs.

JSON Helper documentation now matches Python `>=3.13,<3.14` and completed
runtime validation. Neither change alters production algorithms, manifests,
or generated API declarations. `DISTRIBUTION_PAIR_PROOF.json` records fresh
byte-and-mode roundtrips for both current distribution pairs.

## Existing regression checks

The initial run (`REGRESSION_TEST_OUTPUT.txt`) produced 35 passes, two failures,
and two skips. Missing KJNodes fixtures caused the fixture-dependent failures
and skips. After copying the unchanged fixtures, only those four checks were
rerun (`REGRESSION_TEST_OUTPUT_missing-kjnodes-fixtures.txt`): three passed,
and the existing KJNodes manifest-versus-installed-SDK mismatch remained.
The aggregate is 38 distinct passes and one remaining failure, not two full
suite runs. Both exact outputs are retained; their JSON summaries identify each
run and bind its output hash.
