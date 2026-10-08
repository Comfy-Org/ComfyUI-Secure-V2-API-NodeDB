# Author-story conversion acceptance

Run actual converted pack consumers against supplied provider sources. This is
test-only tooling; it adds no API and changes no runtime, pristine snapshot,
converted release, patch pair, or conversion count.

The `codex/v2-author-story-pipeline` branch includes the four frozen snapshots
and their patch pairs. Pass the checkout itself as `--corpus`; `inputs.json`
records the immutable fixture commit. These are previously converted inputs,
not new conversions or a deployment. The central working catalogue is untouched.

The earlier tooling-only branch needs the separate source-only archive bound
by SHA256/size and manifest identity in `inputs.json`. Verify and safely extract
it into a new directory, then pass `<extracted root>/corpus` as `--corpus`. Its
four-entry `packs/packs.json` is a fixture index, not the central catalogue.
Both forms preserve the pre-owner Metadata snapshot. Missing inputs fail.

`pins.json` binds the full upstream commits, every pristine/V2 file byte and mode,
and the manifests/patch pairs for Comfyroll, My-Mask, InversedNoise and Metadata.
The runner resolves those sources from `--corpus`, refuses drift, then makes new
disposable test copies. Pack code is not vendored into this test directory.

```sh
python tests/author_stories/run.py \
  --core /path/to/core --overlay /path/to/private-overlay \
  --frontend /path/to/frontend --corpus /path/to/pack-db \
  --python /path/to/python --node /path/to/node --pnpm /path/to/pnpm \
  --browser-deps /path/to/frontend-with-playwright \
  --frontend-deps /path/to/frontend-with-installed-node_modules \
  --profile tests/author_stories/mac-local-profile.json \
  --output /path/to/new-results --stories all --compiler-mode required \
  --compiler-profile /path/to/immutable-toolchain/profile.json
```

All paths are explicit. Missing tools, dependencies, browser, pinned sources,
required confinement or provider operations fail acceptance. Tests are run twice
and sources are checked before/after. Receipt/log files are immutable per output
directory. The native frontend fixture is created in a detached worktree at the
supplied frontend HEAD, using explicitly supplied installed test dependencies.
The runner terminates its fixture server; the detached worktree remains for review.
Remove that worktree with `git worktree remove` after review.

| Story | Actual consumer and controls |
| --- | --- |
| 1 | Opaque frontend worker → production shared-storage HTTP relay → Comfyroll `CR Load Text List` in recreated pack files/fresh required Python guests. Same-account continuity, account/pack isolation, corruption refusal/recovery and UID revocation. |
| 2 | Actual Metadata SaveText frontend plus an acceptance-only asynchronous projection; canonical save/reopen/embedded/prompt projection and stale-value refusal, then actual converted Python writer with the queued filename. Generated class/definition registration and the backend text producer are explicit fixtures. |
| 3 | Opt-in wrapper around both actual My-Mask algorithms: DATA-only SafeTensors, input/pin/algorithm/name key, CAS, trusted host test-clock expiry, fresh refs/processes, mutation safety, miss/hit/recompute and account/pack isolation. |
| 4 | My-Mask source-exact dtype/contour controls and required guest/outer execution, including no-contour identity; InversedNoise actual tiny untrained canonical CPU FLOW model, `sample_custom`, `KSAMPLER` and guest `ctx.sample`. |
| 5 | Actual Metadata viewer with explicit node/widget scope: two-node UTF-16 copy/paste, ambiguity/wrong-scope refusal, subscription/unsubscribe, removal/replacement rejection, foreign-pack denial and teardown. Ordinary names and a separately recorded test-only identical-alias variant both run. Ten canonical native owned-element tests run separately. |
| 6 | Provisioned wheels execute actual NumPy/OpenCV/Torch computation in a zero-grant guest; a controlled listening loopback socket is refused with permission errno. A declared immutable toolchain builds/runs/cleans fixed freestanding C in owned scratch. No positive service authority, general compiler compatibility or CUDA claim. |

The cache wrapper is a test consumer, not an implicit change to ordinary My-Mask:
on a cache hit it returns a numerical copy rather than the original no-contour
input reference. The ordinary node's no-contour identity gate is separate.

The default `--compiler-mode required` needs `--compiler-profile /path/to/profile.json`
before story 6 can be accepted. The explicit `wheel-only` and `compiler-only`
modes record partial coverage and exclude story 6 from complete accepted stories.
A compiler profile binds its absolute executable, fixed flags, actual compiler/
linker identities and headers using path/SHA256/bytes/mode records. The gate builds
a fixed small C program under the guest's existing `TMPDIR`, runs it there, checks
its result and removes all generated files, through two fresh required guests.
No compiler host RPC, read-root addition, tool installation or network grant is
introduced. An installed host compiler that cannot run inside the declared guest
profile fails this control; it is not a guest toolchain attestation.

`provision_macos_toolchain.py --help` describes the local provisioning command.
It copies exact installed compiler/linker/library/header bytes into a new read-only
artifact root. Its eight-file arm64 closure is admitted through existing fixture
roots, with explicit resource/include/linker paths and no ambient SDK fallback.
Inherited base OS/shared-cache libraries are not a sealed dependency attestation.
The artifact is Apple-local and must not be reused as Linux compiler evidence.

The supplied profile is measured Mac-local Python 3.13 and inherited compiled
dependencies. It does not describe Linux wheels, a sealed ABI, compiler
availability, positive service authority, Internet reachability, trained weights,
GPU execution, Cloud authentication or Cloud durability. A disconnected Linux
loopback errno is not accepted as permission denial by this probe. Linux requires
a separately reviewed provider/profile control and exact offline dependency
artifacts; do not relabel or relax this control to obtain a pass.

All provider roots and sampled participating source bytes are recorded, including
the native owner implementation, checked-in declaration and API inventory.
New test copies adapt sandbox-kind assertions and scope the Metadata viewer's
three existing element calls to its own node/widget. Canonical public interfaces
are consumed as supplied; original packs/stubs remain unchanged. Profile path
relocation is test provisioning rather than a guest-selected read grant.

The shared-alias variant changes only the alias in new test copies; callbacks,
mounts and selection/edit behavior remain the actual Metadata implementation.
Against predecessor overlay `67a7351678a5c6fe5fd9ab41178dbb6c2570e676`,
the same control copies the whole first-node text rather than its selected emoji.
That failed assertion is separate historical evidence, not a predecessor pass or
an instruction to accept unscoped behavior. The published owner successor is
required for story 5.
