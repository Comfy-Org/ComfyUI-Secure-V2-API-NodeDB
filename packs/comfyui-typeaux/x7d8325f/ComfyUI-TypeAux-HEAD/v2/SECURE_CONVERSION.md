# ComfyUI-TypeAux — Secure Nodes V2

Source: https://github.com/sleechengn/ComfyUI-TypeAux
Pinned commit: `7d8325f0c2e83ea4b6e85b2a3f8e6d8cbe83680c` (`x7d8325f`).

Actual imported entrypoint: **2 Python supported, 0 rejected, 0 pending**;
**0 frontend extensions, 0 JS-only nodes, 0 routes**.
Registered IDs/classes: `PromptTextNodeFunction` / `PromptTextNode` and
`StringReplaceFunction` / `StringReplace`. Category, input ordering/defaults,
multiline/dynamicPrompts/defaultInput metadata, combo ordering/default,
STRING versus custom TEXT outputs, and absence of custom display names are
preserved. The legacy methods are replaced by public `io.ComfyNode` classmethods.

## Behavior and authority

Both algorithms stay in the pack with value-mode inputs (`SDK_REFS=False`) and
zero permissions. PromptTextNode passes STRING content to a TEXT socket without
altering its content. StringReplace retains literal `str.replace` and native
Python `re` DOTALL semantics, including inline flags, lookarounds, numeric/named
backreferences and native empty-match ordering. The original greedy think-tag
removal default is preserved exactly. No regex whitelist, approximate engine,
private SDK constructor, filesystem, network, route, subprocess, runtime install,
raw tensor, or model authority is introduced. The unused legacy `os` import is
removed. Nodes have no third-party dependencies or resources.

Bounded direct inputs deliberately reject nonstrings and malformed Unicode:

- PromptTextNode input/output: 128 KiB UTF-8.
- StringReplace text: 64 KiB UTF-8; search expression: 8 KiB UTF-8;
  replacement template: 1 KiB UTF-8; output: 128 KiB UTF-8.

These limits leave room for worst-case sixfold JSON escaping in the transport's
default 1 MiB frame. Real-guest tests exercise maximum-length NUL text and
replacement output, not just ASCII inputs.

Literal output expansion is sized before allocation. Regex replacements are
validated by the native engine even when there are no matches. A bounded
callback uses public `Match.expand` and counts emitted UTF-8 bytes while the
native substitution engine retains its exact match-order semantics. Accumulated
expansion stops at the output budget; a trailing unmatched slice is at most
64 KiB. One expansion's conservative upper bound from the bounded source and
template is 64 MiB, so backreference amplification cannot allocate an unbounded
result. Unknown match_type values fail closed instead of returning the legacy
method's implicit None. Invalid regex/templates still raise their native errors.

## Regex CPU deadline proof

Catastrophic backtracking is not solved by input size limits. Execution relies
on the existing **isolated guest process deadline**. The host default is
**600 seconds**, configured with `COMFY_SECURE_EXEC_TIMEOUT`; this conversion
does not alter that deployment setting or claim a one-second production limit.
Operators should choose a deadline appropriate to their render workload.

The regression runs `(a+)+$` against 40 `a` characters plus `!` in the real
seatbelt guest with a test-only one-second host deadline. It verifies SIGKILL
returncode, absence of the old PID, dead session, removal of socket/scratch
directories, reclamation of a process-held resource, and successful execution
after restarting with a distinct PID. This is process termination, not a thread
timer returning while regex computation continues. The preflight observed
1.009 seconds and returncode -9. Normal matching/backreferences are also exercised
through the real guest with zero capabilities; substituting a host tensor is
rejected by the raw-authority boundary.

## Persistence disposition

**No durable state.** Upstream has no endpoint-backed files, authored settings,
process-global user data or browser storage. Inputs/defaults belong to the
workflow; all substitution bookkeeping is per execution. Tests recreate the
pack filesystem and guest three times across user A, user B, then user A and
verify identical results without a persistent store. No durable-cloud-storage
claim is needed or made for this pack.

## Validation and packaging

Focused test:
`v2/tests/test_typeaux_secure_conversion.py`.
Run using the ComfyUI development interpreter with `PYTHONDONTWRITEBYTECODE=1`,
`COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes`, pytest
`-p no:cacheprovider`. It verifies exact imported census/schema/manifest,
explicit and 2,000 randomized upstream replacements, native failure behavior,
input/output bounds, both real-guest nodes, denied raw substitution, deadline
termination/reclamation, fresh-render statelessness, canonical stub hashes,
pristine identity when the pinned clone is available, cache hygiene, and a
byte-exact pristine-to-V2 patch roundtrip.

Canonical contracts: d.ts
`4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3`;
pyi `50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78`.
No shared changes or API gaps. Linux sandbox execution is not directly exercised
by this macOS suite; real process-deadline enforcement is exercised on seatbelt.
Upstream declares MIT in pyproject.toml but ships no LICENSE text; preserve that
metadata caveat rather than inventing license text.
