# Copyright 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: Apache-2.0
"""Original Lynx ArcFace, largest-face selection and crop/embedding math."""
import numpy as np
import torch
from .lynx.face.arcface import Backbone
device=torch.device('cuda')
offload_device=torch.device('cpu')

def get_lynx_landmarks_original(detector, image):
    """
    Detect landmarks with insightface.

    Args:
        image (np.ndarray or PIL.Image):
            The input image in RGB format.

    Returns:
        5 2D keypoints, only one face will be returned.
    """
    in_image = np.array(image).copy()
    faces = detector.get(in_image)
    if len(faces) == 0:
        raise ValueError('No face detected in the image')
    face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    keypoints = face.kps
    return keypoints

def build_arcface_recognition_original(state_dict, device):
    model = Backbone(num_layers=50, drop_ratio=0.6, mode='ir_se').to('cuda').eval()
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    model = model.to(device)
    return model

class FaceEncoderArcFace:
    """ Official ArcFace, no_grad-only """

    def __repr__(self):
        return 'ArcFace'

    def init_encoder_model(self, device, state_dict, eval_mode=True):
        self.device = device
        self.encoder_model = build_arcface_recognition_original(state_dict, device)
        if eval_mode:
            self.encoder_model.eval()

    def __call__(self, in_image):
        return self.encoder_model(in_image[:, [2, 1, 0], :, :].contiguous())

def crop_lynx_face_original(detector, image, image_size=112):
    from .lynx.face.face_utils import align_face
    from insightface.utils import face_align
    image_np = (image[0].numpy() * 255).astype(np.uint8)
    landmarks = get_lynx_landmarks_original(detector, image_np)
    in_image = np.array(image_np)
    landmark = np.array(landmarks)
    ip_face_aligned = face_align.norm_crop(in_image, landmark=landmark, image_size=112)
    ref_face_aligned = align_face(in_image, landmark, extend_face_crop=True, face_size=256)
    ip_face_aligned = torch.from_numpy(ip_face_aligned).unsqueeze(0).float() / 255.0
    ref_face_aligned = torch.from_numpy(ref_face_aligned).unsqueeze(0).float() / 255.0
    ip_face_aligned = (ip_face_aligned - ip_face_aligned.min()) / (ip_face_aligned.max() - ip_face_aligned.min())
    ref_face_aligned = (ref_face_aligned - ref_face_aligned.min()) / (ref_face_aligned.max() - ref_face_aligned.min())
    ref_face_aligned = ref_face_aligned[:, :, :, [2, 1, 0]]
    return (ip_face_aligned, ref_face_aligned)

def encode_lynx_face_original(face_encoder, resampler, ip_image):
    image_in = ip_image.permute(0, 3, 1, 2).to(device) * 2 - 1
    arcface_embed = face_encoder(image_in).to(device, resampler.dtype)[0]
    arcface_embed = arcface_embed.reshape([1, -1, 512])
    resampler.to(device)
    ip_x = resampler(arcface_embed)
    ip_x_uncond = resampler(arcface_embed * 0)
    resampler.to(offload_device)
    ip_x = ip_x.to(resampler.dtype)
    out_dict = {'ip_x': ip_x, 'ip_x_uncond': ip_x_uncond}
    return (out_dict,)
