import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location("author_pipeline", Path(__file__).with_name("run.py"))
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def corpus(tmp_path):
    root = tmp_path / "packs/example/x1234567/Example-HEAD"
    root.mkdir(parents=True)
    (root / "nodes.py").write_bytes(b"source\r\n")
    (root / "nodes.py").chmod(0o644)
    source = {"commit": "1" * 40, "key": "x1234567", "pack": "Example-HEAD", "upstream": "https://example.invalid/pack"}
    (tmp_path / "packs/packs.json").write_text(json.dumps({"example": source}))
    pins = {"packs": {"example": {"source": source, "root": root.relative_to(tmp_path).as_posix(),
                                  "files": [{"path": "nodes.py", **RUNNER.digest(root / "nodes.py")}], "artifacts": []}}}
    return root, pins


@pytest.mark.parametrize("mutation", ["bytes", "mode", "extra", "catalogue", "symlink", "bytecode"])
def test_exact_source_admission_refuses_drift(tmp_path, mutation):
    root, pins = corpus(tmp_path)
    assert RUNNER.corpus_sources(tmp_path, pins) == {"example": root}
    if mutation == "bytes":
        (root / "nodes.py").write_bytes(b"source\n")
    elif mutation == "mode":
        (root / "nodes.py").chmod(0o755)
    elif mutation == "extra":
        (root / "extra.py").write_bytes(b"extra")
    elif mutation == "catalogue":
        (tmp_path / "packs/packs.json").write_text("{}")
    elif mutation == "symlink":
        (root / "linked").symlink_to(root / "nodes.py")
    else:
        (root / "nodes.pyc").write_bytes(b"cache")
    with pytest.raises(RuntimeError):
        RUNNER.corpus_sources(tmp_path, pins)


def test_missing_source_is_not_an_acceptance_skip(tmp_path):
    root, pins = corpus(tmp_path)
    (root / "nodes.py").unlink()
    with pytest.raises(RuntimeError, match="tree mismatch"):
        RUNNER.corpus_sources(tmp_path, pins)


@pytest.mark.parametrize("failure", ["launch", "exit", "timeout"])
def test_failed_stage_retains_reviewable_receipt(tmp_path, monkeypatch, failure):
    command = [sys.executable, "-c", "raise SystemExit(7)"]
    if failure == "launch":
        command = [str(tmp_path / "missing-executable")]
    if failure == "timeout":
        def timed_out(*args, **kwargs):
            raise subprocess.TimeoutExpired(command, 300)
        monkeypatch.setattr(RUNNER.subprocess, "run", timed_out)
    with pytest.raises((RuntimeError, OSError, subprocess.TimeoutExpired)):
        RUNNER.execute_stage("failed-stage", command, tmp_path, {}, tmp_path)
    receipt = json.loads((tmp_path / "failed-stage-failure.json").read_text())
    assert receipt["command"] == command
    assert receipt["acceptance"] == "failed; no skip/fallback"
    assert receipt["log"]["sha256"] == RUNNER.digest(tmp_path / "failed-stage.log")["sha256"]
    if failure == "exit":
        assert receipt["exit_code"] == 7
    else:
        assert receipt["exception"] == ("FileNotFoundError" if failure == "launch" else "TimeoutExpired")
