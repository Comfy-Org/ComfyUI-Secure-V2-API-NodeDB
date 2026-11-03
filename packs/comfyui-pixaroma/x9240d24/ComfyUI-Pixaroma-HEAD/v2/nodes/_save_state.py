import json
import re
import time
import numpy as np
from PIL import Image
from ._save_helpers import strip_stale_preview

DEFAULT_STATE = {
    "version": 1,
    "folder": "",
    "pattern": "image_%date:yyyy-MM-dd%_%counter%",
    "format": "png",
    "quality": 100,
    "embedWorkflow": True,
    "civitaiMeta": False,
    "saveOnRun": True,
    "dateStyle": "yyyy-MM-dd",  # JS-only (what the + Date chip inserts)
    "counterDigits": 3,         # %counter% zero-padding (001 = 3)
    "folded": False,            # JS-only (node body collapsed on the canvas)
    "hideBarWhenFolded": False, # JS-only (also hide the toolbar when folded)
    "webpLossless": False,      # WebP written lossless (quality is ignored)
    # Let a WIRED name keep its folders instead of flattening them to '_'.
    # OFF by default: a wired value creating folders on its own would surprise
    # anyone whose workflow already relies on the flattened name. Containment
    # does NOT depend on this flag - the joined pattern still goes through
    # _safe_prefix, which refuses '..', a leading '/', and turns a drive colon
    # into '_', so the result can only ever land under the save folder.
    "inputSubfolders": False,
    # JS-only: which optional buttons the node face shows. Absent/true = shown,
    # so an older saved workflow keeps every button.
    "showOpen": True,
    "showCopy": True,
    "showFolder": True,
    "showPng": True,
    "showJpg": True,
    "showWebp": True,
}

# Extensions stripped off a wired `name` value so "cat.png" doesn't become
# "cat.png_00001.png". Only known media extensions - "model_v1.2" keeps its dot.
_MEDIA_EXT_RE = re.compile(
    r"\.(png|jpe?g|webp|gif|bmp|tiff?|avif|mp4|mov|webm|mkv|m4v)$", re.IGNORECASE
)


def _expand_native_tokens(s):
    """Expand ComfyUI's native %year% %month% %day% %hour% %minute% %second%
    tokens. Native SaveImage gets these from folder_paths.get_save_image_path
    (compute_vars), which this node bypasses because it saves to arbitrary
    folders - so expand them here with the same zero-padded values (real user
    report: they worked in Preview Image Pixaroma but came out literal here)."""
    if not isinstance(s, str) or "%" not in s:
        return s
    now = time.localtime()
    for k, v in (
        ("%year%", f"{now.tm_year:04}"),
        ("%month%", f"{now.tm_mon:02}"),
        ("%day%", f"{now.tm_mday:02}"),
        ("%hour%", f"{now.tm_hour:02}"),
        ("%minute%", f"{now.tm_min:02}"),
        ("%second%", f"{now.tm_sec:02}"),
    ):
        s = s.replace(k, v)
    return s



def _tensor_to_pil(tensor):
    """Convert a HxWxC float [0,1] tensor frame to a PIL.Image.

    ComfyUI's IMAGE contract is 3 or 4 channels, but a misbehaving upstream
    node can emit 1/2/5+ channels - PIL's fromarray raises a raw TypeError on
    those, so normalize instead of crashing the save (1 -> grayscale, 2 ->
    grayscale+alpha, 5+ -> first three as RGB).
    """
    arr = (tensor.cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
    if arr.ndim == 3:
        c = arr.shape[2]
        if c == 1:
            return Image.fromarray(arr[:, :, 0], "L")
        if c == 2:
            return Image.fromarray(arr, "LA")
        if c > 4:
            arr = arr[:, :, :3]
    return Image.fromarray(arr)



def _parse_state(raw):
    """The node state -> a full dict with every default filled in.

    `raw` is the hidden SaveImageState JSON string on a run, or the object itself
    from the Save now route. Untrusted either way: anything that is not a JSON
    object leaves the defaults.
    """
    state = dict(DEFAULT_STATE)
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
    if isinstance(data, dict):
        state.update(data)
    return state



def _strip_stale_preview(extra):
    """This node's binding of the shared helper: drop every Save Image node's
    remembered preview (`pixSiLastRun`) from the EMBEDDED workflow copy.

    The reasoning, and the copy-never-mutate rule that goes with it, live in
    _save_helpers.strip_stale_preview - shared with Save Video Pixaroma since
    2026-08-10 so the two cannot drift.
    """
    return strip_stale_preview(extra, "PixaromaSaveImage", "pixSiLastRun")


