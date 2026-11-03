# Dependency profile (NED profile r1): tqdm 4.70.1, einops 0.8.2
- A production guest sees only its sealed lock, the pack's runtime base and its declared dependency profile, not
  Core's requirements; base 0cd9adec has neither tqdm nor einops.
- Rows that cannot load without them (module level):
  - einops: the 13 rows in `nodes/ltxv_nodes` (through `nodes/_ltx_utils.py:4`);
  - tqdm: the 2 rows in `nodes/lora_nodes` (`nodes/lora_nodes.py:9`).
- Rows that need tqdm when they run: the 6 mask nodes whose upstream methods run through `_w3_l_upstream`
  (`nodes/mask_nodes.py:309`): BlockifyMask, ColorToMask, ConsolidateMasksKJ, CreateFadeMask, CreateFadeMaskAdvanced,
  CreateFluidMask.
- `pyproject.toml` pins exactly `tqdm==4.70.1` and `einops==0.8.2` (py3-none-any wheels; PyPI sha256
  c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73 and
  54058201ac7087911181bfec4af6091bb59380360f069276601256a76af08193). They replace the upstream's unpinned
  `pillow`, `color-matcher` and `matplotlib`, which are not profile pins (Pillow is in the base).
- Not covered by this profile: some rows also need, when they run, modules a guest base lacks (torchvision,
  scipy, matplotlib, pandas, color-matcher, OpenCV). Each of those rows needs a profile entry or a refusal by name.
- `secure-nodes.json` gains `runtime.dependencies.profile_sha256` when the profile is built.
- `tests/test_dependency_profile.py` lets both modules, and the modules the guest bases lack (scipy, torchvision,
  tqdm, yaml, cv2), come only from the pinned copies under /deps.
