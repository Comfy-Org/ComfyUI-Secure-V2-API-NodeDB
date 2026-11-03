# Secure Nodes V2 conversion

Upstream: `https://github.com/Lhyejin/ComfyUI-Fill-Image-for-Outpainting`

Pinned commit: `4c21e317c04b2e87fe3c2f9c2fcbae94be250b80`

The single registered node is supported. Its three image-fill algorithms remain
pack-owned and execute in the bounded raw-compute tier. The conversion preserves
the original first-image behavior, quantization, mask result, OpenCV algorithms,
and iterative edge padding. It has no frontend extension, route, filesystem,
network, model, or process authority.

## Repair NED r1: the mask crosses exactly; dependency profile opencv-python-headless 4.11.0.86, scipy 1.18.1
- Upstream returns its mask as the two-dimensional HxW tensor `torch.from_numpy(mask) / 255.0`. A guest publishes a
  MASK output only as BHW (or B1HW), so `execute` (now async) returns it through `sdk.ValueRef.from_value`: the host
  holds upstream's exact tensor, unchanged in shape and values.
- A production guest sees only its sealed lock, the pack's runtime base and its declared dependency profile, not
  Core's requirements; the guest bases have neither OpenCV nor SciPy. `nodes.py` imports both when it loads (cv2 for
  the two inpainting methods, scipy.signal for edge_pad), so without the profile the node does not load.
- `pyproject.toml` pins exactly `opencv-python-headless==4.11.0.86` (cp37-abi3 manylinux_2_17 x86_64; PyPI sha256
  0e0a27c19dd1f40ddff94976cfe43066fbbe9dfbb2ec1907d66c19caef42a57b) and `scipy==1.18.1` (cp313 manylinux_2_27/2_28
  x86_64; PyPI sha256 fdaf5ea890a6183d0565f51a61799d67081bd5b1cf03c5f4b3fd3732108625c9). They replace the earlier
  ranges: numpy and torch are in the sealed lock, and the headless OpenCV build provides the same cv2 module without
  the GUI libraries.
- `secure-nodes.json` gains `runtime.dependencies.profile_sha256` when the profile is built.
- `tests/test_dependency_profile.py` lets cv2 and scipy, and the other modules the guest bases lack (torchvision,
  tqdm, yaml), come only from the pinned copies under /deps. Its guest cases run all three fill methods against the
  pristine upstream node.
- `tests/test_fill_image_for_outpainting_secure_conversion.py` awaits `execute` in an in-process runtime and resolves
  the exact-value mask; `from_value` is no longer on its list of names `nodes.py` must not use.
