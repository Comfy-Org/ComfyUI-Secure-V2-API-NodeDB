from __future__ import annotations
from comfy_api.latest import io as _remaining_w_io
_remaining_w_SCHEDULES = ['standard_static', 'standard_static_balanced', 'standard_uniform', 'looped_uniform', 'batched', 'batched_shifted']
_remaining_w_FUSE_METHODS = ['pyramid', 'relative', 'flat', 'overlap-linear', 'hann', 'gaussian']

class ContextWindowsVisualizerKJSecure(_remaining_w_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_w_io.Schema:
        return _remaining_w_io.Schema(node_id='ContextWindowsVisualizerKJSecure', display_name='🔒 Context Windows Visualizer (KJ) (secure)', category='KJNodes/misc', description='Configures context-window placement, overlap blending, causal anchoring and FreeNoise on an optional model.', is_experimental=True, inputs=[_remaining_w_io.Model.Input('model', optional=True), _remaining_w_io.Combo.Input('frame_units', options=['pixel', 'latent'], default='pixel'), _remaining_w_io.Int.Input('dim', default=2, min=0, max=5, advanced=True), _remaining_w_io.Int.Input('temporal_downscale', default=4, min=1, max=16), _remaining_w_io.Int.Input('num_frames', default=161, min=1, max=100000), _remaining_w_io.Int.Input('context_length', default=81, min=1, max=100000), _remaining_w_io.Int.Input('context_overlap', default=30, min=0, max=100000), _remaining_w_io.Combo.Input('context_schedule', options=_remaining_w_SCHEDULES), _remaining_w_io.Int.Input('context_stride', default=1, min=1, max=32), _remaining_w_io.Boolean.Input('closed_loop', default=False), _remaining_w_io.Combo.Input('fuse_method', options=_remaining_w_FUSE_METHODS, default='pyramid'), _remaining_w_io.Boolean.Input('causal_window_fix', default=False, advanced=True), _remaining_w_io.Boolean.Input('freenoise', default=True, advanced=True), _remaining_w_io.String.Input('cond_retain_index_list', default='', advanced=True)], outputs=[_remaining_w_io.Model.Output('model', display_name='model')])

    @classmethod
    async def execute(cls, frame_units, temporal_downscale, num_frames, context_length, context_overlap, context_schedule, context_stride, closed_loop, fuse_method, dim, causal_window_fix, freenoise, cond_retain_index_list='', model=None) -> _remaining_w_io.NodeOutput:
        if model is None:
            return _remaining_w_io.NodeOutput(None)
        if frame_units == 'pixel':
            factor = max(int(temporal_downscale), 1)
            context_length = max((context_length - 1) // factor + 1, 1)
            context_overlap = max((context_overlap - 1) // factor + 1, 0)
        retain_indices = [int(item.strip()) for item in cond_retain_index_list.split(',')] if cond_retain_index_list else []
        patched = await model.patch('context_windows', context_schedule=context_schedule, fuse_method=fuse_method, context_length=context_length, context_overlap=context_overlap, context_stride=context_stride, closed_loop=closed_loop, dim=dim, freenoise=freenoise, causal_window_fix=causal_window_fix, cond_retain_indices=retain_indices)
        return _remaining_w_io.NodeOutput(patched)

NODE_CLASS_MAPPINGS = {
    'ContextWindowsVisualizerKJSecure': ContextWindowsVisualizerKJSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'ContextWindowsVisualizerKJSecure': '🔒 Context Windows Visualizer (KJ) (secure)',
}
