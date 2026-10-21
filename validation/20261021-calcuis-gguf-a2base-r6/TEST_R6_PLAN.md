# calcuis-gguf test r6 (rev 5, port r7)

Tiers A, B and Q are the r5 tiers rebound to the port r7 bytes, with tqdm absent from the converted role, as on the live
guest (MERVYN m_d8caf14335). Everything else is unchanged from r5.

- **Tier A (in process).** The converted package is imported with `sys.modules['tqdm'] = None` (restored afterwards: the
  pristine original and the host keep tqdm, as the live host engine does).
  - The new control T0 imports the published rev 4 `encoding_math.py` under the same block and must fail with an
    ImportError that names tqdm. This shows both the live failure and the block.
  - After the import, no converted module may hold a tqdm object.
  - The 17 mutants are imported under the block too.
- **Tiers B and Q (converted nodes in guests).** Every guest's PYTHONPATH starts with `/driver/no_tqdm`, a `tqdm` package
  that raises ImportError. A run where any guest started without it fails (check `T:guest_tqdm_block`). The only lazy
  tqdm import in the SDK (`_sdk.py:9235`, `_sample_self_refine_video`) is host-side sampling code that calcuis never
  calls.

Same launcher r3 and limits as r5: 3 GiB = swap, 240 s, uid 1000, no network.

For the rev 5 report: the 7 tested rows get the label "evidence produced in a test env that supplied tqdm" for their earlier evidence. They stay tested
on the strength of these re-runs on the rev 5 bytes.
