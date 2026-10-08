# Secure conversion: EBU PromptHelper

## Identity, provenance and declarations

Upstream https://github.com/burnsbert/ComfyUI-EBU-PromptHelper at
45c1ec2458369ea69a6b7d739a033f6823f62af8; release x45c1ec2. The pinned
codeload archive SHA256 is
4f8c273e6103c8f70766daa88a33c2413399c7b5e5ec42f63a39d546b9c12c42.
All 47 pristine paths and bytes match that archive. Independent Git tree API
verification is unavailable; no live HEAD or version substitution.
The source MIT license, author notice, palette/trait/weather catalogues and
examples remain present and byte-exact where unchanged.

| Backend ID | Disposition | Behavior evidence |
| --- | --- | --- |
| EbuPromptHelperCombineTwoStrings | supported | Empty/nonempty strings, delimiter, actual guest and outer STRING |
| EbuPromptHelperConsumeListItem | supported | Selection/revised workflow list, duplicate removal, exact seeded choice |
| EbuPromptHelperCurrentDateTime | supported | Source formats, actual admitted guest clock, explicit timezone qualification |
| EbuPromptHelperListSampler | supported | Number stripping, shuffle/order, counts/numbering, guest seeded selection |
| EbuPromptHelperLoadFileAsString | supported | Bounded managed INPUT UTF8 content/newlines/missing/errors and denial |
| EbuPromptHelperRandomColorPalette | supported | Eight families, 3/4/5 sizes, preferences/fallback, exact ordered/hex outputs |
| EbuPromptHelperRandomize | supported | Delimiters/tickets/seed/case/template behavior, guest weighted selection |
| EbuPromptHelperReplace | supported | Sequential literal/escaped regex replacement, actual work/output bounds |
| EbuPromptHelperSeasonWeatherTimeOfDay | supported | Date/time/skew/weather draws, overnight ranges, guest output |
| EbuPromptHelperTruncate | supported | First literal match, inclusive/exclusive/missing/empty substring |
| EbuPromptHelperCharacterDescriberFemale | supported | Trait toggles and repeated per-trait reseeds, four STRING slots |
| EbuPromptHelperCharacterDescriberMale | supported | Trait toggles and repeated per-trait reseeds, five STRING slots |

Recommendation: twelve bounded local supported nodes, zero rejected/pending in
this local conversion scope. Frontend axes: zero extensions, zero JS-only graph
definitions, zero routes. Names/IDs/categories/schema options/ordered outputs are
preserved, including exact uint64 seed maximum and the original optional sockets.
INT display is expressed through the public NumberDisplay enum, retaining the
source display string. No frontend-only work is inferred from native widgets.
Catalogue/integration/count decisions belong to the coordinator.

## Pack behavior and approved adaptations

Algorithms remain in the pack. Source helper and nonfile algorithm ASTs are
exact after normalizing three reviewed changes: local RNG imports, bounded
replacement wrappers, and the managed file loader. The weather node uses shipped
lexical weighted lists, not a network weather service.

All helper modules share a per-execution ContextVar random.Random. Every source
seed/reseed and draw stays in its original order, including seed+trait offsets.
Source seed zero actually reseeds deterministically despite its comments; that
behavior is retained. Ambient global RNG continuation is deliberately isolated,
not silently claimed equivalent. Native controls save/restore global oracle
state, converted controls verify no mutation, and concurrent interleaved scopes
verify no cross-execution mixing.

Loader directory/name are managed INPUT logical labels rather than OS paths.
Absolute/traversal/backslash/drive/control labels are refused, broker confinement
also refuses outside symlinks. Only this node declares assets authority. There is
no arbitrary filesystem or raw authority. A complete <=64KiB UTF8 read uses public
exists/resolve/size/read_range; universal CRLF/CR newlines are preserved.
Admitted missing files and invalid UTF8 return empty text as native source does.
Oversize/change/security/unknown broker failures are distinct refusals, not
broad-caught empty-string success. Concurrent file disappearance after admission
can propagate a broker failure; native broad-exception behavior is not used to
mask security/transport failures. Managed catalogue import/Cloud ownership remains
an external deployment boundary, not proof of arbitrary file compatibility.

CurrentDateTime retains the admitted guest clock. The measured guest is UTC while
the host oracle was Pacific; the failed host-timezone assumption is retained.
The corrected test measures guest offset and validates source formatting in that
same runtime plus a timestamp window. Fixed clock controls prove month-name date,
minute-only display time, second-resolution datetime and filename formatting.
No authenticated trusted clock, host-local identity, locale portability or Cloud
time identity is claimed.

## Bounds and security

Supported workload: <=64KiB aggregate input/output UTF8 text, <=65536 weighted
tickets, and <=16777216 cumulative replacement-input characters. Before each
literal replacement, exact projected UTF8 output is checked; regex replacement
uses escaped literal target patterns and checks each projected match expansion
before full substitution. Backslash templates have an explicit conservative
<=64KiB expansion reserve, preserving admitted native syntax/errors.
Growing replacements are charged by actual current input length, not an initial
estimate. Invalid/over-budget operations fail before unbounded ticket/output
materialization. Source unsafe open is removed from V2; the inactive algorithm
class's file method is sealed and the public V3 loader owns the broker path.
No private refs, ambient host module/object, credentials, process, dynamic code,
install, network, weights or shared code are introduced.

## Observed evidence and reproduction

tests/test_amy_ebu.py contains per-ID source differentials, eight palette families
at all three sizes/four seeds, preference retry/fallback controls, trait switches,
text/template/list/date/time native outcomes, source AST comparisons and bounds.
Two fresh complete pack copies and required Seatbelt guest PIDs execute all twelve
registered nodes through the production outer executor, with nonempty text and
all eight palette families, exact STRING arity/values, managed reads/refusals,
assets/raw denial and recovery. No service/model doubles are used to claim trained
inference; this pack has no learned model family.

From v2/tests:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_amy_ebu.py -q --tb=short
```

The full final gate additionally checks all resources/pristine hashes, source
census/schema/current stubs/manifest/proxy, cache hygiene, direct-pair and ZIP
pristine-to-V2 reconstructions byte-for-byte/mode-for-mode and wrong-source atomic
refusal. Final results and exact live shared fingerprints are external in
amy-oct7-ebu-handoff.json and final logs; no result is inferred from test-source
inspection. Initial fixture failures (date/time expectations, missing direct SDK
runtime binding, probe module source registration, expected symlink wording) and
the actual guest timezone mismatch remain recorded separately. No numerical or
algorithm assertion was relaxed to hide a conversion difference.

## Runtime, persistence and limitations

Explicit canonical COMFY_CORE_ROOT as above; bytecode disabled, no snapshot caches.
Python artifact outputs/many-oct7-image-mask-comfy-api.pyi SHA256
4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183.
Frontend composite outputs/many-oct6-model-catalogue-checked-comfy-api.d.ts SHA256
2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090.
No shared API or gratuitous declaration changes.

Persistence disposition: no authored durable state. Consumed/revised lists are
explicit workflow input/output values; no hidden process/file progress cache is
used across renders. Palette/trait/weather defaults are immutable source resources,
not a substitute for editable user state. User text assets belong to the managed
input catalogue; fresh-render access is tested with fresh workers/pack copies in
the same local host, not authenticated cloud user/backing-store continuity.
No Linux, Cloud deployment, locale/timezone portability, hostile filesystem-race,
trained/GPU or broader workload proof is claimed.

Only owned pack/tests/report/pair are written. No catalogue/shared/core/stub
generator edits, commit, push or merge. This is a whole local conversion review
recommendation, not a deployment or daily-count claim.
