"""Create a bounded test-only read-only closure from an installed Apple toolchain."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import stat
import subprocess


def row(path):
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
            "mode": stat.S_IMODE(path.stat().st_mode)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--resource", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == "Darwin" and platform.machine() == "arm64"
    output = args.output.resolve()
    assert not output.exists(), "Never overwrite an immutable profile"
    artifact = output / "artifact"
    mapping = [(args.toolchain / "bin/clang", "bin/clang"), (args.toolchain / "bin/ld", "bin/ld"),
               *[(args.toolchain / "lib" / name, "lib/" + name) for name in
                 ["libtapi.dylib", "libcodedirectory.dylib", "libLTO.dylib", "libswiftDemangle.dylib"]],
               (args.resource / "include/stdint.h", "resource/include/stdint.h"),
               (args.sdk / "usr/lib/libSystem.B.tbd", "sdk/usr/lib/libSystem.tbd")]
    provenance = []
    dependencies = {}
    for source, name in mapping:
        source = source.resolve(strict=True)
        target = artifact / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o555 if name.startswith("bin/") else 0o444)
        provenance.append({"source": str(source), "source_identity": row(source), "target": name, "target_identity": row(target)})
        if target.suffix == ".dylib" or name.startswith("bin/"):
            dependencies[name] = subprocess.check_output(["otool", "-L", str(source)], text=True)
    for path in artifact.rglob("*"):
        if path.is_dir():
            path.chmod(0o555)
    artifact.chmod(0o555)
    inventory = {p.relative_to(artifact).as_posix(): row(p) for p in sorted(artifact.rglob("*")) if p.is_file()}
    profile = {"compiler": str(artifact / "bin/clang"), "flags": ["-arch", "arm64", "-std=c11", "-O0", "-ffreestanding", "-nostdinc",
        "-isystem", str(artifact / "resource/include"), "-resource-dir", str(artifact / "resource"), "-isysroot", str(artifact / "sdk"),
        "-fuse-ld=" + str(artifact / "bin/ld"), "-nostdlib", "-lSystem"],
        "artifact_root": str(artifact), "artifact_files": inventory, "architecture": platform.machine(),
        "identities": [{"path": str(artifact / name), **inventory[name]} for name in inventory if name.startswith(("bin/", "lib/"))],
        "headers": [{"path": str(artifact / "resource/include/stdint.h"), **inventory["resource/include/stdint.h"]}],
        "provenance": provenance, "dynamic_dependencies": dependencies,
        "base_os": subprocess.check_output(["sw_vers"], text=True),
        "limits": ["Small freestanding C probe only; no general Python-extension/C++/CUDA toolchain claim",
                   "Immutable local installed artifacts; no download/install or Linux profile",
                   "System shared-cache libraries remain inherited base OS substrate, not fully hashed/sealed",
                   "Existing admitted pack fixture root only; no ambient developer SDK read grant"]}
    (output / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    print(output / "profile.json")


if __name__ == "__main__":
    main()
