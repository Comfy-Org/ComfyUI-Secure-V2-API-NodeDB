# Platform request #22 (draft for MERVYN's list): WAN FantasyPortrait ONNX profile admission

| # | For | Item | Source | Status |
|---|---|---|---|---|
| 22 | registry operator (per Ben), as #14 | **WAN `FantasyPortraitFaceDetector`, counted as tested (scoped), refuses on live.** The live WAN dependency profile `c7dc0bb4` (bundle `2fd45c30...` per #14) has no ONNX package, so the converted detector's original import path stops at `import onnx` (ModuleNotFoundError) before any model read. Ask: admit a WAN profile with the tested additions, onnxruntime 1.30.0, onnx 1.23.1, ml-dtypes 0.6.0 and flatbuffers 25.12.19 (CPython 3.13 manylinux x86_64; the set in image `e48accf7` that the evidence ran on), or record a refusal. Then one live check with device cpu. | WAN r10 (`validation/20261021-wan-portrait-r1`); MERVYN m_dcc2a7f403 | not yet sent |

Details:
- Tested closure: image `e48accf7` (readback r2 PROBE-01) has onnxruntime 1.30.0, onnx 1.23.1, ml-dtypes 0.6.0, flatbuffers
  25.12.19, protobuf 7.36.2, sympy 1.14.0, packaging 25.0 and numpy 2.2.6. It has no coloredlogs or humanfriendly, so the
  four packages above are the only additions the tested set needs beyond packages the 2026-10-14 proposal lists as already in
  `c7dc0bb4`: numpy 2.2.6, protobuf 7.36.2, sympy 1.14.0, packaging 25.0, opencv-python-headless 4.12.0.88 and scipy 1.18.1.
- The 2026-10-14 proposal (`PORTRAIT_ONNX_PROFILE_PROPOSAL.json`: onnx 1.19.0, onnxruntime 1.22.1, ml-dtypes 0.5.3, coloredlogs,
  humanfriendly, flatbuffers 25.2.10) was never acquired, and it is not what was tested. Admitting those versions instead would
  need its own run.
- Wheel files and their sha256 are to be taken from the PyPI JSON at acquisition, with the usual download rules. JACK downloaded
  nothing.
- Until admitted: with device cpu the detector raises ModuleNotFoundError at `import onnx`, after its image checks and before any
  checkpoint read; with the default device cuda on a host without CUDA, it raises RuntimeError earlier. `FantasyPortraitModelLoader`
  needs no ONNX package.
- The default device cuda is a separate gap: it needs CUDA on the host, plus a CUDA provider profile.
