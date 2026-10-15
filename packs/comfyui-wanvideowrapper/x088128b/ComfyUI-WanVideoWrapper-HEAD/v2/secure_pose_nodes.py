"""Bounded pack-owned face contour tracking; no detector/model inference."""
import logging
import numpy as np
import torch
from einops import rearrange
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS

log=logging.getLogger(__name__)

def _preflight_pose(frames):
    _bound_payload(frames)
    if not isinstance(frames,(list,tuple)):
        return
    pixels=0
    largest=0
    for frame in frames:
        if not isinstance(frame,dict):
            continue
        width,height=frame.get('canvas_width'),frame.get('canvas_height')
        if isinstance(width,int) and isinstance(height,int) and width>=0 and height>=0:
            area=width*height
            pixels+=area
            largest=max(largest,area)
    # RGB canvases + RGB stack + float RGB conversion + returned MASK.
    # Conservatively reserve their overlapping lifetime before any zeros.
    if pixels*3>MAX_TENSOR_ELEMENTS or pixels*19+largest*3>MAX_PAYLOAD_BYTES:
        raise ValueError('Wan pose projected canvas/mask exceeds tensor/64 MiB bounds')

class FaceMaskFromPoseKeypoints(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FaceMaskFromPoseKeypoints',display_name='Face Mask From Pose Keypoints',
            category='ControlNet Preprocessors/Pose Keypoint Postprocess',
            inputs=[io.Custom('POSE_KEYPOINT').Input('pose_kps'),
                io.Int.Input('person_index',default=0,min=0,max=100,step=1,tooltip='Index of the person to start with')],
            outputs=[io.Mask.Output()])

    @classmethod
    async def execute(cls, pose_kps, person_index):
        _preflight_pose(pose_kps)
        pose_frames = pose_kps
        prev_center = None
        np_frames = []
        for i, pose_frame in enumerate(pose_frames):
            selected_idx, prev_center = cls.select_closest_person(pose_frame, person_index if i == 0 else prev_center)
            np_frames.append(cls.draw_kps(pose_frame, selected_idx))
        if not np_frames:
            log.warning('No valid pose frames found, returning empty mask')
            return io.NodeOutput(torch.zeros((1, 64, 64), dtype=torch.float32))
        np_frames = np.stack(np_frames, axis=0)
        tensor = torch.from_numpy(np_frames).float() / 255.0
        log.info(f'tensor.shape: {tensor.shape}')
        tensor = tensor[:, :, :, 0]
        return io.NodeOutput(tensor)

    @staticmethod
    def select_closest_person(pose_frame, prev_center_or_index):
        people = pose_frame['people']
        if not people:
            return (-1, None)
        centers = []
        valid_people_indices = []
        for idx, person in enumerate(people):
            if 'face_keypoints_2d' not in person or not person['face_keypoints_2d']:
                continue
            kps = np.array(person['face_keypoints_2d'])
            if len(kps) == 0:
                continue
            n = len(kps) // 3
            if n == 0:
                continue
            facial_kps = rearrange(kps, '(n c) -> n c', n=n, c=3)[:, :2]
            if np.all(facial_kps == 0):
                continue
            center = facial_kps.mean(axis=0)
            if np.isnan(center).any() or np.isinf(center).any():
                continue
            centers.append(center)
            valid_people_indices.append(idx)
        if not centers:
            return (-1, None)
        if isinstance(prev_center_or_index, (int, np.integer)):
            if 0 <= prev_center_or_index < len(valid_people_indices):
                idx = valid_people_indices[prev_center_or_index]
                return (idx, centers[prev_center_or_index])
            elif valid_people_indices:
                idx = valid_people_indices[0]
                return (idx, centers[0])
            else:
                return (-1, None)
        elif prev_center_or_index is not None:
            prev_center = np.array(prev_center_or_index)
            dists = [np.linalg.norm(center - prev_center) for center in centers]
            min_idx = int(np.argmin(dists))
            actual_idx = valid_people_indices[min_idx]
            return (actual_idx, centers[min_idx])
        elif valid_people_indices:
            idx = valid_people_indices[0]
            return (idx, centers[0])
        else:
            return (-1, None)

    @staticmethod
    def draw_kps(pose_frame, person_index):
        import cv2
        width, height = (pose_frame['canvas_width'], pose_frame['canvas_height'])
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        people = pose_frame['people']
        if person_index < 0 or person_index >= len(people):
            return canvas
        person = people[person_index]
        if 'face_keypoints_2d' not in person or not person['face_keypoints_2d']:
            return canvas
        face_kps_data = person['face_keypoints_2d']
        if len(face_kps_data) == 0:
            return canvas
        n = len(face_kps_data) // 3
        if n < 17:
            return canvas
        facial_kps = rearrange(np.array(face_kps_data), '(n c) -> n c', n=n, c=3)[:, :2]
        if np.all(facial_kps == 0):
            return canvas
        if np.isnan(facial_kps).any() or np.isinf(facial_kps).any():
            return canvas
        if np.any(facial_kps < 0):
            return canvas
        min_margin = 5
        if np.any(facial_kps[:, 0] < min_margin) or np.any(facial_kps[:, 1] < min_margin) or np.any(facial_kps[:, 0] > width - min_margin) or np.any(facial_kps[:, 1] > height - min_margin):
            corner_points = np.sum((facial_kps[:, 0] < min_margin) & (facial_kps[:, 1] < min_margin))
            if corner_points > 3:
                return canvas
        facial_kps = facial_kps.astype(np.int32)
        facial_kps[:, 0] = np.clip(facial_kps[:, 0], 0, width - 1)
        facial_kps[:, 1] = np.clip(facial_kps[:, 1], 0, height - 1)
        part_color = (255, 255, 255)
        outer_contour = facial_kps[:17]
        if len(outer_contour) >= 3:
            min_x, min_y = np.min(outer_contour, axis=0)
            max_x, max_y = np.max(outer_contour, axis=0)
            contour_width = max_x - min_x
            contour_height = max_y - min_y
            if contour_width > 0.8 * width or contour_height > 0.8 * height:
                return canvas
            unique_points = np.unique(outer_contour, axis=0)
            if len(unique_points) >= 3:
                contour_area = cv2.contourArea(outer_contour)
                canvas_area = width * height
                if 0.001 * canvas_area <= contour_area <= 0.5 * canvas_area:
                    cv2.fillPoly(canvas, pts=[outer_contour], color=part_color)
        return canvas

NODE_CLASS_MAPPINGS={'FaceMaskFromPoseKeypoints':FaceMaskFromPoseKeypoints}
