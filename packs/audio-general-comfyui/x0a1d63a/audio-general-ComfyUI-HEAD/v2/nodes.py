"""Secure, behavior-equivalent Audio General nodes.

The pinned pack's algorithms stay here in the guest. AUDIO crosses the host
boundary only through ``AudioRef.value`` and ``AudioRef.from_value``; no host
objects, paths, network clients, or process-global hooks are exposed.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any

import torch

from comfy_api.latest import io, sdk


_AUDIO_NAME = re.compile(r"^audio([0-9]+)$")
_VOLUME_TOOLTIP = (
    "Example: 0 = silent, 0.5 = half, 1 = normal, 2 = twice volume"
)
_START_TOOLTIP = "Number of seconds to wait before starting audio"


async def _audio_value(value: Any) -> dict[str, Any]:
    if isinstance(value, sdk.AudioRef):
        value = await value.value()
    return value


async def _audio_values(values: Any) -> list[dict[str, Any]]:
    return [await _audio_value(value) for value in values]


async def _audio_output(value: dict[str, Any]) -> sdk.AudioRef:
    return await sdk.AudioRef.from_value(value)


def _always_changed(cls, **_kwargs: Any) -> float:
    # Every pinned IS_CHANGED except AudioInfo raises TypeError while feeding
    # dict/scalar values to hashlib.update. Comfy catches that and records NaN,
    # intentionally making those nodes run again on every prompt.
    return float("NaN")


def _last_audio(kwargs: dict[str, Any]) -> int:
    last_audio = 0
    for key in kwargs:
        match = _AUDIO_NAME.match(key)
        if match is not None:
            index = int(match.group(1))
            if index >= last_audio:
                last_audio = index
    return last_audio


def _audios_max(audios: list[list[Any]]) -> tuple[int, int, int]:
    max_time_len = 0
    max_sample_rate = 0
    max_channels = 0
    for audio_arr in audios:
        audio, _volume = audio_arr
        audio_count, channels, waveform_len = audio["waveform"].shape
        sample_rate = audio["sample_rate"]
        if sample_rate > max_sample_rate:
            max_sample_rate = sample_rate
        time_len = waveform_len / sample_rate
        if time_len > max_time_len:
            max_time_len = time_len
        if channels > max_channels:
            max_channels = channels
        max_waveform_len = int(math.ceil(max_time_len * max_sample_rate))
    print(
        f"max channels:{max_channels}, max_sample_rate:{max_sample_rate}, "
        f"max_waveform: {max_waveform_len}"
    )
    return max_waveform_len, max_sample_rate, max_channels


def _pad_resample_audios(
    audios: list[list[Any]],
    max_waveform_len: int | None,
    max_sample_rate: int,
    max_channels: int | None,
) -> list[torch.Tensor]:
    import torchaudio

    out_audios = []
    for audio_arr in audios:
        audio, volume = audio_arr
        waveform = audio["waveform"]
        sample_rate = audio["sample_rate"]
        audio_count, channels, waveform_len = waveform.shape
        if max_channels is not None and channels < max_channels:
            waveform = waveform.expand(audio_count, max_channels, waveform_len)

        if sample_rate < max_sample_rate:
            resample = torchaudio.transforms.Resample(
                sample_rate, max_sample_rate
            )
            waveform = resample(waveform)

        _audio_count, _channels, waveform_len = waveform.shape
        if (
            max_waveform_len is not None
            and waveform_len < max_waveform_len
        ):
            pad = int(max_waveform_len - waveform_len)
            waveform = torch.nn.functional.pad(waveform, pad=(0, pad))

        if volume != 1.0:
            waveform = waveform.multiply(volume)
        if volume > 0.0:
            out_audios.append(waveform)
    return out_audios


class _AudioNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)


class AudioInfo(_AudioNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioInfo",
            display_name="Audio Info",
            category="Audio",
            inputs=[io.Audio.Input("audio")],
            outputs=[
                io.Float.Output("seconds", display_name="seconds"),
                io.Custom("int").Output(
                    "sample_rate", display_name="sample_rate"
                ),
                io.Boolean.Output("mono", display_name="mono"),
            ],
        )

    @classmethod
    async def execute(cls, audio: sdk.AudioRef) -> io.NodeOutput:
        value = await _audio_value(audio)
        waveform = value["waveform"]
        sample_rate = value["sample_rate"]
        seconds = len(waveform[0][0]) / sample_rate
        return io.NodeOutput(seconds, sample_rate, len(waveform[0]) == 1)


class AudioSampleRate(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioSampleRate",
            display_name="Audio Pitch (Sample Rate)",
            category="Audio",
            description="Quickly change the pitch by changing the sample rate",
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "change",
                    default=1.0,
                    step=0.01,
                    tooltip=(
                        "Less than 1.0 for a lower pitch. More than 1.0 for "
                        "a higher pitch"
                    ),
                ),
            ],
            outputs=[io.Audio.Output("audio", display_name="audio")],
        )

    @classmethod
    async def execute(
        cls, audio: sdk.AudioRef, change: float
    ) -> io.NodeOutput:
        value = await _audio_value(audio)
        result = {
            "waveform": value["waveform"],
            "sample_rate": int(value["sample_rate"] * change),
        }
        return io.NodeOutput(await _audio_output(result))


class AudioPitch(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioPitch",
            display_name="Audio Pitch",
            category="Audio",
            description="Change the pitch with torchaudio",
            inputs=[
                io.Audio.Input("audio"),
                io.Int.Input(
                    "n_steps",
                    default=2,
                    step=1,
                    display_mode=io.NumberDisplay.number,
                    tooltip="The (fractional) steps to shift waveform.",
                ),
                io.Int.Input(
                    "bins_per_octave",
                    default=12,
                    step=1,
                    optional=True,
                    tooltip="The number of steps per octave (Default : 12).",
                ),
                io.Int.Input(
                    "n_fft",
                    default=512,
                    step=16,
                    optional=True,
                    tooltip=(
                        "Size of FFT, creates n_fft // 2 + 1 bins "
                        "(Default: 512)."
                    ),
                ),
                io.Int.Input(
                    "win_length",
                    default=-1,
                    min=-1,
                    optional=True,
                    display_mode=io.NumberDisplay.number,
                    tooltip="Window size. If -1, then n_fft is used",
                ),
                io.Int.Input(
                    "hop_length",
                    default=-1,
                    min=-1,
                    optional=True,
                    tooltip=(
                        "Length of hop between STFT windows. If None, then "
                        "win_length // 4 is used"
                    ),
                ),
            ],
            outputs=[io.Audio.Output("audio", display_name="audio")],
        )

    @classmethod
    async def execute(
        cls,
        audio: sdk.AudioRef,
        n_steps: int,
        bins_per_octave: int,
        n_fft: int,
        win_length: int,
        hop_length: int,
    ) -> io.NodeOutput:
        import torchaudio

        value = await _audio_value(audio)
        sample_rate = value["sample_rate"]
        transform = torchaudio.transforms.PitchShift(
            sample_rate,
            n_steps,
            bins_per_octave,
            None if n_fft < 0 else n_fft,
            None if win_length < 0 else win_length,
            None if hop_length < 0 else hop_length,
        )
        result = {
            "waveform": transform(value["waveform"]),
            "sample_rate": sample_rate,
        }
        return io.NodeOutput(await _audio_output(result))


class AudioMix(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioMix",
            display_name="Audio Mix",
            category="Audio",
            description="Mix audios into one",
            is_input_list=True,
            accept_all_inputs=True,
            inputs=[
                io.Boolean.Input("constant_volume", default=False),
                io.Audio.Input("audio1"),
                io.Float.Input(
                    "volume1",
                    default=1.0,
                    step=0.05,
                    display_mode=io.NumberDisplay.number,
                    tooltip=_VOLUME_TOOLTIP,
                ),
                io.Float.Input(
                    "start_secs1",
                    default=0.0,
                    min=0.0,
                    step=0.1,
                    display_mode=io.NumberDisplay.number,
                    tooltip=_START_TOOLTIP,
                ),
            ],
            outputs=[io.Audio.Output("audio", display_name="audio")],
        )

    @classmethod
    async def execute(cls, constant_volume: Any, **kwargs: Any) -> io.NodeOutput:
        last_audio = _last_audio(kwargs)
        audios: list[list[Any]] = []
        for index in range(1, last_audio + 1):
            audio_name = f"audio{index}"
            volume_name = f"volume{index}"
            start_name = f"start_secs{index}"
            if (
                audio_name not in kwargs
                or start_name not in kwargs
                or volume_name not in kwargs
            ):
                continue

            audio_list = await _audio_values(kwargs[audio_name])
            volume = kwargs[volume_name]
            start_secs = kwargs[start_name]
            audio_list_len = len(audio_list)
            if len(volume) != audio_list_len:
                volume = [volume[0]] * audio_list_len
            if len(start_secs) != audio_list_len:
                start_secs = [start_secs[0]] * audio_list_len

            for position, audio in enumerate(audio_list):
                new_audio = copy.copy(audio)
                if start_secs[position] > 0:
                    pad = (int(start_secs[position] * audio["sample_rate"]), 0)
                    new_audio["waveform"] = torch.nn.functional.pad(
                        new_audio["waveform"], pad=pad
                    )
                audios.append([new_audio, volume[position]])

        max_waveform_len, max_sample_rate, max_channels = _audios_max(audios)
        out_audios = _pad_resample_audios(
            audios, max_waveform_len, max_sample_rate, max_channels
        )
        out_audios_tensor = torch.cat(out_audios, 0)
        out_audio = torch.sum(out_audios_tensor, 0)

        # INPUT_IS_LIST makes even ``False`` arrive as ``[False]`` upstream;
        # that list is truthy. This intentionally preserves that pinned quirk.
        if constant_volume:
            out_audio = out_audio.divide(len(out_audios_tensor))
        else:
            non_zeroes = torch.count_nonzero(out_audios_tensor, dim=0)
            non_zeroes = torch.where(non_zeroes == 0, 1, non_zeroes)
            out_audio = out_audio.divide(non_zeroes)
        result = {
            "waveform": out_audio[None, :, :],
            "sample_rate": max_sample_rate,
        }
        return io.NodeOutput(await _audio_output(result))


class AudioConcatenate(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioConcat",
            display_name="Audio Concatenate",
            category="Audio",
            description="Concatenate audios into one",
            is_input_list=True,
            accept_all_inputs=True,
            inputs=[io.Audio.Input("audio1")],
            outputs=[io.Audio.Output("audio_out", display_name="audio_out")],
        )

    @classmethod
    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        audios: list[list[Any]] = []
        last_audio = _last_audio(kwargs)
        for index in range(1, last_audio + 1):
            audio_name = f"audio{index}"
            if audio_name not in kwargs or kwargs[audio_name] is None:
                continue
            for audio in await _audio_values(kwargs[audio_name]):
                audios.append([audio, 1])

        _max_waveform_len, max_sample_rate, max_channels = _audios_max(audios)
        out_audios = _pad_resample_audios(
            audios, None, max_sample_rate, max_channels
        )
        result = {
            "waveform": torch.cat(out_audios, 2),
            "sample_rate": max_sample_rate,
        }
        return io.NodeOutput(await _audio_output(result))


class AudioTrimSilenceVAD(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        values = [
            ("trigger_level", 7.0, None, None, None, (
                "The measurement level used to trigger activity detection. "
                "This may need to be cahnged depending on the noise level, "
                "signal level, and other characteristics of the input audio. "
                "(Default: 7.0)"
            )),
            ("trigger_time", 0.25, None, None, 0.05, (
                "The time constant (in seconds) used to help ignore short "
                "bursts of sound. (Default: 0.25)"
            )),
            ("search_time", 1.0, None, None, 0.1, (
                "The amount of audio (in seconds) to search for quieter/shorter "
                "bursts of audio to include prior to the detected trigger "
                "point. (Default: 1.0)"
            )),
            ("allowed_gap", 0.25, None, None, 0.05, (
                "The allowed gap (in seconds) between quieter/shorter bursts "
                "of audio to include prior to the detected trigger point. "
                "(Default: 0.25)"
            )),
            ("pre_trigger_time", 0.0, None, None, 0.01, (
                "The amount of audio (in seconds) to preserve before the "
                "trigger point and any found quieter/shorter bursts. "
                "(Default: 0.0)"
            )),
            ("boot_time", 0.35, None, None, 0.05, (
                "estimation/reduction in order to detect the start of the "
                "wanted audio. This option sets the time for the initial "
                "noise estimate. (Default: 0.35)"
            )),
            ("noise_up_time", 0.1, None, None, 0.01, (
                "for when the noise level is increasing. (Default: 0.1)"
            )),
            ("noise_down_time", 0.01, None, None, 0.001, (
                "for when the noise level is decreasing. (Default: 0.01)"
            )),
            ("noise_reduction_amount", 1.35, None, None, 0.05, (
                "the detection algorithm (e.g. 0, 0.5, …). (Default: 1.35)"
            )),
            ("measure_freq", 20.0, None, None, 0.5, (
                "processing/measurements. (Default: 20.0)"
            )),
            ("measure_smooth_time", 0.4, None, None, 0.05, (
                "spectral measurements. (Default: 0.4)"
            )),
            ("hp_filter_freq", 50.0, None, None, 1.0, None),
            ("lp_filter_freq", 6000.0, None, 1000000.0, 1.0, (
                "Put this number down if there is high frequency background "
                "noise."
            )),
            ("hp_lifter_freq", 150.0, None, None, 1.0, None),
            ("lp_lifter_freq", 2000.0, None, None, 1.0, None),
        ]
        optional = [
            io.Float.Input(
                name,
                default=default,
                min=minimum,
                max=maximum,
                step=step,
                tooltip=tooltip,
                optional=True,
            )
            for name, default, minimum, maximum, step, tooltip in values
        ]
        return io.Schema(
            node_id="AudioTrimSilenceVAD",
            display_name="Audio Trim Silence (Voice Activity)",
            category="Audio",
            description=(
                "Trim silence from audio using torchaudio's Voice Activity "
                "Detector.  Lower lp_filter_freq if you have high frequency "
                "background noise."
            ),
            inputs=[io.Audio.Input("audio"), *optional],
            outputs=[io.Audio.Output("audio", display_name="audio")],
        )

    @classmethod
    async def execute(
        cls,
        audio: sdk.AudioRef,
        trigger_level: float = 7.0,
        trigger_time: float = 0.25,
        search_time: float = 1.0,
        allowed_gap: float = 0.25,
        pre_trigger_time: float = 0.0,
        boot_time: float = 0.35,
        noise_up_time: float = 0.1,
        noise_down_time: float = 0.01,
        noise_reduction_amount: float = 1.35,
        measure_freq: float = 20.0,
        measure_smooth_time: float = 0.4,
        hp_filter_freq: float = 50.0,
        lp_filter_freq: float = 6000.0,
        hp_lifter_freq: float = 150.0,
        lp_lifter_freq: float = 2000.0,
    ) -> io.NodeOutput:
        import torchaudio

        value = await _audio_value(audio)
        waveform = value["waveform"]
        sample_rate = value["sample_rate"]
        options = {
            "trigger_level": trigger_level,
            "trigger_time": trigger_time,
            "search_time": search_time,
            "allowed_gap": allowed_gap,
            "pre_trigger_time": pre_trigger_time,
            "boot_time": boot_time,
            "noise_up_time": noise_up_time,
            "noise_down_time": noise_down_time,
            "noise_reduction_amount": noise_reduction_amount,
            "measure_freq": measure_freq,
            "measure_smooth_time": measure_smooth_time,
            "hp_filter_freq": hp_filter_freq,
            "lp_filter_freq": lp_filter_freq,
            "hp_lifter_freq": hp_lifter_freq,
            "lp_lifter_freq": lp_lifter_freq,
        }
        new_waveform = torchaudio.functional.vad(
            waveform, sample_rate, **options
        )
        new_waveform = new_waveform.flip(2)
        new_waveform = torchaudio.functional.vad(
            new_waveform, sample_rate, **options
        )
        result = {
            "waveform": new_waveform.flip(2),
            "sample_rate": sample_rate,
        }
        return io.NodeOutput(await _audio_output(result))


class AudioTrimSilenceRosa(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioTrimSilenceRosa",
            display_name="Audio Trim Silence (dB)",
            category="Audio",
            description="Trim silence from audio.",
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "decibel",
                    default=0.0,
                    optional=True,
                    tooltip=(
                        "Either use decibel or bins, not both.\n"
                        "Set to 0 to disable."
                    ),
                ),
                io.Int.Input(
                    "bins",
                    default=7,
                    optional=True,
                    tooltip=(
                        "Bins will detect the decibel based on the middle bin.  "
                        "Should be an odd number.\nThe more bins the lower the "
                        "decibel and more of the audio will be trimmed.\n"
                        "Set to 0 to disable."
                    ),
                ),
            ],
            outputs=[
                io.Audio.Output(
                    "audio",
                    display_name="audio",
                    tooltip="Audio",
                ),
                io.Float.Output(
                    "decibel",
                    display_name="decibel",
                    tooltip=(
                        "Decibel number used only useful if you're using bins."
                    ),
                ),
            ],
        )

    @classmethod
    async def execute(
        cls,
        audio: sdk.AudioRef,
        decibel: float = 60,
        bins: int = 7,
    ) -> io.NodeOutput:
        import librosa
        import numpy

        value = await _audio_value(audio)
        waveform = value["waveform"]
        sample_rate = value["sample_rate"]
        waveform_np = torch.Tensor.numpy(waveform)

        if bins > 0:
            if bins % 2 == 0:
                bins += 1
            spectrum = numpy.abs(librosa.stft(waveform_np))
            decibel_np = librosa.power_to_db(spectrum**2)
            _histogram, bin_edges = numpy.histogram(decibel_np, bins=bins)
            middle = int(len(bin_edges) / 2)
            edge = bin_edges[middle]
            decibel = edge + ((bin_edges[middle + 1] - edge) / 2)

        trimmed_np = librosa.effects.trim(waveform_np, top_db=decibel)
        result = {
            "waveform": torch.from_numpy(trimmed_np[0]),
            "sample_rate": sample_rate,
        }
        # librosa/numpy yields a numpy scalar; FLOAT's transport boundary is a
        # JSON number, so normalize without changing its numeric value.
        return io.NodeOutput(await _audio_output(result), float(decibel))


class AudioBassTreble(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioBassTreble",
            display_name="Audio Bass/Treble",
            category="Audio",
            description="Bass / Treble",
            inputs=[
                io.Audio.Input("audio"),
                io.Combo.Input(
                    "frequency_type",
                    options=["Bass", "Treble"],
                    default="Bass",
                ),
                io.Float.Input(
                    "gain",
                    default=15.0,
                    min=-50.0,
                    step=0.1,
                    tooltip=(
                        "desired gain at the boost (or attenuation) in dB."
                    ),
                ),
                io.Float.Input(
                    "central_freq",
                    default=-1.0,
                    min=-1.0,
                    step=1.0,
                    optional=True,
                    tooltip=(
                        "central frequency (in Hz). -1 = Use default "
                        "(Bass: 100, Treble: 3000)"
                    ),
                ),
                io.Float.Input(
                    "Q",
                    default=0.707,
                    step=0.001,
                    optional=True,
                    tooltip="https://en.wikipedia.org/wiki/Q_factor",
                ),
            ],
            outputs=[io.Audio.Output("audio", display_name="audio")],
        )

    @classmethod
    async def execute(
        cls,
        audio: sdk.AudioRef,
        frequency_type: str,
        gain: float,
        central_freq: float,
        Q: float = 0.707,
    ) -> io.NodeOutput:
        import torchaudio

        value = await _audio_value(audio)
        sample_rate = value["sample_rate"]
        if central_freq < 0:
            type_dict = {"Bass": 100, "Treble": 3000}
            if frequency_type in type_dict:
                central_freq = type_dict[frequency_type]
        if frequency_type == "Bass":
            waveform = torchaudio.functional.bass_biquad(
                value["waveform"], sample_rate, gain, central_freq, Q
            )
        else:
            waveform = torchaudio.functional.treble_biquad(
                value["waveform"], sample_rate, gain, central_freq, Q
            )
        result = {"waveform": waveform, "sample_rate": sample_rate}
        return io.NodeOutput(await _audio_output(result))


class AudioSpeed(_AudioNode):
    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioSpeed",
            display_name="Audio Speed",
            category="Audio",
            description="Change the speed of the audio",
            is_input_list=True,
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "speed",
                    default=1.5,
                    step=0.01,
                    tooltip="Speed. >1.0 slower. <1.0 faster",
                ),
                io.Combo.Input(
                    "speed_type",
                    options=["torch-time-stretch", "TDHS"],
                    default="torch-time-stretch",
                    optional=True,
                    tooltip=(
                        "TDHS - Time-domain harmonic scaling. "
                        "torch-time-stretch - "
                        "torchaudio.transforms.TimeStretch."
                    ),
                ),
            ],
            outputs=[io.Audio.Output("audio", display_name="audio")],
        )

    @staticmethod
    def _time_shift_audiostretchy(
        audio: dict[str, Any], speed: float
    ) -> dict[str, Any]:
        from audiostretchy.stretch import AudioStretch

        rate = audio["sample_rate"]
        waveform = audio["waveform"]
        new_waveforms = []
        for channel in range(0, waveform.shape[0]):
            ta_audio16 = waveform[0][channel] * 32768
            audio_stretch = AudioStretch()
            audio_stretch.samples = audio_stretch.in_samples = (
                ta_audio16.numpy().astype("int16")
            )
            audio_stretch.nchannels = 1
            audio_stretch.sampwidth = 2
            audio_stretch.framerate = rate
            audio_stretch.nframes = waveform.shape[2]
            audio_stretch.stretch(ratio=speed)
            new_waveforms.append(torch.from_numpy(audio_stretch.samples))
        new_waveform = torch.stack(new_waveforms)
        new_waveform = torch.stack([new_waveform])
        return {"waveform": new_waveform, "sample_rate": rate}

    @staticmethod
    def _time_shift_torch_ts(
        audio: dict[str, Any], speed: float
    ) -> dict[str, Any]:
        import torch_time_stretch

        rate = audio["sample_rate"]
        waveform = audio["waveform"]
        new_waveform = torch_time_stretch.time_stretch(
            waveform,
            torch_time_stretch.Fraction(math.floor(speed * 100), 100),
            rate,
        )
        return {"waveform": new_waveform, "sample_rate": rate}

    @classmethod
    async def execute(
        cls,
        audio: Any,
        speed: Any,
        speed_type: Any = "torch-time-shift",
    ) -> io.NodeOutput:
        audio_values = await _audio_values(audio)
        if not isinstance(speed, list):
            speed = [speed] * len(audio_values)
        for index, value in enumerate(audio_values):
            if speed_type == "torch-time-shift":
                new_audio = cls._time_shift_torch_ts(value, speed[index])
            else:
                new_audio = cls._time_shift_audiostretchy(
                    value, speed[index]
                )
        # The pinned node intentionally returns only the last list item.
        return io.NodeOutput(await _audio_output(new_audio))


NODE_CLASS_MAPPINGS = {
    "AudioInfo": AudioInfo,
    "AudioSampleRate": AudioSampleRate,
    "AudioPitch": AudioPitch,
    "AudioMix": AudioMix,
    "AudioConcat": AudioConcatenate,
    "AudioTrimSilenceVAD": AudioTrimSilenceVAD,
    "AudioTrimSilenceRosa": AudioTrimSilenceRosa,
    "AudioBassTreble": AudioBassTreble,
    "AudioSpeed": AudioSpeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AudioInfo": "Audio Info",
    "AudioSampleRate": "Audio Pitch (Sample Rate)",
    "AudioPitch": "Audio Pitch",
    "AudioMix": "Audio Mix",
    "AudioConcat": "Audio Concatenate",
    "AudioTrimSilenceVAD": "Audio Trim Silence (Voice Activity)",
    "AudioTrimSilenceRosa": "Audio Trim Silence (dB)",
    "AudioBassTreble": "Audio Bass/Treble",
    "AudioSpeed": "Audio Speed",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
