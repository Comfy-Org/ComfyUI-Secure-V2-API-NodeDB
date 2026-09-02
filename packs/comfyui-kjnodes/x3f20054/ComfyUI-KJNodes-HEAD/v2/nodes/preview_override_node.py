from __future__ import annotations
from comfy_api.latest import io as _remaining_zr_io, sdk as _remaining_zr_sdk

class ModelPreviewOverrideKJSecure(_remaining_zr_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zr_io.Schema:
        return _remaining_zr_io.Schema(node_id='ModelPreviewOverrideKJSecure', display_name='🔒 Model Preview Override (secure)', category='KJNodes/sampling', description='Attaches a trusted live-preview policy to the model while keeping model weights, VAE objects, frames, and UI publication outside the guest.', inputs=[_remaining_zr_io.Model.Input('model'), _remaining_zr_io.Int.Input('max_resolution', default=1024, min=0, max=8192, step=8), _remaining_zr_io.Int.Input('jpeg_quality', default=80, min=30, max=100, step=1), _remaining_zr_io.Boolean.Input('suppress_default_preview', default=True), _remaining_zr_io.Int.Input('preview_frames', default=1, min=1, max=1024, step=1), _remaining_zr_io.Int.Input('preview_fps', default=12, min=1, max=60, step=1), _remaining_zr_io.Vae.Input('vae', optional=True), _remaining_zr_io.Combo.Input('tiny_vae', options=['none'], default='none', optional=True, remote=_remaining_zr_io.RemoteOptions(route='/models/vae_approx/choices', refresh_button=True))], outputs=[_remaining_zr_io.Model.Output('model')], is_experimental=True)

    @classmethod
    def validate_inputs(cls, tiny_vae='none'):
        if not isinstance(tiny_vae, str) or not tiny_vae:
            return 'tiny_vae must be a logical catalogue name'
        normalized = tiny_vae.replace('\\', '/')
        if '\x00' in tiny_vae or normalized.startswith('/') or '..' in normalized.split('/'):
            return 'tiny_vae must stay inside the vae_approx catalogue'
        return True

    @classmethod
    async def execute(cls, model, max_resolution, jpeg_quality, suppress_default_preview, preview_frames, preview_fps, vae=None, tiny_vae='none') -> _remaining_zr_io.NodeOutput:
        result = await _remaining_zr_sdk.ctx().preview_override.attach(model, max_resolution=max_resolution, jpeg_quality=jpeg_quality, suppress_default_preview=suppress_default_preview, preview_frames=preview_frames, preview_fps=preview_fps, vae=vae, tiny_vae=tiny_vae)
        return _remaining_zr_io.NodeOutput(result)

class GetPreviewOverrideFramesKJSecure(_remaining_zr_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zr_io.Schema:
        return _remaining_zr_io.Schema(node_id='GetPreviewOverrideFramesKJSecure', display_name='🔒 Get Preview Override Frames (secure)', category='KJNodes/sampling', description='Returns frames captured by the preview policy after the sampler has completed.', inputs=[_remaining_zr_io.Model.Input('model'), _remaining_zr_io.MultiType.Input('after_sample', [_remaining_zr_io.Latent, _remaining_zr_io.Image])], outputs=[_remaining_zr_io.Image.Output('frames')], is_experimental=True)

    @classmethod
    async def execute(cls, model, after_sample) -> _remaining_zr_io.NodeOutput:
        frames = await _remaining_zr_sdk.ctx().preview_override.frames(model, after_sample)
        return _remaining_zr_io.NodeOutput(frames)

NODE_CLASS_MAPPINGS = {
    'ModelPreviewOverrideKJSecure': ModelPreviewOverrideKJSecure,
    'GetPreviewOverrideFramesKJSecure': GetPreviewOverrideFramesKJSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'ModelPreviewOverrideKJSecure': '🔒 Model Preview Override (secure)',
    'GetPreviewOverrideFramesKJSecure': '🔒 Get Preview Override Frames (secure)',
}
