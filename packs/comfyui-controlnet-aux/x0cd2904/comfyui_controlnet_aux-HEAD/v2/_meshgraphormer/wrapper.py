from .._uniformer.schema_source import define_preprocessor_inputs, INPUT, MAX_RESOLUTION
from .selection import require_setup
from .detector import MeshGraphormerDetector
import numpy as np
import torch
from einops import rearrange
import scipy.ndimage
import cv2

def expand_mask(mask, expand, tapered_corners):
    c = 0 if tapered_corners else 1
    kernel = np.array([[c, 1, c],
                        [1, 1, 1],
                        [c, 1, c]])
    mask = mask.reshape((-1, mask.shape[-2], mask.shape[-1]))
    out = []
    for m in mask:
        output = m.numpy()
        for _ in range(abs(expand)):
            if expand < 0:
                output = scipy.ndimage.grey_erosion(output, footprint=kernel)
            else:
                output = scipy.ndimage.grey_dilation(output, footprint=kernel)
        output = torch.from_numpy(output)
        out.append(output)
    return torch.stack(out, dim=0)

class Mesh_Graphormer_Depth_Map_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            mask_bbox_padding=("INT", {"default": 30, "min": 0, "max": 100}),
            resolution=INPUT.RESOLUTION(),
            mask_type=INPUT.COMBO(["based_on_depth", "tight_bboxes", "original"]),
            mask_expand=INPUT.INT(default=5, min=-MAX_RESOLUTION, max=MAX_RESOLUTION),
            rand_seed=INPUT.INT(default=88, min=0, max=0xffffffffffffffff),
            detect_thr=INPUT.FLOAT(default=0.6, min=0.1),
            presence_thr=INPUT.FLOAT(default=0.6, min=0.1)
        )

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("IMAGE", "INPAINTING_MASK")
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Normal and Depth Estimators"

    async def execute(self, image, mask_bbox_padding=30, mask_type="based_on_depth", mask_expand=5, resolution=512, rand_seed=88, detect_thr=0.6, presence_thr=0.6, *, selection, construction, **kwargs):
        require_setup(selection)
        model = kwargs["model"] if "model" in kwargs \
            else (await MeshGraphormerDetector.from_managed(detect_thr=detect_thr, presence_thr=presence_thr, construction=construction)).to(selection['device'])
        
        depth_map_list = []
        mask_list = []
        for single_image in image:
            np_image = np.asarray(single_image.cpu() * 255., dtype=np.uint8)
            depth_map, mask, info = model(np_image, output_type="np", detect_resolution=resolution, mask_bbox_padding=mask_bbox_padding, seed=rand_seed)
            if mask_type == "based_on_depth":
                H, W = mask.shape[:2]
                mask = cv2.resize(depth_map.copy(), (W, H))
                mask[mask > 0] = 255

            elif mask_type == "tight_bboxes":
                mask = np.zeros_like(mask)
                hand_bboxes = (info or {}).get("abs_boxes") or []
                for hand_bbox in hand_bboxes: 
                    x_min, x_max, y_min, y_max = hand_bbox
                    mask[y_min:y_max+1, x_min:x_max+1, :] = 255 #HWC

            mask = mask[:, :, :1]
            depth_map_list.append(torch.from_numpy(depth_map.astype(np.float32) / 255.0))
            mask_list.append(torch.from_numpy(mask.astype(np.float32) / 255.0))
        depth_maps, masks = torch.stack(depth_map_list, dim=0), rearrange(torch.stack(mask_list, dim=0), "n h w 1 -> n 1 h w")
        return depth_maps, expand_mask(masks, mask_expand, tapered_corners=True)
