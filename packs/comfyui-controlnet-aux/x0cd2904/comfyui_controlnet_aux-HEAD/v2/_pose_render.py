import numpy as np
import cv2
from typing import List,Tuple,Union,Optional
from ._pose_types import Keypoint,BodyResult,PoseResult,AnimalPoseResult
from . import _pose_draw as util
def draw_animalposes(animals: list[list[Keypoint]], H: int, W: int) -> np.ndarray:
    canvas = np.zeros(shape=(H, W, 3), dtype=np.uint8)
    for animal_pose in animals:
        canvas = draw_animalpose(canvas, animal_pose)
    return canvas

def draw_animalpose(canvas: np.ndarray, keypoints: list[Keypoint]) -> np.ndarray:
    keypointPairsList = [(1, 2), (2, 3), (1, 3), (3, 4), (4, 9), (9, 10), (10, 11), (4, 6), (6, 7), (7, 8), (4, 5), (5, 15), (15, 16), (16, 17), (5, 12), (12, 13), (13, 14)]
    colorsList = [(255, 255, 255), (100, 255, 100), (150, 255, 255), (100, 50, 255), (50, 150, 200), (0, 255, 255), (0, 150, 0), (0, 0, 255), (0, 0, 150), (255, 50, 255), (255, 0, 255), (255, 0, 0), (150, 0, 0), (255, 255, 100), (0, 150, 0), (255, 255, 0), (150, 150, 150)]
    for ind, (i, j) in enumerate(keypointPairsList):
        p1 = keypoints[i - 1]
        p2 = keypoints[j - 1]
        if p1 is not None and p2 is not None:
            cv2.line(canvas, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), colorsList[ind], 5)
    return canvas

def draw_poses(poses: List[PoseResult], H, W, draw_body=True, draw_hand=True, draw_face=True, xinsr_stick_scaling=False):
    """
    Draw the detected poses on an empty canvas.

    Args:
        poses (List[PoseResult]): A list of PoseResult objects containing the detected poses.
        H (int): The height of the canvas.
        W (int): The width of the canvas.
        draw_body (bool, optional): Whether to draw body keypoints. Defaults to True.
        draw_hand (bool, optional): Whether to draw hand keypoints. Defaults to True.
        draw_face (bool, optional): Whether to draw face keypoints. Defaults to True.

    Returns:
        numpy.ndarray: A 3D numpy array representing the canvas with the drawn poses.
    """
    canvas = np.zeros(shape=(H, W, 3), dtype=np.uint8)
    for pose in poses:
        if draw_body:
            canvas = util.draw_bodypose(canvas, pose.body.keypoints, xinsr_stick_scaling)
        if draw_hand:
            canvas = util.draw_handpose(canvas, pose.left_hand)
            canvas = util.draw_handpose(canvas, pose.right_hand)
        if draw_face:
            canvas = util.draw_facepose(canvas, pose.face)
    return canvas

def decode_json_as_poses(pose_json: dict) -> Tuple[List[PoseResult], List[AnimalPoseResult], int, int]:
    """Decode the json_string complying with the openpose JSON output format
    to poses that controlnet recognizes.
    https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/02_output.md

    Args:
        json_string: The json string to decode.

    Returns:
        human_poses
        animal_poses
        canvas_height
        canvas_width
    """
    height = pose_json['canvas_height']
    width = pose_json['canvas_width']

    def chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def decompress_keypoints(numbers: Optional[List[float]]) -> Optional[List[Optional[Keypoint]]]:
        if not numbers:
            return None
        assert len(numbers) % 3 == 0

        def create_keypoint(x, y, c):
            if c < 1.0:
                return None
            keypoint = Keypoint(x, y)
            return keypoint
        return [create_keypoint(x, y, c) for x, y, c in chunks(numbers, n=3)]
    return ([PoseResult(body=BodyResult(keypoints=decompress_keypoints(pose.get('pose_keypoints_2d'))), left_hand=decompress_keypoints(pose.get('hand_left_keypoints_2d')), right_hand=decompress_keypoints(pose.get('hand_right_keypoints_2d')), face=decompress_keypoints(pose.get('face_keypoints_2d'))) for pose in pose_json.get('people', [])], [decompress_keypoints(pose) for pose in pose_json.get('animals', [])], height, width)
