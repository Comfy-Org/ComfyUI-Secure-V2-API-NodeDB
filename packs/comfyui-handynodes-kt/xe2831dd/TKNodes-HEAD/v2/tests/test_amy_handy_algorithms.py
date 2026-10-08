"""Pinned source controls for the 26 independent selected native algorithms.

AST extraction avoids eager Sherpa downloads/routes/import side effects. This is
trusted in-process source testing, NOT a guest confinement or whole29 claim.
"""
import ast
import copy
import importlib.util
import math
import os
from pathlib import Path
import sys
import types
import json
import cv2
import numpy as np
import pytest
import torch
import torchaudio
from pydub import AudioSegment
from pydub.silence import detect_silence

V2 = Path(__file__).resolve().parents[1]
SOURCE = V2.parent
PACKAGE = "amy_handy_algorithms_test"
pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(V2)]
pkg.__package__ = PACKAGE
pkg.__spec__ = importlib.util.spec_from_file_location(PACKAGE, V2 / "__init__.py",
                                                    submodule_search_locations=[str(V2)])
pkg.__file__ = str(V2 / "__init__.py")
sys.modules[PACKAGE] = pkg
spec = importlib.util.spec_from_file_location(PACKAGE + "._algorithms", V2 / "_algorithms.py")
converted = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = converted
spec.loader.exec_module(converted)

def native_module():
    source_package = types.ModuleType("amy_handy_source_control")
    source_package.__path__ = [str(SOURCE)]
    sys.modules[source_package.__name__] = source_package
    source_speakers = types.ModuleType("amy_handy_source_control.speakers")
    sys.modules[source_speakers.__name__] = source_speakers
    env = dict(__name__=source_speakers.__name__, __package__=source_package.__name__,
               math=math, os=os, json=json, torch=torch, F=torch.nn.functional,
               torchaudio=torchaudio, np=np, cv2=cv2, AudioSegment=AudioSegment,
               detect_silence=detect_silence, ANY=converted.ANY, any_type=converted.ANY)
    names = set(converted.NODE_CLASS_MAPPINGS)
    for module in ("tknodes", "misc", "audioChunker", "speakers", "utilnodes"):
        filename = SOURCE / (module + ".py")
        tree = ast.parse(filename.read_bytes())
        nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names
                 or module == "utilnodes" and isinstance(n, ast.FunctionDef)]
        # Immutable assigned resource is the only native filesystem branch.
        env["__file__"] = str(filename)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(filename), "exec"), env)
    env["__file__"] = str(SOURCE / "speakers.py")
    source_speakers.__dict__.update(env)
    return env

native = native_module()
IDS = sorted(converted.NODE_CLASS_MAPPINGS)

def clone(value):
    if isinstance(value, torch.Tensor):
        return value.clone()
    if type(value) is dict:
        return {k: clone(v) for k, v in value.items()}
    if type(value) in (list, tuple):
        return type(value)(clone(v) for v in value)
    return copy.deepcopy(value)

def equal(a, b):
    assert type(a) is type(b)
    if isinstance(a, torch.Tensor):
        assert a.dtype == b.dtype and a.shape == b.shape and a.device == b.device
        assert torch.equal(a, b)
    elif type(a) is dict:
        assert a.keys() == b.keys()
        for key in a:
            equal(a[key], b[key])
    elif type(a) in (tuple, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            equal(x, y)
    elif type(a) is float and math.isnan(a):
        assert math.isnan(b)
    else:
        assert a == b

def inputs(node_id, dtype=torch.float32):
    cls = converted.NODE_CLASS_MAPPINGS[node_id]
    image = torch.linspace(0, 1, 16 * 8 * 8 * 3, dtype=dtype).reshape(16, 8, 8, 3)
    audio = {"waveform": torch.zeros((1, 1, 32000), dtype=dtype), "sample_rate": 16000}
    result = {}
    for rows in cls.INPUT_TYPES().values():
        for name, row in rows.items():
            kind = row[0]
            options = row[1] if len(row) > 1 else {}
            if type(kind) is list:
                value = options.get("default", kind[0])
            elif kind == "IMAGE":
                value = image
            elif kind == "AUDIO":
                value = audio
            elif kind == "TK_IMAGE_PROMPT_LIST":
                value = [{"image": image[:1], "prompt": "one", "filename": "one.png", "slot": 1}]
            elif kind == "TK_IMAGE_LIST":
                value = [{"image": image[:1], "filename": "one.png", "slot": 1}]
            else:
                value = options.get("default", {"STRING": "", "INT": 1, "FLOAT": 1.0,
                                               "BOOLEAN": False, "*": "inert"}[kind])
            result[name] = value
    if node_id == "TKMergeAudioList":
        result["audio_list"] = [audio, clone(audio)]
    if node_id in ("TKSmartAudioChunker", "TKSmartVideoChunker"):
        result.update(chunk_secs=1, variation=0)
    if node_id in ("TKSpeakerAudioTrackExtractor", "TKTotalTracksInAudio"):
        result.update(combinedTrackInfo1="0,0.5", combinedTrackInfo2="0.5,1")
    if node_id == "TKAudioSpeakerTalkTime":
        result.update(track_start_1=0.0, track_end_1=0.5)
    if node_id == "TKPromptLooper":
        result.update(prompt1="first", prompt2="second")
    return result

@pytest.mark.parametrize("node_id", IDS)
def test_exact_selected_schema(node_id):
    a = native[node_id]
    b = converted.NODE_CLASS_MAPPINGS[node_id]
    assert a.INPUT_TYPES() == b.INPUT_TYPES()
    for key in ("RETURN_TYPES", "RETURN_NAMES", "OUTPUT_IS_LIST", "INPUT_IS_LIST",
                "CATEGORY", "DESCRIPTION", "FUNCTION"):
        assert getattr(a, key, None) == getattr(b, key, None)

@pytest.mark.parametrize("node_id", IDS)
@pytest.mark.parametrize("dtype", [torch.float32, torch.float64, torch.float16])
def test_native_algorithm_control(node_id, dtype):
    kwargs = inputs(node_id, dtype)
    a = native[node_id]()
    b = converted.NODE_CLASS_MAPPINGS[node_id]()
    fn = a.FUNCTION
    try:
        expected = getattr(a, fn)(**clone(kwargs))
    except Exception as error:
        with pytest.raises(type(error)) as caught:
            getattr(b, fn)(**clone(kwargs))
        assert str(caught.value) == str(error)
    else:
        actual = getattr(b, fn)(**clone(kwargs))
        equal(expected, actual)

def test_prompt_looper_approved_optional_callshape():
    image = inputs("TKPromptLooper")["image1"]
    with pytest.raises(TypeError, match="prompt2"):
        native["TKPromptLooper"]().getResultsAtIndex(0, "first", image)
    equal(converted.TKPromptLooper().getResultsAtIndex(0, "first", image),
          native["TKPromptLooper"]().getResultsAtIndex(0, "first", image, None, None))

def test_prompt_looper_adv_native_cardinality_and_repair():
    assert native["TKPromptLooperAdv"]().getResultsAtIndex(0) == (0, None, None)
    with pytest.raises(ValueError, match="no valid prompt"):
        converted.TKPromptLooperAdv().getResultsAtIndex(0)

@pytest.mark.parametrize("rate", [8000, 16000, 44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
def test_immutable_breather_intended_float32_pcm_oracle(rate, channels, monkeypatch):
    import struct
    import wave
    payload = (SOURCE / "assets/breather.wav").read_bytes()
    with wave.open(str(SOURCE / "assets/breather.wav"), "rb") as pcm:
        assert (pcm.getnchannels(), pcm.getsampwidth(), pcm.getframerate()) == (2, 2, 48000)
        raw = np.frombuffer(pcm.readframes(pcm.getnframes()), dtype="<i2").reshape(-1, 2)
    oracle = raw.astype(np.float32) / 32768.0
    def intended_loader(path, backend):
        assert backend == "soundfile"
        # Independently specified signed-PCM oracle, not a claimed execution of
        # absent soundfile/TorchCodec. Float32 default-normalized loading intent.
        with wave.open(str(path), "rb") as wav:
            assert (wav.getnchannels(), wav.getsampwidth()) == (2, 2)
            sample_rate = wav.getframerate()
            data = wav.readframes(wav.getnframes())
        values = struct.unpack("<" + "h" * (len(data) // 2), data)
        expected = torch.tensor(values, dtype=torch.float32).reshape(-1, 2).T / 32768
        assert np.array_equal(expected.T.numpy(), oracle)
        return expected, sample_rate
    monkeypatch.setitem(native, "torchaudio", types.SimpleNamespace(load=intended_loader, transforms=torchaudio.transforms))
    kwargs = inputs("TKSpeakerAudioTrackExtractor")
    kwargs["fullaudio"] = {"waveform": torch.zeros(1, channels, rate * 2), "sample_rate": rate}
    kwargs["addBreathNoise"] = True
    a = native["TKSpeakerAudioTrackExtractor"]()
    b = converted.TKSpeakerAudioTrackExtractor()
    equal(a.extractSpeakerTrackAudio(**clone(kwargs)),
          b.extractSpeakerTrackAudio(**clone(kwargs)))

@pytest.mark.parametrize("rate", [8000, 16000, 44100, 48000])
def test_current_pristine_torchcodec_dependency_failure_retained(rate):
    kwargs = inputs("TKSpeakerAudioTrackExtractor")
    kwargs["fullaudio"] = {"waveform": torch.zeros(1, 1, rate * 2), "sample_rate": rate}
    kwargs["addBreathNoise"] = True
    # This is current environment evidence, NOT the adapted decoding oracle.
    with pytest.raises(ImportError, match="TorchCodec is required"):
        native["TKSpeakerAudioTrackExtractor"]().extractSpeakerTrackAudio(**kwargs)

def test_source_no_padding_native_unbound_error_retained():
    kwargs = inputs("TKSpeakerAudioTrackExtractor")
    kwargs["padAudioForLtx"] = False
    with pytest.raises(UnboundLocalError):
        native["TKSpeakerAudioTrackExtractor"]().extractSpeakerTrackAudio(**clone(kwargs))
    with pytest.raises(UnboundLocalError):
        converted.TKSpeakerAudioTrackExtractor().extractSpeakerTrackAudio(**clone(kwargs))

def test_source_merge_mutates_inputs_original_control():
    kwargs = inputs("TKMergeAudioList")
    for item in kwargs["audio_list"]:
        item["waveform"].fill_(0.5)
    before = clone(kwargs)
    native["TKMergeAudioList"]().merge(**kwargs)
    assert any(not torch.equal(a["waveform"], b["waveform"])
               for a, b in zip(kwargs["audio_list"], before["audio_list"]))
