# Source conversion: Hu-Tao66/comfyui-DF-ResizeImage

Pristine source: `d605ed9eb40579c9f3ba5b0fe94bb43117bca30f`. Purpose: resize on the original declared inputs, with the complete original registered ID `comfyui-DF-ResizeImage`.

The complete upstream archive is retained. Its compute module is byte-identical at `_original.py`; the original module path becomes a public V2 boundary adapter. Names, category, input/output ordering, bounds/defaults/list flags and compute remain upstream's. The package gains only its V2 extension entrypoint, Python3.13 runtime declaration and genuine byte-reused public contracts.

Every adapter requests `raw`, materializes its declared IMAGE/MASK once, delegates once, and wraps tensor results with the public native finite factory (`ImageRef.from_value` for BHWC IMAGE, `MaskRef.from_value` for native MASK). These f1 factories validate shape/finite numeric storage and do not clamp, normalize, quantize or cast native values. Flatten's original tensor-identity passthrough keeps the input ref. Scalar outputs pass unchanged.

No model, route, file, network or frontend capability is requested. The original license and copyright bytes are preserved. Finite comparisons and wrong-answer controls are prepared in the one combined batch worker; none has run. Public empty/nonfinite/unsupported-shape rejections are separate boundary diagnostics, not parity credit. SOURCE_REVIEW_PENDING; no generated manifest, pair, runtime pass or shipped-pack claim.
