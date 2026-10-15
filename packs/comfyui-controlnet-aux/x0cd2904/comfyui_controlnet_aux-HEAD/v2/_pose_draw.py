import math
import numpy as np
import cv2
import matplotlib.colors
from typing import List,Tuple,Union,Optional
from ._pose_types import Keypoint,BodyResult
eps=0.01
def is_normalized(keypoints: List[Optional[Keypoint]]) -> bool:
    point_normalized = [0 <= abs(k.x) <= 1 and 0 <= abs(k.y) <= 1 for k in keypoints if k is not None]
    if not point_normalized:
        return False
    return all(point_normalized)

def draw_bodypose(canvas: np.ndarray, keypoints: List[Keypoint], xinsr_stick_scaling: bool=False) -> np.ndarray:
    """
    Draw keypoints and limbs representing body pose on a given canvas.

    Args:
        canvas (np.ndarray): A 3D numpy array representing the canvas (image) on which to draw the body pose.
        keypoints (List[Keypoint]): A list of Keypoint objects representing the body keypoints to be drawn.
        xinsr_stick_scaling (bool): Whether or not scaling stick width for xinsr ControlNet

    Returns:
        np.ndarray: A 3D numpy array representing the modified canvas with the drawn body pose.

    Note:
        The function expects the x and y coordinates of the keypoints to be normalized between 0 and 1.
    """
    if not is_normalized(keypoints):
        H, W = (1.0, 1.0)
    else:
        H, W, _ = canvas.shape
    CH, CW, _ = canvas.shape
    stickwidth = 4
    max_side = max(CW, CH)
    if xinsr_stick_scaling:
        stick_scale = 1 if max_side < 500 else min(2 + max_side // 1000, 7)
    else:
        stick_scale = 1
    limbSeq = [[2, 3], [2, 6], [3, 4], [4, 5], [6, 7], [7, 8], [2, 9], [9, 10], [10, 11], [2, 12], [12, 13], [13, 14], [2, 1], [1, 15], [15, 17], [1, 16], [16, 18]]
    colors = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0], [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255], [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]
    for (k1_index, k2_index), color in zip(limbSeq, colors):
        keypoint1 = keypoints[k1_index - 1]
        keypoint2 = keypoints[k2_index - 1]
        if keypoint1 is None or keypoint2 is None:
            continue
        Y = np.array([keypoint1.x, keypoint2.x]) * float(W)
        X = np.array([keypoint1.y, keypoint2.y]) * float(H)
        mX = np.mean(X)
        mY = np.mean(Y)
        length = ((X[0] - X[1]) ** 2 + (Y[0] - Y[1]) ** 2) ** 0.5
        angle = math.degrees(math.atan2(X[0] - X[1], Y[0] - Y[1]))
        polygon = cv2.ellipse2Poly((int(mY), int(mX)), (int(length / 2), stickwidth * stick_scale), int(angle), 0, 360, 1)
        cv2.fillConvexPoly(canvas, polygon, [int(float(c) * 0.6) for c in color])
    for keypoint, color in zip(keypoints, colors):
        if keypoint is None:
            continue
        x, y = (keypoint.x, keypoint.y)
        x = int(x * W)
        y = int(y * H)
        cv2.circle(canvas, (int(x), int(y)), 4, color, thickness=-1)
    return canvas

def draw_handpose(canvas: np.ndarray, keypoints: Union[List[Keypoint], None]) -> np.ndarray:
    """
    Draw keypoints and connections representing hand pose on a given canvas.

    Args:
        canvas (np.ndarray): A 3D numpy array representing the canvas (image) on which to draw the hand pose.
        keypoints (List[Keypoint]| None): A list of Keypoint objects representing the hand keypoints to be drawn
                                          or None if no keypoints are present.

    Returns:
        np.ndarray: A 3D numpy array representing the modified canvas with the drawn hand pose.

    Note:
        The function expects the x and y coordinates of the keypoints to be normalized between 0 and 1.
    """
    if not keypoints:
        return canvas
    if not is_normalized(keypoints):
        H, W = (1.0, 1.0)
    else:
        H, W, _ = canvas.shape
    edges = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [0, 9], [9, 10], [10, 11], [11, 12], [0, 13], [13, 14], [14, 15], [15, 16], [0, 17], [17, 18], [18, 19], [19, 20]]
    for ie, (e1, e2) in enumerate(edges):
        k1 = keypoints[e1]
        k2 = keypoints[e2]
        if k1 is None or k2 is None:
            continue
        x1 = int(k1.x * W)
        y1 = int(k1.y * H)
        x2 = int(k2.x * W)
        y2 = int(k2.y * H)
        if x1 > eps and y1 > eps and (x2 > eps) and (y2 > eps):
            cv2.line(canvas, (x1, y1), (x2, y2), matplotlib.colors.hsv_to_rgb([ie / float(len(edges)), 1.0, 1.0]) * 255, thickness=2)
    for keypoint in keypoints:
        if keypoint is None:
            continue
        x, y = (keypoint.x, keypoint.y)
        x = int(x * W)
        y = int(y * H)
        if x > eps and y > eps:
            cv2.circle(canvas, (x, y), 4, (0, 0, 255), thickness=-1)
    return canvas

def draw_facepose(canvas: np.ndarray, keypoints: Union[List[Keypoint], None]) -> np.ndarray:
    """
    Draw keypoints representing face pose on a given canvas.

    Args:
        canvas (np.ndarray): A 3D numpy array representing the canvas (image) on which to draw the face pose.
        keypoints (List[Keypoint]| None): A list of Keypoint objects representing the face keypoints to be drawn
                                          or None if no keypoints are present.

    Returns:
        np.ndarray: A 3D numpy array representing the modified canvas with the drawn face pose.

    Note:
        The function expects the x and y coordinates of the keypoints to be normalized between 0 and 1.
    """
    if not keypoints:
        return canvas
    if not is_normalized(keypoints):
        H, W = (1.0, 1.0)
    else:
        H, W, _ = canvas.shape
    for keypoint in keypoints:
        if keypoint is None:
            continue
        x, y = (keypoint.x, keypoint.y)
        x = int(x * W)
        y = int(y * H)
        if x > eps and y > eps:
            cv2.circle(canvas, (x, y), 3, (255, 255, 255), thickness=-1)
    return canvas
