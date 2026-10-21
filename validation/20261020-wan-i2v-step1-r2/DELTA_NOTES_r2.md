# I2V Step 1 r2: delta from r1 and notes for publication

Requested by MERVYN m_11da48bcaf, after the independent review of r1 (CLEAR_WITH_NOTES; REVIEW.md sha256 in REVIEW_R1_REF.json).
H1-H3, the candidate tree (wan_v2_i2v1, digest 487df3cf) and the materials (4d2aa51f) are unchanged from r1. Every r2 file is
derived from the pinned r1 packet by exact-once anchored edits; the edits are shown in docs/R1_TO_R2/.

## Changes

| Review | Change |
|---|---|
| M2 | CASE adds `t1_t2v_model_with_plain_i2v_dict` (item `i2v_dict_on_t2v_model`), the one H1 change users can reach. See below. |
| M1 | `tools/selftest_comparator.py` ships (stdlib only). `docs/COMPARATOR_SELFTEST.json` is produced by it on the shipped CASE.json. See below. |
| L5 | Comparator rev6 adds `outputs_finite` to every returning case: each tensor meta in samples, denoised and each forward `noise_pred` must be finite, in both roles. |
| L10 | rev6 writes the CASE label into every COMPARISON item (`info.label`). PLAN's not-claimed list is completed. |
| L9 | The controller parses CASE.json and FIXTURE_SPEC.json from the same bytes it checks against the pinned SHA256SUMS, after the first integrity pass. |
| L6 | After verifying the fixture copy, the controller scans `<materials>/candidate` for the fixture sha256 text with the stdlib. It refuses if found and records the result in the receipt. |
| L8 | The comparator inputs are re-hashed right before the comparator runs. PLAN says plainly that on the /mnt/c (drvfs) output root the 0700/0444/0755 modes are not enforced; integrity rests on digests. |
| L7 | The fixture writes one safetensors metadata key, so its file digest is reproducible. FIXTURE.json also gains `payload_sha256` over the sorted (name, dtype, shape, raw bytes) rows. |
| I6 | The review mails and JACK's own mails are on the controller's preparation-mail deny list. Select with your own message. |

### M2: case t1

- **Inputs:** the plain 13-key I2V dict (fixture inputs, clip on) with the approved 1.3B T2V model, on the published admission.
  It runs after t0 and before the seam (`seam_required` is absent).
- **r8:** refused the dict before load with NotImplementedError.
- **H1:** admits the dict. The model loads, then the vendored original raises its own
  `ValueError("T2V (text to video) model detected, encoded images only work with I2V (Image to video) models")` in `process`
  (`nodes_sampler.py:230-232`). This happens after its own load, as in the original.
- **Checks:** both raise, with the same type and message; full-message digest and length; raising function and file; the exact
  cited message; the cited form (prefix and suffix, `process` in `nodes_sampler.py`); 0 forwards; t2v transformer
  configuration; no seam; and converted release.
- **Cost:** one more 1.3B load per role (about 20-40 s) and no higher peak than t0.

### M1: comparator self-test

- The record contains the CASE.json and comparator sha256.
- The clean run covers every case, including i3's effect chain and t1. Every item must PASS.
- 22 controls: the r1 14, plus `i3_effect`, `non_finite`, `non_finite_forward`, `t1_cited_error`, `t1_seam_state`,
  `t1_model_type`, `t1_raising_site` and `fixture_architecture`.
- Each control must make its targeted check fail and its item FAIL. All other failing checks are recorded.
- r1's COMPARATOR_REV5_SELFTEST.json, made on a stale CASE layout, is not carried forward. It stays in the sealed r1 packet.

## L2: deliberate fidelity change (to be recorded in SECURE_CONVERSION.md at publication)

H2 picks the model variant with the original's own rules: `model_variant_for` = `nodes_model_loading.py:1374-1392`. That
includes the name rule:

- A catalogue name containing "high" or "low" anywhere in its path selects the Wan2.2 variant (`14B_2.2`, or `i2v_14B_2.2` for
  i2v). "workflows/" counts, because it contains "low".
- r8's `configuration_13b` used `1_3B` for the approved digest whatever the name.

So for the approved 1.3B file under such a name, TeaCache (with coefficients) and MagCache now follow the original's
coefficients and ratios, not r8's. Converted output then matches the original instead of r8. This is deliberate original parity.

Without a cache the variant has no effect. t0 runs no cache, and its catalogue name contains neither substring, so its byte
equality with r8 is unaffected. No case binds the file under a "low"/"high" name. That is not claimed.

## L1: publication procedure (for the later H1-H3 publication)

- Apply `docs/delta-r1/H1..H3` to the then-current corpus main (they apply with fuzz 0). Do not copy `wan_v2_i2v1`: its
  SECURE_CONVERSION.md is the r7 text.
- Verify the three files against 23b1dd70 / 22b4dbc5 / f58bd270, and that every other code file equals main.
- Bind the evidence to those three hashes, not to the candidate tree digest 487df3cf.
- Regenerate the pack pair: the `.json` pins `v2_sha256` for the three files, plus the `.diff`. `secure-nodes.json` is
  unchanged.
- Record L2 in SECURE_CONVERSION.md. Publish with the label in the synthetic column: "I2V code path: synthetic code-path parity
  only; no real I2V model admitted".

## Not changed in r2 (deferred, by MERVYN's "no H1-H3 change")

These need production changes and so a new review:
- L3: type refusals inside the 13-key dict.
- L4: `MappingProxyType` for ADMITTED.
- I7: refusing unconsumed state keys.

They are listed in DESIGN_AMENDMENTS_r2.md and in PLAN's not-claimed list.
