# Secure conversion: LatentGC Aggressive

## Identity and declarations

Upstream: https://github.com/Raapys/ComfyUI-LatentGC_Aggressive
Commit: a080aa9bbc652275bc880348a1b7414df189673b
Release: xa080aa9. Four pristine files are byte-identical to the retained pinned
codeload archive SHA256 4368b0188af7b53878b0dbe976e0bc293423f971fdccbdccfe76da9c193d2483.
Independent Git-tree API verification remains unavailable; this is an exact
commit-addressed archive comparison, not a live-HEAD substitution.

| Backend ID | Disposition | Evidence scope |
| --- | --- | --- |
| LatentGC | supported | Bounded local values and managed cleanup, real confined guests and production outer LATENT |

Backend census: 1 supported, 0 rejected, 0 pending. Frontend axes: 0 extension
registrations, 0 frontend-only graph nodes, 0 routes; no frontend implementation
is inferred or required. Source has no display-name map; default ID, category,
one required LATENT input and one LATENT output are preserved.

## Behavior and approved adaptations

The pack still shallow-copies the dictionary before cleanup. Native source and
converted in-process controls preserve exact keys, ordering, dtype, tensor
values, nested metadata, and all shallow aliases without mutating the input.
Three separate existing public models.memory_cleanup calls preserve the native
order: collect_cycles, unload_all_models, empty_cache. Each call disables the
other two flags. The trusted unload broker also clears managed SDK ephemeral
model caches: coordinator-approved lifetime normalization, not a claim of exact
legacy-global cache ownership. No private constructors or host-object recovery.

SDK_REFS=False uses the permissioned raw-compute tier for this pack-local
dictionary algorithm. The declared outer LATENT output retains its complete
admitted values. Guest input/output snapshots do not preserve host dictionary or
tensor alias identity; the independent returned snapshot and unchanged input are
the explicitly approved transport/lifetime normalization. Unknown opaque
metadata is refused distinctly, never silently stripped.

Admission is a plain string-keyed wire dictionary containing dense tensors,
scalar/string/bytes values, and bounded plain dict/list/tuple nesting. The whole
input is checked before any cleanup: 64MiB conservative aggregate logical/backing
tensor bytes plus text/scalars, 4096 visited values/keys, depth 16, no cycles.
These are supported local workload bounds, not source maxima. Sparse tensors,
unsupported objects and nonstring mapping keys fail closed. No allocations,
downloads, paths, subprocesses, secrets, installs or network services are added.

## Evidence and reproducibility

Owned tests: tests/test_amy_latentgc.py. Seven dtype controls each cover ordinary,
empty-batch and noncontiguous tensors against the pinned source shallow-copy
algorithm, with recording cleanup only for source oracle safety. Separate actual
required Seatbelt guests in two fresh pack copies invoke the real managed cleanup
broker and production outer executor, covering fp32/fp16/BF16 values, nested tuple
metadata, no input mutation, work refusal before cleanup, unknown-value rejection,
raw/models.manage denial, raw-ref denial and post-denial recovery. Actual native
cleanup functions are wrapped only to observe order, not replaced in that gate.
No trained model, resident GPU/VRAM-pressure experiment, Linux, Cloud deployment
or cross-user model cache isolation is asserted.

Command from v2/tests:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_amy_latentgc.py -q --tb=short
```

The complete gate includes exact schema/proxy/manifest, source/resources,
stub hashes, cache hygiene, two pristine-to-V2 byte/mode reconstructions
(direct pair and ZIP bundle), and wrong-source atomic refusal. Final observed
results are frozen in the external amy-oct7-latentgc-handoff.json and logs; this
report does not infer results from test-source inspection. Initial fixture RED:
missing not-yet-generated manifest and incorrectly patching _sdk.ctx rather than
the public sdk namespace; corrected without algorithm/tolerance changes.

## Contracts, persistence and publication

Python stub origin: outputs/many-oct7-image-mask-comfy-api.pyi SHA256
4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183.
Frontend composite: outputs/many-oct6-model-catalogue-checked-comfy-api.d.ts SHA256
2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090.
Canonical COMFY_CORE_ROOT is explicit; no gratuitous API/stub changes.

Persistence disposition: no authored durable state or user presets. Cleanup
affects host-managed ephemeral compute/model caches; cloud durable storage is
not required for the pack algorithm. Subsequent fresh-render values are supplied
by the workflow, not a source-local cache.

The source pyproject references LICENSE but no LICENSE file is present. Local
conversion is authorized; later distribution/publication permission is unresolved,
not an invented license or security rejection. Root owns serial review,
integration and all completion/count decisions. No shared/catalog edits,
commit, merge, push or deployment are part of this owned handoff.
