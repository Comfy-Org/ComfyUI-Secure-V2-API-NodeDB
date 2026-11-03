from comfy_api.latest import io, sdk
from ._secure_boundary import SecureConversionRefusal, data_input


class D2_SaveAudioEagle(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Save Audio Eagle', display_name='D2 Save Audio Eagle', category='D2/Audio', is_output_node=True, inputs=[io.Audio.Input('audio'), io.String.Input('filename_prefix', default='audoi/ComfyUI'), io.String.Input('eagle_folder', default=''), io.Combo.Input('format', options=['FLAC', 'MP3', 'Opus'], default='FLAC'), io.Combo.Input('mp3_quality', options=['V0', '128k', '320k'], default='V0'), io.Combo.Input('opus_quality', options=['64k', '96k', '128k', '192k', '320k'], default='128k'), io.String.Input('memo_text', default=''), io.Custom('AUDIO_UI').Input('audioUI')], outputs=[], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Save Audio Eagle is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Save Audio Eagle is not yet converted to Secure Nodes V2: The purpose writes audio to a host path and sends it to the local Eagle HTTP service; no faithful public guest contract.')


NODE_CLASS_MAPPINGS = {
    "D2 Save Audio Eagle": D2_SaveAudioEagle,
}
