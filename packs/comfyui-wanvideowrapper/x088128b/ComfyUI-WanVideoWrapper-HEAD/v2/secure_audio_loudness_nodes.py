"""Permissioned AUDIO boundary around the unchanged native loudness algorithm."""
from comfy_api.latest import io, sdk


class NormalizeAudioLoudness(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NormalizeAudioLoudness",
            display_name="Normalize Audio Loudness",
            category="WanVideoWrapper",
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "lufs", default=-23.0, min=-100.0, max=0.0, step=0.1,
                    extra_dict={
                        "tool": "Loudness Units relative to Full Scale, higher LUFS values (closer to 0) mean louder audio. Lower LUFS values (more negative) mean quieter audio."
                    },
                ),
            ],
            outputs=[io.Audio.Output(display_name="audio")],
        )

    @classmethod
    async def execute(cls, audio, lufs):
        materialized = await audio.value()
        # Schema discovery never imports scientific libraries or the vendor.
        # Materialization is separately permitted by the real runtime before
        # importing and invoking the previously preserved pack algorithm.
        from .secure_audio_loudness_algorithm import AudioLoudnessNormalizationAlgorithm

        result, = AudioLoudnessNormalizationAlgorithm().normalize(materialized, lufs)
        return io.NodeOutput(await sdk.AudioRef.from_value(result))


NODE_CLASS_MAPPINGS = {"NormalizeAudioLoudness": NormalizeAudioLoudness}
