"""RES4LYF's RK sampling loop, vendored for the Secure Nodes V2 guest.

- Files listed in VENDOR.json are the upstream modules at 057a913e, unchanged except for their ComfyUI-core
  imports, which point to ``_comfy`` (guest-side stand-ins).
- ``res4lyf.py``, ``sigmas.py`` and ``style_transfer.py`` here are small stand-ins for the upstream modules of the
  same name. The loop imports them, but the reduced envelope only reaches their logging helpers; everything else
  refuses.
"""
