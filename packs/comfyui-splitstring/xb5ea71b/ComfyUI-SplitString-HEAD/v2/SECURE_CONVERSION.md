# Split String — Secure Nodes V2

Upstream: <https://github.com/brayevalerien/ComfyUI-SplitString>

Pinned commit: `b5ea71bd43aca8ec9afe940782811d2b591c63dd`.
Existing release: `xb5ea71b`. This updates evidence and normal generated metadata
for the existing source; it does not identify a newly acquired upstream pack.

## Census and qualification

One original Python node, one converted registration, zero frontend extensions
and zero backend routes/settings.

| Node | Status | Scope |
| --- | --- | --- |
| `Split String` | tested (native original/default SDK basic behavior) | 25 exact valid cases, four exact original errors, real registration/schema and normal generation. Public executor, downstream variable-arity integration and Guest remain separate. |

The full original package and actual registered converted class were exercised
on the selected native Mac profile. Both declare twelve scalar STRING outputs,
but their result tuple contains only the available first one to twelve parts.
The conversion does not pad that tuple, drop empty values or infer downstream
execution behavior from its declaration.

Literal `\n\n` splitting, leading/trailing/middle empty parts, Unicode, combining
characters, RTL, NUL, whitespace, duplicate order and twelve-part truncation
match the original. Single newlines, CRLF and Unicode paragraph separators are
not substituted for the literal separator. The same actual original error type,
message and console output are preserved for None, integer, list and bytes
inputs in the finite native comparison.

Only explicitly declared schema fields are compared: node ID, input ID/type,
twelve output types and list flags. SDK-generated UI defaults for fields absent
from the original are recorded separately; this test does not establish browser
UI or public graph equivalence.

## Resource and authority scope

The historical report's claim of bounded splitting is corrected here. Neither
the original nor converted function has a production input-byte guard. Python
`split` materializes all parts before the twelve-part slice. The finite harness
admits at most 4 MiB of UTF-8 input, including a 1 MiB separator-density case;
that selection bound is not a new production cap or proof of unrestricted input
resource behavior. Production code is unchanged and no new rejection is added.

The node declares `SDK_REFS=False`, empty permissions and no dependencies. It
requests no files, network, model, tensor, subprocess, route or persistent-state
authority.

## Evidence

- Selected native environment: Python 3.13.14, `comfy_api` 0.42.0, Core
  `44564d0279c275eef52b11750a9d76349f4e7a88`, backend
  `59bd3e1acba6520bb32717ad03833f6ab2967ecc`.
- 92 primary checks: 25 valid original-versus-actual-default-SDK cases
  and four exact original errors, with six coherent wrong-tuple controls. Those
  controls detect padding to twelve, dropped empty parts, reordering, wrong
  truncation, splitting single newlines and trimming spaces.
- Small values are retained verbatim. Large values are compared by exact UTF-8
  byte lengths, per-element hashes, tuple arity/order and a length-framed tuple
  hash. No Unicode, whitespace or error normalization is used.
- One selected attempt under `m_fad206d2c5`: 3.1413877919999997 seconds and
  274300928 bytes peak observed aggregate RSS. No automatic retry. All eight
  workers and the outer group were independently absent; all sixteen worker
  cleanup rows confirmed reaping and group absence. Full input, runtime, site,
  component and configuration maps were unchanged.
- Evidence archive SHA-256: `9b97fe4f7dfc012e202416d7bef140901eba72890de37be0c387a8b175bc47bb`.
  Independent strict review SHA-256: `f418eb9fd74acbe98e0d73916a19c1b8bbf84a6268ce50f94693d356999d6bb9`.
- The actual normal generator produced the twelve-output manifest. Official
  pair/bundle generation and both pristine replays passed with all eighteen
  files byte- and Unix-mode-exact and the original eight Git blobs preserved.
  This source-only stage changes only this report after generation, retains
  that manifest byte for byte, and repeats canonical file-only pair and bundle
  replay. No native node or generator is rerun.

Six fixtures and SDK/Guest test code were recovered from the historical test
source. No concrete prior runtime receipt was recovered in the bounded census;
the existence of that source was not counted as a passing execution.

Actual public `PromptExecutor` execution, downstream handling of short tuples
against twelve schema outputs, Guest/gVisor, browser UI and deployed-service or
registry adoption are unqualified by this native basic-behavior evidence.
