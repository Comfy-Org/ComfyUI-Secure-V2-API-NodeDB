# Secure conversion status

Pinned upstream commit: `58e077a7435631301cf7443412515cf958e7f3d1`.

All 207 frozen upstream backend node mappings are supported by concrete Secure
Nodes 2.0 handlers. No node mapping is rejected and no mapping is left on an
unsupported fallback.

The conversion keeps loader, pipe, prompt, XY-plot, adapter, inpaint, sampling,
detailer, image, loop, and wildcard orchestration pack-side. Core is used for
typed model operations and confined asset, output, graph, interaction, UI, and
sampling primitives.

Additional models are declared as pinned Hugging Face weights with hashes.
Downloads are brokered into the managed model catalogue and reused after the
first verified download; a node does not download a weight on every execution.

`secure-nodes.json` is the authoritative sealed schema/permission census. The
operational classification and representative real-guest behavior are enforced
by `backend/tests/test_popular_pack_conversions.py`, including an explicit
`207 supported / 0 rejected` assertion.
