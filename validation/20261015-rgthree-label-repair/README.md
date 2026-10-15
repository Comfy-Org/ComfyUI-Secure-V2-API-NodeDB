# rgthree Label implementation candidate

The deployed V2 Label module previously contained only refusal comments and an
empty export. This increment registers `Label (rgthree)` and restores its text,
eight saved properties, drawing, editing, and pinned interaction through a
generic public frontend API. It changes only the Label module, its drawing
helper and the generated public declarations in the pack. The other rgthree
repairs remain separate.

**Status: source and focused tests pass; frontend integration and browser
acceptance are pending.** Do not activate this pack revision on the old frontend.
The prerequisite frontend and extension-host patches are retained under
`prerequisites/`; their exact preimages and resulting hashes are in
`SOURCE_HANDOFF.json`. They target the recorded frontend snapshot plus its bound
local changes, not an assumed pristine checkout of its base Git commit.

The focused suite passed 111 cases twice on identical source. It compares the
pinned original drawing operations and exercises Label editing/lifecycle,
bounded canvas and bitmap transport, pinned pointer routing, and generated
public TypeScript declarations. These are focused harness results, not a live
browser or complete repository build. Results and exact source hashes are in
`focused/`.

`DISTRIBUTION_REPLAY.json` verifies the official patch manifest, diff and bundle
reconstruct all 226 V2 files byte-for-byte with their modes and preserve all 258
original source files. Only three V2 files changed. This proves distribution
integrity rather than browser behavior.

The remaining acceptance gate is the prerequisite frontend/host integration
checks and `BROWSER_ACCEPTANCE.json` in both Classic canvas and Vue Nodes,
including editing, pinned click-through, save/reload and cleanup. The fixture
requires no model or queued render. This record makes no whole-pack completion
claim and adds no accepted pack to the conversion count.
