"""Wan ControlNet and ATI payloads; model execution stays with the consumer."""
import numpy as np
from comfy_api.latest import io, sdk
from ._wan_model_control_options import clone_model_options
from .secure_model_control_nodes import _options, _with_options
from .secure_tensor_nodes import _bound_payload
from .secure_ati_visual_nodes import pad_pts, parse_json_tracks, _preflight_text
from .ATI.motion import process_tracks


class WanVideoControlnetApply(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoControlnet', display_name='WanVideo Controlnet Apply',
            category='WanVideoWrapper', inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Custom('WANVIDEOCONTROLNET').Input('controlnet'),
                io.Image.Input('control_images'),
                io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.0001, tooltip='controlnet strength'),
                io.Int.Input('control_stride', default=3, min=1, max=8, step=1, tooltip='controlnet stride'),
                io.Float.Input('control_start_percent', default=0.0, min=0.0, max=1.0, step=0.01,
                               tooltip='Start percent of the steps to apply controlnet'),
                io.Float.Input('control_end_percent', default=1.0, min=0.0, max=1.0, step=0.01,
                               tooltip='End percent of the steps to apply controlnet'),
            ], outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    async def execute(cls, model, controlnet, control_images, strength, control_stride,
                      control_start_percent, control_end_percent):
        options = clone_model_options(_options(model))
        if 'transformer_options' not in options:
            options['transformer_options'] = {}
        images = await control_images.raw() if isinstance(control_images, sdk.ImageRef) else control_images
        _bound_payload(images)
        control_input = images.permute(3, 0, 1, 2).unsqueeze(0).contiguous()
        control_input = control_input * 2.0 - 1.0
        _bound_payload(control_input)
        options['transformer_options']['controlnet'] = {
            'controlnet': controlnet,
            'control_latents': await sdk.ValueRef.from_value(control_input),
            'controlnet_strength': strength,
            'control_stride': control_stride,
            'controlnet_start': control_start_percent,
            'controlnet_end': control_end_percent,
        }
        return _with_options(model, options)


class WanVideoATITracks(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoATITracks', display_name='WanVideo ATI Tracks',
            category='WanVideoWrapper', inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.String.Input('tracks'),
                io.Int.Input('width', default=832, min=64, max=2048, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=29048, step=8, tooltip='Height of the image to encode'),
                io.Float.Input('temperature', default=220.0, min=0.0, max=1000.0, step=0.1),
                io.Int.Input('topk', default=2, min=1, max=10, step=1),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01,
                               tooltip='Start percent of the steps to apply ATI'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01,
                               tooltip='End percent of the steps to apply ATI'),
            ], outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    async def execute(cls, model, tracks, width, height, temperature, topk, start_percent, end_percent):
        _preflight_text(tracks)
        tracks_data = parse_json_tracks(tracks)
        _bound_payload(tracks_data)
        arrs = []
        for track in tracks_data:
            pts = pad_pts(track)
            arrs.append(pts)
        tracks_np = np.stack(arrs, axis=0)
        processed_tracks = process_tracks(tracks_np, (width, height))
        options = clone_model_options(_options(model))
        transformer_options = options['transformer_options']
        payload = processed_tracks.unsqueeze(0)
        _bound_payload(payload)
        transformer_options['ati_tracks'] = await sdk.ValueRef.from_value(payload)
        transformer_options['ati_temperature'] = temperature
        transformer_options['ati_topk'] = topk
        transformer_options['ati_start_percent'] = start_percent
        transformer_options['ati_end_percent'] = end_percent
        return _with_options(model, options)


NODE_CLASS_MAPPINGS = {'WanVideoControlnet': WanVideoControlnetApply,
                       'WanVideoATITracks': WanVideoATITracks}
