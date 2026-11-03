# to50-lane-20261102 (work in progress, not for merging)

Lane tooling for converting custom node packs to the Secure Nodes V2 API:

- `to50-tools/run_in_gate.sh`: bounded, network-less gate container runner.
- `to50-tools/packpair.py`: an independent implementation of the comfy-pack-patch/1 pair (generate, apply, compare).
- `to50-tools/review/`: the publication review and publish tooling:
  - `review_stage.sh`: the replay proof, pair regeneration, real-encoder manifest recompute, a static SDK compatibility
    check, a V1/V2 interface diff, a parity re-run and the mention-policy scan;
  - `publish_stage.sh`: a verified commit, re-proved from `git archive`;
  - `omit_media.py` / `prepare_omitted.sh`: the mirror omission policy.

Planning and evidence material is kept outside git.
