# Simple Prompt Batcher — Secure Nodes V2

Pinned upstream: `f7f14462ff06a50cac6c14b668b822f6e2640a54`.

## Census

- Python nodes: **1 supported, 0 rejected, 0 pending**
- Frontend extensions: **0**
- Backend routes: **0**

`SimplePromptBatcher` retains the exact input order and metadata, list-output
semantics, blank-line filtering, whitespace trimming, comma insertion, empty
fallback, and console previews of the pinned source.

The conversion executes with no resource references, host capabilities, files,
network, models, tensors, subprocesses, frontend code, or persistent state.
Generous byte, line-count, and expanded-output bounds fail closed before an
untrusted workflow can consume unbounded guest memory.
