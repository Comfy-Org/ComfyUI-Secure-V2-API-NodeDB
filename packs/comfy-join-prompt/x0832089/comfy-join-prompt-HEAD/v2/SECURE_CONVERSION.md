<!-- secure-conversion-report-v1 -->

> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Native backend differential and genuine normal-manifest evidence was verified on 2026-10-19.
> The older conversion suites below are historical and unrefreshed; they are not claimed to pass
> unchanged on the current SDK. Frontend, Guest/public executor and service acceptance remain open.
> Not accepted: no whole-pack certificate.

# Secure Nodes V2 conversion report — comfy-join-prompt

## Provenance

- Upstream: https://github.com/jupo-ai/comfy-join-prompt
- Pinned commit: `0832089ec5f5f1808c6b649777b125a2b1db516c`.
- Release: `x0832089/comfy-join-prompt-HEAD`.
- Complete codeload snapshot SHA-256: `0b1ba349ef353269c42c0226db4788c178ff77ec855300f6ad7e1c0035dd788f`.
- Central baseline catalog SHA-256: `cee2cbc4d5af77549dac4b9d180720e9f3595025428ae24ad77af79d1012f6f9`.
- Selection: historical Aug 4 registry download snapshot, rank 1671 / 2226 downloads; not a current trending claim.

## Backend node dispositions

Declarations below describe the bounded converted implementation, not full cloud deployment certification. Final observed gate results are recorded separately.

| Exact backend ID | Declared disposition | Registered | Scope |
| --- | --- | --- | --- |
| `jupo.JoinPrompt.JoinStrings` | supported | yes | Ordered autogrow values, escaped delimiters, per-line comma cleanup and native malformed group errors. |
| `jupo.JoinPrompt.JoinPrompt` | supported | yes | Truthy prev/text composition, options parsing/fallback/native non-dict errors, same join/cleanup algorithm. |

## Frontend and ancillary scope

Pristine actual entrypoint census: 2 Python nodes, 1 extension, 0 JS-only graph nodes, 0 routes. The unused `Endpoint` helper accesses a server instance but is never decorated/called; V2 eliminates it and directory-based module discovery.

The frontend targets only `jupo.JoinPrompt.JoinPrompt`. A typed node menu and selection-scoped command open a mounted host dialog with delimiter and cleanup controls. Operations preserve first eligible selected target, immediate change updates, hidden options widget/socket removal, per-node configuration, property edits, workflow serialization/reload, and teardown. JoinStrings uses the core schema's autogrow UI (1–50 rows).

Approved deliberate placement difference: the legacy selection-toolbox chrome and node-relative modal coordinates are not reproduced; equivalent configuration access is through `Open Config Dialog` and `jupo.JoinPrompt.OpenConfigDialog`. No identical-chrome/full-browser-parity claim. The host owns modal layout/overlay and keyboard focus; Escape is dialog-scoped, no global key interception.

## Current native evidence (2026-10-19)

The actual selected Mac attempt used Python 3.13.14, installed SDK 0.42.0/API141, Core `44564d0279c275eef52b11750a9d76349f4e7a88` and backend `59bd3e1acba6520bb32717ad03833f6ab2967ecc`. The genuine full original package and candidate completed 704 value/error comparisons plus 704 unchanged-component crosschecks, 7 resource guard denials and 6 detected comparator controls. Genuine normal encoding, canonical pair/bundle generation and both pristine-tree replays passed. Exact returned evidence and missing-purpose qualification are published separately under `validation/20261019-moe-resolution-join-native/joinprompt2`. This proves the recorded native backend and artifact subset; it does not exercise the current frontend, isolated Guest/Core public executor or shared service.

This publication successor changes only this report and regenerates its canonical patch artifacts with byte/mode checks. Runtime code, the genuine normal manifest and prior native evidence remain byte-identical; the native scientific tests were not rerun for these prose changes.

## Historical verification results (unrefreshed)

All test counts, paths and environment hashes in this section describe older observations. The retained Python test builds its expected manifest by hand and includes `frontend_permissions: []`; the current genuine encoder omits that empty field. Consequently these historical tests are not represented as currently passing unchanged. The genuine SDK differential and normal-generation evidence above stands separately; it does not refresh this whole historical suite.

- Test source: `tests/test_join_prompt_secure_conversion.py` and `tests/frontend_harness.mjs`.
- Initial observed check: 52 passing cases (3 release/executor tests excluded pending artifacts), including 200 generated differential inputs, exact malformed paths and real zero-capability guests in original/recreated pack filesystems.
- Frontend evidence: recording typed facade + owned DOM elements, no ambient document/window. This tests operations/lifecycle/state, not physical browser chrome or visual placement.
- Observed pre-artifact gate: 56 passed / 0 failed, including actual public outer executor for BOTH STRING nodes with core-finalized autogrow keys, typed contract compilation and complete pinned-file hash inventory.
- Observed full release gate: **57 passed / 0 failed twice**, 8.01s and 7.84s. Captured completion logs: `/Users/ben/popbot/raw-chats/outputs/jack-oct6-join-FO1sbS/jack-join-gate1.log` and `jack-join-gate2.log`. Those historical logs are retained as provenance; this successor does not claim that suite was refreshed.
- Reproduction from pack-db root: `PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -p no:cacheprovider --confcutdir=packs/comfy-join-prompt/x0832089/comfy-join-prompt-HEAD/v2 --rootdir=packs/comfy-join-prompt/x0832089/comfy-join-prompt-HEAD/v2 -q packs/comfy-join-prompt/x0832089/comfy-join-prompt-HEAD/v2/tests/test_join_prompt_secure_conversion.py --tb=short`.

## Current manifest and historical release integrity

- Current genuine normal manifest SHA-256: `fdaced83feb6523a1e4d0903313c3a8f716022bbbf786478172a5d16f0f6ce94`.
- Other stub/runtime hashes below are retained historical environment identifiers, not current pins.

- Historical canonical d.ts SHA-256: `4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3`.
- Historical canonical pyi SHA-256: `50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78`.
- Exact schema retained including autogrow prefix/min/max, optional prev/options, force-input, multiline and advanced attributes.
- Historical handwritten manifest SHA-256 (superseded): `29fce6f7fdaf711ef8f6174fc48cea55a8bd5360b89fda3c92c6837396ea8a69`.
- Core HEAD exercised: `233c894a295faeb9c4e7c10b9860990c55ba0891`; `_sdk.py` SHA-256 `9313967d03f461d8c9d62eec710513b4a2f2b9d30b8e52123bb8fd2447c0573f`.
- Secure runtime HEAD: `f57f065d8500506cb8e148348079db722684306c`; `transport/host.py` SHA-256 `a8b74d8e115e2c8cda729883d7f7a6597be6987a07f4774a83c2818ee682963b`, `packdb.py` SHA-256 `07efb519392ad421a10e20fc749f10d90fa3ac825eed69affe4d06b162d9e528`. Unrelated worktree changes were not modified.
- Pristine source is immutable; MIT LICENSE retained byte-for-byte. No models/weights/credentials/external integrations or extra runtime dependencies.
- Patch reconstruction is integrity evidence, not independent behavioral certification.

## Authority and assets

Both nodes use public value mode (`SDK_REFS=False`), permissions `[]`; frontend permissions `[]`. No server, filesystem, network, subprocess, private constructors, parent DOM or shared API changes. The active two-control dialog needs no upstream remote/CSS assets; legacy helper widgets unused by the extension remain pristine-only.

## Persistence and limitations

Workflow-serialized state; no durable pack state. Delimiter/cleanup travel with saved node state and the hidden options widget; no reusable user library is edited. Fresh-filesystem/fresh-guest tests exercise the stateless Python continuity; recording frontend tests exercise reload and per-graph/per-node isolation. No cloud KV durability claim is required.

Safety narrowing: text/options/delimiter input ≤64 KiB UTF-8 (surrogatepass for native direct calls), ≤50 autogrow values, projected joined output ≤1 MiB before final join allocation. Dialog edits are checked against the encoded options JSON limit including escaping overhead. Schema min=1 remains; direct empty groups still return the native empty string. Cleanup is bounded per input, and preserves empty tags and line structure; it does not deduplicate. Input/output beyond bounds is deliberately rejected rather than silently truncated.

No full multi-pack workflow/browser deployment is certified by a recording harness or schema pass. Final supported recommendation requires the focused guest/executor/behavior/security/artifact gate twice and coordinator review.
