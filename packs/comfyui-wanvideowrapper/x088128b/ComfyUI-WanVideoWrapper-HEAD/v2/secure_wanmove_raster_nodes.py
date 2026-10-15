"""Pinned WanMove raster math under bounded raw compute, not model tracking."""
import logging
import math
import numpy as np
import torch
import torchvision.transforms.functional as TF
from PIL import Image, ImageDraw
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
log = logging.getLogger(__name__)
MAX_DRAW_STEPS = 250000

def _preflight(images, tracks, line_resolution, circle_size, opacity, line_width):
    _bound_payload((images, tracks))
    if not isinstance(images, torch.Tensor):
        return
    if images.device.type != 'cpu':
        raise ValueError('WanMove raster accepts dense CPU values only')
    if images.ndim != 4:
        return
    frames, height, width, channels = images.shape
    if frames > 512 or max(height, width) > 1024:
        raise ValueError('WanMove raster frame/geometry bounds')
    output_frames = frames
    path = tracks.get('track_path') if isinstance(tracks, dict) else None
    if isinstance(path, torch.Tensor):
        if path.device.type != 'cpu':
            raise ValueError('WanMove tracks accept CPU values only')
        if path.ndim == 3 and path.shape[-1] == 2:
            if path.shape[0] > 512 or path.shape[1] > 128:
                raise ValueError('WanMove track frame/count bounds')
            if not torch.isfinite(path).all() or ((path < -4096) | (path > 4096)).any():
                raise ValueError('WanMove track coordinates must be finite and bounded4096')
            for value, limit in ((line_resolution, 64), (circle_size, 20), (line_width, 50)):
                if not isinstance(value, int) or abs(value) > limit:
                    raise ValueError('WanMove drawing scalar bounds')
            if not isinstance(opacity, (int, float)) or not math.isfinite(opacity) or abs(opacity) > 1:
                raise ValueError('WanMove opacity must be finite and bounded')
            if frames and frames != path.shape[0]:
                output_frames = frames * (path.shape[0] // frames)
            points = path.long()
            work = 0
            for t in range(1, points.shape[0]):
                for n in range(points.shape[1]):
                    dx = int(points[t, n, 0]) - int(points[t - 1, n, 0])
                    dy = int(points[t, n, 1]) - int(points[t - 1, n, 1])
                    work += max(int(math.hypot(dx, dy)), 1) * max(line_resolution, 0)
                    if work > MAX_DRAW_STEPS:
                        raise ValueError('WanMove projected drawing work exceeds250000steps')
    projected = images.numel() * images.element_size() + output_frames * height * width * channels * 14 + height * width * 64
    if projected > MAX_PAYLOAD_BYTES:
        raise ValueError('WanMove projected raster exceeds64MiB')

def draw_tracks_on_video(video, tracks, visibility=None, track_frame=24, circle_size=12, opacity=0.5, line_width=16):
    color_map = [(102, 153, 255), (0, 255, 255), (255, 255, 0), (255, 102, 204), (0, 255, 0)]
    video = video.byte().cpu().numpy()
    tracks = tracks[0].long().detach().cpu().numpy()
    if visibility is not None:
        visibility = visibility[0].detach().cpu().numpy()
    num_frames, height, width = video.shape[:3]
    num_tracks = tracks.shape[1]
    alpha_opacity = int(255 * opacity)
    output_frames = []
    try:
        for t in range(num_frames):
            frame_rgb = video[t].astype(np.float32)
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            try:
                draw_overlay = ImageDraw.Draw(overlay)
                polyline_data = []
                for n in range(num_tracks):
                    if visibility is not None and visibility[t, n] == 0:
                        continue
                    track_coord = tracks[t, n]
                    color = color_map[n % len(color_map)]
                    circle_color = color + (alpha_opacity,)
                    draw_overlay.ellipse((track_coord[0] - circle_size, track_coord[1] - circle_size, track_coord[0] + circle_size, track_coord[1] + circle_size), fill=circle_color)
                    tracks_coord = tracks[max(t - track_frame, 0):t + 1, n]
                    if len(tracks_coord) > 1:
                        polyline_data.append((tracks_coord, color))
                overlay_np = np.array(overlay)
                alpha = overlay_np[:, :, 3:4] / 255.0
                frame_rgb = overlay_np[:, :, :3] * alpha + frame_rgb * (1 - alpha)
                if polyline_data:
                    polyline_overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                    try:
                        for tracks_coord, color in polyline_data:
                            _draw_gradient_polyline_on_overlay(polyline_overlay, line_width, tracks_coord, color, opacity)
                        polyline_np = np.array(polyline_overlay)
                        alpha = polyline_np[:, :, 3:4] / 255.0
                        frame_rgb = polyline_np[:, :, :3] * alpha + frame_rgb * (1 - alpha)
                    finally:
                        polyline_overlay.close()
                output_frames.append(Image.fromarray(frame_rgb.astype(np.uint8)))
            finally:
                overlay.close()
        return output_frames
    except BaseException:
        for frame in output_frames:
            frame.close()
        raise

def _draw_gradient_polyline_on_overlay(overlay, line_width, points, start_color, opacity=1.0):
    """
    Draw a gradient polyline directly onto an existing RGBA overlay image.
    This is an optimized version that doesn't create new images.
    """
    draw = ImageDraw.Draw(overlay, 'RGBA')
    points = points[::-1]
    total_length = 0
    segment_lengths = []
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        length = (dx * dx + dy * dy) ** 0.5
        segment_lengths.append(length)
        total_length += length
    if total_length == 0:
        return
    accumulated_length = 0
    for idx, (start_point, end_point) in enumerate(zip(points[:-1], points[1:])):
        segment_length = segment_lengths[idx]
        steps = max(int(segment_length), 1)
        for i in range(steps):
            current_length = accumulated_length + i / steps * segment_length
            ratio = current_length / total_length
            alpha = int(255 * (1 - ratio) * opacity)
            color = (*start_color, alpha)
            x = int(start_point[0] + (end_point[0] - start_point[0]) * i / steps)
            y = int(start_point[1] + (end_point[1] - start_point[1]) * i / steps)
            dynamic_line_width = max(int(line_width * (1 - ratio)), 1)
            draw.line([(x, y), (x + 1, y)], fill=color, width=dynamic_line_width)
        accumulated_length += segment_length

class WanVideoWanDrawWanMoveTracks(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoWanDrawWanMoveTracks', display_name='WanVideo Draw WanMove Tracks', category='WanVideoWrapper', inputs=[io.Image.Input('images'), io.Custom('TRACKS').Input('tracks'), io.Int.Input('line_resolution', default=24, min=4, max=64, step=1, optional=True, tooltip='Number of points to use for each line segment'), io.Int.Input('circle_size', default=10, min=1, max=20, step=1, optional=True, tooltip='Size of the circle to draw for each track point'), io.Float.Input('opacity', default=0.5, min=0.0, max=1.0, step=0.01, optional=True, tooltip='Opacity of the circle to draw for each track point'), io.Int.Input('line_width', default=14, min=1, max=50, step=1, optional=True, tooltip='Width of the line to draw for each track')], outputs=[io.Image.Output(display_name='image')])

    @classmethod
    def execute(cls, images, tracks, line_resolution=24, circle_size=10, opacity=0.5, line_width=14):
        _preflight(images, tracks, line_resolution, circle_size, opacity, line_width)
        if tracks is None or 'track_path' not in tracks:
            log.warning('WanVideoWanDrawWanMoveTracks: No tracks provided.')
            return io.NodeOutput(images.float().cpu())
        track = tracks['track_path'].unsqueeze(0)
        track_visibility = tracks['track_visibility'].unsqueeze(0)
        images_in = images * 255.0
        if images_in.shape[0] != track.shape[1]:
            repeat_count = track.shape[1] // images.shape[0]
            images_in = images_in.repeat(repeat_count, 1, 1, 1)
        track_video = draw_tracks_on_video(images_in, track, track_visibility, track_frame=line_resolution, circle_size=circle_size, opacity=opacity, line_width=line_width)
        try:
            output = torch.stack([TF.to_tensor(frame) for frame in track_video], dim=0).movedim(1, -1)
            return io.NodeOutput(output.float().cpu())
        finally:
            for frame in track_video:
                frame.close()
NODE_CLASS_MAPPINGS = {'WanVideoWanDrawWanMoveTracks': WanVideoWanDrawWanMoveTracks}
