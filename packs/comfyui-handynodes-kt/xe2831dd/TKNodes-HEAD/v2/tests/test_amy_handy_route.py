"""Actual private-handler seam, not a synthetic host runtime injection."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
import wave
import pytest

import test_amy_handy_v3 as proof


def test_required_asset_backed_route_from_fresh_guest(tmp_path, monkeypatch):
    import folder_paths
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")
    monkeypatch.setattr(folder_paths, "get_input_directory", lambda: str(tmp_path))
    with wave.open(str(tmp_path / "silence.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * 1600)

    async def run():
        original = proof.packruntime.resolve_for_tenant
        def selected(spec, tenant):
            resolved = original(spec, tenant)
            assert resolved.python_executable == Path(sys.executable)
            return replace(resolved, spec=replace(resolved.spec, pack_root=proof.V2))
        with monkeypatch.context() as config:
            config.setattr(proof.packruntime, "resolve_for_tenant", selected)
            guest = await proof.GuestSession("amy-handy-private-route",
                module_source_root=proof.V2, guest_runtime_root=proof.HOST).start()
        try:
            assert guest.sandbox_kind == "seatbelt"
            result = await guest.serve_route(
                module_name="amy_handy_v3_test._broker",
                module_file=str(proof.V2 / "_broker.py"),
                handler="detect_speakers", capabilities=("assets",),
                request={"method": "post", "path": "/detect_speakers",
                    "query": {}, "body": json.dumps({"audio": "silence.wav", "silence_threshold": 1})})
            assert result["status"] == 200
            assert json.loads(result["body"]) == {
                "speaker_times": [], "duration": 0.1, "silence_threshold": 1000}
            print(json.dumps({"pid": guest.pid, "tier": "fresh-required-seatbelt-private-handler",
                "qualification": "Staged unsealed dependency profile; no host runtime field injection."}))
        finally:
            await guest.kill()
    asyncio.run(run())
