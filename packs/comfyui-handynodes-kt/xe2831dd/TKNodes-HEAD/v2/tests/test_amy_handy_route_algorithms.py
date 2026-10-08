"""Managed label priority/silence math vs selected pinned source methods."""
import ast
import asyncio
import json
import os
from pathlib import Path
import struct
import types
import wave
import pytest
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import test_amy_handy_assets as assets_proof
import test_amy_handy_v3 as proof

@pytest.fixture
def native(tmp_path):
    source = proof.V2.parent / "speakers.py"
    tree = ast.parse(source.read_bytes())
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TKLocateSpeakersUsingSilenceBreaks")
    methods = {"get_diarization_speakers_using_silence", "get_diarization_from_labels", "merge_small_consecutive_segments", "get_diarization_speakers_from_audio_file"}
    cls = ast.ClassDef(name="Native", bases=[], keywords=[], body=[node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in methods], decorator_list=[])
    env = {"os": os, "Path": types.SimpleNamespace(home=lambda: tmp_path), "AudioSegment": AudioSegment, "detect_nonsilent": detect_nonsilent}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(source), "exec"), env)
    return env["Native"]()

def install(root):
    (root / "audio").mkdir()
    (root / "handy-labels").mkdir()
    (root / "Documents").mkdir()
    with wave.open(str(root / "audio/voice.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        values = [10000] * 3200 + [0] * 3200 + [-10000] * 3200
        stream.writeframes(struct.pack("<" + "h" * len(values), *values))

@pytest.mark.parametrize("choice", ["sibling", "authored-fallback", "silence"])
@pytest.mark.parametrize("threshold", [0.1, 1.0])
def test_managed_priority_native_label_and_silence_values(tmp_path, monkeypatch, native, choice, threshold):
    import folder_paths
    install(tmp_path)
    monkeypatch.setattr(folder_paths, "get_input_directory", lambda: str(tmp_path))
    sibling = "0\t.12\tspeaker1\r\n.2\t.4\tspeaker2\r\n"
    authored = ".01\t.15\tlabel\n.25\t.45\tother\n"
    if choice == "sibling":
        (tmp_path / "audio/voice.txt").write_bytes(sibling.encode())
        (tmp_path / "handy-labels/voice.txt").write_text(authored)
        (tmp_path / "Documents/voice.txt").write_text(authored)
    elif choice == "authored-fallback":
        (tmp_path / "handy-labels/voice.txt").write_text(authored)
        # Native source's Documents lookup is confined to this test fixture,
        # not an ambient path recovered by the converted node.
        (tmp_path / "Documents/voice.txt").write_text(authored)
    rows, duration = native.get_diarization_speakers_from_audio_file(str(tmp_path / "audio/voice.wav"), int(threshold * 1000))
    rt = assets_proof.runtime()
    async def run():
        with proof._sdk.bind_runtime(rt.refs, rt.ctx, rt.ops):
            result = await proof.broker.detect_speakers({"body": json.dumps({"audio": "audio/voice.wav", "silence_threshold": threshold})})
            assert result["status"] == 200
            assert json.loads(result["body"]) == {"speaker_times": rows, "duration": duration, "silence_threshold": int(threshold * 1000)}
    asyncio.run(run())

@pytest.mark.parametrize("content,error", [(b"\xff", UnicodeDecodeError), (b"x" * 65537, ValueError)])
def test_invalid_or_oversized_authored_labels_not_reset(tmp_path, monkeypatch, content, error):
    import folder_paths
    install(tmp_path)
    (tmp_path / "audio/voice.txt").write_bytes(content)
    monkeypatch.setattr(folder_paths, "get_input_directory", lambda: str(tmp_path))
    rt = assets_proof.runtime()
    async def run():
        with proof._sdk.bind_runtime(rt.refs, rt.ctx, rt.ops):
            with pytest.raises(error):
                await proof.broker.detect_speakers({"body": json.dumps({"audio": "audio/voice.wav"})})
    asyncio.run(run())

@pytest.mark.parametrize("threshold", [True, float("nan"), float("inf"), -1, 601])
def test_route_threshold_refuses_before_any_asset_operation(threshold, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("managed assets entered")
    monkeypatch.setattr(proof.broker, "managed_bytes", forbidden)
    with pytest.raises(ValueError, match="threshold"):
        asyncio.run(proof.broker.detect_speakers({"body": json.dumps({"audio": "voice.wav", "silence_threshold": threshold})}))
