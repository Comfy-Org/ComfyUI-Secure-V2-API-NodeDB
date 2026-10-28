# TT Resolution Selector conversion

Source preparation only, 2026-10-27. Runtime qualification, normal manifest
generation, packaging replays and publication are pending. No new shipped ID or
whole-node/service/registry acceptance is claimed.

Upstream: AICoderTudou/ComfyUI-TT-Resolution_selector-Node at
`b69cf75c2ce5f864e3db5301dba46a6b5eeaa8fb`, tree
`3cc7ce7cdee4808d369b17db26c6ea1a34fa8704`. All five original files are retained
outside v2. The full original pack registers exactly one ID, TTResolutionSelector.

The V2 schema retains all four inputs in order, all 27 preset strings in their
original order, the Chinese display/boolean labels, integer defaults and bounds,
and two INT outputs named width/height. Its public io.ComfyNode delegates to the
byte-identical original nodes/resolution_selector.py. No dependency, raw/model or
other capability is requested. It uses no browser, route, storage, network, RNG,
clock or persistent state API. Scalar SDK inputs are native values in the retained
qualified dispatch pattern; opaque ValueRef inputs are not newly claimed here.

Custom mode returns the two supplied dimensions without casting or clamping.
Preset mode ignores those dimensions and performs the original dictionary lookup.
The original direct method falls back to (1024,1024) for unknown hashable labels;
this is preserved, but it is not a claim that queue validation admits such labels.
The separate direct-method diagnostics do not enlarge the declared input domain.

The pinned pyproject declares `license = {text = "MIT"}`. Upstream supplies no
separate LICENSE file and its author/contact fields are placeholders. Those facts
are retained literally; no copyright owner or full license text is invented.

The finite proposal covers 62 schema-domain rows and four separate direct-method
diagnostics across genuine original, default SDK and one observed required Guest.
Six outcome comparator poisons must fail. Its owner must bind the installed API,
normal-site profile, ordinary Guest, complete source maps, actual creation journal,
finite guards and independent retirement before execution is selected. No SDK,
scientific, pack, model or browser execution occurred while preparing this source.
