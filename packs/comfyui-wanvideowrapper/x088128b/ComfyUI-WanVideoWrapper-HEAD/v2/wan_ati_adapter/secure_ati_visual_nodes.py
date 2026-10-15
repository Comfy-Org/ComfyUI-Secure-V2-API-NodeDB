"""Bounded pack-owned ATI trail rasterization, not ATI model inference."""
import json
import math
import numpy as np
import torch
from typing import Tuple
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS

FIXED_LENGTH = 121
MAX_TRACKS = 64
MAX_DRAW_CALLS = 250000

def _preflight_images(images):
    _bound_payload(images)
    if not isinstance(images, torch.Tensor) or images.ndim != 4:
        return
    count, height, width, channels = images.shape
    if count == 0:
        return  # preserve source ZeroDivisionError after valid track parsing
    backing = count if count >= 81 else count * ((81 + count - 1) // count)
    elements = 81 * height * width * channels
    frame_bytes = height * width * channels * images.element_size()
    # Input + possible CPU copy, repeat + CPU copy, raster copy + current frame,
    # float32 publication. Charge conservative overlapping lifetime before repeat.
    projected = 2 * images.numel() * images.element_size() + (2 * backing + 82) * frame_bytes + elements * 4
    if elements > MAX_TENSOR_ELEMENTS or projected > MAX_PAYLOAD_BYTES:
        raise ValueError('Wan ATI projected repeat/raster exceeds tensor/64 MiB bounds')

def _preflight_text(tracks):
    text = [tracks] if isinstance(tracks, str) else tracks if isinstance(tracks, (list, tuple)) else ()
    if sum(len(value.encode('utf-8', errors='surrogatepass')) for value in text if isinstance(value, str)) > 65536:
        raise ValueError('Wan ATI track text exceeds 64 KiB')

def _preflight_tracks(tracks, tracks_data, min_radius, max_radius, max_retain):
    _bound_payload(tracks_data)
    if isinstance(tracks_data, (list, tuple)) and len(tracks_data) > MAX_TRACKS:
        raise ValueError('Wan ATI track count exceeds 64')
    # The source examines all past points, even when max_retain later hides them.
    if isinstance(tracks_data, (list, tuple)) and len(tracks_data) * 81 * 82 // 2 > MAX_DRAW_CALLS:
        raise ValueError('Wan ATI projected trail work exceeds bound')
    for radius in (min_radius, max_radius):
        if isinstance(radius, (int, float)) and math.isfinite(radius) and abs(radius) > 100:
            raise ValueError('Wan ATI radius exceeds bounded raster work')
    if isinstance(max_retain, (int, float)) and math.isfinite(max_retain) and abs(max_retain) > 100:
        raise ValueError('Wan ATI retention exceeds bounded work')
    for track in tracks_data if isinstance(tracks_data, (list, tuple)) else ():
        for point in track if isinstance(track, (list, tuple)) else ():
            if isinstance(point, dict):
                for axis in ('x', 'y'):
                    coordinate = point.get(axis)
                    if isinstance(coordinate, (int, float)) and (not math.isfinite(coordinate) or abs(coordinate) > 1000000):
                        raise ValueError('Wan ATI coordinates exceed finite bounded input')

def pad_pts(tr):
    """Convert list of {x,y} to (FIXED_LENGTH,1,3) array, padding/truncating."""
    pts = np.array([[p['x'], p['y'], 1] for p in tr], dtype=np.float32)
    n = pts.shape[0]
    if n < FIXED_LENGTH:
        pad = np.zeros((FIXED_LENGTH - n, 3), dtype=np.float32)
        pts = np.vstack((pts, pad))
    else:
        pts = pts[:FIXED_LENGTH]
    return pts.reshape(FIXED_LENGTH, 1, 3)

def age_to_bgr(ratio: float) -> Tuple[int, int, int]:
    """
    Map ratio∈[0,1] through: 0→blue, 1/3→green, 2/3→yellow, 1→red.
    Returns (B,G,R) for OpenCV.
    """
    if ratio <= 1 / 3:
        t = ratio / (1 / 3)
        b = int(255 * (1 - t))
        g = int(255 * t)
        r = 0
    elif ratio <= 2 / 3:
        t = (ratio - 1 / 3) / (1 / 3)
        b = 0
        g = 255
        r = int(255 * t)
    else:
        t = (ratio - 2 / 3) / (1 / 3)
        b = 0
        g = int(255 * (1 - t))
        r = 255
    return (r, g, b)

def paint_point_track(frames: np.ndarray, point_tracks: np.ndarray, visibles: np.ndarray, min_radius: int=1, max_radius: int=6, max_retain: int=50) -> np.ndarray:
    """
    Draws every past point of each track on each frame, with radius and color
    interpolated by the point's age (old→small to new→large).

    Args:
      frames:      [F, H, W, 3] uint8 RGB
      point_tracks:[N, F, 2] float32  – (x,y) in pixel coords
      visibles:    [N, F] bool        – visibility mask
      min_radius:  radius for the very first point (oldest)
      max_radius:  radius for the current point (newest)

    Returns:
      video: [F, H, W, 3] uint8 RGB
    """
    import cv2
    num_points, num_frames = point_tracks.shape[:2]
    H, W = frames.shape[1:3]
    video = frames.copy()
    for t in range(num_frames):
        frame = video[t].copy()
        for i in range(num_points):
            for τ in range(t + 1):
                if not visibles[i, τ]:
                    continue
                if t - τ > max_retain:
                    continue
                x, y = point_tracks[i, τ] + 0.5
                xi = int(np.clip(x, 0, W - 1))
                yi = int(np.clip(y, 0, H - 1))
                if num_frames > 1:
                    ratio = 1 - float(t - τ) / max_retain
                else:
                    ratio = 1.0
                radius = int(round(min_radius + (max_radius - min_radius) * ratio))
                color_rgb = age_to_bgr(ratio)
                cv2.circle(frame, (xi, yi), radius, color_rgb, thickness=-1)
        video[t] = frame
    return video

def parse_json_tracks(tracks):
    tracks_data = []
    try:
        if isinstance(tracks, str):
            parsed = json.loads(tracks.replace("'", '"'))
            tracks_data.extend(parsed)
        else:
            for track_str in tracks:
                parsed = json.loads(track_str.replace("'", '"'))
                tracks_data.append(parsed)
        if tracks_data and isinstance(tracks_data[0], dict) and ('x' in tracks_data[0]):
            tracks_data = [tracks_data]
        elif tracks_data and isinstance(tracks_data[0], list) and tracks_data[0] and isinstance(tracks_data[0][0], dict) and ('x' in tracks_data[0][0]):
            pass
        else:
            print(f'Warning: Unexpected track format: {type(tracks_data[0])}')
    except json.JSONDecodeError as e:
        print(f'Error parsing tracks JSON: {e}')
        tracks_data = []
    return tracks_data

class WanVideoATITracksVisualize(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoATITracksVisualize',
            display_name='WanVideo ATI Tracks Visualize', category='WanVideoWrapper',
            inputs=[io.Image.Input('images'), io.String.Input('tracks'),
                io.Int.Input('min_radius', default=1, min=0, max=100, step=1, tooltip='radius for the very first point (oldest)'),
                io.Int.Input('max_radius', default=6, min=0, max=100, step=1, tooltip='radius for the current point (newest)'),
                io.Int.Input('max_retain', default=50, min=0, max=100, step=1, tooltip='Maximum number of points to retain')],
            outputs=[io.Image.Output(display_name='images')])

    @classmethod
    def execute(cls, images, tracks, min_radius, max_radius, max_retain):
        _preflight_images(images)
        _bound_payload(tracks)
        _preflight_text(tracks)
        tracks_data = parse_json_tracks(tracks)
        _preflight_tracks(tracks, tracks_data, min_radius, max_radius, max_retain)
        arrs = []
        for track in tracks_data:
            pts = pad_pts(track)
            arrs.append(pts)
        tracks_np = np.stack(arrs, axis=0)
        track = np.repeat(tracks_np, 2, axis=1)[:, ::3]
        points = track[:, :, 0, :2].astype(np.float32)
        visibles = track[:, :, 0, 2].astype(np.float32)
        if images.shape[0] < points.shape[1]:
            repeat_count = (points.shape[1] + images.shape[0] - 1) // images.shape[0]
            images = images.repeat(repeat_count, 1, 1, 1)
            images = images[:points.shape[1]]
        elif images.shape[0] > points.shape[1]:
            images = images[:points.shape[1]]
        video_viz = paint_point_track(images.cpu().numpy(), points, visibles, min_radius, max_radius, max_retain)
        video_viz = torch.from_numpy(video_viz).float()
        return io.NodeOutput(video_viz)

NODE_CLASS_MAPPINGS = {'WanVideoATITracksVisualize': WanVideoATITracksVisualize}
