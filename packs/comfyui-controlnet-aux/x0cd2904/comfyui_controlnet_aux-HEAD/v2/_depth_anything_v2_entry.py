"""Held source entry: the caller supplies selected genuine state and device.

No SDK, weight declarations, downloads, asset loading, or registry activation.
The existing successor's _annotator owns unchanged batch/IMAGE quantization.
"""
from ._annotator import common_annotator_call
from ._depth_anything_v2 import DepthAnythingV2Detector

RELATIVE_FILENAMES = (
    "depth_anything_v2_vitg.pth",
    "depth_anything_v2_vitl.pth",
    "depth_anything_v2_vitb.pth",
    "depth_anything_v2_vits.pth",
)


def execute(image, ckpt_name="depth_anything_v2_vitl.pth", resolution=512,
            *, state, device, **kwargs):
    if ckpt_name not in RELATIVE_FILENAMES:
        raise ValueError("Only the four pinned relative node modes are exposed")
    model = DepthAnythingV2Detector.from_state_dict(state, filename=ckpt_name).to(device)
    out = common_annotator_call(model, image, resolution=resolution, max_depth=1)
    del model
    return (out, )
