# Sentence Filter conversion

Upstream: https://github.com/Slartibart23/comfyui-sentence-filter at
`149af6b01cb810d8d514ae154c2edcbfed1a809a`. The eight original Git files
and MIT license are retained. One original node, `SentenceFilterNode`, is
converted. Its calculation module is byte-identical to the original. The
adapter preserves the text input, four optional inputs, defaults, labels,
placeholders and three STRING/INT/INT outputs, including native errors.

The wrapper uses public ComfyExtension and io APIs with SDK_REFS=True and
empty permissions. It requires no models, routes or external dependencies.
Normal manifest generation and canonical JSON/diff and ZIP replays passed.

Validation on 2026-10-19: 32 original-versus-actual-SDK cases passed in the
recorded Mac development environment: 28 values and four exact exceptions,
with schema, registration and NodeOutput checks. This is scoped development
evidence; it does not establish general managed-runtime adoption.

The local PC Docker Node Pack Repository TEST service executed the unchanged
production node through gVisor. A TEST-only typed STRING consumer checked 27
valid UI cases against fixed strings from the original and forwarded the
seed image to a 64x64 PNG. Deliberately changing one expected string produced
the exact expected AssertionError. One direct null-optionals case and the
four invalid/null exception cases are not claimed as Core UI cases. The
TEST helper and augmented declaration are absent from this release.

Only this document changed after testing. Production source and the normal
node declaration remain identical to the tested candidate. The final pair
was regenerated and both pair/ZIP replays checked on genuine POSIX0644 files.
Evidence and scope are in validation/20261019-sentence-filter in the corpus.
The earlier source-generation monitor captured two of five tool process
groups; three short-lived group IDs were unobserved. That limit is retained;
all five canonical commands returned zero and their artifacts were verified.
No generation rerun or retrospective all-groups-absent claim was made.

Normal catalogue registration and active installation are tracked separately;
the TEST session does not establish either.
