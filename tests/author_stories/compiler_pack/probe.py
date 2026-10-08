"""Acceptance-only installed toolchain execution in the guest's temporary root."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from comfy_api.latest import io

SOURCE = b"#include <stdint.h>\nint main(void) { volatile int32_t x = 11; return x * 3 + 7 == 40 ? 0 : 1; }\n"


class OwnedScratchCompiler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="ManyOwnedScratchCompiler", inputs=[], outputs=[io.String.Output()])

    @classmethod
    async def execute(cls):
        profile = json.loads(Path(__file__).with_name("profile.json").read_text())
        temporary_root = Path(os.environ["TMPDIR"]).resolve()
        with tempfile.TemporaryDirectory(prefix="compiler-", dir=temporary_root) as directory:
            directory = Path(directory)
            assert directory.parent == temporary_root
            source = directory / "probe.c"
            artifact = directory / "probe"
            source.write_bytes(SOURCE)
            command = [profile["compiler"], *profile["flags"], str(source), "-o", str(artifact)]
            compiled = subprocess.run(command, cwd=directory, capture_output=True, timeout=20)
            if compiled.returncode:
                raise RuntimeError(f"Declared guest compiler failed ({compiled.returncode}): " +
                                   compiled.stderr[:16384].decode(errors="replace"))
            assert artifact.is_file() and 0 < artifact.stat().st_size <= 1048576
            result = subprocess.run([str(artifact)], cwd=directory, capture_output=True, timeout=5)
            assert result.returncode == 0 and result.stdout == b"" and result.stderr == b""
            report = {"compiled": True, "executed": True, "source_sha256": hashlib.sha256(SOURCE).hexdigest(),
                      "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                      "artifact_bytes": artifact.stat().st_size, "pid": os.getpid(), "capabilities": []}
        assert not directory.exists()
        report["cleanup"] = True
        return io.NodeOutput(json.dumps(report, sort_keys=True))
