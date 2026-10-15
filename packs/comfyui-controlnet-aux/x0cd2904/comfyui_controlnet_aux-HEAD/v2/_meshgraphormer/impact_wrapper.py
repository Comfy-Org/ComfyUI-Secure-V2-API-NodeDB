"""Pinned external-detector crop/merge semantics; managed construction held.

No external detector proxy or custom value transport is invented here.
"""
import torch
from .selection import require_setup
from .detector import MeshGraphormerDetector
from .wrapper import Mesh_Graphormer_Depth_Map_Preprocessor

class Mesh_Graphormer_With_ImpactDetector_Depth_Map_Preprocessor:
    async def execute(self, image, bbox_detector, bbox_threshold=0.5, bbox_dilation=10, bbox_crop_factor=3.0, drop_size=10, resolution=512, *, selection, construction, **mesh_graphormer_kwargs):
        require_setup(selection)
        mesh_graphormer_node = Mesh_Graphormer_Depth_Map_Preprocessor()
        model = (await MeshGraphormerDetector.from_managed(detect_thr=0.6, presence_thr=0.6, construction=construction)).to(selection['device'])
        mesh_graphormer_kwargs['model'] = model
        frames = image
        depth_maps, masks = ([], [])
        for idx in range(len(frames)):
            frame = frames[idx:idx + 1, ...]
            bbox_detector.setAux('face')
            _, segs = bbox_detector.detect(frame, bbox_threshold, bbox_dilation, bbox_crop_factor, drop_size)
            bbox_detector.setAux(None)
            n, h, w, _ = frame.shape
            depth_map, mask = (torch.zeros_like(frame), torch.zeros(n, 1, h, w))
            for i, seg in enumerate(segs):
                x1, y1, x2, y2 = seg.crop_region
                cropped_image = frame[:, y1:y2, x1:x2, :]
                mesh_graphormer_kwargs['resolution'] = 0
                sub_depth_map, sub_mask = await mesh_graphormer_node.execute(cropped_image, selection=selection, construction=construction, **mesh_graphormer_kwargs)
                depth_map[:, y1:y2, x1:x2, :] = sub_depth_map
                mask[:, :, y1:y2, x1:x2] = sub_mask
            depth_maps.append(depth_map)
            masks.append(mask)
        return (torch.cat(depth_maps), torch.cat(masks))
