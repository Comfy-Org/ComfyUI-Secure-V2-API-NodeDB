# Test-only owner-input portability successor

The production four-call scope change, all Python runtime/declarations,
schemas/defaults/capabilities, resources, and frontend algorithms are byte-exact
with frozen ad76af63394ec7f3540b26846bbd1b82b0289174d4c775df1ecffecdad8f1c36.
This new successor changes only the owner-delta test, its immutable input
inventory, the pair-test ZIP input, and generated reports/artifacts.
The prior Mac-local receipt and all its logs remain historical and immutable.

Required test inputs, with no ambient machine-path default:

- AMY_METADATA_PREDECESSOR_V2: exact pre-owner full53-file V2 root.
- AMY_METADATA_CANONICAL_FRONTEND_ROOT: published frontend60e1387 root.
- AMY_METADATA_PAIR_ZIP: exact successor ZIP for the existing full pair test;
  never defaults to the old frozen release ZIP.

tests/owned_elements_inputs.json pins every predecessor file's bytes/hash/mode
and the four exact relevant frontend provider/declaration file identities.
The reachable acceptance corpus commit9d061f0bc8bd04340ea517f2f123059b648ec677
has the complete predecessor byte-exact with9a42; no exclusions or variants
are admitted. Missing/non-directory roots, unexpected files, symlinks and
hash/mode drift fail visibly. There is no skip or fallback.

AMY_METADATA_SUCCESSOR_V2 may point a separately staged copy of the test at its
release tree; normally the release is located relative to the test itself.
This enables stdlib/pytest-only relocated delta controls without importing the
whole ComfyUI package. Full pack gates still use the actual declared providers.

All exact four-call delta, Python/declaration/schema/capability/resource and
ordinary-name controls remain. Added missing-root, nonexistent-root, drifted
predecessor, extra-file and drifted declaration negatives do not bypass them.
Ordinary/shared-alias Viewer and MAX actual worker/renderer/lifecycle gates
remain unchanged. No native website/Linux/Cloud/sealed deployment or new count
claim follows from portable static tests.
