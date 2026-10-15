"""Pinned WanMove producer math with bounded raw CPU tensors."""
import json
import logging
import math
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
log = logging.getLogger(__name__)
device = torch.device("cpu")
VAE_STRIDE = (4, 8, 8)


def _preflight(payload, height, width, frames, track_coords=None, tracks=None):
    _bound_payload(payload)
    if not all(isinstance(value, int) and 1 <= value <= limit for value, limit in ((height, 2048), (width, 2048), (frames, 512))):
        raise ValueError("WanMove geometry exceeds 2048 pixels/512 frames")
    projected = (((frames - 1) // 4 + 1) * (height // 8) * (width // 8) * 16 * 4)
    if projected * 2 > MAX_PAYLOAD_BYTES:
        raise ValueError("WanMove projected feature map exceeds64MiB")
    if track_coords is not None:
        values = parse_json_tracks(track_coords)
        if not values or len(values) > 128 or not 1 <= len(values[0]) <= 512 or any(len(track) != len(values[0]) for track in values):
            raise ValueError("WanMove requires1..128 equal tracks of1..512 frames")
        for track in values:
            for point in track:
                if not all(isinstance(point.get(key), (int, float)) and math.isfinite(point[key]) and abs(point[key]) <= 16384 for key in ("x", "y")):
                    raise ValueError("WanMove coordinates must be finite and bounded16384")
    elif tracks is not None and "track_path" in tracks:
        path = tracks["track_path"]
        if not isinstance(path, torch.Tensor) or path.device.type != "cpu" or path.ndim != 3 or path.shape[-1] != 2 or not 1 <= path.shape[0] <= 512 or not 1 <= path.shape[1] <= 128:
            raise ValueError("WanMove track tensor requires CPU[frames,tracks,2]")
        if not torch.isfinite(path).all() or (path.abs() > 16384).any():
            raise ValueError("WanMove coordinates must be finite and bounded16384")
    else:
        raise ValueError("WanMove requires JSON coordinates or track_path")


def _conditioning_set_values(conditioning, values={}, append=False):
    c = []
    for t in conditioning:
        n = [t[0], t[1].copy()]
        for k in values:
            val = values[k]
            if append:
                old_val = n[1].get(k, None)
                if old_val is not None:
                    val = old_val + val
            n[1][k] = val
        c.append(n)
    return c


def parse_json_tracks(tracks):
    tracks_data = []
    try:
        # If tracks is a string, try to parse it as JSON
        if isinstance(tracks, str):
            parsed = json.loads(tracks.replace("'", '"'))
            tracks_data.extend(parsed)
        else:
            # If tracks is a list of strings, parse each one
            for track_str in tracks:
                parsed = json.loads(track_str.replace("'", '"'))
                tracks_data.append(parsed)

        # Check if we have a single track (dict with x,y) or a list of tracks
        if tracks_data and isinstance(tracks_data[0], dict) and 'x' in tracks_data[0]:
            # Single track detected, wrap it in a list
            tracks_data = [tracks_data]
        elif tracks_data and isinstance(tracks_data[0], list) and tracks_data[0] and isinstance(tracks_data[0][0], dict) and 'x' in tracks_data[0][0]:
            # Already a list of tracks, nothing to do
            pass
        else:
            # Unexpected format
            log.warning(f"Warning: Unexpected track format: {type(tracks_data[0])}")

    except json.JSONDecodeError as e:
        log.warning(f"Error parsing tracks JSON: {e}")
        tracks_data = []

    return tracks_data

def _add( image_embeds, track_coords=None, tracks=None, strength=1.0, track_mask=None):
    from .WanMove.trajectory import create_pos_feature_map, replace_feature
    updated = dict(image_embeds)
    track_visibility = None
    target_shape = image_embeds.get('target_shape')
    if target_shape is not None:
        height = target_shape[2] * VAE_STRIDE[1]
        width = target_shape[3] * VAE_STRIDE[2]
    else:
        height = image_embeds['lat_h'] * VAE_STRIDE[1]
        width = image_embeds['lat_w'] * VAE_STRIDE[2]
    num_frames = image_embeds['num_frames']
    if track_coords is not None:
        tracks_data = parse_json_tracks(track_coords)
        track_list = [[[track[frame]['x'], track[frame]['y']] for track in tracks_data] for frame in range(len(tracks_data[0]))]
        track = torch.tensor(track_list, dtype=torch.float32, device=device)
    elif tracks is not None and 'track_path' in tracks:
        track = tracks['track_path']
        if track_mask is None:
            track_visibility = tracks.get('track_visibility', None)
    track = track[:num_frames]
    num_tracks = track.shape[-2]
    if track_visibility is None:
        if track_mask is None:
            track_visibility = torch.ones((num_frames, num_tracks), dtype=torch.bool, device=device)
        else:
            track_visibility = (track_mask > 0).any(dim=(1, 2)).unsqueeze(-1)
    feature_map, track_pos = create_pos_feature_map(track, track_visibility, VAE_STRIDE, height, width, 16, track_num=num_tracks, device=device)
    updated.setdefault('wanmove_embeds', {})
    updated['wanmove_embeds']['track_pos'] = track_pos
    updated['wanmove_embeds']['strength'] = strength
    tracks_dict = {'track_path': track, 'track_visibility': track_visibility}
    return (updated, tracks_dict)

def _patchcond( positive, track_coords, track_mask=None):
    from .WanMove.trajectory import create_pos_feature_map, replace_feature
    concat_latent_image = positive[0][1]['concat_latent_image']
    B, C, T, H, W = concat_latent_image.shape
    num_frames = (T - 1) * 4 + 1
    width = W * 8
    height = H * 8
    tracks_data = parse_json_tracks(track_coords)
    track_list = [[[track[frame]['x'], track[frame]['y']] for track in tracks_data] for frame in range(len(tracks_data[0]))]
    track = torch.tensor(track_list, dtype=torch.float32, device=device)
    track = track[:num_frames]
    num_tracks = track.shape[-2]
    if track_mask is None:
        track_visibility = torch.ones((num_frames, num_tracks), dtype=torch.bool, device=device)
    else:
        track_visibility = (track_mask > 0).any(dim=(1, 2)).unsqueeze(-1)
    feature_map, track_pos = create_pos_feature_map(track, track_visibility, VAE_STRIDE, height, width, 16, track_num=num_tracks, device=device)
    wanmove_cond = replace_feature(concat_latent_image, track_pos.unsqueeze(0))
    positive = _conditioning_set_values(positive, {'concat_latent_image': wanmove_cond})
    tracks_dict = {'track_path': track, 'track_visibility': track_visibility}
    return (positive, tracks_dict)


class WanVideoAddWanMoveTracks(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoAddWanMoveTracks", display_name="WanVideo Add WanMove Tracks", category="WanVideoWrapper",
                         inputs=[io.Custom("WANVIDIMAGE_EMBEDS").Input("image_embeds"),
                                 io.Float.Input("strength", default=1.0, min=0.0, max=10.0, step=0.01, tooltip="Strength of the reference embedding"),
                                 io.Mask.Input("track_mask", optional=True),
                                 io.String.Input("track_coords", optional=True, force_input=True, tooltip="JSON string or list of JSON strings representing the tracks"),
                                 io.Custom("TRACKS").Input("tracks", optional=True, tooltip="Alternatively use Comfy Tracks dictionary")],
                         outputs=[io.Custom("WANVIDIMAGE_EMBEDS").Output(display_name="image_embeds"), io.Custom("TRACKS").Output(display_name="tracks")])

    @classmethod
    def execute(cls, image_embeds, strength=1.0, track_mask=None, track_coords=None, tracks=None):
        target = image_embeds.get("target_shape")
        height, width = (target[2] * 8, target[3] * 8) if target is not None else (image_embeds["lat_h"] * 8, image_embeds["lat_w"] * 8)
        _preflight((image_embeds, track_mask, track_coords, tracks), height, width, image_embeds["num_frames"], track_coords, tracks)
        return io.NodeOutput(*_add(image_embeds, track_coords, tracks, strength, track_mask))


class WanMove_native(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanMove_native", display_name="WanMove Native", category="WanVideoWrapper", is_deprecated=True,
                         inputs=[io.Conditioning.Input("positive"), io.String.Input("track_coords", force_input=True, tooltip="JSON string or list of JSON strings representing the tracks"), io.Mask.Input("track_mask", optional=True)],
                         outputs=[io.Conditioning.Output(display_name="positive"), io.Custom("TRACKS").Output(display_name="tracks")])

    @classmethod
    def execute(cls, positive, track_coords, track_mask=None):
        latent = positive[0][1]["concat_latent_image"]
        _preflight((positive, track_coords, track_mask), latent.shape[-2] * 8, latent.shape[-1] * 8, (latent.shape[-3] - 1) * 4 + 1, track_coords)
        return io.NodeOutput(*_patchcond(positive, track_coords, track_mask))


NODE_CLASS_MAPPINGS = {"WanVideoAddWanMoveTracks": WanVideoAddWanMoveTracks, "WanMove_native": WanMove_native}
